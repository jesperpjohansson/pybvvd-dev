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

from pybvvd import api
from pybvvd.client._token_manager import (
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
