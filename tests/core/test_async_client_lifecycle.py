from __future__ import annotations

import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.exceptions import ClientClosedError


def _settings() -> AvitoSettings:
    return AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))


def test_access_before_aenter_raises() -> None:
    client = AsyncAvitoClient(_settings())

    with pytest.raises(RuntimeError):
        client.debug_info()


@pytest.mark.asyncio
async def test_aclose_is_idempotent_and_closes_public_methods() -> None:
    client = AsyncAvitoClient(_settings())
    await client.__aenter__()

    assert client.debug_info().requires_auth is True
    await client.aclose()
    await client.aclose()

    with pytest.raises(ClientClosedError):
        client.auth()

