"""Типизированные модели раздела realty."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from avito.core import ApiModel, JsonReader, RequestModel
from avito.core.validation import DateInput, serialize_iso_date


class RealtyStatus(str, Enum):
    """Статус сущности realty."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"
    SUCCESS = "success"
    CANCELED = "canceled"
    PENDING = "pending"


class RealtyBookingStatus(str, Enum):
    """Статус бронирования недвижимости."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"
    CANCELED = "canceled"
    PENDING = "pending"


class RealtyOperationStatus(str, Enum):
    """Статус результата операции realty API."""

    UNKNOWN = "__unknown__"
    SUCCESS = "success"


@dataclass(slots=True, frozen=True)
class RealtyActionResult(ApiModel):
    """Результат mutation-операции по недвижимости."""

    success: bool
    status: RealtyOperationStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> RealtyActionResult:
        """Преобразует результат mutation-операции realty."""

        data = JsonReader.expect_mapping(payload)
        reader = JsonReader(payload)
        result = _optional_str_or_int(data, "result")
        status = reader.enum(
            RealtyOperationStatus,
            "result",
            "status",
            unknown=RealtyOperationStatus.UNKNOWN,
        )
        return cls(
            success=result == "success" or bool(data.get("success", False)),
            status=status,
        )


@dataclass(slots=True, frozen=True)
class RealtyBookingsUpdateRequest(RequestModel):
    """Запрос обновления занятости по объекту."""

    blocked_dates: list[DateInput]

    def to_payload(self) -> dict[str, object]:
        """Сериализует JSON payload запроса бронирований."""

        return {
            "bookings": [
                {"date_start": date_value, "date_end": date_value}
                for date_value in (
                    serialize_iso_date(f"blocked_dates[{index}]", blocked_date)
                    for index, blocked_date in enumerate(self.blocked_dates)
                )
            ]
        }


@dataclass(slots=True, frozen=True)
class RealtyBookingSafeDeposit(ApiModel):
    """Информация о предоплате по бронированию."""

    owner_amount: int | None
    tax: int | None
    total_amount: int | None


@dataclass(slots=True, frozen=True)
class RealtyBookingContact(ApiModel):
    """Контактные данные гостя."""

    name: str | None
    email: str | None
    phone: str | None


@dataclass(slots=True, frozen=True)
class RealtyBookingInfo(ApiModel):
    """Информация о бронировании объекта недвижимости."""

    booking_id: int | None
    base_price: int | None
    check_in: str | None
    check_out: str | None
    contact: RealtyBookingContact | None
    guest_count: int | None
    nights: int | None
    safe_deposit: RealtyBookingSafeDeposit | None
    status: RealtyBookingStatus | None

    @classmethod
    def from_payload(cls, payload: object) -> RealtyBookingInfo:
        """Преобразует JSON-объект бронирования в SDK-модель."""

        data = JsonReader.expect_mapping(payload)
        reader = JsonReader(payload)
        contact = reader.mapping("contact")
        safe_deposit = reader.mapping("safe_deposit")
        return cls(
            booking_id=_optional_int(data, "avito_booking_id", "id"),
            base_price=reader.optional_int("base_price"),
            check_in=reader.optional_str("check_in"),
            check_out=reader.optional_str("check_out"),
            contact=(
                RealtyBookingContact(
                    name=JsonReader(contact).optional_str("name"),
                    email=JsonReader(contact).optional_str("email"),
                    phone=JsonReader(contact).optional_str("phone"),
                )
                if contact is not None
                else None
            ),
            guest_count=reader.optional_int("guest_count"),
            nights=reader.optional_int("nights"),
            safe_deposit=(
                RealtyBookingSafeDeposit(
                    owner_amount=JsonReader(safe_deposit).optional_int("owner_amount"),
                    tax=JsonReader(safe_deposit).optional_int("tax"),
                    total_amount=JsonReader(safe_deposit).optional_int("total_amount"),
                )
                if safe_deposit is not None
                else None
            ),
            status=reader.enum(
                RealtyBookingStatus,
                "status",
                unknown=RealtyBookingStatus.UNKNOWN,
            ),
        )


@dataclass(slots=True, frozen=True)
class RealtyBookingsResult(ApiModel):
    """Список бронирований по объявлению."""

    items: list[RealtyBookingInfo]

    @classmethod
    def from_payload(cls, payload: object) -> RealtyBookingsResult:
        """Преобразует список бронирований."""

        reader = JsonReader(payload)
        return cls(
            items=[
                RealtyBookingInfo.from_payload(item)
                for item in reader.list("bookings", "items")
                if isinstance(item, Mapping)
            ],
        )


@dataclass(slots=True, frozen=True)
class RealtyBookingsQuery(RequestModel):
    """Query-параметры запроса бронирований."""

    date_start: str
    date_end: str
    with_unpaid: bool | None = None

    def to_params(self) -> dict[str, object]:
        """Сериализует query-параметры запроса бронирований."""

        params: dict[str, object] = {
            "date_start": self.date_start,
            "date_end": self.date_end,
        }
        if self.with_unpaid is not None:
            params["with_unpaid"] = "true" if self.with_unpaid else "false"
        return params


@dataclass(slots=True, frozen=True)
class RealtyPricePeriod(RequestModel):
    """Период с ценой в запросе обновления цен."""

    date_from: DateInput
    price: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует период с ценой."""

        return {"date_from": serialize_iso_date("date_from", self.date_from), "night_price": self.price}


@dataclass(slots=True, frozen=True)
class RealtyPricesUpdateRequest(RequestModel):
    """Запрос обновления цен по объекту."""

    periods: list[RealtyPricePeriod]

    def to_payload(self) -> dict[str, object]:
        """Сериализует JSON payload запроса цен."""

        return {"prices": [period.to_payload() for period in self.periods]}


@dataclass(slots=True, frozen=True)
class RealtyInterval(RequestModel):
    """Интервал доступности объекта."""

    date: DateInput
    available: bool

    def to_payload(self) -> dict[str, object]:
        """Сериализует интервал доступности."""

        date_value = serialize_iso_date("date", self.date)
        return {
            "date_start": date_value,
            "date_end": date_value,
            "open": 1 if self.available else 0,
        }


@dataclass(slots=True, frozen=True)
class RealtyIntervalsRequest(RequestModel):
    """Запрос заполнения интервалов доступности."""

    item_id: int
    intervals: list[RealtyInterval]

    def to_payload(self) -> dict[str, object]:
        """Сериализует JSON payload запроса интервалов."""

        return {
            "item_id": self.item_id,
            "intervals": [interval.to_payload() for interval in self.intervals],
        }


@dataclass(slots=True, frozen=True)
class RealtyBaseParamsUpdateRequest(RequestModel):
    """Запрос обновления базовых параметров объекта."""

    min_stay_days: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует JSON payload запроса базовых параметров."""

        return {"minimal_duration": self.min_stay_days}


@dataclass(slots=True, frozen=True)
class RealtyMarketPriceInfo(ApiModel):
    """Соответствие цены рыночной стоимости."""

    correspondence: str | None
    error_message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> RealtyMarketPriceInfo:
        """Преобразует соответствие цены рыночной."""

        reader = JsonReader(payload)
        error = reader.mapping("error")
        return cls(
            correspondence=reader.optional_str("correspondence"),
            error_message=JsonReader(error).optional_str("message") if error is not None else None,
        )


@dataclass(slots=True, frozen=True)
class RealtyAnalyticsInfo(ApiModel):
    """Информация об аналитическом отчете по недвижимости."""

    success: bool
    report_link: str | None = None
    error_message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> RealtyAnalyticsInfo:
        """Преобразует ответ аналитического отчета."""

        reader = JsonReader(payload)
        success_mapping = reader.mapping("success") or {}
        success_data = JsonReader(success_mapping).mapping("success") or {}
        errors = JsonReader(success_mapping).mapping("errors") or {}
        result = reader.mapping("result") or {}
        return cls(
            success=bool(success_data) or JsonReader(result).optional_str("result") == "success",
            report_link=JsonReader(success_data).optional_str("reportLink"),
            error_message=JsonReader(errors).optional_str("message"),
        )


def _optional_str_or_int(payload: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _optional_int(payload: Mapping[str, object], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


__all__ = (
    "RealtyActionResult",
    "RealtyAnalyticsInfo",
    "RealtyBaseParamsUpdateRequest",
    "RealtyBookingContact",
    "RealtyBookingInfo",
    "RealtyBookingSafeDeposit",
    "RealtyBookingStatus",
    "RealtyBookingsQuery",
    "RealtyBookingsResult",
    "RealtyBookingsUpdateRequest",
    "RealtyInterval",
    "RealtyIntervalsRequest",
    "RealtyMarketPriceInfo",
    "RealtyOperationStatus",
    "RealtyPricePeriod",
    "RealtyPricesUpdateRequest",
    "RealtyStatus",
)
