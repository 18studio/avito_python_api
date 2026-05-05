"""Типизированные модели раздела autoteka."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from avito.core.enums import map_enum_or_unknown
from avito.core.exceptions import ResponseMappingError
from avito.core.models import ApiModel, RequestModel


class AutotekaStatus(StrEnum):
    """Статус сущности Автотеки."""

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class CatalogResolveRequest(RequestModel):
    """Запрос актуализации параметров автокаталога."""

    brand_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос автокаталога."""

        return {"fieldsValueIds": [{"id": 110000, "valueId": self.brand_id}]}


@dataclass(slots=True, frozen=True)
class LeadsRequest(RequestModel):
    """Запрос событий сервиса Сигнал."""

    subscription_id: int
    limit: int
    last_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос событий Сигнал."""

        payload: dict[str, object] = {"subscriptionId": self.subscription_id}
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.last_id is not None:
            payload["lastId"] = self.last_id
        return payload


@dataclass(slots=True, frozen=True)
class VinRequest(RequestModel):
    """Запрос по VIN."""

    vin: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует VIN-запрос."""

        return {"vin": self.vin}


@dataclass(slots=True, frozen=True)
class VehicleIdRequest(RequestModel):
    """Запрос по идентификатору автомобиля."""

    vehicle_id: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос по vehicle id."""

        return {"vehicleId": self.vehicle_id}


@dataclass(slots=True, frozen=True)
class ItemIdRequest(RequestModel):
    """Запрос по идентификатору объявления."""

    item_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос по item id."""

        return {"itemId": self.item_id}


@dataclass(slots=True, frozen=True)
class ExternalItemPreviewRequest(RequestModel):
    """Запрос превью по внешнему объявлению."""

    item_id: str
    site: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос внешнего объявления."""

        return {"itemId": self.item_id, "site": self.site}


@dataclass(slots=True, frozen=True)
class RegNumberRequest(RequestModel):
    """Запрос по государственному номеру."""

    reg_number: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос по госномеру."""

        return {"regNumber": self.reg_number}


@dataclass(slots=True, frozen=True)
class PlateNumberRequest(RequestModel):
    """Запрос по номерному знаку."""

    plate_number: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос по номерному знаку."""

        return {"plateNumber": self.plate_number}


@dataclass(slots=True, frozen=True)
class PreviewReportRequest(RequestModel):
    """Запрос отчета по preview id."""

    preview_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос отчета по preview id."""

        return {"previewId": self.preview_id}


@dataclass(slots=True, frozen=True)
class MonitoringBucketRequest(RequestModel):
    """Запрос изменения списка мониторинга."""

    vehicles: list[str]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос изменения списка мониторинга."""

        return {"data": list(self.vehicles)}


@dataclass(slots=True, frozen=True)
class MonitoringEventsQuery(RequestModel):
    """Query событий мониторинга."""

    limit: int | None = None

    def to_params(self) -> dict[str, object]:
        """Сериализует query событий мониторинга."""

        params: dict[str, object] = {}
        if self.limit is not None:
            params["limit"] = self.limit
        return params


@dataclass(slots=True, frozen=True)
class TeaserCreateRequest(RequestModel):
    """Запрос создания тизера."""

    vehicle_id: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос создания тизера."""

        return {"vehicleId": self.vehicle_id}


@dataclass(slots=True, frozen=True)
class ValuationBySpecificationRequest(RequestModel):
    """Запрос оценки автомобиля по specification id."""

    specification_id: int
    mileage: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос оценки автомобиля."""

        empty_choice = {"label": "", "valueId": 0}
        return {
            "specification": {
                "brand": {"label": "", "valueId": self.specification_id},
                "model": empty_choice,
                "year": {"label": "", "valueId": self.specification_id},
                "generation": empty_choice,
                "modification": empty_choice,
                "ownersCount": empty_choice,
            },
            "mileage": self.mileage,
        }


@dataclass(slots=True, frozen=True)
class CatalogFieldValue(ApiModel):
    """Значение параметра автокаталога."""

    value_id: str | None
    label: str | None


@dataclass(slots=True, frozen=True)
class CatalogField(ApiModel):
    """Параметр автокаталога."""

    field_id: str | None
    label: str | None
    data_type: str | None
    values: list[CatalogFieldValue]


@dataclass(slots=True, frozen=True)
class CatalogResolveResult(ApiModel):
    """Результат актуализации параметров автокаталога."""

    items: list[CatalogField]

    @classmethod
    def from_payload(cls, payload: object) -> CatalogResolveResult:
        """Преобразует ответ автокаталога."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        return cls(
            items=[
                CatalogField(
                    field_id=_str(item, "id", "fieldId"),
                    label=_str(item, "label"),
                    data_type=_str(item, "dataType", "type"),
                    values=[
                        CatalogFieldValue(
                            value_id=_str(value, "valueId", "id"),
                            label=_str(value, "label", "value"),
                        )
                        for value in _list(item, "values", "items")
                    ],
                )
                for item in _list(result, "fields", "items")
            ],
        )


@dataclass(slots=True, frozen=True)
class AutotekaLeadEvent(ApiModel):
    """Событие сервиса Сигнал."""

    event_id: str | None
    subscription_id: str | None
    vehicle_id: str | None
    item_id: int | None
    brand: str | None
    model: str | None
    price: int | None
    created_at: str | None
    url: str | None


@dataclass(slots=True, frozen=True)
class AutotekaLeadsResult(ApiModel):
    """Список событий сервиса Сигнал."""

    items: list[AutotekaLeadEvent]
    last_id: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaLeadsResult:
        """Преобразует события сервиса Сигнал."""

        data = _expect_mapping(payload)
        pagination = _mapping(data, "pagination")
        items = []
        for item in _list(data, "result", "items"):
            event_payload = _mapping(item, "payload")
            items.append(
                AutotekaLeadEvent(
                    event_id=_str(item, "id"),
                    subscription_id=_str(item, "subscriptionId"),
                    vehicle_id=_str(event_payload, "vin", "vehicleId"),
                    item_id=_int(event_payload, "itemId"),
                    brand=_str(event_payload, "brand"),
                    model=_str(event_payload, "model"),
                    price=_int(event_payload, "price"),
                    created_at=_str(event_payload, "itemCreatedAt"),
                    url=_str(event_payload, "url"),
                )
            )
        return cls(items=items, last_id=_int(pagination, "lastId"))


@dataclass(slots=True, frozen=True)
class MonitoringInvalidVehicle(ApiModel):
    """Невалидный идентификатор авто в запросах мониторинга."""

    vehicle_id: str | None
    description: str | None


@dataclass(slots=True, frozen=True)
class MonitoringBucketResult(ApiModel):
    """Результат изменения списка мониторинга."""

    success: bool
    invalid_vehicles: list[MonitoringInvalidVehicle]

    @classmethod
    def from_payload(cls, payload: object) -> MonitoringBucketResult:
        """Преобразует результат изменения bucket мониторинга."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        return cls(
            success=bool(result.get("isOk", False)),
            invalid_vehicles=[
                MonitoringInvalidVehicle(
                    vehicle_id=_str(item, "vehicleID", "vehicleId"),
                    description=_str(item, "description"),
                )
                for item in _list(result, "invalidVehicles", "items")
            ],
        )


@dataclass(slots=True, frozen=True)
class MonitoringEvent(ApiModel):
    """Событие мониторинга регистрационных действий."""

    vehicle_id: str | None
    brand: str | None
    model: str | None
    year: int | None
    operation_code: int | None
    operation_date_from: str | None
    operation_date_to: str | None
    owner_code: int | None
    actual_at: int | None


@dataclass(slots=True, frozen=True)
class MonitoringEventsResult(ApiModel):
    """Список событий мониторинга."""

    items: list[MonitoringEvent]
    has_next: bool | None = None
    next_cursor: str | None = None
    next_link: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> MonitoringEventsResult:
        """Преобразует события мониторинга."""

        data = _expect_mapping(payload)
        pagination = _mapping(data, "pagination")
        return cls(
            items=[
                MonitoringEvent(
                    vehicle_id=_str(item, "vin", "vehicleId"),
                    brand=_str(item, "brand"),
                    model=_str(item, "model"),
                    year=_int(item, "year"),
                    operation_code=_int(item, "operationCode"),
                    operation_date_from=_str(item, "operationDateFrom", "operationDate"),
                    operation_date_to=_str(item, "operationDateTo"),
                    owner_code=_int(item, "ownerCode"),
                    actual_at=_int(item, "actualAt"),
                )
                for item in _list(data, "data", "items")
            ],
            has_next=_bool(pagination, "hasNext"),
            next_cursor=_str(pagination, "nextCursor"),
            next_link=_str(pagination, "nextLink"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaPackageInfo(ApiModel):
    """Информация о текущем пакете отчетов Автотеки."""

    reports_total: int | None
    reports_remaining: int | None
    created_at: str | None
    expires_at: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaPackageInfo:
        """Преобразует информацию о пакете отчетов."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        package = _mapping(result, "package")
        return cls(
            reports_total=_int(package, "reportsCnt"),
            reports_remaining=_int(package, "reportsCntRemain"),
            created_at=_str(package, "createdTime"),
            expires_at=_str(package, "expireTime"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaPreviewInfo(ApiModel):
    """Информация о превью автомобиля."""

    preview_id: str | None
    status: AutotekaStatus | None
    vehicle_id: str | None
    reg_number: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaPreviewInfo:
        """Преобразует превью автомобиля."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        preview = _mapping(result, "preview")
        source = preview or result or data
        return cls(
            preview_id=_str(source, "previewId"),
            status=_status(source),
            vehicle_id=_str(source, "vin", "vehicleId"),
            reg_number=_str(source, "regNumber", "plateNumber"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaReportInfo(ApiModel):
    """Информация об отчете Автотеки."""

    report_id: str | None
    status: AutotekaStatus | None
    vehicle_id: str | None
    created_at: str | None
    web_link: str | None
    pdf_link: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaReportInfo:
        """Преобразует один отчет Автотеки."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        report = _mapping(result, "report")
        source = report or result or data
        return _map_report_source(source)


@dataclass(slots=True, frozen=True)
class AutotekaReportsResult(ApiModel):
    """Список отчетов Автотеки."""

    items: list[AutotekaReportInfo]

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaReportsResult:
        """Преобразует список отчетов."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_report_source(item) for item in _list(data, "result", "items")],
        )


@dataclass(slots=True, frozen=True)
class AutotekaScoringInfo(ApiModel):
    """Информация о скоринге рисков."""

    scoring_id: str | None
    is_completed: bool | None
    created_at: int | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaScoringInfo:
        """Преобразует ответ скоринга."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        scoring = _mapping(result, "scoring", "risksAssessment")
        source = scoring or result or data
        return cls(
            scoring_id=_str(source, "scoringId"),
            is_completed=_bool(source, "isCompleted"),
            created_at=_int(source, "createdAt"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaSpecificationInfo(ApiModel):
    """Информация о запросе спецификации автомобиля."""

    specification_id: str | None
    status: AutotekaStatus | None
    vehicle_id: str | None
    plate_number: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaSpecificationInfo:
        """Преобразует ответ спецификации."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        specification = _mapping(result, "specification")
        source = specification or result or data
        return cls(
            specification_id=_str(source, "specificationId"),
            status=_status(source),
            vehicle_id=_str(source, "vehicleId"),
            plate_number=_str(source, "plateNumber"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaTeaserInfo(ApiModel):
    """Информация о тизере Автотеки."""

    teaser_id: str | None
    status: AutotekaStatus | None
    brand: str | None = None
    model: str | None = None
    year: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaTeaserInfo:
        """Преобразует ответ тизера."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        teaser_wrapper = _mapping(result, "teaser")
        teaser_data = _mapping(teaser_wrapper, "data") or _mapping(data, "data")
        source = teaser_wrapper or result or data
        return cls(
            teaser_id=_str(source, "teaserId"),
            status=_status(source),
            brand=_str(teaser_data, "brand") if teaser_data else _str(source, "brand"),
            model=_str(teaser_data, "model") if teaser_data else _str(source, "model"),
            year=_int(teaser_data, "year") if teaser_data else _int(source, "year"),
        )


@dataclass(slots=True, frozen=True)
class AutotekaValuationInfo(ApiModel):
    """Оценка стоимости автомобиля."""

    status: AutotekaStatus | None
    vehicle_id: str | None
    brand: str | None
    model: str | None
    year: int | None
    owners_count: str | None
    mileage: int | None
    avg_price_with_condition: int | None
    avg_market_price: int | None

    @classmethod
    def from_payload(cls, payload: object) -> AutotekaValuationInfo:
        """Преобразует ответ оценки автомобиля."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        valuation = _mapping(result, "valuation")
        source = result or data
        return cls(
            status=_status(source),
            vehicle_id=_str(source, "vehicleId"),
            brand=_str(source, "brand"),
            model=_str(source, "model"),
            year=_int(source, "year"),
            owners_count=_str(source, "ownersCount"),
            mileage=_int(source, "mileage"),
            avg_price_with_condition=_int(valuation, "avgPriceWithCondition"),
            avg_market_price=_int(valuation, "avgMarketPrice"),
        )


Payload = dict[str, object]


def _expect_mapping(payload: object) -> Payload:
    if not isinstance(payload, dict):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return cast(Payload, payload)


def _mapping(payload: Payload, *keys: str) -> Payload:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return cast(Payload, value)
    return {}


def _list(payload: Payload, *keys: str) -> list[Payload]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [cast(Payload, item) for item in value if isinstance(item, dict)]
    return []


def _str(payload: Payload, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _int(payload: Payload, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _bool(payload: Payload, *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _status(payload: Payload) -> AutotekaStatus | None:
    return map_enum_or_unknown(
        _str(payload, "status"),
        AutotekaStatus,
        enum_name="autoteka.status",
    )


def _map_report_source(source: Payload) -> AutotekaReportInfo:
    data = _mapping(source, "data")
    return AutotekaReportInfo(
        report_id=_str(source, "reportId"),
        status=_status(source),
        vehicle_id=_str(data, "vin", "vehicleId") or _str(source, "vin"),
        created_at=_str(source, "createdAt") or _str(data, "createdAt"),
        web_link=_str(source, "webLink"),
        pdf_link=_str(source, "pdfLink"),
    )
