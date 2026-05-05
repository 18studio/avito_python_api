"""Типизированные модели раздела ads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast

from avito.core.enums import map_enum_or_unknown
from avito.core.exceptions import ResponseMappingError, ValidationError
from avito.core.serialization import SerializableModel


class ListingStatus(str, Enum):
    """Статус объявления."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"
    REMOVED = "removed"
    OLD = "old"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"
    ANOTHER_USER = "another_user"


class AdsActionStatus(str, Enum):
    """Статус мутационной операции ads."""

    UNKNOWN = "__unknown__"
    APPLIED = "applied"
    UPDATED = "updated"


class AdAnalyticsGrouping(str, Enum):
    """Группировка расширенной аналитики объявлений."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ITEM = "item"
    TOTALS = "totals"


class AdSpendingsGrouping(str, Enum):
    """Группировка статистики расходов."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


AdAnalyticsGroupingInput = AdAnalyticsGrouping | str
AdSpendingsGroupingInput = AdSpendingsGrouping | str


class AutoloadFieldType(str, Enum):
    """Тип поля автозагрузки."""

    UNKNOWN = "__unknown__"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    INPUT = "input"
    SELECT = "select"
    CHECKBOX = "checkbox"


class AutoloadReportStatus(str, Enum):
    """Статус отчета автозагрузки."""

    UNKNOWN = "__unknown__"
    DONE = "done"
    PROCESSING = "processing"
    SUCCESS = "success"
    SUCCESS_WARNING = "success_warning"
    ERROR = "error"
    PROBLEM = "problem"
    NOT_PUBLISH = "not_publish"
    WILL_PUBLISH_LATER = "will_publish_later"
    DUPLICATE = "duplicate"
    WITHOUT_ID = "without_id"
    DELETED = "deleted"
    UPSTREAM_UNKNOWN = "unknown"


class AutoloadItemStatus(str, Enum):
    """Статус объявления в отчете автозагрузки."""

    UNKNOWN = "__unknown__"
    SUCCESS = "success"
    PROBLEM = "problem"
    ERROR = "error"
    NOT_PUBLISH = "not_publish"
    WILL_PUBLISH_LATER = "will_publish_later"
    DUPLICATE = "duplicate"
    WITHOUT_ID = "without_id"
    DELETED = "deleted"
    UPSTREAM_UNKNOWN = "unknown"


class AutoloadItemStatusDetail(str, Enum):
    """Подробный статус объявления в отчете автозагрузки."""

    UNKNOWN = "__unknown__"
    SUCCESS_ADDED = "success_added"
    SUCCESS_ACTIVATED = "success_activated"
    SUCCESS_ACTIVATED_UPDATED = "success_activated_updated"
    SUCCESS_UPDATED = "success_updated"
    SUCCESS_SKIPPED = "success_skipped"
    PROBLEM_OBSOLETE = "problem_obsolete"
    PROBLEM_PARAMS_CRITICAL = "problem_params_critical"
    PROBLEM_PARAMS = "problem_params"
    PROBLEM_PHONE = "problem_phone"
    PROBLEM_IMAGES = "problem_images"
    PROBLEM_VAS = "problem_vas"
    PROBLEM_OTHER = "problem_other"
    PROBLEM_SEVERAL = "problem_several"
    ERROR_FEE = "error_fee"
    ERROR_PARAMS = "error_params"
    ERROR_PHONE = "error_phone"
    ERROR_REJECTED = "error_rejected"
    ERROR_BLOCKED = "error_blocked"
    ERROR_DELETED = "error_deleted"
    ERROR_OTHER = "error_other"
    ERROR_SEVERAL = "error_several"
    STOPPED_END_DATE_COMPLETE = "stopped_end_date_complete"
    STOPPED_END_DATE_ERROR = "stopped_end_date_error"
    DATE_IN_FUTURE = "date_in_future"
    PUBLISH_LATER = "publish_later"
    LINKER = "linker"
    REMOVED_COMPLETE = "removed_complete"
    REMOVED_ERROR = "removed_error"
    NEED_SYNC = "need_sync"
    DUPLICATE = "duplicate"
    WITHOUT_ID = "without_id"


class AutoloadAvitoStatus(str, Enum):
    """Статус объявления на Авито из отчета автозагрузки."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"
    OLD = "old"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    REMOVED = "removed"


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


def _mapping(payload: _Payload, *keys: str) -> _Payload | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return cast(_Payload, value)
    return None


def _str(payload: _Payload, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def _nested_str(payload: _Payload, *keys: str) -> str | None:
    value = _str(payload, *keys)
    if value is not None:
        return value
    for key in keys:
        nested = _mapping(payload, key)
        if nested is None:
            continue
        nested_value = _str(nested, "value", "name", "title", "slug", "status")
        if nested_value is not None:
            return nested_value
    return None


def _datetime(payload: _Payload, *keys: str) -> datetime | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                continue
    return None


def _int(payload: _Payload, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _float(payload: _Payload, *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Mapping):
            nested = cast(_Payload, value)
            nested_value = _float(nested, "value", "amount", "current", "price")
            if nested_value is not None:
                return nested_value
    return None


def _bool(payload: _Payload, *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _enum_value[EnumT: Enum](
    enum_type: type[EnumT],
    name: str,
    value: EnumT | str,
) -> str:
    if isinstance(value, enum_type):
        return str(value.value)
    try:
        return str(enum_type(value).value)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise ValidationError(f"`{name}` должен быть одним из: {allowed}.") from exc


def _visibility(payload: _Payload) -> bool | None:
    visible = _bool(payload, "is_visible", "isVisible", "visible")
    if visible is not None:
        return visible
    status = _nested_str(payload, "status")
    if status is None:
        return None
    return status in {"active", "published", "visible"}


@dataclass(slots=True, frozen=True)
class Listing(SerializableModel):
    """Объявление пользователя."""

    item_id: int | None
    user_id: int | None
    title: str | None
    description: str | None
    status: ListingStatus | None
    price: float | None
    url: str | None
    category: str | None = None
    city: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    is_moderated: bool | None = None
    is_visible: bool | None = None

    @classmethod
    def from_payload(cls, payload: object) -> Listing:
        """Преобразует объявление в dataclass."""

        data = _expect_mapping(payload)
        source = _mapping(data, "item", "resource", "listing", "ad") or data
        return cls(
            item_id=_int(source, "id", "item_id", "itemId", "itemID"),
            user_id=_int(source, "user_id", "userId"),
            title=_str(source, "title", "name"),
            description=_str(source, "description", "descriptionHtml"),
            status=map_enum_or_unknown(
                _nested_str(source, "status", "state"),
                ListingStatus,
                enum_name="ads.listing_status",
            ),
            price=_float(source, "price"),
            url=_str(source, "url", "link", "uri"),
            category=_nested_str(source, "category", "categoryName"),
            city=_nested_str(source, "city", "location"),
            published_at=_datetime(
                source, "published_at", "publishedAt", "created_at", "createdAt"
            ),
            updated_at=_datetime(source, "updated_at", "updatedAt"),
            is_moderated=_bool(source, "is_moderated", "isModerated", "moderated"),
            is_visible=_visibility(source),
        )


@dataclass(slots=True, frozen=True)
class AdsListResult(SerializableModel):
    """Результат списка объявлений."""

    items: list[Listing]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AdsListResult:
        """Преобразует список объявлений в dataclass."""

        data = _expect_mapping(payload)
        items = [Listing.from_payload(item) for item in _list(data, "items", "result", "resources")]
        meta = _mapping(data, "meta")
        total = _int(data, "total", "count")
        if total is None and meta is not None:
            total = _int(meta, "total", "count")
        return cls(items=items, total=total)


@dataclass(slots=True, frozen=True)
class UpdatePriceRequest:
    """Запрос изменения цены объявления."""

    price: int | float

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос смены цены."""

        return {"price": self.price}


@dataclass(slots=True, frozen=True)
class UpdatePriceResult(SerializableModel):
    """Результат обновления цены объявления."""

    item_id: int | None
    price: float | None
    status: AdsActionStatus | None

    @classmethod
    def from_payload(cls, payload: object) -> UpdatePriceResult:
        """Преобразует результат обновления цены."""

        data = _expect_mapping(payload)
        return cls(
            item_id=_int(data, "item_id", "itemId", "id"),
            price=_float(data, "price"),
            status=map_enum_or_unknown(
                _str(data, "status", "result"),
                AdsActionStatus,
                enum_name="ads.action_status",
            ),
        )


@dataclass(slots=True, frozen=True)
class CallsStatsRequest:
    """Запрос статистики звонков."""

    item_ids: list[int] = field(default_factory=list)
    date_from: str = ""
    date_to: str = ""

    def to_payload(self) -> dict[str, object]:
        """Сериализует фильтр статистики звонков."""

        return {
            key: value
            for key, value in {
                "itemIds": self.item_ids or None,
                "dateFrom": self.date_from,
                "dateTo": self.date_to,
            }.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class CallStats(SerializableModel):
    """Статистика звонков по объявлению."""

    item_id: int | None
    calls: int | None
    answered_calls: int | None
    missed_calls: int | None


@dataclass(slots=True, frozen=True)
class CallsStatsResult(SerializableModel):
    """Статистика звонков по набору объявлений."""

    items: list[CallStats]

    @classmethod
    def from_payload(cls, payload: object) -> CallsStatsResult:
        """Преобразует статистику звонков."""

        data = _expect_mapping(payload)
        items = [
            CallStats(
                item_id=_int(item, "item_id", "itemId", "id"),
                calls=_int(item, "calls", "total"),
                answered_calls=_int(item, "answered_calls", "answeredCalls"),
                missed_calls=_int(item, "missed_calls", "missedCalls"),
            )
            for item in _list(data, "items", "result", "stats")
        ]
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class ItemStatsRequest:
    """Запрос статистики по объявлениям."""

    item_ids: list[int]
    date_from: str
    date_to: str
    fields: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос статистики."""

        return {
            key: value
            for key, value in {
                "itemIds": self.item_ids,
                "dateFrom": self.date_from,
                "dateTo": self.date_to,
                "fields": self.fields or None,
            }.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class ItemAnalyticsRequest:
    """Запрос расширенной аналитики по объявлениям."""

    date_from: str
    date_to: str
    metrics: list[str]
    grouping: AdAnalyticsGroupingInput
    limit: int
    offset: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос расширенной аналитики."""

        return {
            "dateFrom": self.date_from,
            "dateTo": self.date_to,
            "metrics": self.metrics,
            "grouping": _enum_value(AdAnalyticsGrouping, "grouping", self.grouping),
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(slots=True, frozen=True)
class ListingStats(SerializableModel):
    """Статистические показатели объявления."""

    item_id: int | None
    views: int | None
    contacts: int | None
    favorites: int | None


def _map_item_stat(item: _Payload) -> ListingStats:
    return ListingStats(
        item_id=_int(item, "item_id", "itemId", "id"),
        views=_int(item, "views", "impressions"),
        contacts=_int(item, "contacts", "contacts_total", "contactsTotal"),
        favorites=_int(item, "favorites", "favorites_total", "favoritesTotal"),
    )


@dataclass(slots=True, frozen=True)
class ItemStatsResult(SerializableModel):
    """Статистика по списку объявлений."""

    items: list[ListingStats]

    @classmethod
    def from_payload(cls, payload: object) -> ItemStatsResult:
        """Преобразует статистику по списку объявлений."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_item_stat(item) for item in _list(data, "items", "result", "stats")],
        )


@dataclass(slots=True, frozen=True)
class ItemAnalyticsResult(SerializableModel):
    """Аналитика по профилю или объявлениям."""

    items: list[ListingStats]
    period: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ItemAnalyticsResult:
        """Преобразует расширенную аналитику по объявлениям."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_item_stat(item) for item in _list(data, "items", "result", "stats")],
            period=_str(data, "period"),
        )


@dataclass(slots=True, frozen=True)
class SpendingRecord(SerializableModel):
    """Запись статистики расходов по объявлению."""

    item_id: int | None
    amount: float | None
    service: str | None


@dataclass(slots=True, frozen=True)
class AccountSpendings(SerializableModel):
    """Статистика расходов профиля."""

    items: list[SpendingRecord]
    total: float | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AccountSpendings:
        """Преобразует статистику расходов."""

        data = _expect_mapping(payload)
        items = [
            SpendingRecord(
                item_id=_int(item, "item_id", "itemId", "id"),
                amount=_float(item, "amount", "price", "cost"),
                service=_str(item, "service", "serviceType", "type"),
            )
            for item in _list(data, "items", "result", "spendings")
        ]
        total = _float(data, "total")
        if total is None:
            total = sum(item.amount for item in items if item.amount is not None) or None
        return cls(items=items, total=total)


@dataclass(slots=True, frozen=True)
class SpendingsRequest:
    """Запрос статистики расходов профиля."""

    date_from: str
    date_to: str
    spending_types: list[str]
    grouping: AdSpendingsGroupingInput
    item_ids: list[int] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос статистики расходов."""

        payload: dict[str, object] = {
            "dateFrom": self.date_from,
            "dateTo": self.date_to,
            "spendingTypes": self.spending_types,
            "grouping": _enum_value(AdSpendingsGrouping, "grouping", self.grouping),
        }
        if self.item_ids:
            payload["filter"] = {"itemIDs": self.item_ids}
        return payload


@dataclass(slots=True, frozen=True)
class VasPrice(SerializableModel):
    """Цена и доступность услуги продвижения."""

    code: str | None
    title: str | None
    price: float | None
    is_available: bool | None


@dataclass(slots=True, frozen=True)
class VasPricesRequest:
    """Запрос цен продвижения."""

    item_ids: list[int]
    location_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос цен VAS."""

        return {
            key: value
            for key, value in {
                "itemIds": self.item_ids,
                "locationId": self.location_id,
            }.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class VasPricesResult(SerializableModel):
    """Список цен и доступных услуг продвижения."""

    items: list[VasPrice]

    @classmethod
    def from_payload(cls, payload: object) -> VasPricesResult:
        """Преобразует список доступных услуг продвижения."""

        if isinstance(payload, list):
            items_payload = [item for item in payload if isinstance(item, Mapping)]
        else:
            data = _expect_mapping(payload)
            items_payload = _list(data, "items", "services", "result")
        items = [
            VasPrice(
                code=_str(item, "code", "slug", "type"),
                title=_str(item, "title", "name"),
                price=_float(item, "price", "amount"),
                is_available=_bool(item, "is_available", "isAvailable", "available"),
            )
            for item in items_payload
        ]
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class VasApplyResult(SerializableModel):
    """Результат применения услуг продвижения."""

    success: bool
    status: AdsActionStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> VasApplyResult:
        """Преобразует результат применения продвижения."""

        data = _expect_mapping(payload)
        return cls(
            success=bool(data.get("success", True)),
            status=map_enum_or_unknown(
                _str(data, "status", "result", "message"),
                AdsActionStatus,
                enum_name="ads.action_status",
            ),
        )


@dataclass(slots=True, frozen=True)
class ApplyVasRequest:
    """Запрос применения услуг продвижения."""

    vas_id: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос применения VAS."""

        return {"vas_id": self.vas_id}


@dataclass(slots=True, frozen=True)
class ApplyVasDirectRequest:
    """Запрос применения услуг продвижения через v2 endpoint."""

    slugs: list[str]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос применения VAS v2."""

        return {"slugs": self.slugs}


@dataclass(slots=True, frozen=True)
class ApplyVasPackageRequest:
    """Запрос применения пакета услуг продвижения."""

    package_code: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос применения пакета VAS."""

        return {"package_id": self.package_code}


@dataclass(slots=True, frozen=True)
class AutoloadProfileSettings(SerializableModel):
    """Профиль пользователя автозагрузки."""

    user_id: int | None
    is_enabled: bool | None
    upload_url: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadProfileSettings:
        """Преобразует профиль автозагрузки."""

        data = _expect_mapping(payload)
        return cls(
            user_id=_int(data, "user_id", "userId", "id"),
            is_enabled=_bool(data, "is_enabled", "isEnabled", "enabled"),
            upload_url=_str(data, "upload_url", "uploadUrl", "url"),
        )


@dataclass(slots=True, frozen=True)
class AutoloadProfileUpdateRequest:
    """Запрос сохранения профиля автозагрузки."""

    is_enabled: bool
    report_email: str
    schedule_rate: int
    schedule_weekdays: list[int]
    schedule_time_slots: list[int]
    upload_url: str | None = None
    feed_name: str | None = None
    feed_url: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует изменения профиля."""

        payload: dict[str, object] = {
            "autoload_enabled": self.is_enabled,
            "report_email": self.report_email,
            "schedule": [
                {
                    "rate": self.schedule_rate,
                    "weekdays": list(self.schedule_weekdays),
                    "time_slots": list(self.schedule_time_slots),
                }
            ],
        }
        if self.feed_url is not None:
            payload["feeds_data"] = [
                {"feed_name": self.feed_name or "default", "feed_url": self.feed_url}
            ]
        if self.upload_url is not None:
            payload["upload_url"] = self.upload_url
        return payload


@dataclass(slots=True, frozen=True)
class UploadByUrlRequest:
    """Запрос загрузки файла по ссылке."""

    url: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует ссылку на файл автозагрузки."""

        return {"url": self.url}


@dataclass(slots=True, frozen=True)
class UploadResult(SerializableModel):
    """Результат запуска загрузки файла."""

    success: bool
    report_id: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> UploadResult:
        """Преобразует результат загрузки файла."""

        data = _expect_mapping(payload)
        return cls(
            success=bool(data.get("success", True)),
            report_id=_int(data, "report_id", "reportId", "id"),
        )


@dataclass(slots=True, frozen=True)
class AutoloadField(SerializableModel):
    """Поле категории автозагрузки."""

    slug: str | None
    title: str | None
    type: AutoloadFieldType | None
    required: bool | None


@dataclass(slots=True, frozen=True)
class AutoloadFieldsResult(SerializableModel):
    """Список полей категории автозагрузки."""

    items: list[AutoloadField]

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadFieldsResult:
        """Преобразует список полей категории."""

        data = _expect_mapping(payload)
        items = [
            AutoloadField(
                slug=_str(item, "slug", "code", "id"),
                title=_str(item, "title", "name"),
                type=map_enum_or_unknown(
                    _str(item, "type"),
                    AutoloadFieldType,
                    enum_name="ads.autoload_field_type",
                ),
                required=_bool(item, "required", "is_required", "isRequired"),
            )
            for item in _list(data, "fields", "items", "result")
        ]
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class AutoloadTreeNode(SerializableModel):
    """Узел дерева категорий автозагрузки."""

    slug: str | None
    title: str | None
    children: list[AutoloadTreeNode] = field(default_factory=list)


def _map_tree_node(payload: _Payload) -> AutoloadTreeNode:
    return AutoloadTreeNode(
        slug=_str(payload, "slug", "code", "id"),
        title=_str(payload, "title", "name"),
        children=[_map_tree_node(item) for item in _list(payload, "children", "items")],
    )


@dataclass(slots=True, frozen=True)
class AutoloadTreeResult(SerializableModel):
    """Дерево категорий автозагрузки."""

    items: list[AutoloadTreeNode]

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadTreeResult:
        """Преобразует дерево категорий."""

        data = _expect_mapping(payload)
        items = [_map_tree_node(item) for item in _list(data, "tree", "items", "result")]
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class IdMappingResult(SerializableModel):
    """Сопоставление идентификаторов объявлений."""

    mappings: list[tuple[int | None, int | None]]

    @classmethod
    def from_payload(cls, payload: object) -> IdMappingResult:
        """Преобразует ответ с сопоставлением идентификаторов."""

        data = _expect_mapping(payload)
        mappings: list[tuple[int | None, int | None]] = []
        for item in _list(data, "items", "result", "mappings"):
            mappings.append((_int(item, "ad_id", "adId"), _int(item, "avito_id", "avitoId")))
        return cls(mappings=mappings)


@dataclass(slots=True, frozen=True)
class AutoloadReportSummary(SerializableModel):
    """Краткая информация по отчету автозагрузки."""

    report_id: int | None
    status: AutoloadReportStatus | None
    created_at: datetime | None
    finished_at: datetime | None
    processed_items: int | None


def _map_report_summary(item: _Payload) -> AutoloadReportSummary:
    return AutoloadReportSummary(
        report_id=_int(item, "report_id", "reportId", "id"),
        status=map_enum_or_unknown(
            _str(item, "status"),
            AutoloadReportStatus,
            enum_name="ads.autoload_report_status",
        ),
        created_at=_datetime(item, "created_at", "createdAt"),
        finished_at=_datetime(item, "finished_at", "finishedAt"),
        processed_items=_int(item, "processed_items", "processedItems", "items"),
    )


@dataclass(slots=True, frozen=True)
class AutoloadReportsResult(SerializableModel):
    """Список отчетов автозагрузки."""

    items: list[AutoloadReportSummary]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadReportsResult:
        """Преобразует список отчетов автозагрузки."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_report_summary(item) for item in _list(data, "reports", "items", "result")],
            total=_int(data, "total", "count"),
        )


@dataclass(slots=True, frozen=True)
class AutoloadReportItem(SerializableModel):
    """Объявление внутри отчета автозагрузки."""

    item_id: int | None
    avito_id: int | None
    status: AutoloadItemStatus | None
    title: str | None
    status_detail: AutoloadItemStatusDetail | None = None
    avito_status: AutoloadAvitoStatus | None = None


@dataclass(slots=True, frozen=True)
class AutoloadReportItemsResult(SerializableModel):
    """Список объявлений из отчета автозагрузки."""

    items: list[AutoloadReportItem]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadReportItemsResult:
        """Преобразует список объявлений отчета."""

        data = _expect_mapping(payload)
        items = [
            AutoloadReportItem(
                item_id=_int(item, "item_id", "itemId", "id"),
                avito_id=_int(item, "avito_id", "avitoId"),
                status=map_enum_or_unknown(
                    _str(item, "status"),
                    AutoloadItemStatus,
                    enum_name="ads.autoload_item_status",
                ),
                title=_str(item, "title"),
                status_detail=map_enum_or_unknown(
                    _str(item, "status_detail", "statusDetail"),
                    AutoloadItemStatusDetail,
                    enum_name="ads.autoload_item_status_detail",
                ),
                avito_status=map_enum_or_unknown(
                    _str(item, "avito_status", "avitoStatus"),
                    AutoloadAvitoStatus,
                    enum_name="ads.autoload_avito_status",
                ),
            )
            for item in _list(data, "items", "result")
        ]
        return cls(items=items, total=_int(data, "total", "count"))


@dataclass(slots=True, frozen=True)
class AutoloadFee(SerializableModel):
    """Списание по объявлению в отчете автозагрузки."""

    item_id: int | None
    amount: float | None
    service: str | None


@dataclass(slots=True, frozen=True)
class AutoloadFeesResult(SerializableModel):
    """Списания по объявлениям отчета."""

    items: list[AutoloadFee]
    total: float | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadFeesResult:
        """Преобразует списания по объявлениям отчета."""

        data = _expect_mapping(payload)
        items = [
            AutoloadFee(
                item_id=_int(item, "item_id", "itemId", "id"),
                amount=_float(item, "amount", "price", "cost"),
                service=_str(item, "service", "serviceType", "type"),
            )
            for item in _list(data, "items", "result", "fees")
        ]
        total = _float(data, "total")
        if total is None:
            total = sum(item.amount for item in items if item.amount is not None) or None
        return cls(items=items, total=total)


@dataclass(slots=True, frozen=True)
class AutoloadReportDetails(SerializableModel):
    """Детальная информация по отчету автозагрузки."""

    report_id: int | None
    status: AutoloadReportStatus | None
    created_at: datetime | None
    finished_at: datetime | None
    errors_count: int | None
    warnings_count: int | None

    @classmethod
    def from_payload(cls, payload: object) -> AutoloadReportDetails:
        """Преобразует детализацию отчета автозагрузки."""

        data = _expect_mapping(payload)
        return cls(
            report_id=_int(data, "report_id", "reportId", "id"),
            status=map_enum_or_unknown(
                _str(data, "status"),
                AutoloadReportStatus,
                enum_name="ads.autoload_report_status",
            ),
            created_at=_datetime(data, "created_at", "createdAt"),
            finished_at=_datetime(data, "finished_at", "finishedAt"),
            errors_count=_int(data, "errors_count", "errorsCount"),
            warnings_count=_int(data, "warnings_count", "warningsCount"),
        )


@dataclass(slots=True, frozen=True)
class LegacyAutoloadReport(SerializableModel):
    """Legacy-ответ автозагрузки."""

    report_id: int | None
    status: AutoloadReportStatus | None

    @classmethod
    def from_payload(cls, payload: object) -> LegacyAutoloadReport:
        """Преобразует legacy-ответ отчета автозагрузки."""

        data = _expect_mapping(payload)
        return cls(
            report_id=_int(data, "report_id", "reportId", "id"),
            status=map_enum_or_unknown(
                _str(data, "status"),
                AutoloadReportStatus,
                enum_name="ads.autoload_report_status",
            ),
        )


@dataclass(slots=True, frozen=True)
class AdsActionResult(SerializableModel):
    """Результат мутационной операции ads."""

    success: bool
    message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AdsActionResult:
        """Преобразует ответ мутационной операции ads."""

        if isinstance(payload, Mapping):
            data = cast(_Payload, payload)
            return cls(
                success=bool(data.get("success", True)),
                message=_str(data, "message"),
            )
        return cls(success=True)


__all__ = (
    "AccountSpendings",
    "AdAnalyticsGrouping",
    "AdSpendingsGrouping",
    "AdsActionResult",
    "AdsActionStatus",
    "AdsListResult",
    "ApplyVasPackageRequest",
    "ApplyVasRequest",
    "AutoloadAvitoStatus",
    "AutoloadFee",
    "AutoloadFeesResult",
    "AutoloadField",
    "AutoloadFieldType",
    "AutoloadFieldsResult",
    "AutoloadItemStatus",
    "AutoloadItemStatusDetail",
    "AutoloadProfileSettings",
    "AutoloadProfileUpdateRequest",
    "AutoloadReportDetails",
    "AutoloadReportItem",
    "AutoloadReportItemsResult",
    "AutoloadReportStatus",
    "AutoloadReportSummary",
    "AutoloadReportsResult",
    "AutoloadTreeNode",
    "AutoloadTreeResult",
    "CallStats",
    "CallsStatsRequest",
    "CallsStatsResult",
    "IdMappingResult",
    "ItemAnalyticsResult",
    "ItemStatsRequest",
    "ItemStatsResult",
    "LegacyAutoloadReport",
    "Listing",
    "ListingStats",
    "ListingStatus",
    "SpendingRecord",
    "UpdatePriceRequest",
    "UpdatePriceResult",
    "UploadByUrlRequest",
    "UploadResult",
    "VasApplyResult",
    "VasPrice",
    "VasPricesRequest",
    "VasPricesResult",
)
