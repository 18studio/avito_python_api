from __future__ import annotations

import httpx
import pytest

from avito.config import AvitoSettings
from avito.core.async_transport import AsyncTransport
from avito.core.retries import RetryPolicy
from avito.core.types import RequestContext
from avito.testing import AsyncFakeTransport


@pytest.mark.asyncio
async def test_async_transport_sends_authorization_and_retries_after_401() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("POST", "/token", {"access_token": "old", "expires_in": 3600})
        .add_json("POST", "/token", {"access_token": "new", "expires_in": 3600})
        .add_json("GET", "/core/v1/accounts/self", {"error": "expired"}, status_code=401)
        .add_json("GET", "/core/v1/accounts/self", {"id": 7})
    )
    transport = fake.build(authenticated=True)

    payload = await transport.request_json(
        "GET",
        "/core/v1/accounts/self",
        context=RequestContext("smoke"),
    )

    assert payload == {"id": 7}
    assert fake.count(method="POST", path="/token") == 2
    assert fake.last(method="GET", path="/core/v1/accounts/self").headers["authorization"] == (
        "Bearer new"
    )
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_transport_retries_429_and_propagates_idempotency_key() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("POST", "/items", {"error": "limited"}, status_code=429)
        .add_json("POST", "/items", {"ok": True})
    )
    transport = fake.build(
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_factor=0,
            retryable_methods=("POST",),
        )
    )

    payload = await transport.request_json(
        "POST",
        "/items",
        context=RequestContext("items.create"),
        json_body={"title": "x"},
        idempotency_key="idem-1",
    )

    assert payload == {"ok": True}
    assert fake.count(method="POST", path="/items") == 2
    assert fake.last(method="POST", path="/items").headers["idempotency-key"] == "idem-1"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_transport_aclose_closes_passed_async_client() -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    )
    transport = AsyncTransport(AvitoSettings(), client=http_client)

    await transport.aclose()
    await transport.aclose()

    assert http_client.is_closed is True


@pytest.mark.asyncio
async def test_download_binary_full_buffer_matches_sync_contract() -> None:
    fake = AsyncFakeTransport().add(
        "GET",
        "/file",
        __import__("httpx").Response(
            200,
            content=b"payload",
            headers={"content-type": "application/octet-stream"},
        ),
    )
    transport = fake.build()

    result = await transport.download_binary("/file", context=RequestContext("binary"))

    assert result.content == b"payload"
    assert result.content_type == "application/octet-stream"
    await transport.aclose()
