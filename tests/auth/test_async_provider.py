from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest

from avito.auth.async_provider import AsyncAuthProvider
from avito.auth.models import AccessToken, TokenResponse
from avito.auth.settings import AuthSettings


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
