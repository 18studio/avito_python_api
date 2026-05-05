from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from avito import AvitoClient
from avito.auth import (
    AlternateTokenClient,
    AuthProvider,
    AuthSettings,
    ClientCredentialsRequest,
    RefreshTokenRequest,
    TokenClient,
)
from avito.config import AvitoSettings
from avito.core.exceptions import AuthenticationError
from avito.core.retries import RetryPolicy
from avito.core.types import ApiTimeouts


def make_token_http_client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, base_url="https://api.avito.ru")


def test_token_client_requests_access_token_via_client_credentials() -> None:
    seen_payloads: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(request.content.decode())
        return httpx.Response(
            200,
            json={
                "access_token": "access-1",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh-1",
            },
        )

    token_client = TokenClient(
        AuthSettings(client_id="client-id", client_secret="client-secret"),
        client=make_token_http_client(httpx.MockTransport(handler)),
    )

    token_response = token_client.request_client_credentials_token(
        ClientCredentialsRequest(client_id="client-id", client_secret="client-secret")
    )

    assert token_response.access_token.value == "access-1"
    assert token_response.refresh_token == "refresh-1"
    assert "grant_type=client_credentials" in seen_payloads[0]


def test_token_client_uses_shared_transport_headers_and_timeout() -> None:
    captured_user_agents: list[str] = []
    captured_timeouts: list[dict[str, float]] = []
    settings = AvitoSettings(
        base_url="https://sandbox.avito.ru",
        user_agent_suffix="tests/oauth",
        auth=AuthSettings(client_id="client-id", client_secret="client-secret"),
        timeouts=ApiTimeouts(connect=1.0, read=2.0, write=3.0, pool=4.0),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured_user_agents.append(request.headers["User-Agent"])
        captured_timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={"access_token": "access-1", "expires_in": 3600})

    token_client = TokenClient(
        settings.auth,
        client=make_token_http_client(httpx.MockTransport(handler)),
        sdk_settings=settings,
    )

    token_client.request_client_credentials_token(
        ClientCredentialsRequest(client_id="client-id", client_secret="client-secret")
    )

    assert captured_user_agents[0].startswith("avito-py/")
    assert captured_user_agents[0].endswith("tests/oauth")
    assert captured_timeouts == [{"connect": 1.0, "read": 2.0, "write": 3.0, "pool": 4.0}]


def test_auth_provider_uses_refresh_token_flow_after_initial_token() -> None:
    issued_access_tokens: Iterator[str] = iter(("access-1", "access-2"))

    def handler(request: httpx.Request) -> httpx.Response:
        form_payload = request.content.decode()
        if "grant_type=client_credentials" in form_payload:
            return httpx.Response(
                200,
                json={
                    "access_token": next(issued_access_tokens),
                    "expires_in": 1,
                    "refresh_token": "refresh-1",
                },
            )
        assert "grant_type=refresh_token" in form_payload
        assert "refresh_token=refresh-1" in form_payload
        return httpx.Response(
            200,
            json={
                "access_token": next(issued_access_tokens),
                "expires_in": 3600,
                "refresh_token": "refresh-2",
            },
        )

    token_client = TokenClient(
        AuthSettings(client_id="client-id", client_secret="client-secret"),
        client=make_token_http_client(httpx.MockTransport(handler)),
    )
    provider = AuthProvider(
        AuthSettings(client_id="client-id", client_secret="client-secret"),
        token_client=token_client,
    )

    first_access_token = provider.get_access_token()
    provider._access_token = replace(
        provider._access_token,  # type: ignore[arg-type, attr-defined]
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    second_access_token = provider.get_access_token()

    assert first_access_token == "access-1"
    assert second_access_token == "access-2"


def test_token_client_maps_authentication_error() -> None:
    token_client = TokenClient(
        AuthSettings(client_id="client-id", client_secret="client-secret"),
        client=make_token_http_client(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    401,
                    json={"error": "invalid_client", "error_description": "wrong secret"},
                )
            )
        ),
    )

    with pytest.raises(AuthenticationError) as error:
        token_client.request_client_credentials_token(
            ClientCredentialsRequest(client_id="client-id", client_secret="wrong-secret")
        )

    assert error.value.status_code == 401
    assert error.value.error_code == "invalid_client"
    assert error.value.operation == "auth.oauth_token"
    assert error.value.attempt == 1
    assert error.value.method == "POST"
    assert error.value.endpoint == "/token"


def test_client_auth_surface_exposes_current_token_flows_only() -> None:
    settings = AvitoSettings(
        base_url="https://api.avito.ru",
        auth=AuthSettings(client_id="client-id", client_secret="client-secret"),
        retry_policy=RetryPolicy(),
        timeouts=ApiTimeouts(),
    )
    client = AvitoClient(settings)

    auth_provider = client.auth()
    assert isinstance(auth_provider.token_flow(), TokenClient)
    assert isinstance(auth_provider.alternate_token_flow(), AlternateTokenClient)

    with pytest.raises(AttributeError):
        _ = client.legacy_auth  # type: ignore[attr-defined]


def test_alternate_token_client_uses_refresh_contract_on_duplicate_path() -> None:
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(200, json={"access_token": "legacy-access", "expires_in": 3600})

    alternate_token_client = AlternateTokenClient(
        AuthSettings(
            client_id="client-id", client_secret="client-secret", alternate_token_url="/token"
        ),
        client=make_token_http_client(httpx.MockTransport(handler)),
    )

    token_response = alternate_token_client.request_refresh_token(
        RefreshTokenRequest(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-1",
        )
    )

    assert token_response.access_token.value == "legacy-access"
    assert captured_paths == ["/token"]


def test_auth_provider_uses_separate_autoteka_credentials_for_autoteka_token() -> None:
    captured_payloads: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payloads.append(request.content.decode())
        return httpx.Response(200, json={"access_token": "autoteka-access", "expires_in": 3600})

    settings = AuthSettings(
        client_id="client-id",
        client_secret="client-secret",
        autoteka_client_id="autoteka-client-id",
        autoteka_client_secret="autoteka-client-secret",
        autoteka_scope="autoteka:read",
    )
    provider = AuthProvider(
        settings,
        autoteka_token_client=TokenClient(
            settings,
            client=make_token_http_client(httpx.MockTransport(handler)),
        ),
    )

    token = provider.get_autoteka_access_token()

    assert token == "autoteka-access"
    assert "client_id=autoteka-client-id" in captured_payloads[0]
    assert "client_secret=autoteka-client-secret" in captured_payloads[0]
    assert "scope=autoteka%3Aread" in captured_payloads[0]
