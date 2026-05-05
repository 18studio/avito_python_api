"""Типизированные модели раздела promotion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast

from avito.core.enums import map_enum_or_unknown
from avito.core.exceptions import ResponseMappingError
from avito.core.serialization import SerializableModel


class PromotionStatus(str, Enum):
    """Статус promotion-объекта или операции."""

    UNKNOWN = "__unknown__"
    UPSTREAM_UNKNOWN = "unknown"
    AVAILABLE = "available"
    ACTIVE = "active"
    CREATED = "created"
    INITIALIZED = "initialized"
    WAITING = "waiting"
    IN_PROCESS = "in_process"
    PROCESSED = "processed"
    CANCELED = "canceled"
    ERROR = "error"
    REMOVED = "removed"
    AUTO = "auto"
    MANUAL = "manual"
    APPLIED = "applied"
    PARTIAL = "partial"
    FAILED = "failed"
    PREVIEW = "preview"


class PromotionOrderStatus(str, Enum):
    """Статус заявки на продвижение."""

    UNKNOWN = "__unknown__"
    UPSTREAM_UNKNOWN = "unknown"
    APPLIED = "applied"
    CREATED = "created"
    AUTO = "auto"
    MANUAL = "manual"
    PARTIAL = "partial"
    INITIALIZED = "initialized"
    WAITING = "waiting"
    IN_PROCESS = "in_process"
    PROCESSED = "processed"


class PromotionOrderServiceStatus(str, Enum):
    """Статус услуги внутри заявки на продвижение."""

    UNKNOWN = "__unknown__"
    UPSTREAM_UNKNOWN = "unknown"
    AVAILABLE = "available"
    ACTIVE = "active"
    ERROR = "error"
    CANCELED = "canceled"
    PROCESSED = "processed"


class TargetActionBudgetType(str, Enum):
    """Тип бюджета цены целевого действия."""

    UNKNOWN = "__unknown__"
    DAILY = "1d"
    WEEKLY = "7d"
    MONTHLY = "30d"


class TargetActionSelectedType(str, Enum):
    """Выбранный тип продвижения цены целевого действия."""

    UNKNOWN = "__unknown__"
    AUTO = "auto"
    MANUAL = "manual"


class CampaignType(str, Enum):
    """Тип автокампании."""

    UNKNOWN = "__unknown__"
    AUTOSTRATEGY = "AS"


_Payload = Mapping[str, object]


def _expect_mapping(payload: object) -> _Payload:
    if not isinstance(payload, Mapping):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return cast(_Payload, payload)


def _list(payload: _Payload, *keys: str) -> list[_Payload]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _mapping(payload: _Payload, *keys: str) -> _Payload:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return cast(_Payload, value)
    return {}


def _str(payload: _Payload, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def _int(payload: _Payload, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _bool(payload: _Payload, *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _datetime(payload: _Payload, *keys: str) -> datetime | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _items_payload(payload: _Payload) -> list[_Payload]:
    return _list(payload, "items", "result", "services", "orders", "campaigns")


@dataclass(slots=True, frozen=True)
class PromotionServiceType(SerializableModel):
    """Тип услуги продвижения."""

    code: str | None
    title: str | None


@dataclass(slots=True, frozen=True)
class PromotionServiceDictionary(SerializableModel):
    """Словарь услуг продвижения."""

    items: list[PromotionServiceType]

    @classmethod
    def from_payload(cls, payload: object) -> PromotionServiceDictionary:
        """Преобразует словарь услуг продвижения."""

        if isinstance(payload, list):
            items_payload = [item for item in payload if isinstance(item, Mapping)]
        else:
            data = _expect_mapping(payload)
            items_payload = _items_payload(data)
        return cls(
            items=[
                PromotionServiceType(
                    code=_str(item, "code", "serviceCode", "id", "slug"),
                    title=_str(item, "title", "name", "description"),
                )
                for item in items_payload
            ],
        )


@dataclass(slots=True, frozen=True)
class ListPromotionServicesRequest:
    """Запрос списка услуг продвижения."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос списка услуг."""

        return {"itemIds": self.item_ids}


@dataclass(slots=True, frozen=True)
class PromotionService(SerializableModel):
    """Услуга продвижения по объявлению."""

    item_id: int | None
    service_code: str | None
    service_name: str | None
    price: int | None
    status: PromotionOrderServiceStatus | None


@dataclass(slots=True, frozen=True)
class PromotionServicesResult(SerializableModel):
    """Список услуг продвижения."""

    items: list[PromotionService]

    @classmethod
    def from_payload(cls, payload: object) -> PromotionServicesResult:
        """Преобразует список услуг продвижения."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                PromotionService(
                    item_id=_int(item, "itemId", "itemID"),
                    service_code=_str(item, "serviceCode", "code"),
                    service_name=_str(item, "serviceName", "name", "title"),
                    price=_int(item, "price", "pricePenny"),
                    status=map_enum_or_unknown(
                        _str(item, "status"),
                        PromotionOrderServiceStatus,
                        enum_name="promotion.order_service_status",
                    ),
                )
                for item in _items_payload(data)
            ],
        )


@dataclass(slots=True, frozen=True)
class ListPromotionOrdersRequest:
    """Запрос списка заявок на продвижение."""

    item_ids: list[int] | None = None
    order_ids: list[str] | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос списка заявок."""

        return {}


@dataclass(slots=True, frozen=True)
class PromotionOrderInfo(SerializableModel):
    """Заявка на продвижение."""

    order_id: str | None
    item_id: int | None
    service_code: str | None
    status: PromotionOrderStatus | None
    created_at: datetime | None


@dataclass(slots=True, frozen=True)
class PromotionOrdersResult(SerializableModel):
    """Список заявок на продвижение."""

    items: list[PromotionOrderInfo]

    @classmethod
    def from_payload(cls, payload: object) -> PromotionOrdersResult:
        """Преобразует список заявок на продвижение."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                PromotionOrderInfo(
                    order_id=_str(item, "orderId", "orderID", "id"),
                    item_id=_int(item, "itemId", "itemID"),
                    service_code=_str(item, "serviceCode", "code"),
                    status=map_enum_or_unknown(
                        _str(item, "status"),
                        PromotionOrderStatus,
                        enum_name="promotion.order_status",
                    ),
                    created_at=_datetime(item, "createdAt", "created_at"),
                )
                for item in _items_payload(data)
            ],
        )


@dataclass(slots=True, frozen=True)
class GetPromotionOrderStatusRequest:
    """Запрос статуса заявок."""

    order_ids: list[str]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос статуса заявок."""

        return {"orderId": self.order_ids[0]}


@dataclass(slots=True, frozen=True)
class PromotionOrderError(SerializableModel):
    """Ошибка по объявлению в ответе promotion API."""

    item_id: int | None
    error_code: int | None
    error_text: str | None


@dataclass(slots=True, frozen=True)
class PromotionOrderStatusItem(SerializableModel):
    """Статус услуги внутри заявки на продвижение."""

    item_id: int | None
    price: int | None
    slug: str | None
    status: PromotionOrderServiceStatus | None
    error_reason: str | None


@dataclass(slots=True, frozen=True)
class PromotionOrderStatusResult(SerializableModel):
    """Статус заявки на продвижение."""

    order_id: str | None
    status: PromotionOrderStatus | None
    total_price: int | None
    items: list[PromotionOrderStatusItem]
    errors: list[PromotionOrderError]

    @classmethod
    def from_payload(cls, payload: object) -> PromotionOrderStatusResult:
        """Преобразует documented shape статуса заявки на продвижение."""

        data = _expect_mapping(payload)
        order_id = _str(data, "orderId", "orderID", "id")
        status = map_enum_or_unknown(
            _str(data, "status"),
            PromotionOrderStatus,
            enum_name="promotion.order_status",
        )
        if order_id is None or status is None:
            raise ResponseMappingError(
                "Статус заявки promotion должен содержать `orderId` и `status`.",
                payload=payload,
            )
        errors_payload = data.get("errors", [])
        if errors_payload is not None and not isinstance(errors_payload, list):
            raise ResponseMappingError("Поле `errors` должно быть массивом.", payload=payload)
        return cls(
            order_id=order_id,
            status=status,
            total_price=_int(data, "totalPrice"),
            items=[
                PromotionOrderStatusItem(
                    item_id=_int(item, "itemId", "itemID"),
                    price=_int(item, "price"),
                    slug=_str(item, "slug"),
                    status=map_enum_or_unknown(
                        _str(item, "status"),
                        PromotionOrderServiceStatus,
                        enum_name="promotion.order_service_status",
                    ),
                    error_reason=_str(item, "errorReason"),
                )
                for item in _list(data, "items")
            ],
            errors=[
                PromotionOrderError(
                    item_id=_int(item, "itemId", "itemID"),
                    error_code=_int(item, "errorCode"),
                    error_text=_str(item, "errorText"),
                )
                for item in errors_payload or []
                if isinstance(item, Mapping)
            ],
        )


@dataclass(slots=True, frozen=True)
class BbipItem(SerializableModel):
    """Параметры BBIP по объявлению (прогноз или заявка)."""

    item_id: int
    duration: int
    price: int
    old_price: int


@dataclass(slots=True, frozen=True)
class CreateBbipForecastsRequest:
    """Запрос прогноза BBIP."""

    items: list[BbipItem]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос прогноза BBIP."""

        return {
            "items": [
                {
                    "itemId": item.item_id,
                    "duration": item.duration,
                    "price": item.price,
                    "oldPrice": item.old_price,
                }
                for item in self.items
            ]
        }


@dataclass(slots=True, frozen=True)
class PromotionForecast(SerializableModel):
    """Прогноз BBIP по объявлению."""

    item_id: int | None
    min_views: int | None
    max_views: int | None
    total_price: int | None
    total_old_price: int | None


@dataclass(slots=True, frozen=True)
class BbipForecastsResult(SerializableModel):
    """Результат прогноза BBIP."""

    items: list[PromotionForecast]

    @classmethod
    def from_payload(cls, payload: object) -> BbipForecastsResult:
        """Преобразует прогнозы BBIP."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                PromotionForecast(
                    item_id=_int(item, "itemId", "itemID"),
                    min_views=_int(item, "min"),
                    max_views=_int(item, "max"),
                    total_price=_int(item, "totalPrice"),
                    total_old_price=_int(item, "totalOldPrice"),
                )
                for item in _items_payload(data)
            ],
        )


@dataclass(slots=True, frozen=True)
class CreateBbipOrderRequest:
    """Запрос подключения BBIP."""

    items: list[BbipItem]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос подключения BBIP."""

        return {
            "items": [
                {
                    "itemId": item.item_id,
                    "duration": item.duration,
                    "price": item.price,
                    "oldPrice": item.old_price,
                }
                for item in self.items
            ]
        }


@dataclass(slots=True, frozen=True)
class PromotionActionItem(SerializableModel):
    """Результат действия по одному объявлению."""

    item_id: int | None
    success: bool
    status: PromotionStatus | None = None
    message: str | None = None
    upstream_reference: str | None = None


@dataclass(slots=True, frozen=True)
class PromotionActionPayload(SerializableModel):
    """Raw upstream payload for promotion write operations enriched by domain methods."""

    raw_payload: Mapping[str, object]

    @classmethod
    def from_payload(cls, payload: object) -> PromotionActionPayload:
        """Preserve upstream action payload for domain-level normalization."""

        return cls(raw_payload=_expect_mapping(payload))


@dataclass(slots=True, frozen=True)
class PromotionActionResult(SerializableModel):
    """Стабильный результат write-операции продвижения."""

    action: str
    target: dict[str, object] | None
    status: PromotionStatus
    applied: bool
    request_payload: dict[str, object] | None = None
    warnings: list[str] = field(default_factory=list)
    upstream_reference: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_action_payload(
        cls,
        payload: object,
        *,
        action: str,
        target: Mapping[str, object] | None,
        request_payload: Mapping[str, object],
    ) -> PromotionActionResult:
        """Преобразует результат действия по продвижению."""

        if isinstance(payload, PromotionActionPayload):
            payload = payload.raw_payload
        data = _expect_mapping(payload)
        items_payload = _items_payload(data)
        if not items_payload:
            success_payload = _mapping(data, "success")
            items_payload = _list(success_payload, "items", "result")
        items = [
            PromotionActionItem(
                item_id=_int(item, "itemId", "itemID"),
                success=bool(item.get("success", True)),
                status=map_enum_or_unknown(
                    _str(item, "status"),
                    PromotionStatus,
                    enum_name="promotion.status",
                ),
                message=_str(_mapping(item, "error"), "message") or _str(item, "message"),
                upstream_reference=_str(item, "orderId", "requestId", "promotionId", "id"),
            )
            for item in items_payload
        ]
        applied = (
            bool(data.get("success", True)) if not items else all(item.success for item in items)
        )
        statuses = [item.status for item in items if item.status is not None]
        messages = [item.message for item in items if item.message]
        resolved_status = _resolve_action_status(payload=data, statuses=statuses, applied=applied)
        details: dict[str, object] = {}
        if items:
            details["items"] = [
                {
                    "item_id": item.item_id,
                    "success": item.success,
                    "status": item.status,
                    "message": item.message,
                }
                for item in items
            ]
        elif message := _str(data, "message", "status"):
            details["message"] = message
        return cls(
            action=action,
            target=dict(target) if target is not None else None,
            status=resolved_status,
            applied=applied,
            request_payload=dict(request_payload),
            warnings=messages if not applied else [],
            upstream_reference=_extract_upstream_reference(data, items),
            details=details,
        )


def _resolve_action_status(
    *,
    payload: _Payload,
    statuses: list[PromotionStatus],
    applied: bool,
) -> PromotionStatus:
    if statuses:
        unique_statuses = list(dict.fromkeys(statuses))
        if len(unique_statuses) == 1:
            return unique_statuses[0]
        return PromotionStatus.APPLIED if applied else PromotionStatus.PARTIAL
    payload_status = map_enum_or_unknown(
        _str(payload, "status"),
        PromotionStatus,
        enum_name="promotion.status",
    )
    if payload_status is not None:
        return payload_status
    return PromotionStatus.APPLIED if applied else PromotionStatus.FAILED


def _extract_upstream_reference(
    payload: _Payload,
    items: list[PromotionActionItem],
) -> str | None:
    reference = _str(payload, "orderId", "requestId", "promotionId", "id")
    if reference is not None:
        return reference
    for item in items:
        if item.upstream_reference is not None:
            return item.upstream_reference
    return None


@dataclass(slots=True, frozen=True)
class CreateBbipSuggestsRequest:
    """Запрос вариантов бюджета BBIP."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос вариантов бюджета BBIP."""

        return {"itemIds": self.item_ids}


@dataclass(slots=True, frozen=True)
class BbipBudgetOption(SerializableModel):
    """Вариант бюджета BBIP."""

    price: int | None
    old_price: int | None
    is_recommended: bool | None


@dataclass(slots=True, frozen=True)
class BbipDurationRange(SerializableModel):
    """Доступный диапазон длительности BBIP."""

    start: int | None
    stop: int | None
    recommended: int | None


@dataclass(slots=True, frozen=True)
class BbipSuggest(SerializableModel):
    """Варианты бюджета BBIP по объявлению."""

    item_id: int | None
    duration: BbipDurationRange | None
    budgets: list[BbipBudgetOption]


@dataclass(slots=True, frozen=True)
class BbipSuggestsResult(SerializableModel):
    """Результат вариантов бюджета BBIP."""

    items: list[BbipSuggest]

    @classmethod
    def from_payload(cls, payload: object) -> BbipSuggestsResult:
        """Преобразует варианты бюджета BBIP."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                BbipSuggest(
                    item_id=_int(item, "itemId", "itemID"),
                    duration=_map_bbip_duration(_mapping(item, "duration")),
                    budgets=[_map_bbip_budget(option) for option in _list(item, "budgets")],
                )
                for item in _items_payload(data)
            ],
        )


def _map_bbip_budget(payload: _Payload) -> BbipBudgetOption:
    return BbipBudgetOption(
        price=_int(payload, "price"),
        old_price=_int(payload, "oldPrice"),
        is_recommended=_bool(payload, "isRecommended"),
    )


def _map_bbip_duration(payload: _Payload) -> BbipDurationRange | None:
    if not payload:
        return None
    return BbipDurationRange(
        start=_int(payload, "from"),
        stop=_int(payload, "to"),
        recommended=_int(payload, "recommended"),
    )


@dataclass(slots=True, frozen=True)
class TrxItem(SerializableModel):
    """Параметры TrxPromo по объявлению."""

    item_id: int
    commission: int
    date_from: datetime
    date_to: datetime | None = None


@dataclass(slots=True, frozen=True)
class CreateTrxPromotionApplyRequest:
    """Запрос запуска TrxPromo."""

    items: list[TrxItem]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос запуска TrxPromo."""

        items_payload: list[dict[str, object]] = []
        for item in self.items:
            entry: dict[str, object] = {
                "itemID": item.item_id,
                "commission": item.commission,
                "dateFrom": item.date_from.isoformat(),
            }
            if item.date_to is not None:
                entry["dateTo"] = item.date_to.isoformat()
            items_payload.append(entry)
        return {"items": items_payload}


@dataclass(slots=True, frozen=True)
class CancelTrxPromotionRequest:
    """Запрос остановки TrxPromo."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос остановки TrxPromo."""

        return {"itemIDs": list(self.item_ids)}


@dataclass(slots=True, frozen=True)
class GetTrxCommissionsRequest:
    """Запрос доступных комиссий TrxPromo."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос доступных комиссий."""

        return {"itemIDs": self.item_ids}


@dataclass(slots=True, frozen=True)
class TrxCommissionRange(SerializableModel):
    """Диапазон комиссии TrxPromo."""

    value_min: int | None
    value_max: int | None
    step: int | None


@dataclass(slots=True, frozen=True)
class TrxCommissionInfo(SerializableModel):
    """Доступность и комиссия TrxPromo по объявлению."""

    item_id: int | None
    commission: int | None
    is_active: bool | None
    valid_commission_range: TrxCommissionRange | None


@dataclass(slots=True, frozen=True)
class TrxCommissionsResult(SerializableModel):
    """Список комиссий TrxPromo."""

    items: list[TrxCommissionInfo]

    @classmethod
    def from_payload(cls, payload: object) -> TrxCommissionsResult:
        """Преобразует комиссии TrxPromo."""

        data = _expect_mapping(payload)
        items_payload = _items_payload(data)
        if not items_payload:
            success_payload = _mapping(data, "success")
            items_payload = _list(success_payload, "items", "result")
        return cls(
            items=[
                TrxCommissionInfo(
                    item_id=_int(item, "itemId", "itemID"),
                    commission=_int(item, "commission"),
                    is_active=_bool(item, "isActive", "active"),
                    valid_commission_range=_map_trx_range(_mapping(item, "validCommissionRange")),
                )
                for item in items_payload
            ],
        )


def _map_trx_range(payload: _Payload) -> TrxCommissionRange | None:
    if not payload:
        return None
    return TrxCommissionRange(
        value_min=_int(payload, "valueMin"),
        value_max=_int(payload, "valueMax"),
        step=_int(payload, "step"),
    )


@dataclass(slots=True, frozen=True)
class CpaAuctionBidOption(SerializableModel):
    """Доступная ставка CPA-аукциона."""

    price_penny: int | None
    goodness: int | None


@dataclass(slots=True, frozen=True)
class CpaAuctionItemBid(SerializableModel):
    """Текущая и доступные ставки CPA-аукциона по объявлению."""

    item_id: int | None
    price_penny: int | None
    expiration_time: datetime | None
    available_prices: list[CpaAuctionBidOption]


@dataclass(slots=True, frozen=True)
class CpaAuctionBidsResult(SerializableModel):
    """Список ставок CPA-аукциона."""

    items: list[CpaAuctionItemBid]

    @classmethod
    def from_payload(cls, payload: object) -> CpaAuctionBidsResult:
        """Преобразует действующие и доступные ставки CPA-аукциона."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                CpaAuctionItemBid(
                    item_id=_int(item, "itemId", "itemID"),
                    price_penny=_int(item, "pricePenny"),
                    expiration_time=_datetime(item, "expirationTime"),
                    available_prices=[
                        CpaAuctionBidOption(
                            price_penny=_int(option, "pricePenny"),
                            goodness=_int(option, "goodness"),
                        )
                        for option in _list(item, "availablePrices")
                    ],
                )
                for item in _items_payload(data)
            ],
        )


@dataclass(slots=True, frozen=True)
class CpaAuctionBidInput(SerializableModel):
    """Входные параметры одной ставки CPA-аукциона."""

    item_id: int
    price_penny: int


@dataclass(slots=True, frozen=True)
class CreateItemBid:
    """Новая ставка CPA-аукциона."""

    item_id: int
    price_penny: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует одну ставку CPA-аукциона."""

        return {"itemID": self.item_id, "pricePenny": self.price_penny}


@dataclass(slots=True, frozen=True)
class CreateItemBidsRequest:
    """Запрос сохранения новых ставок CPA-аукциона."""

    items: list[CreateItemBid]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос сохранения ставок."""

        return {"items": [item.to_payload() for item in self.items]}


@dataclass(slots=True, frozen=True)
class TargetActionBid(SerializableModel):
    """Доступная цена целевого действия."""

    value_penny: int | None
    min_forecast: int | None
    max_forecast: int | None
    compare: int | None


@dataclass(slots=True, frozen=True)
class TargetActionManualBids(SerializableModel):
    """Детали ручной ставки цены целевого действия."""

    bid_penny: int | None
    limit_penny: int | None
    rec_bid_penny: int | None
    min_bid_penny: int | None
    max_bid_penny: int | None
    min_limit_penny: int | None
    max_limit_penny: int | None
    bids: list[TargetActionBid]


@dataclass(slots=True, frozen=True)
class TargetActionBudget(SerializableModel):
    """Диапазон доступных бюджетов цены целевого действия."""

    budget_penny: int | None
    min_forecast: int | None
    max_forecast: int | None
    compare: int | None


@dataclass(slots=True, frozen=True)
class TargetActionAutoBids(SerializableModel):
    """Детали автоматического продвижения цены целевого действия."""

    budget_penny: int | None
    budget_type: TargetActionBudgetType | None
    min_budget_penny: int | None
    max_budget_penny: int | None
    daily_budget: list[TargetActionBudget]
    weekly_budget: list[TargetActionBudget]
    monthly_budget: list[TargetActionBudget]


@dataclass(slots=True, frozen=True)
class TargetActionGetBidsResult(SerializableModel):
    """Ответ GET /cpxpromo/1/getBids/{itemId}."""

    action_type_id: int
    selected_type: TargetActionSelectedType
    auto: TargetActionAutoBids | None = None
    manual: TargetActionManualBids | None = None

    @classmethod
    def from_payload(cls, payload: object) -> TargetActionGetBidsResult:
        """Преобразует documented shape GET /cpxpromo/1/getBids/{itemId}."""

        data = _expect_mapping(payload)
        action_type_id = _int(data, "actionTypeID")
        selected_type = map_enum_or_unknown(
            _str(data, "selectedType"),
            TargetActionSelectedType,
            enum_name="promotion.target_action_selected_type",
        )
        if action_type_id is None or selected_type is None:
            raise ResponseMappingError(
                "Ответ getBids должен содержать `actionTypeID` и `selectedType`.",
                payload=payload,
            )
        return cls(
            action_type_id=action_type_id,
            selected_type=selected_type,
            auto=(
                _map_target_action_auto(cast(_Payload, data["auto"]))
                if isinstance(data.get("auto"), Mapping)
                else None
            ),
            manual=(
                _map_target_action_manual(cast(_Payload, data["manual"]))
                if isinstance(data.get("manual"), Mapping)
                else None
            ),
        )


def _map_target_action_bid(item: _Payload) -> TargetActionBid:
    return TargetActionBid(
        value_penny=_int(item, "valuePenny"),
        min_forecast=_int(item, "minForecast"),
        max_forecast=_int(item, "maxForecast"),
        compare=_int(item, "compare"),
    )


def _map_target_action_budget(item: _Payload) -> TargetActionBudget:
    return TargetActionBudget(
        budget_penny=_int(item, "valuePenny"),
        min_forecast=_int(item, "minForecast"),
        max_forecast=_int(item, "maxForecast"),
        compare=_int(item, "compare"),
    )


def _map_target_action_manual(payload: _Payload) -> TargetActionManualBids:
    bids_payload = payload.get("bids")
    if bids_payload is not None and not isinstance(bids_payload, list):
        raise ResponseMappingError("Поле `manual.bids` должно быть массивом.", payload=payload)
    return TargetActionManualBids(
        bid_penny=_int(payload, "bidPenny"),
        limit_penny=_int(payload, "limitPenny"),
        rec_bid_penny=_int(payload, "recBidPenny"),
        min_bid_penny=_int(payload, "minBidPenny"),
        max_bid_penny=_int(payload, "maxBidPenny"),
        min_limit_penny=_int(payload, "minLimitPenny"),
        max_limit_penny=_int(payload, "maxLimitPenny"),
        bids=[
            _map_target_action_bid(item) for item in bids_payload or [] if isinstance(item, Mapping)
        ],
    )


def _map_budget_values(payload: _Payload, key: str) -> list[TargetActionBudget]:
    budget = payload.get(key)
    if budget is None:
        return []
    if not isinstance(budget, Mapping):
        raise ResponseMappingError(f"Поле `{key}` должно быть объектом.", payload=payload)
    values = budget.get("budgets")
    if values is not None and not isinstance(values, list):
        raise ResponseMappingError(f"Поле `{key}.budgets` должно быть массивом.", payload=payload)
    return [_map_target_action_budget(item) for item in values or [] if isinstance(item, Mapping)]


def _map_target_action_auto(payload: _Payload) -> TargetActionAutoBids:
    return TargetActionAutoBids(
        budget_penny=_int(payload, "budgetPenny"),
        budget_type=map_enum_or_unknown(
            _str(payload, "budgetType"),
            TargetActionBudgetType,
            enum_name="promotion.target_action_budget_type",
        ),
        min_budget_penny=_int(payload, "minBudgetPenny"),
        max_budget_penny=_int(payload, "maxBudgetPenny"),
        daily_budget=_map_budget_values(payload, "dailyBudget"),
        weekly_budget=_map_budget_values(payload, "weeklyBudget"),
        monthly_budget=_map_budget_values(payload, "monthlyBudget"),
    )


@dataclass(slots=True, frozen=True)
class TargetActionAutoPromotion(SerializableModel):
    """Текущий auto-budget по объявлению."""

    budget_penny: int | None
    budget_type: TargetActionBudgetType | None


@dataclass(slots=True, frozen=True)
class TargetActionManualPromotion(SerializableModel):
    """Текущая manual-настройка по объявлению."""

    bid_penny: int | None
    limit_penny: int | None


@dataclass(slots=True, frozen=True)
class TargetActionPromotion(SerializableModel):
    """Текущая настройка цены целевого действия по объявлению."""

    item_id: int
    action_type_id: int
    auto: TargetActionAutoPromotion | None = None
    manual: TargetActionManualPromotion | None = None


@dataclass(slots=True, frozen=True)
class TargetActionPromotionsByItemIdsResult(SerializableModel):
    """Ответ POST /cpxpromo/1/getPromotionsByItemIds."""

    items: list[TargetActionPromotion]

    @classmethod
    def from_payload(cls, payload: object) -> TargetActionPromotionsByItemIdsResult:
        """Преобразует documented shape POST /cpxpromo/1/getPromotionsByItemIds."""

        data = _expect_mapping(payload)
        items_payload = data.get("items")
        if not isinstance(items_payload, list):
            raise ResponseMappingError(
                "Ответ getPromotionsByItemIds должен содержать массив `items`.",
                payload=payload,
            )
        items: list[TargetActionPromotion] = []
        for item in items_payload:
            if not isinstance(item, Mapping):
                continue
            item_id = _int(item, "itemID")
            action_type_id = _int(item, "actionTypeID")
            if item_id is None or action_type_id is None:
                raise ResponseMappingError(
                    "Элемент getPromotionsByItemIds должен содержать `itemID` и `actionTypeID`.",
                    payload=item,
                )
            items.append(
                TargetActionPromotion(
                    item_id=item_id,
                    action_type_id=action_type_id,
                    auto=(
                        TargetActionAutoPromotion(
                            budget_penny=_int(cast(_Payload, item["autoPromotion"]), "budgetPenny"),
                            budget_type=map_enum_or_unknown(
                                _str(cast(_Payload, item["autoPromotion"]), "budgetType"),
                                TargetActionBudgetType,
                                enum_name="promotion.target_action_budget_type",
                            ),
                        )
                        if isinstance(item.get("autoPromotion"), Mapping)
                        else None
                    ),
                    manual=(
                        TargetActionManualPromotion(
                            bid_penny=_int(cast(_Payload, item["manualPromotion"]), "bidPenny"),
                            limit_penny=_int(cast(_Payload, item["manualPromotion"]), "limitPenny"),
                        )
                        if isinstance(item.get("manualPromotion"), Mapping)
                        else None
                    ),
                )
            )
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class GetPromotionsByItemIdsRequest:
    """Запрос настроек по нескольким объявлениям."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос настроек по нескольким объявлениям."""

        return {"itemIDs": self.item_ids}


@dataclass(slots=True, frozen=True)
class DeletePromotionRequest:
    """Запрос остановки продвижения с ЦД."""

    item_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос остановки продвижения."""

        return {"itemID": self.item_id}


@dataclass(slots=True, frozen=True)
class UpdateAutoBidRequest:
    """Запрос автоматической настройки цены целевого действия."""

    item_id: int
    action_type_id: int
    budget_penny: int
    budget_type: TargetActionBudgetType | str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос автоматической настройки."""

        return {
            "itemID": self.item_id,
            "actionTypeID": self.action_type_id,
            "budgetPenny": self.budget_penny,
            "budgetType": self.budget_type,
        }


@dataclass(slots=True, frozen=True)
class UpdateManualBidRequest:
    """Запрос ручной настройки цены целевого действия."""

    item_id: int
    action_type_id: int
    bid_penny: int
    limit_penny: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос ручной настройки."""

        payload: dict[str, object] = {
            "itemID": self.item_id,
            "actionTypeID": self.action_type_id,
            "bidPenny": self.bid_penny,
        }
        if self.limit_penny is not None:
            payload["limitPenny"] = self.limit_penny
        return payload


@dataclass(slots=True, frozen=True)
class AutostrategyBudgetPoint(SerializableModel):
    """Оценка бюджета автокампании."""

    total: int | None
    real: int | None
    bonus: int | None
    calls_from: int | None
    calls_to: int | None
    views_from: int | None
    views_to: int | None


@dataclass(slots=True, frozen=True)
class AutostrategyPriceRange(SerializableModel):
    """Ценовой диапазон бюджета автокампании."""

    price_from: int | None
    price_to: int | None
    percent: int | None
    calls_from: int | None
    calls_to: int | None
    views_from: int | None
    views_to: int | None


@dataclass(slots=True, frozen=True)
class AutostrategyBudget(SerializableModel):
    """Расчет бюджета автокампании."""

    calc_id: int | None
    recommended: AutostrategyBudgetPoint | None
    minimal: AutostrategyBudgetPoint | None
    maximal: AutostrategyBudgetPoint | None
    price_ranges: list[AutostrategyPriceRange]

    @classmethod
    def from_payload(cls, payload: object) -> AutostrategyBudget:
        """Преобразует расчет бюджета автокампании."""

        data = _expect_mapping(payload)
        source = _mapping(data, "budget")
        return cls(
            calc_id=_int(data, "calcId"),
            recommended=_map_budget_point(_mapping(source, "recommended")),
            minimal=_map_budget_point(_mapping(source, "minimal")),
            maximal=_map_budget_point(_mapping(source, "maximal")),
            price_ranges=[_map_price_range(item) for item in _list(source, "priceRanges")],
        )


def _map_budget_point(payload: _Payload) -> AutostrategyBudgetPoint | None:
    if not payload:
        return None
    return AutostrategyBudgetPoint(
        total=_int(payload, "total"),
        real=_int(payload, "real"),
        bonus=_int(payload, "bonus"),
        calls_from=_int(payload, "callsFrom"),
        calls_to=_int(payload, "callsTo"),
        views_from=_int(payload, "viewsFrom"),
        views_to=_int(payload, "viewsTo"),
    )


def _map_price_range(payload: _Payload) -> AutostrategyPriceRange:
    return AutostrategyPriceRange(
        price_from=_int(payload, "priceFrom"),
        price_to=_int(payload, "priceTo"),
        percent=_int(payload, "percent"),
        calls_from=_int(payload, "callsFrom"),
        calls_to=_int(payload, "callsTo"),
        views_from=_int(payload, "viewsFrom"),
        views_to=_int(payload, "viewsTo"),
    )


@dataclass(slots=True, frozen=True)
class CreateAutostrategyBudgetRequest:
    """Запрос расчета бюджета кампании."""

    campaign_type: CampaignType | str
    start_time: datetime | None = None
    finish_time: datetime | None = None
    items: list[int] | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос расчета бюджета."""

        payload: dict[str, object] = {"campaignType": self.campaign_type}
        if self.start_time is not None:
            payload["startTime"] = self.start_time.isoformat()
        if self.finish_time is not None:
            payload["finishTime"] = self.finish_time.isoformat()
        if self.items is not None:
            payload["items"] = list(self.items)
        return payload


@dataclass(slots=True, frozen=True)
class CampaignInfo(SerializableModel):
    """Информация об автокампании."""

    campaign_id: int | None
    campaign_type: CampaignType | None
    budget: int | None
    balance: int | None
    create_time: datetime | None
    description: str | None
    finish_time: datetime | None
    items_count: int | None
    start_time: datetime | None
    status_id: int | None
    title: str | None
    update_time: datetime | None
    user_id: int | None
    version: int | None


@dataclass(slots=True, frozen=True)
class CampaignActionResult(SerializableModel):
    """Результат операции с автокампанией."""

    campaign: CampaignInfo | None

    @classmethod
    def from_payload(cls, payload: object) -> CampaignActionResult:
        """Преобразует результат операции с автокампанией."""

        data = _expect_mapping(payload)
        return cls(campaign=_map_campaign(_mapping(data, "campaign")))


def _map_campaign(payload: _Payload) -> CampaignInfo | None:
    if not payload:
        return None
    return CampaignInfo(
        campaign_id=_int(payload, "campaignId"),
        campaign_type=map_enum_or_unknown(
            _str(payload, "campaignType"),
            CampaignType,
            enum_name="promotion.campaign_type",
        ),
        budget=_int(payload, "budget"),
        balance=_int(payload, "balance"),
        create_time=_datetime(payload, "createTime"),
        description=_str(payload, "description"),
        finish_time=_datetime(payload, "finishTime"),
        items_count=_int(payload, "itemsCount"),
        start_time=_datetime(payload, "startTime"),
        status_id=_int(payload, "statusId"),
        title=_str(payload, "title"),
        update_time=_datetime(payload, "updateTime"),
        user_id=_int(payload, "userId"),
        version=_int(payload, "version"),
    )


@dataclass(slots=True, frozen=True)
class CampaignForecastRange(SerializableModel):
    """Диапазон прогноза кампании."""

    from_value: int | None
    to_value: int | None


@dataclass(slots=True, frozen=True)
class CampaignForecast(SerializableModel):
    """Прогноз кампании автостратегии."""

    calls: CampaignForecastRange | None
    views: CampaignForecastRange | None


@dataclass(slots=True, frozen=True)
class CampaignItem(SerializableModel):
    """Объявление внутри автокампании."""

    item_id: int | None
    is_active: bool | None


@dataclass(slots=True, frozen=True)
class CampaignDetailsResult(SerializableModel):
    """Полный ответ ручки информации о кампании."""

    campaign: CampaignInfo | None
    forecast: CampaignForecast | None
    items: list[CampaignItem]

    @classmethod
    def from_payload(cls, payload: object) -> CampaignDetailsResult:
        """Преобразует полную информацию об автокампании."""

        data = _expect_mapping(payload)
        return cls(
            campaign=_map_campaign(_mapping(data, "campaign")),
            forecast=_map_campaign_forecast(_mapping(data, "forecast")),
            items=[_map_campaign_item(item) for item in _list(data, "items")],
        )


def _map_campaign_forecast(payload: _Payload) -> CampaignForecast | None:
    if not payload:
        return None
    return CampaignForecast(
        calls=_map_campaign_forecast_range(_mapping(payload, "calls")),
        views=_map_campaign_forecast_range(_mapping(payload, "views")),
    )


def _map_campaign_forecast_range(payload: _Payload) -> CampaignForecastRange | None:
    if not payload:
        return None
    return CampaignForecastRange(
        from_value=_int(payload, "from"),
        to_value=_int(payload, "to"),
    )


def _map_campaign_item(payload: _Payload) -> CampaignItem:
    return CampaignItem(
        item_id=_int(payload, "itemId"),
        is_active=_bool(payload, "isActive"),
    )


@dataclass(slots=True, frozen=True)
class CampaignsResult(SerializableModel):
    """Список автокампаний."""

    items: list[CampaignInfo]
    total_count: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CampaignsResult:
        """Преобразует список автокампаний."""

        data = _expect_mapping(payload)
        items: list[CampaignInfo] = []
        for raw in _list(data, "campaigns"):
            campaign = _map_campaign(raw)
            if campaign is None:
                raise ResponseMappingError("Не удалось смэппить кампанию.", payload=raw)
            items.append(campaign)
        return cls(items=items, total_count=_int(data, "totalCount"))


@dataclass(slots=True, frozen=True)
class AutostrategyStatItem(SerializableModel):
    """Статистика кампании за день."""

    date: datetime | None
    calls: int | None
    views: int | None
    calls_forecast: CampaignForecastRange | None = None
    views_forecast: CampaignForecastRange | None = None


@dataclass(slots=True, frozen=True)
class AutostrategyStatTotals(SerializableModel):
    """Суммарная статистика кампании."""

    calls: int | None
    views: int | None


@dataclass(slots=True, frozen=True)
class AutostrategyStat(SerializableModel):
    """Статистика автокампании."""

    items: list[AutostrategyStatItem]
    totals: AutostrategyStatTotals | None

    @classmethod
    def from_payload(cls, payload: object) -> AutostrategyStat:
        """Преобразует статистику автокампании."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_autostrategy_stat_item(item) for item in _list(data, "stat")],
            totals=_map_autostrategy_stat_totals(_mapping(data, "totals")),
        )


def _map_autostrategy_stat_item(payload: _Payload) -> AutostrategyStatItem:
    return AutostrategyStatItem(
        date=_datetime(payload, "date"),
        calls=_int(payload, "calls"),
        views=_int(payload, "views"),
        calls_forecast=_map_campaign_forecast_range(_mapping(payload, "callsForecast")),
        views_forecast=_map_campaign_forecast_range(_mapping(payload, "viewsForecast")),
    )


def _map_autostrategy_stat_totals(payload: _Payload) -> AutostrategyStatTotals | None:
    if not payload:
        return None
    return AutostrategyStatTotals(
        calls=_int(payload, "calls"),
        views=_int(payload, "views"),
    )


@dataclass(slots=True, frozen=True)
class CreateAutostrategyCampaignRequest:
    """Запрос создания автокампании."""

    campaign_type: CampaignType | str
    title: str
    budget: int | None = None
    budget_bonus: int | None = None
    budget_real: int | None = None
    calc_id: int | None = None
    description: str | None = None
    finish_time: datetime | None = None
    items: list[int] | None = None
    start_time: datetime | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос создания кампании."""

        payload: dict[str, object] = {
            "campaignType": self.campaign_type,
            "title": self.title,
        }
        if self.budget is not None:
            payload["budget"] = self.budget
        if self.budget_bonus is not None:
            payload["budgetBonus"] = self.budget_bonus
        if self.budget_real is not None:
            payload["budgetReal"] = self.budget_real
        if self.calc_id is not None:
            payload["calcId"] = self.calc_id
        if self.description is not None:
            payload["description"] = self.description
        if self.finish_time is not None:
            payload["finishTime"] = self.finish_time.isoformat()
        if self.items is not None:
            payload["items"] = list(self.items)
        if self.start_time is not None:
            payload["startTime"] = self.start_time.isoformat()
        return payload


@dataclass(slots=True, frozen=True)
class UpdateAutostrategyCampaignRequest:
    """Запрос редактирования автокампании."""

    campaign_id: int
    version: int
    budget: int | None = None
    calc_id: int | None = None
    description: str | None = None
    finish_time: datetime | None = None
    items: list[int] | None = None
    start_time: datetime | None = None
    title: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос редактирования кампании."""

        payload: dict[str, object] = {
            "campaignId": self.campaign_id,
            "version": self.version,
        }
        if self.budget is not None:
            payload["budget"] = self.budget
        if self.calc_id is not None:
            payload["calcId"] = self.calc_id
        if self.description is not None:
            payload["description"] = self.description
        if self.finish_time is not None:
            payload["finishTime"] = self.finish_time.isoformat()
        if self.items is not None:
            payload["items"] = list(self.items)
        if self.start_time is not None:
            payload["startTime"] = self.start_time.isoformat()
        if self.title is not None:
            payload["title"] = self.title
        return payload


@dataclass(slots=True, frozen=True)
class GetAutostrategyCampaignInfoRequest:
    """Запрос полной информации о кампании."""

    campaign_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос информации о кампании."""

        return {"campaignId": self.campaign_id}


@dataclass(slots=True, frozen=True)
class StopAutostrategyCampaignRequest:
    """Запрос остановки автокампании."""

    campaign_id: int
    version: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос остановки кампании."""

        return {"campaignId": self.campaign_id, "version": self.version}


@dataclass(slots=True, frozen=True)
class CampaignUpdateTimeFilter:
    """Фильтр кампаний по времени обновления."""

    from_time: datetime | None = None
    to_time: datetime | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует фильтр по времени обновления."""

        payload: dict[str, object] = {}
        if self.from_time is not None:
            payload["from"] = self.from_time.isoformat()
        if self.to_time is not None:
            payload["to"] = self.to_time.isoformat()
        return payload


@dataclass(slots=True, frozen=True)
class CampaignListFilter:
    """Фильтр списка кампаний."""

    by_update_time: CampaignUpdateTimeFilter | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует фильтр списка кампаний."""

        payload: dict[str, object] = {}
        if self.by_update_time is not None:
            payload["byUpdateTime"] = self.by_update_time.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class CampaignOrderBy:
    """Параметры сортировки списка кампаний."""

    column: str
    direction: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует сортировку списка кампаний."""

        return {"column": self.column, "direction": self.direction}


@dataclass(slots=True, frozen=True)
class ListAutostrategyCampaignsRequest:
    """Запрос списка автокампаний."""

    limit: int
    offset: int | None = None
    status_id: list[int] | None = None
    order_by: list[CampaignOrderBy] | None = None
    filter: CampaignListFilter | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос списка кампаний."""

        payload: dict[str, object] = {"limit": self.limit}
        if self.offset is not None:
            payload["offset"] = self.offset
        if self.status_id is not None:
            payload["statusId"] = list(self.status_id)
        if self.order_by is not None:
            payload["orderBy"] = [item.to_payload() for item in self.order_by]
        if self.filter is not None:
            payload["filter"] = self.filter.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class GetAutostrategyStatRequest:
    """Запрос статистики автокампании."""

    campaign_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос статистики кампании."""

        return {"campaignId": self.campaign_id}
