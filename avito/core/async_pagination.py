"""Асинхронные абстракции пагинации для типизированных ответов SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from avito.core.types import JsonPage

type AsyncPageFetcher[ItemT] = Callable[[int | None, str | None], Awaitable[JsonPage[ItemT]]]


class AsyncPaginatedList[ItemT]:
    """Ленивый async-контейнер страниц без list API."""

    def __init__(
        self,
        fetch_page: AsyncPageFetcher[ItemT],
        *,
        start_page: int = 1,
        first_page: JsonPage[ItemT] | None = None,
    ) -> None:
        """Initialize AsyncPaginatedList."""
        self._fetch_page = fetch_page
        self._items: list[ItemT] = []
        self._known_total: int | None = None
        self._source_total: int | None = None
        self._next_page_number: int | None = start_page
        self._next_cursor: str | None = None
        self._exhausted = False
        self._active_iterator = False
        if first_page is not None:
            self._consume_page(first_page)

    def __aiter__(self) -> AsyncIterator[ItemT]:
        """Run the aiter helper."""
        if self._active_iterator:
            raise RuntimeError(
                "AsyncPaginatedList уже итерируется; используйте materialize() "
                "или создайте отдельный список."
            )
        self._active_iterator = True
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[ItemT]:
        """Iterate iterate."""
        index = 0
        try:
            while True:
                if index < len(self._items):
                    yield self._items[index]
                    index += 1
                    continue
                if self._exhausted:
                    return
                await self._load_next_page()
        finally:
            self._active_iterator = False

    async def materialize(self) -> list[ItemT]:
        """Явно загружает все страницы и возвращает snapshot-список."""

        while not self._exhausted:
            await self._load_next_page()
        return list(self._items)

    async def aload_until(self, index: int) -> None:
        """Загружает страницы, пока локально не появится элемент с указанным индексом."""

        while len(self._items) <= index and not self._exhausted:
            await self._load_next_page()

    @property
    def loaded_count(self) -> int:
        """Количество элементов, уже загруженных локально."""

        return len(self._items)

    @property
    def known_total(self) -> int | None:
        """Общее количество элементов, если API вернул достоверный total."""

        return self._known_total

    @property
    def source_total(self) -> int | None:
        """Общий total из API без ограничения локальным limit."""

        return self._source_total

    @property
    def is_materialized(self) -> bool:
        """Показывает, загружены ли все страницы коллекции."""

        return self._exhausted

    async def _load_next_page(self) -> None:
        """Load next page."""
        if self._exhausted:
            return
        page = await self._fetch_page(self._next_page_number, self._next_cursor)
        self._consume_page(page)

    def _consume_page(self, page: JsonPage[ItemT]) -> None:
        """Consume page."""
        self._items.extend(page.items)
        self._known_total = page.total
        if page.source_total is not None:
            self._source_total = page.source_total
        if not page.has_next:
            self._exhausted = True
            self._next_page_number = None
            self._next_cursor = None
            return
        if page.next_cursor is not None:
            self._next_cursor = page.next_cursor
            self._next_page_number = None
            return
        if page.page is not None:
            self._next_page_number = page.page + 1
            self._next_cursor = None
            return
        if self._next_page_number is not None:
            self._next_page_number += 1
            return
        self._exhausted = True
        self._next_cursor = None


class AsyncPaginator[ItemT]:
    """Обходит страницы API асинхронно и собирает типизированный результат."""

    def __init__(self, fetch_page: AsyncPageFetcher[ItemT]) -> None:
        """Initialize AsyncPaginator."""
        self._fetch_page = fetch_page

    async def iter_pages(self, *, start_page: int = 1) -> AsyncIterator[JsonPage[ItemT]]:
        """Итерирует страницы, пока API сообщает о продолжении списка."""

        page_number: int | None = start_page
        cursor: str | None = None
        while True:
            page = await self._fetch_page(page_number, cursor)
            yield page
            if not page.has_next:
                return
            if page.next_cursor is not None:
                cursor = page.next_cursor
                page_number = None
                continue
            if page_number is None:
                return
            page_number += 1

    async def collect(self, *, start_page: int = 1) -> list[ItemT]:
        """Собирает элементы всех страниц в один список."""

        items: list[ItemT] = []
        async for page in self.iter_pages(start_page=start_page):
            items.extend(page.items)
        return items

    def as_list(
        self,
        *,
        start_page: int = 1,
        first_page: JsonPage[ItemT] | None = None,
    ) -> AsyncPaginatedList[ItemT]:
        """Возвращает ленивый async-контейнер поверх последовательности страниц."""

        return AsyncPaginatedList(
            self._fetch_page,
            start_page=start_page,
            first_page=first_page,
        )


__all__ = ("AsyncPageFetcher", "AsyncPaginatedList", "AsyncPaginator")
