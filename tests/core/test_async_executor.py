from __future__ import annotations

import httpx
import pytest

from avito.core.domain import AsyncDomainObject
from avito.core.operations import AsyncOperationExecutor, OperationExecutor, OperationSpec
from avito.core.swagger import swagger_operation
from avito.core.types import RequestContext, RetryOverride
from avito.testing import AsyncFakeTransport

BINARY_SPEC: OperationSpec[object] = OperationSpec(
    name="test.binary.download",
    method="GET",
    path="/binary/{item_id}",
    response_kind="binary",
)


class _TestBinaryDomain(AsyncDomainObject):
    @swagger_operation("GET", "/binary/{item_id}", spec="Test.json", variant="async")
    async def download(self, item_id: int) -> object:
        return await self._execute(BINARY_SPEC, path_params={"item_id": item_id})


class BinaryTransport:
    def __init__(self) -> None:
        self.contexts: list[RequestContext] = []

    async def request(self, *args: object, **kwargs: object) -> httpx.Response:
        self.contexts.append(kwargs["context"])
        request = httpx.Request("GET", "https://api.avito.ru/file")
        return httpx.Response(
            200,
            content=b"file",
            headers={"content-disposition": 'attachment; filename="label.pdf"'},
            request=request,
        )

    async def request_json(self, *args: object, **kwargs: object) -> object:
        self.contexts.append(kwargs["context"])
        return {}


class SyncRetryTransport:
    def __init__(self) -> None:
        self.contexts: list[RequestContext] = []

    def request(self, *args: object, **kwargs: object) -> httpx.Response:
        self.contexts.append(kwargs["context"])
        request = httpx.Request("GET", "https://api.avito.ru/items")
        return httpx.Response(204, request=request)

    def request_json(self, *args: object, **kwargs: object) -> object:
        self.contexts.append(kwargs["context"])
        return {}


@pytest.mark.asyncio
async def test_binary_branch_uses_async_request() -> None:
    spec: OperationSpec[object] = OperationSpec(
        name="orders.label.download",
        method="GET",
        path="/file",
        response_kind="binary",
    )

    result = await AsyncOperationExecutor(BinaryTransport()).execute(spec)

    assert result.content == b"file"
    assert result.filename == "label.pdf"


@pytest.mark.asyncio
async def test_async_executor_full_binary_pipeline() -> None:
    fake = AsyncFakeTransport().add(
        "GET",
        "/binary/42",
        httpx.Response(
            200,
            content=b"full-pipeline",
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'attachment; filename="full.pdf"',
            },
        ),
    )
    transport = fake.build()

    result = await _TestBinaryDomain(transport).download(42)

    assert result.content == b"full-pipeline"
    assert result.content_type == "application/pdf"
    assert result.filename == "full.pdf"
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/pdf"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_operation_transport_protocol_uses_async_methods() -> None:
    response = await BinaryTransport().request("GET", "/x", context=RequestContext("x"))

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retry", "spec_retry", "allow_retry", "retry_disabled"),
    [
        (None, "enabled", True, False),
        ("disabled", "enabled", False, True),
        ("enabled", "default", True, False),
    ],
)
async def test_executor_retry_resolution_matches_sync(
    retry: RetryOverride | None,
    spec_retry: RetryOverride,
    allow_retry: bool,
    retry_disabled: bool,
) -> None:
    spec: OperationSpec[object] = OperationSpec(
        name="items.list",
        method="GET",
        path="/items",
        retry_mode=spec_retry,
    )
    sync_transport = SyncRetryTransport()
    async_transport = BinaryTransport()

    OperationExecutor(sync_transport).execute(spec, retry=retry)
    await AsyncOperationExecutor(async_transport).execute(spec, retry=retry)

    assert sync_transport.contexts[0].allow_retry == allow_retry
    assert async_transport.contexts[0].allow_retry == allow_retry
    assert sync_transport.contexts[0].retry_disabled == retry_disabled
    assert async_transport.contexts[0].retry_disabled == retry_disabled
