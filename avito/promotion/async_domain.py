"""Async-доменные объекты пакета promotion."""

from __future__ import annotations

import builtins
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import (
    validate_non_empty,
    validate_non_empty_string,
    validate_positive_int,
)
from avito.promotion.models import (
    AutostrategyBudget,
    AutostrategyStat,
    BbipForecastsResult,
    BbipItem,
    BbipSuggestsResult,
    CampaignActionResult,
    CampaignDetailsResult,
    CampaignListFilter,
    CampaignOrderBy,
    CampaignsResult,
    CampaignType,
    CampaignUpdateTimeFilter,
    CancelTrxPromotionRequest,
    CpaAuctionBidInput,
    CpaAuctionBidsResult,
    CreateAutostrategyBudgetRequest,
    CreateAutostrategyCampaignRequest,
    CreateBbipForecastsRequest,
    CreateBbipOrderRequest,
    CreateBbipSuggestsRequest,
    CreateItemBid,
    CreateItemBidsRequest,
    CreateTrxPromotionApplyRequest,
    DeletePromotionRequest,
    GetAutostrategyCampaignInfoRequest,
    GetAutostrategyStatRequest,
    GetPromotionOrderStatusRequest,
    GetPromotionsByItemIdsRequest,
    GetTrxCommissionsRequest,
    ListAutostrategyCampaignsRequest,
    ListPromotionOrdersRequest,
    ListPromotionServicesRequest,
    PromotionActionResult,
    PromotionOrdersResult,
    PromotionOrderStatusResult,
    PromotionServiceDictionary,
    PromotionServicesResult,
    PromotionStatus,
    StopAutostrategyCampaignRequest,
    TargetActionBudgetType,
    TargetActionGetBidsResult,
    TargetActionPromotionsByItemIdsResult,
    TrxCommissionsResult,
    TrxItem,
    UpdateAutoBidRequest,
    UpdateAutostrategyCampaignRequest,
    UpdateManualBidRequest,
)
from avito.promotion.operations import (
    APPLY_TRX,
    CANCEL_TRX,
    CREATE_AUTOSTRATEGY_BUDGET,
    CREATE_AUTOSTRATEGY_CAMPAIGN,
    CREATE_BBIP_ORDER,
    CREATE_CPA_AUCTION_BIDS,
    DELETE_AUTOSTRATEGY_CAMPAIGN,
    DELETE_TARGET_ACTION_PROMOTION,
    GET_AUTOSTRATEGY_CAMPAIGN,
    GET_AUTOSTRATEGY_STAT,
    GET_BBIP_FORECASTS,
    GET_BBIP_SUGGESTS,
    GET_CPA_AUCTION_BIDS,
    GET_ORDER_STATUS,
    GET_SERVICE_DICTIONARY,
    GET_TARGET_ACTION_BIDS,
    GET_TARGET_ACTION_PROMOTIONS,
    GET_TRX_COMMISSIONS,
    LIST_AUTOSTRATEGY_CAMPAIGNS,
    LIST_ORDERS,
    LIST_SERVICES,
    TRX_HEADERS,
    UPDATE_AUTOSTRATEGY_CAMPAIGN,
    UPDATE_TARGET_ACTION_AUTO,
    UPDATE_TARGET_ACTION_MANUAL,
)


def _preview_result(
    *,
    action: str,
    target: Mapping[str, object],
    request_payload: Mapping[str, object],
) -> PromotionActionResult:
    return PromotionActionResult(
        action=action,
        target=dict(target),
        status=PromotionStatus.PREVIEW,
        applied=False,
        request_payload=dict(request_payload),
        details={"validated": True},
    )


def _validate_optional_datetime(name: str, value: datetime | None) -> None:
    if value is not None and not isinstance(value, datetime):
        raise ValidationError(f"`{name}` должен быть datetime.")


@dataclass(slots=True, frozen=True)
class AsyncPromotionOrder(AsyncDomainObject):
    """Доменный объект заявок и словарей promotion API."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "promotion_order"
    __sdk_factory_args__ = {"order_id": "path.order_id"}

    order_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/dict",
        spec="Продвижение.json",
        operation_id="get_dict_of_services_v1",
        variant="async",
    )
    async def get_service_dictionary(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> PromotionServiceDictionary:
        """Получает словарь услуг продвижения.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionServiceDictionary` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_SERVICE_DICTIONARY, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/get",
        spec="Продвижение.json",
        operation_id="get_services_by_items_v1",
        method_args={"item_ids": "body.item_ids"},
        variant="async",
    )
    async def list_services(
        self,
        *,
        item_ids: list[int],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionServicesResult:
        """Возвращает доступные услуги продвижения для объявлений.

        Аргументы:
            item_ids: передает идентификаторы объявлений или товаров.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionServicesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_SERVICES,
            request=ListPromotionServicesRequest(item_ids=item_ids),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/orders/get",
        spec="Продвижение.json",
        operation_id="list_orders_by_user_v1",
        variant="async",
    )
    async def list_orders(
        self,
        *,
        item_ids: list[int] | None = None,
        order_ids: list[str] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionOrdersResult:
        """Возвращает заказы продвижения по объявлениям или идентификаторам заказов.

        Аргументы:
            item_ids: передает идентификаторы объявлений или товаров.
            order_ids: передает идентификаторы заказов.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionOrdersResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_ORDERS,
            request=ListPromotionOrdersRequest(item_ids=item_ids, order_ids=order_ids),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/orders/status",
        spec="Продвижение.json",
        operation_id="get_order_status_v1",
        variant="async",
    )
    async def get_order_status(
        self,
        *,
        order_ids: list[str] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionOrderStatusResult:
        """Получает статусы заявок на продвижение.

        Аргументы:
            order_ids: идентификаторы заказов продвижения.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionOrderStatusResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_order_ids = order_ids or (
            [str(self.order_id)] if self.order_id is not None else []
        )
        if not resolved_order_ids:
            raise ValidationError("Для операции требуется хотя бы один `order_id`.")
        return await self._execute(
            GET_ORDER_STATUS,
            request=GetPromotionOrderStatusRequest(order_ids=resolved_order_ids),
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncBbipPromotion(AsyncDomainObject):
    """Доменный объект BBIP-продвижения."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "bbip_promotion"
    __sdk_factory_args__ = {"item_id": "path.item_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/bbip/forecasts/get",
        spec="Продвижение.json",
        operation_id="get_bbip_forecasts_by_items_v1",
        method_args={"items": "body.items"},
        variant="async",
    )
    async def get_forecasts(
        self,
        *,
        items: list[BbipItem],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> BbipForecastsResult:
        """Получает прогнозы BBIP.

        Аргументы:
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `BbipForecastsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_BBIP_FORECASTS,
            request=CreateBbipForecastsRequest(items=list(items)),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "PUT",
        "/promotion/v1/items/services/bbip/orders/create",
        spec="Продвижение.json",
        operation_id="create_bbip_order_for_items_v1",
        method_args={"items": "body.items"},
        variant="async",
    )
    async def create_order(
        self,
        *,
        items: list[BbipItem],
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Подключает BBIP-продвижение.

        Аргументы:
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
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

        validate_non_empty("items", items)
        for index, item in enumerate(items):
            validate_positive_int(f"items[{index}].item_id", item.item_id)
            validate_positive_int(f"items[{index}].duration", item.duration)
            validate_positive_int(f"items[{index}].price", item.price)
            validate_positive_int(f"items[{index}].old_price", item.old_price)
        bbip_items = list(items)
        request_payload = CreateBbipOrderRequest(items=bbip_items).to_payload()
        target: dict[str, object] = {"item_ids": [item.item_id for item in items]}
        if dry_run:
            return _preview_result(
                action="create_order",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            CREATE_BBIP_ORDER,
            request=CreateBbipOrderRequest(items=bbip_items),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="create_order",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "POST",
        "/promotion/v1/items/services/bbip/suggests/get",
        spec="Продвижение.json",
        operation_id="get_bbip_suggests_by_items_v1",
        variant="async",
    )
    async def get_suggests(
        self,
        *,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> BbipSuggestsResult:
        """Получает варианты бюджета BBIP.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `BbipSuggestsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_item_ids = item_ids or self._resource_item_ids()
        return await self._execute(
            GET_BBIP_SUGGESTS,
            request=CreateBbipSuggestsRequest(item_ids=resolved_item_ids),
            timeout=timeout,
            retry=retry,
        )

    def _resource_item_ids(self) -> list[int]:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id` или список `item_ids`.")
        return [int(self.item_id)]


@dataclass(slots=True, frozen=True)
class AsyncTrxPromotion(AsyncDomainObject):
    """Доменный объект TrxPromo."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "trx_promotion"
    __sdk_factory_args__ = {"item_id": "path.item_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/trx-promo/1/apply",
        spec="TrxPromo.json",
        operation_id="api_trx_promo_open_api_apply",
        method_args={"items": "body.items"},
        variant="async",
    )
    async def apply(
        self,
        *,
        items: list[TrxItem],
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Запускает TrxPromo.

        Аргументы:
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
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

        validate_non_empty("items", items)
        for index, item in enumerate(items):
            validate_positive_int(f"items[{index}].item_id", item.item_id)
            validate_positive_int(f"items[{index}].commission", item.commission)
            if not isinstance(item.date_from, datetime):
                raise ValidationError(f"items[{index}].date_from должен быть datetime.")
        trx_items = list(items)
        request_payload = CreateTrxPromotionApplyRequest(items=trx_items).to_payload()
        target: dict[str, object] = {"item_ids": [item.item_id for item in items]}
        if dry_run:
            return _preview_result(action="apply", target=target, request_payload=request_payload)
        payload = await self._execute(
            APPLY_TRX,
            request=CreateTrxPromotionApplyRequest(items=trx_items),
            headers=TRX_HEADERS,
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="apply",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "POST",
        "/trx-promo/1/cancel",
        spec="TrxPromo.json",
        operation_id="api_trx_promo_open_api_cancel",
        method_args={"item_ids": "body.itemIDs"},
        variant="async",
    )
    async def delete(
        self,
        *,
        item_ids: list[int] | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Останавливает TrxPromo.

        Аргументы:
            item_ids: список идентификаторов объявлений.
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

        resolved_item_ids = item_ids or self._resource_item_ids()
        validate_non_empty("item_ids", resolved_item_ids)
        request_payload = CancelTrxPromotionRequest(item_ids=resolved_item_ids).to_payload()
        target = {"item_ids": list(resolved_item_ids)}
        if dry_run:
            return _preview_result(action="delete", target=target, request_payload=request_payload)
        payload = await self._execute(
            CANCEL_TRX,
            request=CancelTrxPromotionRequest(item_ids=resolved_item_ids),
            headers=TRX_HEADERS,
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="delete",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "GET",
        "/trx-promo/1/commissions",
        spec="TrxPromo.json",
        operation_id="api_trx_promo_open_api_commissions",
        method_args={"item_ids": "body.item_ids"},
        variant="async",
    )
    async def get_commissions(
        self,
        *,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> TrxCommissionsResult:
        """Получает доступные комиссии TrxPromo.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `TrxCommissionsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_item_ids = item_ids or self._resource_item_ids()
        return await self._execute(
            GET_TRX_COMMISSIONS,
            request=GetTrxCommissionsRequest(item_ids=resolved_item_ids),
            headers=TRX_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    def _resource_item_ids(self) -> list[int]:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id` или список `item_ids`.")
        return [int(self.item_id)]


@dataclass(slots=True, frozen=True)
class AsyncCpaAuction(AsyncDomainObject):
    """Доменный объект CPA-аукциона."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "cpa_auction"
    __sdk_factory_args__ = {"item_id": "path.item_id"}

    item_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/auction/1/bids",
        spec="CPA-аукцион.json",
        operation_id="getUserBids",
        variant="async",
    )
    async def get_user_bids(
        self,
        *,
        from_item_id: int | None = None,
        batch_size: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaAuctionBidsResult:
        """Получает действующие и доступные ставки.

        Аргументы:
            from_item_id: идентификатор объявления, с которого начинается выборка.
            batch_size: размер пакетной выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaAuctionBidsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_AUCTION_BIDS,
            query={"fromItemID": from_item_id, "batchSize": batch_size},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/auction/1/bids",
        spec="CPA-аукцион.json",
        operation_id="saveItemBids",
        method_args={"items": "body.items"},
        variant="async",
    )
    async def create_item_bids(
        self,
        *,
        items: list[CpaAuctionBidInput],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Сохраняет новые ставки по объявлениям.

        Аргументы:
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `PromotionActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        bids = [CreateItemBid(item_id=item.item_id, price_penny=item.price_penny) for item in items]
        request = CreateItemBidsRequest(items=bids)
        payload = await self._execute(
            CREATE_CPA_AUCTION_BIDS,
            request=request,
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="create_item_bids",
            target={"item_ids": [item.item_id for item in items]},
            request_payload=request.to_payload(),
        )


@dataclass(slots=True, frozen=True)
class AsyncTargetActionPricing(AsyncDomainObject):
    """Доменный объект цены целевого действия."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "target_action_pricing"
    __sdk_factory_args__ = {"item_id": "path.item_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/cpxpromo/1/getBids/{itemId}",
        spec="Настройкаценыцелевогодействия.json",
        operation_id="getBids",
        variant="async",
    )
    async def get_bids(
        self,
        *,
        item_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> TargetActionGetBidsResult:
        """Получает детализированные цены и бюджеты.

        Аргументы:
            item_id: идентификатор объявления.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `TargetActionGetBidsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_TARGET_ACTION_BIDS,
            path_params={"itemId": item_id or self._require_item_id()},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpxpromo/1/getPromotionsByItemIds",
        spec="Настройкаценыцелевогодействия.json",
        operation_id="getPromotionsByItemIds",
        variant="async",
    )
    async def get_promotions_by_item_ids(
        self,
        *,
        item_ids: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> TargetActionPromotionsByItemIdsResult:
        """Получает текущие настройки по нескольким объявлениям.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `TargetActionPromotionsByItemIdsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_item_ids = item_ids or [self._require_item_id()]
        return await self._execute(
            GET_TARGET_ACTION_PROMOTIONS,
            request=GetPromotionsByItemIdsRequest(item_ids=resolved_item_ids),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpxpromo/1/remove",
        spec="Настройкаценыцелевогодействия.json",
        operation_id="removePromotion",
        variant="async",
    )
    async def delete(
        self,
        *,
        item_id: int | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Останавливает продвижение.

        Аргументы:
            item_id: идентификатор объявления.
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

        resolved_item_id = item_id or self._require_item_id()
        validate_positive_int("item_id", resolved_item_id)
        request_payload = DeletePromotionRequest(item_id=resolved_item_id).to_payload()
        target = {"item_id": resolved_item_id}
        if dry_run:
            return _preview_result(action="delete", target=target, request_payload=request_payload)
        payload = await self._execute(
            DELETE_TARGET_ACTION_PROMOTION,
            request=DeletePromotionRequest(item_id=resolved_item_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="delete",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "POST",
        "/cpxpromo/1/setAuto",
        spec="Настройкаценыцелевогодействия.json",
        operation_id="saveAutoBid",
        method_args={
            "action_type_id": "body.action_type_id",
            "budget_penny": "body.budget_penny",
            "budget_type": "body.budget_type",
        },
        variant="async",
    )
    async def update_auto(
        self,
        *,
        action_type_id: int,
        budget_penny: int,
        budget_type: TargetActionBudgetType | str,
        item_id: int | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Применяет автоматическую настройку.

        Аргументы:
            action_type_id: идентификатор целевого действия.
            budget_penny: бюджет в копейках.
            budget_type: тип бюджета кампании.
            item_id: идентификатор объявления.
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

        resolved_item_id = item_id or self._require_item_id()
        validate_positive_int("item_id", resolved_item_id)
        validate_positive_int("action_type_id", action_type_id)
        validate_positive_int("budget_penny", budget_penny)
        validate_non_empty_string("budget_type", budget_type)
        request_payload = UpdateAutoBidRequest(
            item_id=resolved_item_id,
            action_type_id=action_type_id,
            budget_penny=budget_penny,
            budget_type=budget_type,
        ).to_payload()
        target = {"item_id": resolved_item_id}
        if dry_run:
            return _preview_result(
                action="update_auto",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            UPDATE_TARGET_ACTION_AUTO,
            request=UpdateAutoBidRequest(
                item_id=resolved_item_id,
                action_type_id=action_type_id,
                budget_penny=budget_penny,
                budget_type=budget_type,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="update_auto",
            target=target,
            request_payload=request_payload,
        )

    @swagger_operation(
        "POST",
        "/cpxpromo/1/setManual",
        spec="Настройкаценыцелевогодействия.json",
        operation_id="saveManualBid",
        method_args={"action_type_id": "body.action_type_id", "bid_penny": "body.bid_penny"},
        variant="async",
    )
    async def update_manual(
        self,
        *,
        action_type_id: int,
        bid_penny: int,
        limit_penny: int | None = None,
        item_id: int | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PromotionActionResult:
        """Применяет ручную настройку.

        Аргументы:
            action_type_id: идентификатор целевого действия.
            bid_penny: ставка в копейках.
            limit_penny: лимит расходов в копейках.
            item_id: идентификатор объявления.
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

        resolved_item_id = item_id or self._require_item_id()
        validate_positive_int("item_id", resolved_item_id)
        validate_positive_int("action_type_id", action_type_id)
        validate_positive_int("bid_penny", bid_penny)
        if limit_penny is not None:
            validate_positive_int("limit_penny", limit_penny)
        request_payload = UpdateManualBidRequest(
            item_id=resolved_item_id,
            action_type_id=action_type_id,
            bid_penny=bid_penny,
            limit_penny=limit_penny,
        ).to_payload()
        target = {"item_id": resolved_item_id}
        if dry_run:
            return _preview_result(
                action="update_manual",
                target=target,
                request_payload=request_payload,
            )
        payload = await self._execute(
            UPDATE_TARGET_ACTION_MANUAL,
            request=UpdateManualBidRequest(
                item_id=resolved_item_id,
                action_type_id=action_type_id,
                bid_penny=bid_penny,
                limit_penny=limit_penny,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )
        return PromotionActionResult.from_action_payload(
            payload,
            action="update_manual",
            target=target,
            request_payload=request_payload,
        )

    def _require_item_id(self) -> int:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return int(self.item_id)


@dataclass(slots=True, frozen=True)
class AsyncAutostrategyCampaign(AsyncDomainObject):
    """Доменный объект кампаний автостратегии."""

    __swagger_domain__ = "promotion"
    __sdk_factory__ = "autostrategy_campaign"
    __sdk_factory_args__ = {"campaign_id": "path.campaign_id"}

    campaign_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/autostrategy/v1/budget",
        spec="Автостратегия.json",
        operation_id="getAutostrategyBudget",
        method_args={"campaign_type": "body.campaign_type"},
        variant="async",
    )
    async def create_budget(
        self,
        *,
        campaign_type: CampaignType | str,
        start_time: datetime | None = None,
        finish_time: datetime | None = None,
        items: list[int] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutostrategyBudget:
        """Рассчитывает бюджет кампании.

        Аргументы:
            campaign_type: тип автостратегии или рекламной кампании.
            start_time: дата и время начала кампании.
            finish_time: дата и время окончания кампании.
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutostrategyBudget` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        _validate_optional_datetime("start_time", start_time)
        _validate_optional_datetime("finish_time", finish_time)
        return await self._execute(
            CREATE_AUTOSTRATEGY_BUDGET,
            request=CreateAutostrategyBudgetRequest(
                campaign_type=campaign_type,
                start_time=start_time,
                finish_time=finish_time,
                items=items,
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/campaign/create",
        spec="Автостратегия.json",
        operation_id="createAutostrategyCampaign",
        method_args={"campaign_type": "body.campaign_type", "title": "body.title"},
        variant="async",
    )
    async def create(
        self,
        *,
        campaign_type: CampaignType | str,
        title: str,
        budget: int | None = None,
        budget_bonus: int | None = None,
        budget_real: int | None = None,
        calc_id: int | None = None,
        description: str | None = None,
        finish_time: datetime | None = None,
        items: list[int] | None = None,
        start_time: datetime | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CampaignActionResult:
        """Создает новую кампанию.

        Аргументы:
            campaign_type: тип автостратегии или рекламной кампании.
            title: название кампании.
            budget: бюджет кампании.
            budget_bonus: бонусный бюджет кампании.
            budget_real: реальный бюджет кампании.
            calc_id: идентификатор расчета или прогноза кампании.
            description: описание кампании.
            finish_time: дата и время окончания кампании.
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
            start_time: дата и время начала кампании.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CampaignActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        _validate_optional_datetime("start_time", start_time)
        _validate_optional_datetime("finish_time", finish_time)
        return await self._execute(
            CREATE_AUTOSTRATEGY_CAMPAIGN,
            request=CreateAutostrategyCampaignRequest(
                campaign_type=campaign_type,
                title=title,
                budget=budget,
                budget_bonus=budget_bonus,
                budget_real=budget_real,
                calc_id=calc_id,
                description=description,
                finish_time=finish_time,
                items=items,
                start_time=start_time,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/campaign/edit",
        spec="Автостратегия.json",
        operation_id="editAutostrategyCampaign",
        method_args={"campaign_id": "body.campaignId", "version": "body.version"},
        variant="async",
    )
    async def update(
        self,
        *,
        version: int,
        campaign_id: int | None = None,
        budget: int | None = None,
        calc_id: int | None = None,
        description: str | None = None,
        finish_time: datetime | None = None,
        items: list[int] | None = None,
        start_time: datetime | None = None,
        title: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CampaignActionResult:
        """Редактирует кампанию.

        Аргументы:
            version: версия кампании для optimistic locking или согласованного обновления.
            campaign_id: идентификатор кампании.
            budget: бюджет кампании.
            calc_id: идентификатор расчета или прогноза кампании.
            description: описание кампании.
            finish_time: дата и время окончания кампании.
            items: элементы запроса с объявлениями, ставками или настройками продвижения.
            start_time: дата и время начала кампании.
            title: название кампании.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CampaignActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        _validate_optional_datetime("start_time", start_time)
        _validate_optional_datetime("finish_time", finish_time)
        return await self._execute(
            UPDATE_AUTOSTRATEGY_CAMPAIGN,
            request=UpdateAutostrategyCampaignRequest(
                campaign_id=campaign_id or self._require_campaign_id(),
                version=version,
                budget=budget,
                calc_id=calc_id,
                description=description,
                finish_time=finish_time,
                items=items,
                start_time=start_time,
                title=title,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/campaign/info",
        spec="Автостратегия.json",
        operation_id="getAutostrategyCampaignInfo",
        method_args={"campaign_id": "body.campaign_id"},
        variant="async",
    )
    async def get(
        self,
        *,
        campaign_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CampaignDetailsResult:
        """Получает полную информацию о кампании.

        Аргументы:
            campaign_id: идентификатор кампании.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CampaignDetailsResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AUTOSTRATEGY_CAMPAIGN,
            request=GetAutostrategyCampaignInfoRequest(
                campaign_id=campaign_id or self._require_campaign_id()
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/campaign/stop",
        spec="Автостратегия.json",
        operation_id="stopAutostrategyCampaign",
        method_args={"campaign_id": "body.campaignId", "version": "body.version"},
        variant="async",
    )
    async def delete(
        self,
        *,
        version: int,
        campaign_id: int | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CampaignActionResult:
        """Останавливает кампанию.

        Аргументы:
            version: версия кампании для optimistic locking или согласованного обновления.
            campaign_id: идентификатор кампании.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CampaignActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELETE_AUTOSTRATEGY_CAMPAIGN,
            request=StopAutostrategyCampaignRequest(
                campaign_id=campaign_id or self._require_campaign_id(),
                version=version,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/campaigns",
        spec="Автостратегия.json",
        operation_id="getAutostrategyCampaigns",
        variant="async",
    )
    async def list(
        self,
        *,
        limit: int = 100,
        offset: int | None = None,
        status_id: builtins.list[int] | None = None,
        order_by: builtins.list[tuple[str, str]] | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CampaignsResult:
        """Возвращает кампании автостратегии с фильтрами и пагинацией.

        Аргументы:
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            status_id: фильтрует результат по числовому статусу.
            order_by: задает порядок сортировки результата.
            updated_from: фильтрует записи, обновленные не раньше указанного времени.
            updated_to: фильтрует записи, обновленные не позже указанного времени.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CampaignsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        filter_payload = (
            CampaignListFilter(
                by_update_time=CampaignUpdateTimeFilter(
                    from_time=updated_from,
                    to_time=updated_to,
                )
            )
            if updated_from is not None or updated_to is not None
            else None
        )
        order_by_payload = (
            [CampaignOrderBy(column=column, direction=direction) for column, direction in order_by]
            if order_by is not None
            else None
        )
        return await self._execute(
            LIST_AUTOSTRATEGY_CAMPAIGNS,
            request=ListAutostrategyCampaignsRequest(
                limit=limit,
                offset=offset,
                status_id=status_id,
                order_by=order_by_payload,
                filter=filter_payload,
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autostrategy/v1/stat",
        spec="Автостратегия.json",
        operation_id="getAutostrategyStat",
        variant="async",
    )
    async def get_stat(
        self,
        *,
        campaign_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutostrategyStat:
        """Получает статистику кампании.

        Аргументы:
            campaign_id: идентификатор кампании.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutostrategyStat` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AUTOSTRATEGY_STAT,
            request=GetAutostrategyStatRequest(
                campaign_id=campaign_id or self._require_campaign_id()
            ),
            timeout=timeout,
            retry=retry,
        )

    def _require_campaign_id(self) -> int:
        if self.campaign_id is None:
            raise ValidationError("Для операции требуется `campaign_id`.")
        return int(self.campaign_id)


__all__ = (
    "AsyncAutostrategyCampaign",
    "AsyncBbipPromotion",
    "AsyncCpaAuction",
    "AsyncPromotionOrder",
    "AsyncTargetActionPricing",
    "AsyncTrxPromotion",
)
