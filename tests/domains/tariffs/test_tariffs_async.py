from __future__ import annotations

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.exceptions import AuthenticationError, RateLimitError, TransportError
from avito.core.retries import RetryPolicy
from avito.tariffs import AsyncTariff
from avito.testing import AsyncFakeTransport


def _tariff_payload() -> dict[str, object]:
    return {
        "current": {
            "level": "Тариф Максимальный",
            "isActive": True,
            "startTime": 1713427200,
            "closeTime": 1716029200,
            "bonus": 10,
            "packages": [{"id": 1}, {"id": 2}],
            "price": {"price": 1990, "originalPrice": 2490},
        },
        "scheduled": {
            "level": "Тариф Базовый",
            "isActive": False,
            "startTime": 1716029300,
            "closeTime": None,
            "bonus": 0,
            "packages": [],
            "price": {"price": 990, "originalPrice": 990},
        },
    }


@pytest.mark.asyncio
async def test_async_tariff_flow() -> None:
    fake = AsyncFakeTransport().add_json("GET", "/tariff/info/1", _tariff_payload())
    transport = fake.build()

    tariff = AsyncTariff(transport)
    info = await tariff.get_tariff_info()

    assert info.current is not None
    assert info.current.level == "Тариф Максимальный"
    assert info.current.packages_count == 2
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_tariff_factory_returns_async_tariff() -> None:
    fake = AsyncFakeTransport().add_json("GET", "/tariff/info/1", _tariff_payload())
    client = fake.as_client()

    tariff = client.tariff()
    info = await tariff.get_tariff_info()

    assert isinstance(tariff, AsyncTariff)
    assert info.scheduled is not None
    assert info.scheduled.level == "Тариф Базовый"
    await client.aclose()


@pytest.mark.asyncio
async def test_async_tariff_maps_401() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/tariff/info/1",
        {"error": "unauthorized"},
        status_code=401,
    )
    transport = fake.build()

    with pytest.raises(AuthenticationError):
        await AsyncTariff(transport).get_tariff_info()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_tariff_maps_429() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/tariff/info/1",
        {"error": "rate limit"},
        status_code=429,
    )
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(RateLimitError):
        await AsyncTariff(transport).get_tariff_info()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_tariff_maps_transport_error() -> None:
    def raise_network_error(request: object) -> httpx.Response:
        raise httpx.NetworkError("connection failed")

    fake = AsyncFakeTransport().add("GET", "/tariff/info/1", raise_network_error)
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(TransportError):
        await AsyncTariff(transport).get_tariff_info()

    await transport.aclose()


def test_async_client_tariff_requires_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.tariff()
