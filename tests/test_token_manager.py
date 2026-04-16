# tests/client/test_token_manager.py

from __future__ import annotations

import time

import httpx
import pydantic
import pytest

from pybvvd.client._token_manager import (
    BASE_URL_PRODUCTION,
    BASE_URL_TEST,
    CONTENT_TYPE,
    DEFAULT_SCOPE,
    GRANT_TYPE,
    PATH_REVOKE,
    PATH_TOKEN,
    AsyncTokenManager,
    TokenManager,
)
from pybvvd.exceptions import OAuth2Error

CLIENT_CREDENTIALS = {
    "client_id": "test-client-id",
    "client_secret": "test-client-secret",
}


def make_token_response(
    *,
    access_token: str = "access-token-1",
    token_type: str = "Bearer",
    expires_in: int = 3600,
    scope: str = DEFAULT_SCOPE,
) -> dict[str, object]:
    return {
        "access_token": access_token,
        "token_type": token_type,
        "expires_in": expires_in,
        "scope": scope,
    }


def make_oauth2_error_response(
    *,
    error: str = "invalid_client",
    error_description: str = "Bad credentials",
    error_uri: str | None = "https://example.com/error",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "error": error,
        "error_description": error_description,
    }
    if error_uri is not None:
        payload["error_uri"] = error_uri
    return payload


def build_sync_client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def build_async_client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def test_init_rejects_negative_expiry_threshold() -> None:
    with (
        httpx.Client() as session,
        pytest.raises(ValueError, match="Expiry threshold must be non-negative"),
    ):
        TokenManager(
            session,
            CLIENT_CREDENTIALS,
            expiry_threshold=-1,
        )


def test_init_sets_production_base_url() -> None:
    with httpx.Client() as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)
        assert manager.test_environment is False
        assert manager.expiry_threshold == 0.0
        assert manager._base_url == BASE_URL_PRODUCTION


def test_init_sets_test_base_url() -> None:
    with httpx.Client() as session:
        manager = TokenManager(
            session,
            CLIENT_CREDENTIALS,
            test_environment=True,
        )
        assert manager.test_environment is True
        assert manager._base_url == BASE_URL_TEST


def test_token_accessors_raise_when_no_token_available() -> None:
    with httpx.Client() as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        for method in (
            manager.access_token,
            manager.scope,
            manager.token_type,
            manager.auth_header,
            manager.remaining_lifetime,
            manager.is_expired,
        ):
            with pytest.raises(RuntimeError, match="No valid access token available"):
                method()


def test_issue_access_token_stores_token_and_exposes_accessors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{PATH_TOKEN}"
        assert request.headers["Content-Type"] == CONTENT_TYPE

        body = request.read().decode()
        assert f"grant_type={GRANT_TYPE}" in body
        assert (
            "scope=vardefulla-datamangder%3Aread+vardefulla-datamangder%3Aping" in body
        )
        assert "client_id=test-client-id" in body
        assert "client_secret=test-client-secret" in body

        return httpx.Response(
            200,
            json=make_token_response(access_token="abc123"),
        )

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        manager.issue_access_token()

        assert manager.token_available() is True
        assert manager.access_token() == "abc123"
        assert manager.token_type() == "Bearer"
        assert manager.scope() == DEFAULT_SCOPE
        assert manager.auth_header() == "Bearer abc123"
        assert manager.is_expired() is False
        assert manager.remaining_lifetime() <= 3600
        assert manager.remaining_lifetime() > 0


def test_issue_access_token_uses_custom_scope() -> None:
    seen_body: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_body
        seen_body = request.read().decode()
        return httpx.Response(200, json=make_token_response(scope="custom:scope"))

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)
        manager.issue_access_token(scope="custom:scope")

    assert seen_body is not None
    assert "scope=custom%3Ascope" in seen_body


def test_issue_access_token_raises_oauth2_error_on_structured_400() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json=make_oauth2_error_response(
                error="invalid_client",
                error_description="Nope",
                error_uri="https://example.com/oauth-error",
            ),
        )

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(OAuth2Error) as exc_info:
            manager.issue_access_token()

    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.error == "invalid_client"
    assert exc.error_description == "Nope"
    assert exc.error_uri == "https://example.com/oauth-error"


def test_issue_access_token_raises_http_status_error_when_400_body_is_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"unexpected": "shape"})

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            manager.issue_access_token()

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("Failed to parse OAuth2Error" in note for note in notes)


def test_issue_access_token_raises_http_status_error_for_non_oauth_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server exploded"})

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(httpx.HTTPStatusError):
            manager.issue_access_token()


def test_issue_access_token_raises_validation_error_for_invalid_success_payload() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "abc",
                "token_type": "Bearer",
                # expires_in missing
                "scope": DEFAULT_SCOPE,
            },
        )

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(pydantic.ValidationError):
            manager.issue_access_token()


def test_revoke_access_token_revokes_latest_token_only() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == PATH_TOKEN:
            idx = calls.count(f"POST {PATH_TOKEN}")
            return httpx.Response(
                200,
                json=make_token_response(access_token=f"token-{idx}"),
            )
        if request.url.path == PATH_REVOKE:
            body = request.read().decode()
            assert "token=token-2" in body
            return httpx.Response(200, json={})

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)
        manager.issue_access_token()
        manager.issue_access_token()

        assert manager.access_token() == "token-2"

        manager.revoke_access_token()

        assert manager.access_token() == "token-1"
        assert len(manager._issued_tokens) == 1


def test_revoke_access_token_clear_revokes_all_tokens() -> None:
    revoked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            current_count = getattr(handler, "token_count", 0) + 1
            handler.token_count = current_count
            return httpx.Response(
                200,
                json=make_token_response(access_token=f"token-{current_count}"),
            )

        if request.url.path == PATH_REVOKE:
            body = request.read().decode()
            for token in ("token-3", "token-2", "token-1"):
                if f"token={token}" in body:
                    revoked.append(token)
                    break
            return httpx.Response(200, json={})

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    handler.token_count = 0  # type: ignore[attr-defined]

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)
        manager.issue_access_token()
        manager.issue_access_token()
        manager.issue_access_token()

        manager.revoke_access_token(clear=True)

        assert revoked == ["token-3", "token-2", "token-1"]
        assert manager.token_available() is False


def test_revoke_access_token_raises_when_no_token_available() -> None:
    with httpx.Client() as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(RuntimeError, match="No valid access token available"):
            manager.revoke_access_token()


def test_single_token_revokes_existing_token_before_issuing_new_one() -> None:
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            token_number = events.count("issue") + 1
            events.append("issue")
            return httpx.Response(
                200,
                json=make_token_response(access_token=f"token-{token_number}"),
            )

        if request.url.path == PATH_REVOKE:
            body = request.read().decode()
            assert "token=token-1" in body
            events.append("revoke")
            return httpx.Response(200, json={})

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(session, CLIENT_CREDENTIALS, single_token=True)

        manager.issue_access_token()
        manager.issue_access_token()

        assert events == ["issue", "revoke", "issue"]
        assert len(manager._issued_tokens) == 1
        assert manager.access_token() == "token-2"


def test_auth_header_raises_when_token_is_expired() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=make_token_response(expires_in=1),
        )

    with build_sync_client(httpx.MockTransport(handler)) as session:
        manager = TokenManager(
            session,
            CLIENT_CREDENTIALS,
            expiry_threshold=0.5,
        )
        manager.issue_access_token()

        time.sleep(0.7)

        with pytest.raises(RuntimeError, match="No valid access token available"):
            manager.auth_header()

        assert manager.is_expired() is True


@pytest.mark.asyncio
async def test_async_issue_access_token_stores_token_and_exposes_accessors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{PATH_TOKEN}"
        return httpx.Response(
            200,
            json=make_token_response(access_token="async-token"),
        )

    async with build_async_client(httpx.MockTransport(handler)) as session:
        manager = AsyncTokenManager(session, CLIENT_CREDENTIALS)

        await manager.issue_access_token()

        assert await manager.token_available() is True
        assert await manager.access_token() == "async-token"
        assert await manager.token_type() == "Bearer"
        assert await manager.scope() == DEFAULT_SCOPE
        assert await manager.auth_header() == "Bearer async-token"
        assert await manager.is_expired() is False
        assert await manager.remaining_lifetime() > 0


@pytest.mark.asyncio
async def test_async_issue_access_token_raises_oauth2_error_on_structured_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json=make_oauth2_error_response(
                error="invalid_client",
                error_description="Unauthorized",
            ),
        )

    async with build_async_client(httpx.MockTransport(handler)) as session:
        manager = AsyncTokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(OAuth2Error) as exc_info:
            await manager.issue_access_token()

    assert exc_info.value.status_code == 401
    assert exc_info.value.error == "invalid_client"
    assert exc_info.value.error_description == "Unauthorized"


@pytest.mark.asyncio
async def test_async_revoke_access_token_clear_revokes_all_tokens() -> None:
    revoked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            current_count = getattr(handler, "token_count", 0) + 1
            handler.token_count = current_count
            return httpx.Response(
                200,
                json=make_token_response(access_token=f"token-{current_count}"),
            )

        if request.url.path == PATH_REVOKE:
            body = request.read().decode()
            for token in ("token-3", "token-2", "token-1"):
                if f"token={token}" in body:
                    revoked.append(token)
                    break
            return httpx.Response(200, json={})

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    handler.token_count = 0  # type: ignore[attr-defined]

    async with build_async_client(httpx.MockTransport(handler)) as session:
        manager = AsyncTokenManager(session, CLIENT_CREDENTIALS)

        await manager.issue_access_token()
        await manager.issue_access_token()
        await manager.issue_access_token()

        await manager.revoke_access_token(clear=True)

        assert revoked == ["token-3", "token-2", "token-1"]
        assert await manager.token_available() is False


@pytest.mark.asyncio
async def test_async_single_token_revokes_existing_token_before_issuing_new_one() -> (
    None
):
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            token_number = events.count("issue") + 1
            events.append("issue")
            return httpx.Response(
                200,
                json=make_token_response(access_token=f"token-{token_number}"),
            )

        if request.url.path == PATH_REVOKE:
            body = request.read().decode()
            assert "token=token-1" in body
            events.append("revoke")
            return httpx.Response(200, json={})

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    async with build_async_client(httpx.MockTransport(handler)) as session:
        manager = AsyncTokenManager(session, CLIENT_CREDENTIALS, single_token=True)

        await manager.issue_access_token()
        await manager.issue_access_token()

        assert events == ["issue", "revoke", "issue"]
        assert len(manager._issued_tokens) == 1
        assert await manager.access_token() == "token-2"


@pytest.mark.asyncio
async def test_async_revoke_access_token_raises_when_no_token_available() -> None:
    async with httpx.AsyncClient() as session:
        manager = AsyncTokenManager(session, CLIENT_CREDENTIALS)

        with pytest.raises(RuntimeError, match="No valid access token available"):
            await manager.revoke_access_token()
