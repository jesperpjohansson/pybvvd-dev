"""
Client implementations for interacting with Bolagsverket's Värdefulla Datamängder API.

This module provides synchronous and asynchronous API clients with
convenience methods for retrieving organisation data, document lists,
and documents.
"""

from __future__ import annotations

from typing import Literal

import httpx
import pydantic

from pybvvd import api, oauth2
from pybvvd.client._token_manager import (
    DEFAULT_SCOPE,
    AsyncTokenManager,
    TokenManager,
    TokenManagerBase,
)
from pybvvd.exceptions import APIError

type _HTTPRequestMethod = Literal[
    "get",
    "options",
    "head",
    "post",
    "put",
    "patch",
    "delete",
]

"""Base URL for the production environment."""
BASE_URL_PRODUCTION = "https://gw.api.bolagsverket.se"

"""Base URL for the test environment."""
BASE_URL_TEST = "https://gw-accept2.api.bolagsverket.se"

"""Base path shared by all API endpoints."""
BASE_PATH_API = "/vardefulla-datamangder/v1"


class ClientBase[ClientT, TokenManagerT: TokenManagerBase]:
    """Base class for API clients."""

    def __init__(self, session: ClientT, token_manager: TokenManagerT) -> None:
        self._session = session
        self._token_manager = token_manager
        self._base_url = (
            BASE_URL_TEST if token_manager.test_environment else BASE_URL_PRODUCTION
        )

    @property
    def token_manager(self) -> TokenManagerT:
        """Return the token manager used by this client."""
        return self._token_manager

    def _raise_on_http_error(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                model = api.ApiError.model_validate(response.json())
                api_exc = APIError(**model.model_dump())
                raise api_exc from exc
            except (ValueError, pydantic.ValidationError) as parse_exc:
                exc.add_note(f"Failed to parse ApiError:\n\n{parse_exc}")
            raise

    @staticmethod
    def _normalize_identitetsbeteckning(
        identitetsbeteckning: str
        | api.OrganisationerBegaran
        | api.DokumentlistaBegaran,
    ) -> dict[str, str]:
        return (
            identitetsbeteckning.model_dump(mode="json")
            if isinstance(
                identitetsbeteckning,
                (api.OrganisationerBegaran, api.DokumentlistaBegaran),
            )
            else {"identitetsbeteckning": identitetsbeteckning}
        )


class Client(ClientBase[httpx.Client, TokenManager]):
    """
    Synchronous client for Bolagsverket's Värdefulla Datamängder API.

    This client provides a synchronous interface to Bolagsverket's
    Värdefulla Datamängder API. It exposes convenience methods for the
    main API endpoints, including organisation lookups, document listings,
    and document retrieval.

    The API environment (test or production) is derived from the
    token manager configuration.

    Parameters
    ----------
    session : httpx.Client
        Synchronous HTTP client instance used to perform API requests.
    token_manager : TokenManager
        Synchronous OAuth2 token manager.
    """

    @classmethod
    def from_credentials(  # noqa: PLR0913
        cls,
        session: httpx.Client,
        client_credentials: oauth2.ClientCredentials,
        *,
        test_environment: bool = False,
        single_token: bool = False,
        expiry_threshold: float = 0.0,
        issue_token: bool = True,
        scope: str = DEFAULT_SCOPE,
    ) -> Client:
        """
        Create a synchronous client from OAuth2 client credentials.

        This convenience constructor creates a ``TokenManager`` and injects it
        into the returned client.

        Parameters
        ----------
        session : httpx.Client
            Synchronous HTTP client instance used for token and API requests.
        client_credentials : oauth2.ClientCredentials
            OAuth 2.0 client credentials mapping containing ``client_id`` and
            ``client_secret``.
        test_environment : bool, optional
            If ``True``, use the test OAuth 2.0 portal and API endpoints.
        single_token : bool, optional
            If ``True``, existing tokens will automatically be revoked when
            a new one is issued.
        expiry_threshold : float, optional
            Number of seconds before actual expiration when an access token
            should be treated as expired.
        issue_token : bool, optional
            If ``True``, issue an access token before returning the client.
        scope : str, optional
            Scope of the access token issued when ``issue_token`` is ``True``.

        Returns
        -------
        Client
            Configured synchronous API client.
        """
        token_manager = TokenManager(
            session,
            client_credentials,
            test_environment=test_environment,
            single_token=single_token,
            expiry_threshold=expiry_threshold,
        )
        if issue_token:
            token_manager.issue_access_token(scope=scope)
        return cls(session, token_manager)

    def ping(self) -> tuple[str, int]:
        """
        Check API availability.

        Returns
        -------
        tuple[str, int]
            HTTP response body text and status code.

        """
        response = self._call_api(
            "get",
            f"{BASE_PATH_API}/isalive",
            raise_on_http_error=False,
        )
        return response.text, response.status_code

    def organisationer(
        self,
        identitetsbeteckning: str | api.OrganisationerBegaran,
    ) -> api.OrganisationerSvar:
        """
        Fetch organisation data for the given identity number.

        Parameters
        ----------
        identitetsbeteckning : str | OrganisationerBegaran
            Identity number used to look up organisation information.

        Returns
        -------
        OrganisationerSvar
            Parsed response containing organisation data.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        pydantic.ValidationError
            If the API response cannot be parsed into
            ``OrganisationerSvar``.
        """
        response = self._call_api(
            "post",
            f"{BASE_PATH_API}/organisationer",
            raise_on_http_error=True,
            json=self._normalize_identitetsbeteckning(identitetsbeteckning),
        )
        return api.OrganisationerSvar.model_validate(response.json())

    def dokumentlista(
        self,
        identitetsbeteckning: str | api.DokumentlistaBegaran,
    ) -> api.DokumentlistaSvar:
        """
        Fetch the document list for the given identity number.

        Parameters
        ----------
        identitetsbeteckning : str | DokumentlistaBegaran
            Identity number used to look up available documents.

        Returns
        -------
        DokumentlistaSvar
            Parsed response containing document metadata.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        pydantic.ValidationError
            If the API response cannot be parsed into
            ``DokumentlistaSvar``.
        """
        response = self._call_api(
            "post",
            f"{BASE_PATH_API}/dokumentlista",
            raise_on_http_error=True,
            json=self._normalize_identitetsbeteckning(identitetsbeteckning),
        )
        return api.DokumentlistaSvar.model_validate(response.json())

    def dokument(self, dokumentId: str) -> bytes:  # noqa: N803
        """
        Fetch a document by its document ID.

        Parameters
        ----------
        dokumentId : str
            Unique identifier of the document to retrieve.

        Returns
        -------
        bytes
            Raw document content.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        """
        return self._call_api(
            "get",
            f"{BASE_PATH_API}/dokument/{dokumentId}",
            raise_on_http_error=True,
        ).content

    def _call_api(
        self,
        method: _HTTPRequestMethod,
        path: str,
        *,
        raise_on_http_error: bool,
        **kwargs,
    ) -> httpx.Response:
        """
        Execute an authenticated API request.

        Parameters
        ----------
        method : str
            HTTP method name to call on the underlying session, such as
            ``"get"`` or ``"post"``.
        path : str
            Path appended to the base URL to form the endpoint URL.
        **kwargs
            Additional keyword arguments forwarded to the corresponding
            ``httpx.Client`` request method.

        Returns
        -------
        httpx.Response
            HTTP response returned by the API.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        """
        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            headers={"Authorization": self._token_manager.auth_header()},
            **kwargs,
        )
        if raise_on_http_error:
            self._raise_on_http_error(response)

        return response


class AsyncClient(ClientBase[httpx.AsyncClient, AsyncTokenManager]):
    """
    Asynchronous client for Bolagsverket's Värdefulla Datamängder API.

    This client provides an asynchronous interface to Bolagsverket's
    Värdefulla Datamängder API. It exposes convenience methods for the
    main API endpoints, including organisation lookups, document listings,
    and document retrieval.

    The API environment (test or production) is derived from the
    token manager configuration.

    Parameters
    ----------
    session : httpx.AsyncClient
        Asynchronous HTTP client instance used to perform API requests.
    token_manager : AsyncTokenManager
        Asynchronous OAuth2 token manager.
    """

    @classmethod
    async def from_credentials(  # noqa: PLR0913
        cls,
        session: httpx.AsyncClient,
        client_credentials: oauth2.ClientCredentials,
        *,
        test_environment: bool = False,
        single_token: bool = False,
        expiry_threshold: float = 0.0,
        issue_token: bool = True,
        scope: str = DEFAULT_SCOPE,
    ) -> AsyncClient:
        """
        Create an asynchronous client from OAuth2 client credentials.

        This convenience constructor creates an ``AsyncTokenManager`` and
        injects it into the returned client.

        Parameters
        ----------
        session : httpx.AsyncClient
            Asynchronous HTTP client instance used for token and API requests.
        client_credentials : oauth2.ClientCredentials
            OAuth 2.0 client credentials mapping containing ``client_id`` and
            ``client_secret``.
        test_environment : bool, optional
            If ``True``, use the test OAuth 2.0 portal and API endpoints.
        single_token : bool, optional
            If ``True``, existing tokens will automatically be revoked when
            a new one is issued.
        expiry_threshold : float, optional
            Number of seconds before actual expiration when an access token
            should be treated as expired.
        issue_token : bool, optional
            If ``True``, issue an access token before returning the client.
        scope : str, optional
            Scope of the access token issued when ``issue_token`` is ``True``.

        Returns
        -------
        AsyncClient
            Configured asynchronous API client.
        """
        token_manager = AsyncTokenManager(
            session,
            client_credentials,
            test_environment=test_environment,
            single_token=single_token,
            expiry_threshold=expiry_threshold,
        )
        if issue_token:
            await token_manager.issue_access_token(scope=scope)
        return cls(session, token_manager)

    async def ping(self) -> tuple[str, int]:
        """
        Check API availability.

        Returns
        -------
        tuple[str, int]
            HTTP response body text and status code.

        """
        response = await self._call_api(
            "get",
            f"{BASE_PATH_API}/isalive",
            raise_on_http_error=False,
        )
        return response.text, response.status_code

    async def organisationer(
        self,
        identitetsbeteckning: str | api.OrganisationerBegaran,
    ) -> api.OrganisationerSvar:
        """
        Fetch organisation data for the given identity number.

        Parameters
        ----------
        identitetsbeteckning : str | OrganisationerBegaran
            Identity number used to look up organisation information.

        Returns
        -------
        OrganisationerSvar
            Parsed response containing organisation data.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        pydantic.ValidationError
            If the API response cannot be parsed into
            ``OrganisationerSvar``.
        """
        response = await self._call_api(
            "post",
            f"{BASE_PATH_API}/organisationer",
            raise_on_http_error=True,
            json=self._normalize_identitetsbeteckning(identitetsbeteckning),
        )
        return api.OrganisationerSvar.model_validate(response.json())

    async def dokumentlista(
        self,
        identitetsbeteckning: str | api.DokumentlistaBegaran,
    ) -> api.DokumentlistaSvar:
        """
        Fetch the document list for the given identity number.

        Parameters
        ----------
        identitetsbeteckning : str | DokumentlistaBegaran
            Identity number used to look up available documents.

        Returns
        -------
        DokumentlistaSvar
            Parsed response containing document metadata.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        pydantic.ValidationError
            If the API response cannot be parsed into
            ``DokumentlistaSvar``.
        """
        response = await self._call_api(
            "post",
            f"{BASE_PATH_API}/dokumentlista",
            raise_on_http_error=True,
            json=self._normalize_identitetsbeteckning(identitetsbeteckning),
        )
        return api.DokumentlistaSvar.model_validate(response.json())

    async def dokument(self, dokumentId: str) -> bytes:  # noqa: N803
        """
        Fetch a document by its document ID.

        Parameters
        ----------
        dokumentId : str
            Unique identifier of the document to retrieve.

        Returns
        -------
        bytes
            Raw document content.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        """
        response = await self._call_api(
            "get",
            f"{BASE_PATH_API}/dokument/{dokumentId}",
            raise_on_http_error=True,
        )
        return response.content

    async def _call_api(
        self,
        method: _HTTPRequestMethod,
        path: str,
        *,
        raise_on_http_error: bool,
        **kwargs,
    ) -> httpx.Response:
        """
        Execute an authenticated API request.

        Parameters
        ----------
        method : str
            HTTP method name to call on the underlying session, such as
            ``"get"`` or ``"post"``.
        path : str
            Path appended to the base URL to form the endpoint URL.
        **kwargs
            Additional keyword arguments forwarded to the corresponding
            ``httpx.AsyncClient`` request method.

        Returns
        -------
        httpx.Response
            HTTP response returned by the API.

        Raises
        ------
        RuntimeError
            If no valid access token is available.
        httpx.HTTPStatusError
            If the API returns an unsuccessful HTTP status code.
        """
        response = await self._session.request(
            method,
            f"{self._base_url}{path}",
            headers={"Authorization": await self._token_manager.auth_header()},
            **kwargs,
        )

        if raise_on_http_error:
            self._raise_on_http_error(response)

        return response
