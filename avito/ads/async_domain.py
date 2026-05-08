"""Async-доменные объекты пакета ads."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from avito.ads.models import (
    AccountSpendings,
    AdAnalyticsGroupingInput,
    AdsActionResult,
    AdSpendingsGroupingInput,
    ApplyVasDirectRequest,
    ApplyVasPackageRequest,
    ApplyVasRequest,
    AutoloadFeesResult,
    AutoloadFieldsResult,
    AutoloadProfileSettings,
    AutoloadProfileUpdateRequest,
    AutoloadReportDetails,
    AutoloadReportItemsResult,
    AutoloadReportSummary,
    AutoloadTreeResult,
    CallsStatsRequest,
    CallsStatsResult,
    IdMappingResult,
    ItemAnalyticsRequest,
    ItemAnalyticsResult,
    ItemStatsRequest,
    ItemStatsResult,
    LegacyAutoloadReport,
    Listing,
    ListingStatus,
    SpendingsRequest,
    UpdatePriceRequest,
    UpdatePriceResult,
    UploadByUrlRequest,
    UploadResult,
    VasPricesRequest,
    VasPricesResult,
)
from avito.ads.operations import (
    APPLY_ITEM_VAS,
    APPLY_ITEM_VAS_PACKAGE,
    APPLY_VAS_DIRECT,
    GET_ACCOUNT_SPENDINGS,
    GET_AD_IDS_BY_AVITO_IDS,
    GET_ARCHIVE_LAST_COMPLETED_REPORT,
    GET_ARCHIVE_PROFILE,
    GET_ARCHIVE_REPORT,
    GET_AUTOLOAD_ITEMS_INFO,
    GET_AUTOLOAD_LAST_COMPLETED_REPORT,
    GET_AUTOLOAD_NODE_FIELDS,
    GET_AUTOLOAD_PROFILE,
    GET_AUTOLOAD_REPORT,
    GET_AUTOLOAD_REPORT_FEES,
    GET_AUTOLOAD_REPORT_ITEMS,
    GET_AUTOLOAD_TREE,
    GET_AVITO_IDS_BY_AD_IDS,
    GET_CALLS_STATS,
    GET_ITEM,
    GET_ITEM_ANALYTICS,
    GET_ITEM_STATS,
    GET_VAS_PRICES,
    LIST_AUTOLOAD_REPORTS,
    LIST_ITEMS,
    SAVE_ARCHIVE_PROFILE,
    SAVE_AUTOLOAD_PROFILE,
    UPDATE_PRICE,
    UPLOAD_BY_URL,
)
from avito.core import (
    ApiTimeouts,
    AsyncPaginatedList,
    AsyncPaginator,
    JsonPage,
    RetryOverride,
    ValidationError,
)
from avito.core.deprecation import deprecated_method
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import (
    DateInput,
    serialize_iso_date,
    validate_non_empty_string,
    validate_string_items,
)
from avito.promotion.models import PromotionActionResult, PromotionStatus


def _preview_result(
    *,
    action: str,
    target: dict[str, object],
    request_payload: dict[str, object],
) -> PromotionActionResult:
    return PromotionActionResult(
        action=action,
        target=target,
        status=PromotionStatus.PREVIEW,
        applied=False,
        request_payload=request_payload,
        details={"validated": True},
    )


StatsDate = DateInput


def _serialize_stats_date(value: StatsDate) -> str:
    return serialize_iso_date("date", value)


def _bounded_total(total: int | None, max_items: int | None) -> int | None:
    if max_items is None:
        return total
    if total is None:
        return None
    return min(total, max_items)


def _has_next_ads_page(
    *,
    page_item_count: int,
    collected_count: int,
    page_size: int,
    total: int | None,
    max_items: int | None,
    already_collected: int,
) -> bool:
    if page_item_count == 0 or page_size <= 0:
        return False
    if max_items is not None and already_collected + collected_count >= max_items:
        return False
    if total is not None:
        return already_collected + collected_count < min(total, max_items or total)
    return page_item_count >= page_size


@dataclass(slots=True, frozen=True)
class AsyncAd(AsyncDomainObject):
    """Доменный объект объявления."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "ad"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/core/v1/accounts/{user_id}/items/{item_id}",
        spec="Объявления.json",
        operation_id="getItemInfo",
        variant="async",
    )
    async def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> Listing:
        """Получает объявление по `item_id`.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `Listing` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        item_id, user_id = await self._require_ids()
        return await self._execute(
            GET_ITEM,
            path_params={"user_id": user_id, "item_id": item_id},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/core/v1/items",
        spec="Объявления.json",
        operation_id="getItemsInfo",
        variant="async",
    )
    async def list(
        self,
        *,
        status: ListingStatus | str | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        offset: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AsyncPaginatedList[Listing]:
        """Возвращает объявления аккаунта с ленивой пагинацией.

        Аргументы:
            status: фильтрует результат по статусу.
            limit: ограничивает размер возвращаемой выборки.
            page_size: задает размер страницы для ленивой пагинации.
            offset: задает смещение первой записи в выборке.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `AsyncPaginatedList[Listing]`; первая страница загружается при создании, следующие страницы - при итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._resolve_user_id(self.user_id)
        resolved_page_size = page_size or limit
        start_offset = offset or 0
        first_page_number = (
            start_offset // resolved_page_size + 1
            if resolved_page_size is not None and resolved_page_size > 0
            else 1
        )
        result = await self._execute(
            LIST_ITEMS,
            query={
                "user_id": user_id,
                "status": status,
                "per_page": resolved_page_size,
                "page": first_page_number,
            },
            timeout=timeout,
            retry=retry,
        )
        list_result = result
        page_size = (
            resolved_page_size
            if resolved_page_size and resolved_page_size > 0
            else len(list_result.items)
        )
        max_items = limit if limit is not None and limit >= 0 else None
        page_offset = start_offset % page_size if page_size > 0 else 0
        available_items = list_result.items[page_offset:]
        first_items = available_items[:max_items] if max_items is not None else available_items
        first_page = JsonPage(
            items=list(first_items),
            total=_bounded_total(list_result.total, max_items),
            source_total=list_result.total,
            page=first_page_number,
            per_page=page_size if page_size > 0 else None,
            has_next_page=_has_next_ads_page(
                page_item_count=len(list_result.items),
                collected_count=len(first_items),
                page_size=page_size,
                total=list_result.total,
                max_items=max_items,
                already_collected=0,
            ),
        )
        return AsyncPaginator(
            lambda page, cursor: self._fetch_ads_page(
                page=page,
                user_id=user_id,
                status=status,
                page_size=page_size,
                max_items=max_items,
                first_page_number=first_page_number,
            )
        ).as_list(start_page=first_page_number, first_page=first_page)

    @swagger_operation(
        "POST",
        "/core/v1/items/{item_id}/update_price",
        spec="Объявления.json",
        operation_id="updatePrice",
        variant="async",
        method_args={"price": "body.price"},
    )
    async def update_price(
        self,
        *,
        price: int | float,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> UpdatePriceResult:
        """Обновляет цену текущего объявления.

        Аргументы:
            price: новое значение цены.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `UpdatePriceResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        item_id = self._require_item_id()
        return await self._execute(
            UPDATE_PRICE,
            path_params={"item_id": item_id},
            request=UpdatePriceRequest(price=price),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    async def _fetch_ads_page(
        self,
        *,
        page: int | None,
        user_id: int | None,
        status: ListingStatus | str | None,
        page_size: int,
        max_items: int | None,
        first_page_number: int,
    ) -> JsonPage[Listing]:
        if page is None:
            raise ValidationError("Для операции требуется `page`.")

        already_collected = max(page - first_page_number, 0) * page_size
        remaining = max_items - already_collected if max_items is not None else None
        if remaining is not None and remaining <= 0:
            return JsonPage(items=[], total=max_items, page=page, per_page=page_size)
        result = await self._execute(
            LIST_ITEMS,
            query={
                "user_id": user_id,
                "status": status,
                "per_page": min(page_size, remaining) if remaining is not None else page_size,
                "page": page,
            },
        )
        list_result = result
        items = list_result.items[:remaining] if remaining is not None else list_result.items
        return JsonPage(
            items=list(items),
            total=_bounded_total(list_result.total, max_items),
            source_total=list_result.total,
            page=page,
            per_page=page_size,
            has_next_page=_has_next_ads_page(
                page_item_count=len(list_result.items),
                collected_count=len(items),
                page_size=page_size,
                total=list_result.total,
                max_items=max_items,
                already_collected=already_collected,
            ),
        )

    def _require_item_id(self) -> int:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return int(self.item_id)

    async def _require_ids(self) -> tuple[int, int]:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return int(self.item_id), await self._resolve_user_id(self.user_id)


@dataclass(slots=True, frozen=True)
class AsyncAdStats(AsyncDomainObject):
    """Доменный объект статистики объявлений."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "ad_stats"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/core/v1/accounts/{user_id}/calls/stats",
        spec="Объявления.json",
        operation_id="postCallsStats",
        variant="async",
        method_args={
            "date_from": "body.dateFrom",
            "date_to": "body.dateTo",
        },
    )
    async def get_calls_stats(
        self,
        *,
        date_from: StatsDate,
        date_to: StatsDate,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CallsStatsResult:
        """Получает статистику звонков.

        Аргументы:
            date_from: начальная дата или дата-время периода.
            date_to: конечная дата или дата-время периода.
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CallsStatsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._require_user_id()
        resolved_item_ids = item_ids or ([int(self.item_id)] if self.item_id is not None else [])
        return await self._execute(
            GET_CALLS_STATS,
            path_params={"user_id": user_id},
            request=CallsStatsRequest(
                item_ids=resolved_item_ids,
                date_from=_serialize_stats_date(date_from),
                date_to=_serialize_stats_date(date_to),
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/stats/v1/accounts/{user_id}/items",
        spec="Объявления.json",
        operation_id="itemStatsShallow",
        variant="async",
        method_args={
            "date_from": "body.dateFrom",
            "date_to": "body.dateTo",
        },
    )
    async def get_item_stats(
        self,
        *,
        date_from: StatsDate,
        date_to: StatsDate,
        item_ids: list[int] | None = None,
        fields: list[str] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ItemStatsResult:
        """Получает статистику по списку объявлений.

        Аргументы:
            date_from: начальная дата или дата-время периода.
            date_to: конечная дата или дата-время периода.
            item_ids: список идентификаторов объявлений.
            fields: список запрошенных полей.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ItemStatsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._require_user_id()
        resolved_item_ids = item_ids or ([int(self.item_id)] if self.item_id is not None else [])
        return await self._execute(
            GET_ITEM_STATS,
            path_params={"user_id": user_id},
            request=ItemStatsRequest(
                item_ids=resolved_item_ids,
                date_from=_serialize_stats_date(date_from),
                date_to=_serialize_stats_date(date_to),
                fields=fields or [],
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/stats/v2/accounts/{user_id}/items",
        spec="Объявления.json",
        operation_id="itemAnalytics",
        variant="async",
        method_args={
            "date_from": "body.dateFrom",
            "date_to": "body.dateTo",
            "metrics": "body.metrics",
            "grouping": "body.grouping",
            "limit": "body.limit",
            "offset": "body.offset",
        },
    )
    async def get_item_analytics(
        self,
        *,
        date_from: StatsDate,
        date_to: StatsDate,
        metrics: list[str],
        grouping: AdAnalyticsGroupingInput,
        limit: int,
        offset: int,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ItemAnalyticsResult:
        """Получает аналитику по профилю.

        Аргументы:
            date_from: начальная дата или дата-время периода.
            date_to: конечная дата или дата-время периода.
            metrics: список метрик статистики, которые нужно вернуть.
            grouping: группировка статистики или расходов.
            limit: максимальное количество элементов в ответе.
            offset: смещение выборки.
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ItemAnalyticsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._require_user_id()
        return await self._execute(
            GET_ITEM_ANALYTICS,
            path_params={"user_id": user_id},
            request=ItemAnalyticsRequest(
                date_from=_serialize_stats_date(date_from),
                date_to=_serialize_stats_date(date_to),
                metrics=metrics,
                grouping=grouping,
                limit=limit,
                offset=offset,
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/stats/v2/accounts/{user_id}/spendings",
        spec="Объявления.json",
        operation_id="accountSpendings",
        variant="async",
        method_args={
            "date_from": "body.dateFrom",
            "date_to": "body.dateTo",
            "spending_types": "body.spendingTypes",
            "grouping": "body.grouping",
        },
    )
    async def get_account_spendings(
        self,
        *,
        date_from: StatsDate,
        date_to: StatsDate,
        spending_types: list[str],
        grouping: AdSpendingsGroupingInput,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AccountSpendings:
        """Получает статистику расходов профиля.

        Аргументы:
            date_from: начальная дата или дата-время периода.
            date_to: конечная дата или дата-время периода.
            spending_types: типы расходов, включаемые в отчет.
            grouping: группировка статистики или расходов.
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AccountSpendings` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._require_user_id()
        resolved_item_ids = item_ids or ([int(self.item_id)] if self.item_id is not None else [])
        return await self._execute(
            GET_ACCOUNT_SPENDINGS,
            path_params={"user_id": user_id},
            request=SpendingsRequest(
                date_from=_serialize_stats_date(date_from),
                date_to=_serialize_stats_date(date_to),
                spending_types=spending_types,
                grouping=grouping,
                item_ids=resolved_item_ids,
            ),
            timeout=timeout,
            retry=retry,
        )

    async def _require_user_id(self) -> int:
        return await self._resolve_user_id(self.user_id)


@dataclass(slots=True, frozen=True)
class AsyncAdPromotion(AsyncDomainObject):
    """Доменный объект продвижения объявления."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "ad_promotion"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/core/v1/accounts/{user_id}/vas/prices",
        spec="Объявления.json",
        operation_id="vasPrices",
        variant="async",
        method_args={"item_ids": "body.item_ids"},
    )
    async def get_vas_prices(
        self,
        *,
        item_ids: list[int],
        location_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> VasPricesResult:
        """Получает цены продвижения и доступные услуги.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            location_id: идентификатор локации для расчета доступности или цены услуги.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `VasPricesResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        user_id = await self._require_user_id()
        return await self._execute(
            GET_VAS_PRICES,
            path_params={"user_id": user_id},
            request=VasPricesRequest(item_ids=item_ids, location_id=location_id),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "PUT",
        "/core/v1/accounts/{user_id}/items/{item_id}/vas",
        spec="Объявления.json",
        operation_id="putItemVas",
        variant="async",
        method_args={"vas_id": "body.vas_id"},
    )
    async def apply_vas(
        self,
        *,
        vas_id: str,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Применяет дополнительные услуги к объявлению.

        Аргументы:
            vas_id: идентификатор VAS-услуги.
            dry_run: если `True`, метод собирает payload и возвращает результат без вызова транспорта.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionActionResult` с типизированными данными ответа.

        Поведение:
            При `dry_run=True` payload строится без вызова транспорта.
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        item_id, user_id = await self._require_ids()
        validate_non_empty_string("vas_id", vas_id)
        request_payload = ApplyVasRequest(vas_id=vas_id).to_payload()
        target: dict[str, object] = {"item_id": item_id, "user_id": user_id}
        if dry_run:
            return _preview_result(
                action="apply_vas",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            APPLY_ITEM_VAS,
            path_params={"user_id": user_id, "item_id": item_id},
            request=ApplyVasRequest(vas_id=vas_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="apply_vas",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "PUT",
        "/core/v2/accounts/{user_id}/items/{item_id}/vas_packages",
        spec="Объявления.json",
        operation_id="putItemVasPackageV2",
        variant="async",
        method_args={"package_code": "body.package_id"},
    )
    async def apply_vas_package(
        self,
        *,
        package_code: str,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Применяет пакет дополнительных услуг.

        Аргументы:
            package_code: код пакета продвижения.
            dry_run: если `True`, метод собирает payload и возвращает результат без вызова транспорта.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionActionResult` с типизированными данными ответа.

        Поведение:
            При `dry_run=True` payload строится без вызова транспорта.
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        item_id, user_id = await self._require_ids()
        validate_non_empty_string("package_code", package_code)
        request_payload = ApplyVasPackageRequest(package_code=package_code).to_payload()
        target: dict[str, object] = {"item_id": item_id, "user_id": user_id}
        if dry_run:
            return _preview_result(
                action="apply_vas_package",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            APPLY_ITEM_VAS_PACKAGE,
            path_params={"user_id": user_id, "item_id": item_id},
            request=ApplyVasPackageRequest(package_code=package_code),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="apply_vas_package",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "PUT",
        "/core/v2/items/{item_id}/vas",
        spec="Объявления.json",
        operation_id="applyVas",
        variant="async",
        method_args={"slugs": "body.slugs"},
    )
    async def apply_vas_direct(
        self,
        *,
        slugs: list[str],
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Применяет услуги продвижения через прямой v2 endpoint.

        Аргументы:
            slugs: slug-идентификаторы узлов дерева категорий.
            dry_run: если `True`, метод собирает payload и возвращает результат без вызова транспорта.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionActionResult` с типизированными данными ответа.

        Поведение:
            При `dry_run=True` payload строится без вызова транспорта.
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        item_id = self._require_item_id()
        validate_string_items("slugs", slugs)
        request_payload = ApplyVasDirectRequest(slugs=slugs).to_payload()
        target: dict[str, object] = {"item_id": item_id}
        if dry_run:
            return _preview_result(
                action="apply_vas_direct",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            APPLY_VAS_DIRECT,
            path_params={"item_id": item_id},
            request=ApplyVasDirectRequest(slugs=slugs),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="apply_vas_direct",
            target=target,
            request_payload=request_payload,
        )

    def _require_item_id(self) -> int:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return int(self.item_id)

    async def _require_user_id(self) -> int:
        return await self._resolve_user_id(self.user_id)

    async def _require_ids(self) -> tuple[int, int]:
        return self._require_item_id(), await self._require_user_id()


@dataclass(slots=True, frozen=True)
class AsyncAutoloadProfile(AsyncDomainObject):
    """Доменный объект профиля автозагрузки."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "autoload_profile"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/autoload/v2/profile",
        spec="Автозагрузка.json",
        operation_id="getProfileV2",
        variant="async",
    )
    async def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadProfileSettings:
        """Получает профиль автозагрузки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadProfileSettings` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_AUTOLOAD_PROFILE, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/autoload/v2/profile",
        spec="Автозагрузка.json",
        operation_id="createOrUpdateProfileV2",
        variant="async",
        method_args={
            "is_enabled": "body.autoload_enabled",
            "feed_url": "body.feeds_data",
            "report_email": "body.report_email",
            "schedule_rate": "body.schedule[].rate",
        },
    )
    async def save(
        self,
        *,
        is_enabled: bool,
        feed_url: str,
        report_email: str,
        schedule_rate: int,
        schedule_weekdays: list[int] | None = None,
        schedule_time_slots: list[int] | None = None,
        feed_name: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AdsActionResult:
        """Сохраняет профиль автозагрузки.

        Аргументы:
            is_enabled: включает или отключает профиль автозагрузки.
            feed_url: URL фида автозагрузки.
            report_email: email для отправки отчетов автозагрузки.
            schedule_rate: ставка расписания продвижения.
            schedule_weekdays: дни недели для расписания; если не передано, используется полный недельный набор.
            schedule_time_slots: временные интервалы расписания; если не передано, используется первый слот.
            feed_name: имя фида автозагрузки.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AdsActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SAVE_AUTOLOAD_PROFILE,
            request=AutoloadProfileUpdateRequest(
                is_enabled=is_enabled,
                report_email=report_email,
                schedule_rate=schedule_rate,
                schedule_weekdays=schedule_weekdays or [0, 1, 2, 3, 4, 5, 6],
                schedule_time_slots=schedule_time_slots or [0],
                feed_name=feed_name,
                feed_url=feed_url,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoload/v1/upload",
        spec="Автозагрузка.json",
        operation_id="upload",
        variant="async",
        method_args={"url": "constant.url"},
    )
    async def upload_by_url(
        self,
        *,
        url: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> UploadResult:
        """Загружает файл по ссылке.

        Аргументы:
            url: URL источника данных.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `UploadResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UPLOAD_BY_URL,
            request=UploadByUrlRequest(url=url),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v1/user-docs/tree",
        spec="Автозагрузка.json",
        operation_id="userDocsTree",
        variant="async",
    )
    async def get_tree(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadTreeResult:
        """Получает дерево категорий.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadTreeResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_AUTOLOAD_TREE, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/autoload/v1/user-docs/node/{node_slug}/fields",
        spec="Автозагрузка.json",
        operation_id="userDocsNodeFields",
        variant="async",
        method_args={"node_slug": "path.node_slug"},
    )
    async def get_node_fields(
        self,
        *,
        node_slug: str,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutoloadFieldsResult:
        """Получает поля категории.

        Аргументы:
            node_slug: slug узла дерева категорий.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadFieldsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AUTOLOAD_NODE_FIELDS,
            path_params={"node_slug": node_slug},
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncAutoloadReport(AsyncDomainObject):
    """Доменный объект отчета автозагрузки."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "autoload_report"
    __sdk_factory_args__ = {"report_id": "path.report_id"}

    report_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/autoload/v3/reports/{report_id}",
        spec="Автозагрузка.json",
        operation_id="getReportByIdV3",
        variant="async",
    )
    async def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadReportDetails:
        """Получает конкретный отчет v3.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadReportDetails` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        report_id = self._require_report_id()
        return await self._execute(
            GET_AUTOLOAD_REPORT,
            path_params={"report_id": report_id},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/reports",
        spec="Автозагрузка.json",
        operation_id="getReportsV2",
        variant="async",
    )
    async def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AsyncPaginatedList[AutoloadReportSummary]:
        """Возвращает отчеты Автозагрузки с ленивой пагинацией.

        Аргументы:
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `AsyncPaginatedList[AutoloadReportSummary]`; первая страница загружается при создании, следующие страницы - при итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        page_size = limit or 25
        base_offset = offset or 0

        async def fetch_page(
            page: int | None, _cursor: str | None
        ) -> JsonPage[AutoloadReportSummary]:
            current_page = page or 1
            current_offset = base_offset + (current_page - 1) * page_size
            result = await self._execute(
                LIST_AUTOLOAD_REPORTS,
                query={"limit": page_size, "offset": current_offset},
                timeout=timeout,
                retry=retry,
            )
            reports = result
            return JsonPage(
                items=reports.items,
                total=reports.total,
                page=current_page,
                per_page=page_size,
            )

        return AsyncPaginator(fetch_page).as_list(first_page=await fetch_page(1, None))

    @swagger_operation(
        "GET",
        "/autoload/v3/reports/last_completed_report",
        spec="Автозагрузка.json",
        operation_id="getLastCompletedReportV3",
        variant="async",
    )
    async def get_last_completed(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadReportDetails:
        """Получает последний завершенный отчет.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadReportDetails` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_AUTOLOAD_LAST_COMPLETED_REPORT, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/autoload/v2/reports/{report_id}/items",
        spec="Автозагрузка.json",
        operation_id="getReportItemsById",
        variant="async",
    )
    async def get_items(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadReportItemsResult:
        """Возвращает позиции выбранного отчета Автозагрузки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadReportItemsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        report_id = self._require_report_id()
        return await self._execute(
            GET_AUTOLOAD_REPORT_ITEMS,
            path_params={"report_id": report_id},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/reports/{report_id}/items/fees",
        spec="Автозагрузка.json",
        operation_id="getReportItemsFeesById",
        variant="async",
    )
    async def get_fees(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadFeesResult:
        """Получает списания по объявлениям отчета.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadFeesResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        report_id = self._require_report_id()
        return await self._execute(
            GET_AUTOLOAD_REPORT_FEES,
            path_params={"report_id": report_id},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/items/ad_ids",
        spec="Автозагрузка.json",
        operation_id="getAdIdsByAvitoIds",
        variant="async",
        method_args={"avito_ids": "query.query"},
    )
    async def get_ad_ids_by_avito_ids(
        self,
        *,
        avito_ids: Sequence[int],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> IdMappingResult:
        """Получает ad ids по avito ids.

        Аргументы:
            avito_ids: список идентификаторов объявлений на Avito.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `IdMappingResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AD_IDS_BY_AVITO_IDS,
            query={"query": ",".join(str(item) for item in avito_ids)},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/items/avito_ids",
        spec="Автозагрузка.json",
        operation_id="getAvitoIdsByAdIds",
        variant="async",
        method_args={"ad_ids": "query.query"},
    )
    async def get_avito_ids_by_ad_ids(
        self,
        *,
        ad_ids: Sequence[int],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> IdMappingResult:
        """Получает avito ids по ad ids.

        Аргументы:
            ad_ids: список внешних идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `IdMappingResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AVITO_IDS_BY_AD_IDS,
            query={"query": ",".join(str(item) for item in ad_ids)},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/reports/items",
        spec="Автозагрузка.json",
        operation_id="getAutoloadItemsInfoV2",
        variant="async",
        method_args={"item_ids": "query.query"},
    )
    async def get_items_info(
        self,
        *,
        item_ids: Sequence[int],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutoloadReportItemsResult:
        """Получает информацию по объявлениям автозагрузки.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadReportItemsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AUTOLOAD_ITEMS_INFO,
            query={"query": ",".join(str(item) for item in item_ids)},
            timeout=timeout,
            retry=retry,
        )

    def _require_report_id(self) -> int:
        if self.report_id is None:
            raise ValidationError("Для операции требуется `report_id`.")
        return int(self.report_id)


@dataclass(slots=True, frozen=True)
class AsyncAutoloadArchive(AsyncDomainObject):
    """Доменный объект архивных операций автозагрузки."""

    __swagger_domain__ = "ads"
    __sdk_factory__ = "autoload_archive"
    __sdk_factory_args__ = {"report_id": "path.report_id"}

    report_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/autoload/v1/profile",
        spec="Автозагрузка.json",
        operation_id="getProfile",
        variant="async",
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncAutoloadArchive.get_profile",
        replacement="autoload_profile().get",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_profile(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutoloadProfileSettings:
        """Получает архивный профиль автозагрузки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutoloadProfileSettings` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_ARCHIVE_PROFILE, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/autoload/v1/profile",
        spec="Автозагрузка.json",
        operation_id="createOrUpdateProfile",
        variant="async",
        deprecated=True,
        legacy=True,
        method_args={
            "is_enabled": "body.autoload_enabled",
            "upload_url": "body.upload_url",
            "report_email": "body.report_email",
            "schedule_rate": "body.schedule[].rate",
        },
    )
    @deprecated_method(
        symbol="AsyncAutoloadArchive.save_profile",
        replacement="autoload_profile().save",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def save_profile(
        self,
        *,
        is_enabled: bool,
        upload_url: str,
        report_email: str,
        schedule_rate: int,
        schedule_weekdays: list[int] | None = None,
        schedule_time_slots: list[int] | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AdsActionResult:
        """Сохраняет архивный профиль автозагрузки.

        Аргументы:
            is_enabled: включает или отключает профиль автозагрузки.
            upload_url: URL фида автозагрузки.
            report_email: email для отправки отчетов автозагрузки.
            schedule_rate: ставка расписания продвижения.
            schedule_weekdays: дни недели для расписания; если не передано, используется полный недельный набор.
            schedule_time_slots: временные интервалы расписания; если не передано, используется первый слот.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AdsActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SAVE_ARCHIVE_PROFILE,
            request=AutoloadProfileUpdateRequest(
                is_enabled=is_enabled,
                report_email=report_email,
                schedule_rate=schedule_rate,
                schedule_weekdays=schedule_weekdays or [0, 1, 2, 3, 4, 5, 6],
                schedule_time_slots=schedule_time_slots or [0],
                upload_url=upload_url,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoload/v2/reports/last_completed_report",
        spec="Автозагрузка.json",
        operation_id="getLastCompletedReport",
        variant="async",
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncAutoloadArchive.get_last_completed_report",
        replacement="autoload_report().get_last_completed",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_last_completed_report(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> LegacyAutoloadReport:
        """Получает архивную статистику по последней выгрузке.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `LegacyAutoloadReport` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_ARCHIVE_LAST_COMPLETED_REPORT, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/autoload/v2/reports/{report_id}",
        spec="Автозагрузка.json",
        operation_id="getReportByIdV2",
        variant="async",
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncAutoloadArchive.get_report",
        replacement="autoload_report().get",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_report(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> LegacyAutoloadReport:
        """Получает архивную статистику по конкретной выгрузке.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `LegacyAutoloadReport` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        report_id = self._require_report_id()
        return await self._execute(
            GET_ARCHIVE_REPORT,
            path_params={"report_id": report_id},
            timeout=timeout,
            retry=retry,
        )

    def _require_report_id(self) -> int:
        if self.report_id is None:
            raise ValidationError("Для операции требуется `report_id`.")
        return int(self.report_id)


__all__ = (
    "AsyncAd",
    "AsyncAdPromotion",
    "AsyncAdStats",
    "AsyncAutoloadArchive",
    "AsyncAutoloadProfile",
    "AsyncAutoloadReport",
)
