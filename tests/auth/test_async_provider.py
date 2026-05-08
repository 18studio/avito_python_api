from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from avito.auth.async_provider import AsyncAuthProvider
from avito.auth.async_token_client import AsyncTokenClient
from avito.auth.models import AccessToken, TokenResponse
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings


@pytest.mark.asyncio
async def test_invalidate_token_is_sync_and_idempotent() -> None:
    async def fetcher(settings: AuthSettings) -> TokenResponse:
        return TokenResponse(
            access_token=AccessToken(
                value="token",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

    provider = AsyncAuthProvider(
        AuthSettings(client_id="id", client_secret="secret"),
        token_fetcher=fetcher,
    )
    assert not inspect.iscoroutinefunction(provider.invalidate_token)

    assert await provider.get_access_token() == "token"
    provider.invalidate_token()
    provider.invalidate_token()

    assert await provider.get_access_token() == "token"


@pytest.mark.asyncio
async def test_autoteka_concurrent_first_touch_single_token_request() -> None:
    token_requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        assert request.url.path == "/autoteka/token"
        token_requests += 1
        await asyncio.sleep(0)
        return httpx.Response(
            200,
            json={"access_token": "autoteka-token", "expires_in": 3600, "token_type": "Bearer"},
        )

    settings = AuthSettings(
        client_id="main-client-id",
        client_secret="main-client-secret",
        autoteka_client_id="autoteka-client-id",
        autoteka_client_secret="autoteka-client-secret",
        autoteka_scope="autoteka:read",
    )
    sdk_settings = AvitoSettings(auth=settings)
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.avito.ru",
    )
    provider = AsyncAuthProvider(
        settings,
        autoteka_token_client=AsyncTokenClient(
            settings,
            token_url=settings.autoteka_token_url,
            client=http_client,
            sdk_settings=sdk_settings,
        ),
    )

    tokens = await asyncio.gather(*(provider.get_autoteka_access_token() for _ in range(20)))

    assert tokens == ["autoteka-token"] * 20
    assert token_requests == 1
    await provider.aclose()
