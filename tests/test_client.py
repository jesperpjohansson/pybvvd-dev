# tests/client/test_client.py

from __future__ import annotations

import httpx
import pydantic
import pytest

from pybvvd import api
from pybvvd.client._client import (
    BASE_PATH_API,
    BASE_URL_PRODUCTION,
    BASE_URL_TEST,
    AsyncClient,
    Client,
)
from pybvvd.client._token_manager import PATH_TOKEN
from pybvvd.exceptions import APIError

CLIENT_CREDENTIALS = {
    "client_id": "test-client-id",
    "client_secret": "test-client-secret",
}


class DummyTokenManager:
    def __init__(
        self, *, test_environment: bool = False, header: str = "Bearer sync-token"
    ):
        self.test_environment = test_environment
        self._header = header

    def auth_header(self) -> str:
        return self._header


class DummyAsyncTokenManager:
    def __init__(
        self,
        *,
        test_environment: bool = False,
        header: str = "Bearer async-token",
    ):
        self.test_environment = test_environment
        self._header = header

    async def auth_header(self) -> str:
        return self._header


def make_api_error_payload(  # noqa: PLR0913
    *,
    type_: str = "about:blank",
    instance: str = "validation.client",
    status: int = 400,
    title: str = "Bad Request",
    detail: str = "Invalid input",
    request_id: str | None = "req-123",
    timestamp: str | None = "2024-09-18T09:32:24Z",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": type_,
        "instance": instance,
        "status": status,
        "title": title,
        "detail": detail,
    }
    if request_id is not None:
        payload["requestId"] = request_id
    if timestamp is not None:
        payload["timestamp"] = timestamp
    return payload


def make_organisationer_payload() -> dict[str, object]:
    return {
        "organisationer": [
            {
                "organisationsidentitet": {
                    "identitetsbeteckning": "5560000001",
                    "typ": {
                        "kod": "ORGNR",
                        "klartext": "Organisationsnummer",
                    },
                },
                "organisationsnamn": {
                    "organisationsnamnLista": [
                        {
                            "namn": "Testbolaget AB",
                            "organisationsnamntyp": {
                                "kod": "NAMN",
                                "klartext": "Företagsnamn",
                            },
                        }
                    ]
                },
            }
        ]
    }


def make_dokumentlista_payload() -> dict[str, object]:
    return {
        "dokument": [
            {
                "dokumentId": "doc-1",
                "filformat": "PDF",
                "rapporteringsperiodTom": "2024-12-31",
                "registreringstidpunkt": "2025-01-15",
            }
        ]
    }


def make_token_response(*, access_token: str = "issued-token") -> dict[str, object]:
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "vardefulla-datamangder:read vardefulla-datamangder:ping",
    }


def test_normalize_identitetsbeteckning_from_string() -> None:
    assert Client._normalize_identitetsbeteckning("5560000001") == {
        "identitetsbeteckning": "5560000001"
    }


def test_normalize_identitetsbeteckning_from_organisationer_begaran() -> None:
    req = api.OrganisationerBegaran(identitetsbeteckning="5560000001")
    assert Client._normalize_identitetsbeteckning(req) == {
        "identitetsbeteckning": "5560000001"
    }


def test_normalize_identitetsbeteckning_from_dokumentlista_begaran() -> None:
    req = api.DokumentlistaBegaran(identitetsbeteckning="5560000001")
    assert Client._normalize_identitetsbeteckning(req) == {
        "identitetsbeteckning": "5560000001"
    }


def test_client_uses_production_base_url() -> None:
    with httpx.Client() as session:
        client = Client(session, DummyTokenManager(test_environment=False))
        assert client._base_url == BASE_URL_PRODUCTION


def test_client_uses_test_base_url() -> None:
    with httpx.Client() as session:
        client = Client(session, DummyTokenManager(test_environment=True))
        assert client._base_url == BASE_URL_TEST


def test_client_from_credentials_issues_token_and_returns_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            body = request.read().decode()
            assert request.method == "POST"
            assert "client_id=test-client-id" in body
            assert "client_secret=test-client-secret" in body
            assert "scope=custom%3Ascope" in body
            return httpx.Response(200, json=make_token_response())

        if request.url.path == f"{BASE_PATH_API}/isalive":
            assert request.headers["Authorization"] == "Bearer issued-token"
            return httpx.Response(200, text="alive")

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client.from_credentials(
            session,
            CLIENT_CREDENTIALS,
            scope="custom:scope",
        )
        body, status = client.ping()

    assert body == "alive"
    assert status == 200


def test_client_from_credentials_can_skip_token_issue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        exc_msg = f"unexpected request: {request.method} {request.url}"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client.from_credentials(
            session,
            CLIENT_CREDENTIALS,
            issue_token=False,
        )

        with pytest.raises(RuntimeError, match="No valid access token available"):
            client.ping()


def test_ping_returns_text_and_status_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/isalive"
        assert request.headers["Authorization"] == "Bearer sync-token"
        return httpx.Response(200, text="alive")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())
        body, status = client.ping()

    assert body == "alive"
    assert status == 200


def test_organisationer_posts_normalized_body_and_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert (
            str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/organisationer"
        )
        assert request.headers["Authorization"] == "Bearer sync-token"
        assert request.read() == b'{"identitetsbeteckning":"5560000001"}'
        return httpx.Response(200, json=make_organisationer_payload())

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())
        result = client.organisationer("5560000001")

    assert isinstance(result, api.OrganisationerSvar)
    assert result.organisationer is not None
    assert result.organisationer[0].organisationsidentitet is not None
    assert (
        result.organisationer[0].organisationsidentitet.identitetsbeteckning
        == "5560000001"
    )


def test_organisationer_accepts_request_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.read() == b'{"identitetsbeteckning":"5560000001"}'
        return httpx.Response(200, json=make_organisationer_payload())

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())
        result = client.organisationer(
            api.OrganisationerBegaran(identitetsbeteckning="5560000001")
        )

    assert result.organisationer is not None
    assert len(result.organisationer) == 1


def test_dokumentlista_posts_normalized_body_and_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/dokumentlista"
        assert request.headers["Authorization"] == "Bearer sync-token"
        assert request.read() == b'{"identitetsbeteckning":"5560000001"}'
        return httpx.Response(200, json=make_dokumentlista_payload())

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())
        result = client.dokumentlista("5560000001")

    assert isinstance(result, api.DokumentlistaSvar)
    assert result.dokument is not None
    assert result.dokument[0].dokumentId == "doc-1"


def test_dokument_returns_raw_bytes() -> None:
    pdf_bytes = b"%PDF-1.7 fake pdf bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert (
            str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/dokument/doc-1"
        )
        assert request.headers["Authorization"] == "Bearer sync-token"
        return httpx.Response(200, content=pdf_bytes)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())
        result = client.dokument("doc-1")

    assert result == pdf_bytes


def test_organisationer_raises_api_error_for_structured_error_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json=make_api_error_payload(
                type_="urn:bolagsverket:error:validation",
                instance="validation.client",
                status=400,
                title="Bad Request",
                detail="JSON parse error",
            ),
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())

        with pytest.raises(APIError) as exc_info:
            client.organisationer("5560000001")

    exc = exc_info.value
    assert exc.type_ == "urn:bolagsverket:error:validation"
    assert exc.instance == "validation.client"
    assert exc.status == 400
    assert exc.title == "Bad Request"
    assert exc.detail == "JSON parse error"
    assert exc.requestId == "req-123"


def test_organisationer_raises_http_status_error_when_error_body_cannot_be_parsed() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"unexpected": "shape"})

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.organisationer("5560000001")

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("Failed to parse ApiError" in note for note in notes)


def test_organisationer_raises_validation_error_for_invalid_success_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organisationer": "not-a-list"})

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, DummyTokenManager())

        with pytest.raises(pydantic.ValidationError):
            client.organisationer("5560000001")


def test_runtime_error_from_token_manager_bubbles_up() -> None:
    class FailingTokenManager(DummyTokenManager):
        def auth_header(self) -> str:
            exc_msg = "No valid access token available."
            raise RuntimeError(exc_msg)

    def handler(request: httpx.Request) -> httpx.Response:
        exc_msg = "request should not be made when auth header retrieval fails"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as session:
        client = Client(session, FailingTokenManager())

        with pytest.raises(RuntimeError, match="No valid access token available"):
            client.ping()


@pytest.mark.asyncio
async def test_async_ping_returns_text_and_status_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/isalive"
        assert request.headers["Authorization"] == "Bearer async-token"
        return httpx.Response(200, text="alive")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())
        body, status = await client.ping()

    assert body == "alive"
    assert status == 200


@pytest.mark.asyncio
async def test_async_client_from_credentials_issues_token_and_returns_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PATH_TOKEN:
            body = request.read().decode()
            assert request.method == "POST"
            assert "client_id=test-client-id" in body
            assert "client_secret=test-client-secret" in body
            assert "scope=custom%3Ascope" in body
            return httpx.Response(200, json=make_token_response())

        if request.url.path == f"{BASE_PATH_API}/isalive":
            assert request.headers["Authorization"] == "Bearer issued-token"
            return httpx.Response(200, text="alive")

        exc_msg = "unexpected request"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = await AsyncClient.from_credentials(
            session,
            CLIENT_CREDENTIALS,
            scope="custom:scope",
        )
        body, status = await client.ping()

    assert body == "alive"
    assert status == 200


@pytest.mark.asyncio
async def test_async_client_from_credentials_can_skip_token_issue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        exc_msg = f"unexpected request: {request.method} {request.url}"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = await AsyncClient.from_credentials(
            session,
            CLIENT_CREDENTIALS,
            issue_token=False,
        )

        with pytest.raises(RuntimeError, match="No valid access token available"):
            await client.ping()


@pytest.mark.asyncio
async def test_async_organisationer_posts_normalized_body_and_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert (
            str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/organisationer"
        )
        assert request.headers["Authorization"] == "Bearer async-token"
        assert request.read() == b'{"identitetsbeteckning":"5560000001"}'
        return httpx.Response(200, json=make_organisationer_payload())

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())
        result = await client.organisationer("5560000001")

    assert isinstance(result, api.OrganisationerSvar)
    assert result.organisationer is not None

    organisation = result.organisationer[0]
    assert organisation.organisationsidentitet is not None
    assert organisation.organisationsidentitet.identitetsbeteckning == "5560000001"


@pytest.mark.asyncio
async def test_async_dokumentlista_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/dokumentlista"
        assert request.read() == b'{"identitetsbeteckning":"5560000001"}'
        return httpx.Response(200, json=make_dokumentlista_payload())

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())
        result = await client.dokumentlista(
            api.DokumentlistaBegaran(identitetsbeteckning="5560000001")
        )

    assert result.dokument is not None
    assert result.dokument[0].dokumentId == "doc-1"


@pytest.mark.asyncio
async def test_async_dokument_returns_raw_bytes() -> None:
    doc_bytes = b"binary-document"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert (
            str(request.url) == f"{BASE_URL_PRODUCTION}{BASE_PATH_API}/dokument/doc-1"
        )
        return httpx.Response(200, content=doc_bytes)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())
        result = await client.dokument("doc-1")

    assert result == doc_bytes


@pytest.mark.asyncio
async def test_async_organisationer_raises_api_error_for_structured_error_response() -> (  # noqa: E501
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json=make_api_error_payload(
                type_="about:blank",
                instance="not.found",
                status=404,
                title="Not Found",
                detail="Organisation not found",
            ),
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())

        with pytest.raises(APIError) as exc_info:
            await client.organisationer("5560000001")

    exc = exc_info.value
    assert exc.status == 404
    assert exc.instance == "not.found"
    assert exc.title == "Not Found"
    assert exc.detail == "Organisation not found"


@pytest.mark.asyncio
async def test_async_organisationer_raises_http_status_error_when_error_body_cannot_be_parsed() -> (  # noqa: E501
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"unexpected": "shape"})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, DummyAsyncTokenManager())

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.organisationer("5560000001")

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("Failed to parse ApiError" in note for note in notes)


@pytest.mark.asyncio
async def test_async_runtime_error_from_token_manager_bubbles_up() -> None:
    class FailingAsyncTokenManager(DummyAsyncTokenManager):
        async def auth_header(self) -> str:
            exc_msg = "No valid access token available."
            raise RuntimeError(exc_msg)

    def handler(request: httpx.Request) -> httpx.Response:
        exc_msg = "request should not be made when auth header retrieval fails"
        raise AssertionError(exc_msg)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as session:
        client = AsyncClient(session, FailingAsyncTokenManager())

        with pytest.raises(RuntimeError, match="No valid access token available"):
            await client.ping()
