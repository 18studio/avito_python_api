from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

import pytest

from avito.core.async_pagination import AsyncPaginatedList
from avito.core.types import JsonPage


@pytest.mark.asyncio
async def test_async_paginated_list_materializes_pages() -> None:
    pages = {
        1: JsonPage(items=[1, 2], page=1, per_page=2, total=3),
        2: JsonPage(items=[3], page=2, per_page=2, total=3),
    }

    async def fetch(page: int | None, cursor: str | None) -> JsonPage[int]:
        assert cursor is None
        return pages[page or 1]

    items = AsyncPaginatedList(fetch, first_page=pages[1])

    assert items.loaded_count == 2
    assert await items.materialize() == [1, 2, 3]
    assert items.is_materialized is True


@pytest.mark.asyncio
async def test_concurrent_aiter_raises_runtime_error() -> None:
    async def fetch(page: int | None, cursor: str | None) -> JsonPage[int]:
        return JsonPage(items=[1], page=page, per_page=1, total=1)

    items = AsyncPaginatedList(fetch)
    iterator = items.__aiter__()

    with pytest.raises(RuntimeError):
        items.__aiter__()

    assert await anext(iterator) == 1
    await cast(AsyncGenerator[int, None], iterator).aclose()
