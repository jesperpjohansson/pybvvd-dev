"""
OAuth 2.0 token managers.

This module provides synchronous and asynchronous OAuth 2.0 token managers that
are intended to be injected into API clients. A token manager provides methods for
requesting the issuance or revocation of access tokens from the authorization server,
and for accessing details about the latest issued access token.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import NoReturn

import httpx
import pydantic

from pybvvd import oauth2
from pybvvd.exceptions import OAuth2Error

"""Base URL for the production environment."""
BASE_URL_PRODUCTION = "https://portal.api.bolagsverket.se"

"""Base URL for the test environment."""
BASE_URL_TEST = "https://portal-accept2.api.bolagsverket.se"

"""OAuth 2.0 grant type."""
GRANT_TYPE = "client_credentials"

"""Path component of the token endpoint."""
PATH_TOKEN = "/oauth2/token"  # noqa: S105

"""Path component of the token revocation endpoint."""
PATH_REVOKE = "/oauth2/revoke"

"""Default scope when requesting the issuance of access tokens."""
DEFAULT_SCOPE = "vardefulla-datamangder:read vardefulla-datamangder:ping"

"""Value of the Content-Type header for form-encoded requests."""
CONTENT_TYPE = "application/x-www-form-urlencoded"


class TokenManagerBase[ClientT]:
    """Base class for OAuth 2.0 token managers."""

    def __init__(
        self,
        session: ClientT,
        client_credentials: oauth2.ClientCredentials,
        *,
        test_environment: bool,
        single_token: bool,
        expiry_threshold: float,
    ) -> None:
        if expiry_threshold < 0:
            exc_msg = "Expiry threshold must be non-negative."
            raise ValueError(exc_msg)

        self._session = session
        self._client_credentials = client_credentials
        self._base_url = BASE_URL_TEST if test_environment else BASE_URL_PRODUCTION
        self._test_environment = test_environment
        self._expiry_threshold = expiry_threshold
        self.single_token = single_token
        self._issued_tokens: list[tuple[float, oauth2.AccessTokenResponse]] = []

    @property
    def test_environment(self) -> bool:
        """Return ``True`` if configured for the test environment."""
        return self._test_environment

    @property
    def expiry_threshold(self) -> float:
        """Return the expiry threshold."""
        return self._expiry_threshold

    @property
    def _latest_token_issued_at(self) -> float:
        """Return the monotonic time at which the latest token was issued."""
        return self._issued_tokens[-1][0]

    @property
    def _latest_token(self) -> oauth2.AccessTokenResponse:
        """Return the parsed response representing the latest issued access token."""
        return self._issued_tokens[-1][1]

    @property
    def _token_available_unlocked(self) -> bool:
        """Return whether at least one access token is stored."""
        return bool(self._issued_tokens)

    @property
    def _access_token_unlocked(self) -> str:
        """Return the access token string."""
        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()
        return self._latest_token.access_token

    @property
    def _scope_unlocked(self) -> str | None:
        """Return the scope associated with the token."""
        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()
        return self._latest_token.scope

    @property
    def _token_type_unlocked(self) -> str:
        """Return the token type."""
        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()
        return self._latest_token.token_type

    @property
    def _auth_header_unlocked(self) -> str:
        """
        Return an Authorization header value.

        The value is suitable for the HTTP Authorization header in the
        format ``"<token_type> <access_token>"``.
        """
        if not self._token_available_unlocked or self._is_expired_unlocked:
            self._raise_token_unavailable_error()
        return f"{self._latest_token.token_type} {self._latest_token.access_token}"

    @property
    def _remaining_lifetime_unlocked(self) -> float:
        """Return the remaining token lifetime in seconds."""
        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()

        return self._latest_token.expires_in - (
            time.monotonic() - self._latest_token_issued_at
        )

    @property
    def _is_expired_unlocked(self) -> bool:
        """
        Return ``True`` if the token is considered expired.

        A token is considered expired if its remaining lifetime is less than
        or equal to the configured expiry threshold.
        """
        return self._remaining_lifetime_unlocked <= self._expiry_threshold

    @staticmethod
    def _raise_on_http_error(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code in (400, 401):
                try:
                    model = oauth2.ErrorResponse.model_validate(response.json())
                    oauth2_exc = OAuth2Error(
                        status_code=response.status_code, **model.model_dump()
                    )
                    raise oauth2_exc from exc
                except (ValueError, pydantic.ValidationError) as parse_exc:
                    exc.add_note(f"Failed to parse OAuth2Error:\n\n{parse_exc}")
            raise

    @staticmethod
    def _raise_token_unavailable_error() -> NoReturn:
        """Raise an error for missing or unusable token state."""
        exc_msg = "No valid access token available."
        raise RuntimeError(exc_msg)


class TokenManager(TokenManagerBase[httpx.Client]):
    """
    Synchronous OAuth 2.0 token manager.

    The ``TokenManager`` manages the lifecycle of OAuth 2.0 access tokens used for
    authenticated requests to the API. It provides methods for requesting the issuance
    or revocation of access tokens from the authorization server, and for accessing
    details about the latest issued access token.

    Issuing a new access token does not revoke previously issued tokens. Issued
    tokens are stored internally until explicitly revoked.

    Parameters
    ----------
    session : httpx.Client
        Synchronous HTTP client instance.
    client_credentials : oauth2.ClientCredentials
        OAuth 2.0 client credentials mapping containing ``client_id`` and
        ``client_secret``.
    test_environment : bool, optional
        If ``True``, use the test OAuth 2.0 portal endpoints instead of the
        production endpoints.
    single_token: bool, optional
        If ``True``, existing tokens will automatically be revoked when
        a new one is issued.
    expiry_threshold : float, optional
        Number of seconds before actual expiration when an access token
        should be treated as expired.
    """

    def __init__(
        self,
        session: httpx.Client,
        client_credentials: oauth2.ClientCredentials,
        *,
        test_environment: bool = False,
        single_token: bool = False,
        expiry_threshold: float = 0.0,
    ) -> None:
        super().__init__(
            session,
            client_credentials,
            test_environment=test_environment,
            single_token=single_token,
            expiry_threshold=expiry_threshold,
        )
        self._lock = threading.Lock()

    def token_available(self) -> bool:
        """Return whether at least one access token is stored."""
        with self._lock:
            return self._token_available_unlocked

    def access_token(self) -> str:
        """Return the access token string."""
        with self._lock:
            return self._access_token_unlocked

    def scope(self) -> str | None:
        """Return the scope associated with the token."""
        with self._lock:
            return self._scope_unlocked

    def token_type(self) -> str:
        """Return the token type."""
        with self._lock:
            return self._token_type_unlocked

    def auth_header(self) -> str:
        """
        Return an Authorization header value.

        The value is suitable for the HTTP Authorization header in the
        format ``"<token_type> <access_token>"``.
        """
        with self._lock:
            return self._auth_header_unlocked

    def remaining_lifetime(self) -> float:
        """Return the remaining token lifetime in seconds."""
        with self._lock:
            return self._remaining_lifetime_unlocked

    def is_expired(self) -> bool:
        """
        Return ``True`` if the token is considered expired.

        A token is considered expired if its remaining lifetime is less than
        or equal to the configured expiry threshold.
        """
        with self._lock:
            return self._is_expired_unlocked

    def _post_request(
        self,
        path: str,
        **data,
    ) -> httpx.Response:
        """
        Send a POST request to the authorization server.

        Parameters
        ----------
        path : str
            Path appended to the base URL to form the endpoint URL.
        **data
            Form-encoded request parameters included in the OAuth 2.0 request
            body, excluding client credentials.

        Returns
        -------
        httpx.Response
            HTTP response returned by the OAuth 2.0 authorization server.
        """
        return self._session.post(
            url=f"{self._base_url}{path}",
            headers={"Content-Type": CONTENT_TYPE},
            data=data | self._client_credentials,
        )

    def _issue_access_token_unlocked(self, *, scope: str) -> None:
        """
        Request the authorization server to issue a new access token.

        The issued access token is stored internally.

        Parameters
        ----------
        scope : str
            Access token scope.

        Raises
        ------
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        pydantic.ValidationError
            If the token response cannot be parsed into an access token model.
        """
        response = self._post_request(PATH_TOKEN, grant_type=GRANT_TYPE, scope=scope)

        self._raise_on_http_error(response)

        self._issued_tokens.append(
            (
                time.monotonic(),
                oauth2.AccessTokenResponse.model_validate(response.json()),
            ),
        )

    def _revoke_access_token_unlocked(self, *, clear: bool) -> None:
        """
        Request the authorization server to revoke one or more issued access tokens.

        Parameters
        ----------
        clear : bool, optional
            If ``True``, revoke all issued access tokens. If ``False``,
            revoke the latest issued access token.

        Raises
        ------
        RuntimeError
            If no access token is stored.
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        """

        def _revoke_latest() -> None:
            response = self._post_request(
                PATH_REVOKE,
                token=self._latest_token.access_token,
            )
            self._raise_on_http_error(response)
            self._issued_tokens.pop()

        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()

        if clear:
            while self._issued_tokens:
                _revoke_latest()
        else:
            _revoke_latest()

    def issue_access_token(self, *, scope: str = DEFAULT_SCOPE) -> None:
        """
        Request the authorization server to issue a new access token.

        The issued access token is stored internally.

        Parameters
        ----------
        scope : str, default="vardefulla-datamangder:read vardefulla-datamangder:ping"
            Access token scope.

        Raises
        ------
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        pydantic.ValidationError
            If the token response cannot be parsed into an access token model.
        """
        with self._lock:
            if self.single_token and self._issued_tokens:
                self._revoke_access_token_unlocked(clear=True)
            self._issue_access_token_unlocked(scope=scope)

    def revoke_access_token(self, *, clear: bool = False) -> None:
        """
        Request the authorization server to revoke one or more issued access tokens.

        Parameters
        ----------
        clear : bool, optional
            If ``True``, revoke all issued access tokens. If ``False``,
            revoke the latest issued access token.

        Raises
        ------
        RuntimeError
            If no access token is stored.
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        """
        with self._lock:
            self._revoke_access_token_unlocked(clear=clear)


class AsyncTokenManager(TokenManagerBase[httpx.AsyncClient]):
    """
    Asynchronous OAuth 2.0 token manager.

    The ``AsyncTokenManager`` manages the lifecycle of OAuth 2.0 access tokens used for
    authenticated requests to the API. It provides methods for requesting the issuance
    or revocation of access tokens from the authorization server, and for accessing
    details about the latest issued access token.

    Issuing a new access token does not revoke previously issued tokens. Issued
    tokens are stored internally until explicitly revoked.

    Parameters
    ----------
    session : httpx.AsyncClient
        Asynchronous HTTP client instance.
    client_credentials : oauth2.ClientCredentials
        OAuth 2.0 client credentials mapping containing ``client_id`` and
        ``client_secret``.
    test_environment : bool, optional
        If ``True``, use the test OAuth 2.0 portal endpoints instead of the
        production endpoints.
    single_token: bool, optional
        If ``True``, existing tokens will automatically be revoked when
        a new one is issued.
    expiry_threshold : float, optional
        Number of seconds before actual expiration when an access token
        should be treated as expired.
    """

    def __init__(
        self,
        session: httpx.AsyncClient,
        client_credentials: oauth2.ClientCredentials,
        *,
        test_environment: bool = False,
        single_token: bool = False,
        expiry_threshold: float = 0.0,
    ) -> None:
        super().__init__(
            session,
            client_credentials,
            test_environment=test_environment,
            single_token=single_token,
            expiry_threshold=expiry_threshold,
        )
        self._lock = asyncio.Lock()

    async def token_available(self) -> bool:
        """Return whether at least one access token is stored."""
        async with self._lock:
            return self._token_available_unlocked

    async def access_token(self) -> str:
        """Return the access token string."""
        async with self._lock:
            return self._access_token_unlocked

    async def scope(self) -> str | None:
        """Return the scope associated with the token."""
        async with self._lock:
            return self._scope_unlocked

    async def token_type(self) -> str:
        """Return the token type."""
        async with self._lock:
            return self._token_type_unlocked

    async def auth_header(self) -> str:
        """
        Return an Authorization header value.

        The value is suitable for the HTTP Authorization header in the
        format ``"<token_type> <access_token>"``.
        """
        async with self._lock:
            return self._auth_header_unlocked

    async def remaining_lifetime(self) -> float:
        """Return the remaining token lifetime in seconds."""
        async with self._lock:
            return self._remaining_lifetime_unlocked

    async def is_expired(self) -> bool:
        """
        Return ``True`` if the token is considered expired.

        A token is considered expired if its remaining lifetime is less than
        or equal to the configured expiry threshold.
        """
        async with self._lock:
            return self._is_expired_unlocked

    async def _post_request(
        self,
        path: str,
        **data,
    ) -> httpx.Response:
        """
        Send a POST request to the authorization server.

        Parameters
        ----------
        path : str
            Path appended to the base URL to form the endpoint URL.
        **data
            Form-encoded request parameters included in the OAuth 2.0 request
            body, excluding client credentials.

        Returns
        -------
        httpx.Response
            HTTP response returned by the OAuth 2.0 authorization server.
        """
        return await self._session.post(
            url=f"{self._base_url}{path}",
            headers={"Content-Type": CONTENT_TYPE},
            data=data | self._client_credentials,
        )

    async def _issue_access_token_unlocked(self, *, scope: str) -> None:
        """
        Request the authorization server to issue a new access token.

        The issued access token is stored internally.

        Parameters
        ----------
        scope : str
            Access token scope.

        Raises
        ------
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        pydantic.ValidationError
            If the token response cannot be parsed into an access token model.

        """
        response = await self._post_request(
            PATH_TOKEN,
            grant_type=GRANT_TYPE,
            scope=scope,
        )

        self._raise_on_http_error(response)

        self._issued_tokens.append(
            (
                time.monotonic(),
                oauth2.AccessTokenResponse.model_validate(response.json()),
            ),
        )

    async def _revoke_access_token_unlocked(self, *, clear: bool) -> None:
        """
        Request the authorization server to revoke one or more issued access tokens.

        Parameters
        ----------
        clear : bool, optional
            If ``True``, revoke all issued access tokens. If ``False``,
            revoke the latest issued access token.

        Raises
        ------
        RuntimeError
            If no access token is stored.
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        """

        async def _revoke_latest() -> None:
            response = await self._post_request(
                PATH_REVOKE,
                token=self._latest_token.access_token,
            )
            self._raise_on_http_error(response)
            self._issued_tokens.pop()

        if not self._token_available_unlocked:
            self._raise_token_unavailable_error()

        if clear:
            while self._issued_tokens:
                await _revoke_latest()
        else:
            await _revoke_latest()

    async def issue_access_token(self, *, scope: str = DEFAULT_SCOPE) -> None:
        """
        Request the authorization server to issue a new access token.

        The issued access token is stored internally.

        Parameters
        ----------
        scope : str, default="vardefulla-datamangder:read vardefulla-datamangder:ping"
            Access token scope.

        Raises
        ------
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        pydantic.ValidationError
            If the token response cannot be parsed into an access token model.

        """
        async with self._lock:
            if self.single_token and self._issued_tokens:
                await self._revoke_access_token_unlocked(clear=True)
            await self._issue_access_token_unlocked(scope=scope)

    async def revoke_access_token(self, *, clear: bool = False) -> None:
        """
        Request the authorization server to revoke one or more issued access tokens.

        Parameters
        ----------
        clear : bool, optional
            If ``True``, revoke all issued access tokens. If ``False``,
            revoke the latest issued access token.

        Raises
        ------
        RuntimeError
            If no access token is stored.
        pybvvd.OAuth2Error
            If the OAuth 2.0 server returns an OAuth 2.0 error response body.
        httpx.HTTPStatusError
            If the OAuth 2.0 server returns an unsuccessful HTTP status code,
            and the error is not an OAuth 2.0 error.
        """
        async with self._lock:
            await self._revoke_access_token_unlocked(clear=clear)
