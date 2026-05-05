"""Типизированные модели раздела orders."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from avito.core import ApiModel, BinaryResponse
from avito.core.enums import map_enum_or_unknown
from avito.core.exceptions import ResponseMappingError, ValidationError
from avito.core.validation import DateInput, serialize_iso_datetime

Payload = Mapping[str, object]


def _delivery_participant(name: str) -> dict[str, object]:
    return {
        "type": "3PL",
        "phones": ["+79999999999"],
        "email": f"{name}@example.test",
        "name": name,
        "delivery": {
            "type": "SORTING_CENTER",
            "sortingCenter": {
                "provider": "exmail",
                "id": f"{name}-sorting-center",
                "accuracy": "EXACT",
            },
        },
    }


def _parcel_client(name: str) -> dict[str, object]:
    return {
        "type": "PRIVATE",
        "phones": ["+79999999999"],
        "email": f"{name}@example.test",
        "name": name,
        "delivery": {
            "type": "TERMINAL",
            "terminal": {
                "provider": "exmail",
                "id": f"{name}-terminal",
                "accuracy": "EXACT",
            },
        },
    }


class OrderStatus(str, Enum):
    """Статус заказа."""

    UNKNOWN = "__unknown__"
    ON_CONFIRMATION = "on_confirmation"
    READY_TO_SHIP = "ready_to_ship"
    IN_TRANSIT = "in_transit"
    CANCELED = "canceled"
    DELIVERED = "delivered"
    ON_RETURN = "on_return"
    IN_DISPUTE = "in_dispute"
    CLOSED = "closed"
    NEW = "new"
    MARKED = "marked"
    CONFIRMED = "confirmed"
    CODE_VALID = "code-valid"
    RANGE_SET = "range-set"
    TRACKING_SET = "tracking-set"
    RETURN_ACCEPTED = "return-accepted"


class OrderActionStatus(str, Enum):
    """Статус результата операции над заказом."""

    UNKNOWN = "__unknown__"
    MARKED = "marked"
    CONFIRMED = "confirmed"
    CODE_VALID = "code-valid"
    RANGE_SET = "range-set"
    TRACKING_SET = "tracking-set"
    RETURN_ACCEPTED = "return-accepted"
    SUCCESS = "success"
    FAIL = "fail"
    EXPIRED = "expired"
    ATTEMPTS = "attempts"


class OrderTransition(str, Enum):
    """Переход статуса заказа."""

    CONFIRM = "confirm"
    REJECT = "reject"
    PERFORM = "perform"
    RECEIVE = "receive"


class LabelTaskStatus(str, Enum):
    """Статус задачи генерации этикеток."""

    UNKNOWN = "__unknown__"
    CREATED = "created"


class DeliveryOperationStatus(str, Enum):
    """Статус результата операции delivery API."""

    UNKNOWN = "__unknown__"
    ANNOUNCEMENT_CREATED = "announcement-created"
    PARCEL_CREATED = "parcel-created"
    ANNOUNCEMENT_CANCELLED = "announcement-cancelled"
    CALLBACK_ACCEPTED = "callback-accepted"
    PARCELS_UPDATED = "parcels-updated"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    FORBIDDEN = "forbidden"
    OK = "OK"
    OK_LOWER = "ok"


class DeliveryTaskState(str, Enum):
    """Статус фоновой задачи delivery API."""

    UNKNOWN = "__unknown__"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    DECLINED = "declined"
    DONE = "done"


class DeliveryStatus(str, Enum):
    """Legacy-статус операции или задачи delivery API."""

    UNKNOWN = "__unknown__"
    ANNOUNCEMENT_CREATED = "announcement-created"
    PARCEL_CREATED = "parcel-created"
    ANNOUNCEMENT_CANCELLED = "announcement-cancelled"
    CALLBACK_ACCEPTED = "callback-accepted"
    PARCELS_UPDATED = "parcels-updated"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    FORBIDDEN = "forbidden"
    OK = "OK"
    OK_LOWER = "ok"
    PROCESSING = "processing"
    PENDING_APPROVAL = "pending_approval"
    DECLINED = "declined"
    DONE = "done"


class TrackingAvitoStatus(str, Enum):
    """Статус Avito для sandbox tracking-события."""

    UNKNOWN = "__unknown__"
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    ON_DELIVERY = "ON_DELIVERY"
    DELIVERED = "DELIVERED"
    IN_TRANSIT_RETURN = "IN_TRANSIT_RETURN"
    ON_DELIVERY_RETURN = "ON_DELIVERY_RETURN"
    RETURNED = "RETURNED"
    LOST = "LOST"
    DESTROYED = "DESTROYED"


class TrackingAvitoEventType(str, Enum):
    """Тип Avito-события для sandbox tracking."""

    UNKNOWN = "__unknown__"


@dataclass(slots=True, frozen=True)
class DeliveryDateInterval:
    """Интервалы доставки/забора для конкретной даты."""

    date: DateInput
    intervals: list[str]

    def to_payload(self) -> dict[str, object]:
        return {"date": serialize_iso_datetime("date", self.date), "intervals": list(self.intervals)}


@dataclass(slots=True, frozen=True)
class CustomAreaScheduleEntry:
    """Кастомное расписание для списка областей доставки."""

    provider_area_numbers: list[str]
    services: list[str]
    custom_schedule: list[DeliveryDateInterval]
    use_all_areas: bool | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "providerAreaNumber": list(self.provider_area_numbers),
            "services": list(self.services),
            "customSchedule": [entry.to_payload() for entry in self.custom_schedule],
        }
        if self.use_all_areas is not None:
            payload["useAllAreas"] = self.use_all_areas
        return payload


@dataclass(slots=True, frozen=True)
class CustomAreaScheduleRequest:
    """Запрос установки кастомного расписания областей."""

    items: list[CustomAreaScheduleEntry]

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]


@dataclass(slots=True, frozen=True)
class OrderMarkingsRequest:
    """Запрос обновления маркировок заказа."""

    order_id: str
    codes: list[str]

    def to_payload(self) -> dict[str, object]:
        return {"markings": [{"orderId": self.order_id, "markings": list(self.codes)}]}


@dataclass(slots=True, frozen=True)
class OrderAcceptReturnRequest:
    """Запрос подтверждения возврата заказа."""

    order_id: str
    postal_office_id: str

    def to_payload(self) -> dict[str, object]:
        return {"orderId": self.order_id, "terminalNumber": self.postal_office_id}


@dataclass(slots=True, frozen=True)
class OrderApplyTransitionRequest:
    """Запрос перехода заказа в другой статус."""

    order_id: str
    transition: OrderTransition | str

    def to_payload(self) -> dict[str, object]:
        return {
            "orderId": self.order_id,
            "transition": _enum_value(OrderTransition, "transition", self.transition),
        }


@dataclass(slots=True, frozen=True)
class OrderConfirmationCodeRequest:
    """Запрос проверки кода подтверждения заказа."""

    order_id: str
    code: str

    def to_payload(self) -> dict[str, object]:
        return {"parcelID": self.order_id, "confirmCode": self.code}


@dataclass(slots=True, frozen=True)
class OrderCncDetailsRequest:
    """Запрос установки деталей cnc-заказа."""

    order_id: str
    pickup_point_id: str
    booking_period: int = 1

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.order_id,
            "marketplaceId": self.pickup_point_id,
            "bookingPeriod": self.booking_period,
        }


@dataclass(slots=True, frozen=True)
class OrderCourierRangeRequest:
    """Запрос установки интервала курьерской доставки."""

    order_id: str
    interval_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "orderId": self.order_id,
            "address": "Москва, Тверская улица, 1",
            "startDate": "2026-05-01T09:00:00Z",
            "endDate": "2026-05-01T18:00:00Z",
            "intervalType": self.interval_id,
            "phone": "+79999999999",
            "name": "Иван Иванов",
        }


@dataclass(slots=True, frozen=True)
class OrderTrackingNumberRequest:
    """Запрос установки трек-номера."""

    order_id: str
    tracking_number: str

    def to_payload(self) -> dict[str, object]:
        return {"orderId": self.order_id, "trackingNumber": self.tracking_number}


@dataclass(slots=True, frozen=True)
class OrderLabelsRequest:
    """Запрос генерации этикеток."""

    order_ids: list[str]

    def to_payload(self) -> dict[str, object]:
        return {"orderIDs": list(self.order_ids)}


@dataclass(slots=True, frozen=True)
class DeliveryAnnouncementRequest:
    """Запрос создания или отмены анонса доставки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "announcementID": self.order_id,
            "announcementType": "DELIVERY",
            "barcode": "000987654321",
            "date": "2026-05-01T09:00:00Z",
            "packages": [
                {
                    "id": "package-1",
                    "parcels": [{"id": "parcel-1", "barcode": "000012345"}],
                }
            ],
            "receiver": _delivery_participant("receiver"),
            "sender": _delivery_participant("sender"),
        }


@dataclass(slots=True, frozen=True)
class DeliveryCancelAnnouncementRequest:
    """Запрос отмены анонса доставки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        return {"announcementID": self.order_id}


@dataclass(slots=True, frozen=True)
class DeliverySandboxAnnouncementRequest:
    """Запрос создания sandbox-анонса доставки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        payload = DeliveryAnnouncementRequest(order_id=self.order_id).to_payload()
        payload["packages"] = [{"id": "package-1", "parcelIDs": ["parcel-1"]}]
        return payload


@dataclass(slots=True, frozen=True)
class DeliveryAnnouncementTrackRequest:
    """Запрос события sandbox-анонса доставки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "announcementID": self.order_id,
            "date": "2026-05-01T09:00:00Z",
            "event": "ACCEPTANCE_DONE",
        }


@dataclass(slots=True, frozen=True)
class DeliveryParcelRequest:
    """Запрос создания посылки."""

    order_id: str
    parcel_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "orderID": self.order_id,
            "parcelID": self.parcel_id,
            "items": [{"id": 105, "title": "Товар", "cost": 1000, "quantity": 1}],
            "sender": _parcel_client("sender"),
            "receiver": _parcel_client("receiver"),
            "payment": {
                "delivery": {"status": "PAID", "costWithoutVat": 0},
                "items": {"cost": 1000, "status": "PAID"},
            },
        }


@dataclass(slots=True, frozen=True)
class SandboxParcelRequest:
    """Запрос создания sandbox-посылки."""

    order_id: str
    parcel_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "items": [{"quantity": 1}],
            "receiver": {"delivery": {"terminal": {"id": "receiver-terminal"}}},
            "sender": {"delivery": {"terminal": {"id": "sender-terminal"}}},
            "tags": [self.order_id, self.parcel_id],
        }


@dataclass(slots=True, frozen=True)
class DeliveryParcelResultRequest:
    """Запрос передачи результата по посылке."""

    parcel_id: str
    result: str

    def to_payload(self) -> dict[str, object]:
        return {"id": self.parcel_id, "status": self.result}


@dataclass(slots=True, frozen=True)
class CancelParcelRequest:
    """Запрос отмены sandbox-посылки."""

    parcel_id: str
    actor: str

    def to_payload(self) -> dict[str, object]:
        return {"parcelID": self.parcel_id, "actor": self.actor}


@dataclass(slots=True, frozen=True)
class SandboxConfirmationCodeRequest:
    """Запрос проверки кода подтверждения sandbox-заказа."""

    parcel_id: str
    confirm_code: str

    def to_payload(self) -> dict[str, object]:
        return {"parcelID": self.parcel_id, "confirmCode": self.confirm_code}


@dataclass(slots=True, frozen=True)
class DeliveryTerms:
    """Параметры условий доставки заказа."""

    cost: int | None = None
    direct_control_date: DateInput | None = None
    receiver_terminal_code: str | None = None
    return_control_date: DateInput | None = None
    sender_receive_terminal_code: str | None = None
    tough_wrap: bool | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.cost is not None:
            payload["cost"] = self.cost
        if self.direct_control_date is not None:
            payload["directControlDate"] = serialize_iso_datetime(
                "direct_control_date", self.direct_control_date
            )
        if self.receiver_terminal_code is not None:
            payload["receiverTerminalCode"] = self.receiver_terminal_code
        if self.return_control_date is not None:
            payload["returnControlDate"] = serialize_iso_datetime(
                "return_control_date", self.return_control_date
            )
        if self.sender_receive_terminal_code is not None:
            payload["senderReceiveTerminalCode"] = self.sender_receive_terminal_code
        if self.tough_wrap is not None:
            payload["toughWrap"] = self.tough_wrap
        return payload


@dataclass(slots=True, frozen=True)
class OrderDeliveryProperties:
    """Набор параметров доставки sandbox-заказа."""

    delivery: DeliveryTerms | None = None
    dimensions: list[int] | None = None
    weight: int | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.delivery is not None:
            payload["delivery"] = self.delivery.to_payload()
        if self.dimensions is not None:
            payload["dimensions"] = list(self.dimensions)
        if self.weight is not None:
            payload["weight"] = self.weight
        return payload


@dataclass(slots=True, frozen=True)
class SetOrderPropertiesRequest:
    """Запрос установки параметров доставки sandbox-заказа."""

    order_id: str
    properties: OrderDeliveryProperties

    def to_payload(self) -> dict[str, object]:
        return {"orderId": self.order_id, "properties": self.properties.to_payload()}


@dataclass(slots=True, frozen=True)
class RealAddress:
    """Фактический адрес приема или возврата."""

    address_type: str
    terminal_number: str

    def to_payload(self) -> dict[str, object]:
        return {
            "addressType": self.address_type,
            "terminalNumber": self.terminal_number,
        }


@dataclass(slots=True, frozen=True)
class SetOrderRealAddressRequest:
    """Запрос передачи фактического адреса sandbox-заказа."""

    order_id: str
    address: RealAddress

    def to_payload(self) -> dict[str, object]:
        return {"orderId": self.order_id, "address": self.address.to_payload()}


@dataclass(slots=True, frozen=True)
class DeliveryTrackingOptions:
    """Дополнительные поля tracking-события."""

    barcode: str | None = None
    return_barcode: str | None = None
    return_dispatch_number: str | None = None
    return_tracking_number: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.barcode is not None:
            payload["barcode"] = self.barcode
        if self.return_barcode is not None:
            payload["returnBarcode"] = self.return_barcode
        if self.return_dispatch_number is not None:
            payload["returnDispatchNumber"] = self.return_dispatch_number
        if self.return_tracking_number is not None:
            payload["returnTrackingNumber"] = self.return_tracking_number
        return payload


@dataclass(slots=True, frozen=True)
class DeliveryTrackingRequest:
    """Запрос передачи tracking-события sandbox-заказа."""

    order_id: str
    avito_status: TrackingAvitoStatus | str
    avito_event_type: TrackingAvitoEventType | str
    provider_event_code: str
    date: DateInput
    location: str
    comment: str | None = None
    options: DeliveryTrackingOptions | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "orderId": self.order_id,
            "avitoStatus": self.avito_status,
            "avitoEventType": self.avito_event_type,
            "providerEventCode": self.provider_event_code,
            "date": serialize_iso_datetime("date", self.date),
            "location": self.location,
        }
        if self.comment is not None:
            payload["comment"] = self.comment
        if self.options is not None:
            payload["options"] = self.options.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class ProhibitOrderAcceptanceRequest:
    """Запрос запрета приема sandbox-посылки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        return {"orderId": self.order_id}


@dataclass(slots=True, frozen=True)
class DeliveryParcelIdsRequest:
    """Запрос пакетной операции по посылкам."""

    parcel_ids: list[str]

    def to_payload(self) -> dict[str, object]:
        return {
            "type": "changeReceiver",
            "applications": [
                {"id": f"application-{index}", "parcelID": parcel_id}
                for index, parcel_id in enumerate(self.parcel_ids, start=1)
            ],
        }


@dataclass(slots=True, frozen=True)
class SandboxArea:
    """Зона sandbox-доставки."""

    city: str

    def to_payload(self) -> dict[str, object]:
        return {
            "directionTag": self.city,
            "providerAreaNumber": self.city,
            "services": ["delivery"],
            "utcTimezone": "3",
            "zipCodes": ["101000"],
            "restrictions": {
                "maxWeight": 1000,
                "maxDimensions": [10, 10, 10],
                "maxDeclaredCost": 10000,
            },
        }


@dataclass(slots=True, frozen=True)
class DeliveryAddress:
    """Адрес сортировочного центра или терминала."""

    country: str
    region: str
    locality: str
    fias: str
    zip_code: str
    lat: float
    lng: float
    address_row: str | None = None
    building: str | None = None
    floor: int | None = None
    house: str | None = None
    housing: str | None = None
    locality_type: str | None = None
    porch: str | None = None
    room: str | None = None
    street: str | None = None
    sub_region: str | None = None
    sub_region_type: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "country": self.country,
            "region": self.region,
            "locality": self.locality,
            "fias": self.fias,
            "zipCode": self.zip_code,
            "lat": self.lat,
            "lng": self.lng,
        }
        if self.address_row is not None:
            payload["addressRow"] = self.address_row
        if self.building is not None:
            payload["building"] = self.building
        if self.floor is not None:
            payload["floor"] = self.floor
        if self.house is not None:
            payload["house"] = self.house
        if self.housing is not None:
            payload["housing"] = self.housing
        if self.locality_type is not None:
            payload["localityType"] = self.locality_type
        if self.porch is not None:
            payload["porch"] = self.porch
        if self.room is not None:
            payload["room"] = self.room
        if self.street is not None:
            payload["street"] = self.street
        if self.sub_region is not None:
            payload["subRegion"] = self.sub_region
        if self.sub_region_type is not None:
            payload["subRegionType"] = self.sub_region_type
        return payload


@dataclass(slots=True, frozen=True)
class DeliveryRestriction:
    """Ограничения терминала или сортировочного центра."""

    max_weight: int
    max_dimensions: list[int]
    max_declared_cost: int
    dimensional_factor: int | None = None
    max_dimensional_weight: int | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "maxWeight": self.max_weight,
            "maxDimensions": list(self.max_dimensions),
            "maxDeclaredCost": self.max_declared_cost,
        }
        if self.dimensional_factor is not None:
            payload["dimensionalFactor"] = self.dimensional_factor
        if self.max_dimensional_weight is not None:
            payload["maxDimensionalWeight"] = self.max_dimensional_weight
        return payload


@dataclass(slots=True, frozen=True)
class WeeklySchedule:
    """Недельное расписание работы."""

    mon: list[str]
    tue: list[str]
    wed: list[str]
    thu: list[str]
    fri: list[str]
    sat: list[str]
    sun: list[str]

    def to_payload(self) -> dict[str, object]:
        return {
            "mon": list(self.mon),
            "tue": list(self.tue),
            "wed": list(self.wed),
            "thu": list(self.thu),
            "fri": list(self.fri),
            "sat": list(self.sat),
            "sun": list(self.sun),
        }


@dataclass(slots=True, frozen=True)
class SortingCenterUpload:
    """Сортировочный центр для загрузки в sandbox delivery API."""

    delivery_provider_id: str
    name: str
    address: DeliveryAddress
    phones: list[str]
    itinerary: str
    photos: list[str]
    schedule: WeeklySchedule
    restriction: DeliveryRestriction
    direction_tag: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "deliveryProviderId": self.delivery_provider_id,
            "name": self.name,
            "address": self.address.to_payload(),
            "phones": list(self.phones),
            "itinerary": self.itinerary,
            "photos": list(self.photos),
            "schedule": self.schedule.to_payload(),
            "restriction": self.restriction.to_payload(),
        }
        return payload


@dataclass(slots=True, frozen=True)
class AddSortingCentersRequest:
    """Запрос загрузки сортировочных центров."""

    items: list[SortingCenterUpload]

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]


@dataclass(slots=True, frozen=True)
class TaggedSortingCenter:
    """Тэг для сортировочного центра."""

    delivery_provider_id: str
    direction_tag: str

    def to_payload(self) -> dict[str, object]:
        return {
            "deliveryProviderId": {
                "deliveryProviderId": self.delivery_provider_id,
                "provider": "exmail",
            },
            "directionTag": self.direction_tag,
        }


@dataclass(slots=True, frozen=True)
class TaggedSortingCentersRequest:
    """Запрос установки тэгов сортировочным центрам."""

    items: list[TaggedSortingCenter]

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]


@dataclass(slots=True, frozen=True)
class TerminalUpload:
    """Терминал для загрузки в sandbox delivery API."""

    delivery_provider_id: str
    name: str
    address: DeliveryAddress
    phones: list[str]
    itinerary: str
    photos: list[str]
    direction_tag: str
    services: list[str]
    schedule: WeeklySchedule
    restriction: DeliveryRestriction
    display_name: str | None = None
    options: list[str] | None = None
    terminal_type: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "deliveryProviderId": self.delivery_provider_id,
            "name": self.name,
            "address": self.address.to_payload(),
            "phones": list(self.phones),
            "itinerary": self.itinerary,
            "photos": list(self.photos),
            "directionTag": self.direction_tag,
            "services": list(self.services),
            "schedule": self.schedule.to_payload(),
            "restriction": self.restriction.to_payload(),
        }
        if self.display_name is not None:
            payload["displayName"] = self.display_name
        if self.options is not None:
            payload["options"] = list(self.options)
        if self.terminal_type is not None:
            payload["type"] = self.terminal_type
        return payload


@dataclass(slots=True, frozen=True)
class AddTerminalsRequest:
    """Запрос загрузки терминалов."""

    items: list[TerminalUpload]

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]


@dataclass(slots=True, frozen=True)
class DeliveryTermsZone:
    """Зона сроков доставки."""

    delivery_provider_zone_id: str | None = None
    min_term: int | None = None
    max_term: int | None = None
    name: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.delivery_provider_zone_id is not None:
            payload["deliveryProviderZoneId"] = self.delivery_provider_zone_id
        if self.min_term is not None:
            payload["minTerm"] = self.min_term
        if self.max_term is not None:
            payload["maxTerm"] = self.max_term
        if self.name is not None:
            payload["name"] = self.name
        return payload


@dataclass(slots=True, frozen=True)
class UpdateTermsRequest:
    """Запрос обновления сроков по тарифу."""

    items: list[DeliveryTermsZone]

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]


@dataclass(slots=True, frozen=True)
class DeliveryDirectionZone:
    """Условия доставки внутри направления тарифа."""

    tariff_zone_id: str | None = None
    terms_zone_id: str | None = None
    type: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.tariff_zone_id is not None:
            payload["tariffZoneId"] = self.tariff_zone_id
        if self.terms_zone_id is not None:
            payload["termsZoneId"] = self.terms_zone_id
        if self.type is not None:
            payload["type"] = self.type
        return payload


@dataclass(slots=True, frozen=True)
class DeliveryDirection:
    """Направление доставки в тарифе."""

    provider_direction_id: str
    tag_from: str
    tag_to: str
    zones: list[DeliveryDirectionZone]

    def to_payload(self) -> dict[str, object]:
        return {
            "providerDirectionId": self.provider_direction_id,
            "tagFrom": self.tag_from,
            "tagTo": self.tag_to,
            "zones": [zone.to_payload() for zone in self.zones],
        }


@dataclass(slots=True, frozen=True)
class DeliveryTariffValue:
    """Значение внутри модели расчета тарифной зоны."""

    cost: int | None = None
    max_weight: int | None = None
    dimensional_factor: int | None = None
    max_declared_cost: int | None = None
    percent: float | None = None
    min_cost: int | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.cost is not None:
            payload["cost"] = self.cost
        if self.max_weight is not None:
            payload["maxWeight"] = self.max_weight
        if self.dimensional_factor is not None:
            payload["dimensionalFactor"] = self.dimensional_factor
        if self.max_declared_cost is not None:
            payload["maxDeclaredCost"] = self.max_declared_cost
        if self.percent is not None:
            payload["percent"] = self.percent
        if self.min_cost is not None:
            payload["minCost"] = self.min_cost
        return payload


@dataclass(slots=True, frozen=True)
class DeliveryTariffItem:
    """Модель расчета стоимости услуги в тарифной зоне."""

    calculation_mechanic: str
    chargeable_parameter: str
    service_name: str
    values: list[DeliveryTariffValue]

    def to_payload(self) -> dict[str, object]:
        return {
            "calculationMechanic": self.calculation_mechanic,
            "chargeableParameter": self.chargeable_parameter,
            "serviceName": self.service_name,
            "values": [value.to_payload() for value in self.values],
        }


@dataclass(slots=True, frozen=True)
class DeliveryTariffZone:
    """Тарифная зона доставки."""

    name: str
    delivery_provider_zone_id: str
    items: list[DeliveryTariffItem]

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "deliveryProviderZoneId": self.delivery_provider_zone_id,
            "items": [item.to_payload() for item in self.items],
        }


@dataclass(slots=True, frozen=True)
class AddTariffV2Request:
    """Запрос загрузки тарифа sandbox delivery API."""

    name: str
    delivery_provider_tariff_id: str
    directions: list[DeliveryDirection]
    tariff_zones: list[DeliveryTariffZone]
    terms_zones: list[DeliveryTermsZone]
    tariff_type: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "deliveryProviderTariffId": self.delivery_provider_tariff_id,
            "directions": [direction.to_payload() for direction in self.directions],
            "tariffZones": [zone.to_payload() for zone in self.tariff_zones],
            "termsZones": [zone.to_payload() for zone in self.terms_zones],
        }
        if self.tariff_type is not None:
            payload["tariffType"] = self.tariff_type
        return payload


@dataclass(slots=True, frozen=True)
class SandboxCancelAnnouncementOptions:
    """Опции отмены тестового анонса."""

    url_to_cancel_announcement: str

    def to_payload(self) -> dict[str, object]:
        return {"urlToCancelAnnouncement": self.url_to_cancel_announcement}


@dataclass(slots=True, frozen=True)
class SandboxCancelAnnouncementRequest:
    """Запрос отмены тестового анонса."""

    announcement_id: str
    date: DateInput
    options: SandboxCancelAnnouncementOptions

    def to_payload(self) -> dict[str, object]:
        return {
            "announcementID": self.announcement_id,
            "date": serialize_iso_datetime("date", self.date),
            "options": self.options.to_payload(),
        }


@dataclass(slots=True, frozen=True)
class CancelSandboxParcelOptions:
    """Опции отмены тестовой посылки."""

    cancelation_url: str

    def to_payload(self) -> dict[str, object]:
        return {"cancelationUrl": self.cancelation_url}


@dataclass(slots=True, frozen=True)
class CancelSandboxParcelRequest:
    """Запрос отмены тестовой посылки."""

    parcel_id: str
    options: CancelSandboxParcelOptions | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"parcelID": self.parcel_id}
        if self.options is not None:
            payload["options"] = self.options.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class ChangeParcelApplication:
    """Изменяемые данные по посылке."""

    kind: str | None = None
    name: str | None = None
    phones: list[str] | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.kind is not None:
            payload["kind"] = self.kind
        if self.name is not None:
            payload["name"] = self.name
        if self.phones is not None:
            payload["phones"] = list(self.phones)
        return payload


@dataclass(slots=True, frozen=True)
class ChangeParcelOptions:
    """Опции создания заявки на изменение посылки."""

    change_parcel_url: str

    def to_payload(self) -> dict[str, object]:
        return {"changeParcelUrl": self.change_parcel_url}


@dataclass(slots=True, frozen=True)
class ChangeParcelRequest:
    """Запрос создания заявки на изменение тестовой посылки."""

    type: str
    parcel_id: str
    application: ChangeParcelApplication | None = None
    options: ChangeParcelOptions | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"type": self.type, "parcelID": self.parcel_id}
        if self.application is not None:
            payload["application"] = self.application.to_payload()
        if self.options is not None:
            payload["options"] = self.options.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class SandboxCreateAnnouncementOptions:
    """Опции создания тестового анонса."""

    url_to_send_announcement: str

    def to_payload(self) -> dict[str, object]:
        return {"urlToSendAnnouncement": self.url_to_send_announcement}


@dataclass(slots=True, frozen=True)
class SandboxDeliveryPoint:
    """Точка отправки или приема в тестовом анонсе."""

    provider: str
    point_id: str | None = None
    accuracy: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"provider": self.provider}
        if self.point_id is not None:
            payload["id"] = self.point_id
        if self.accuracy is not None:
            payload["accuracy"] = self.accuracy
        return payload


@dataclass(slots=True, frozen=True)
class SandboxAnnouncementDelivery:
    """Логистическая точка участника тестового анонса."""

    type: str
    terminal: SandboxDeliveryPoint | None = None
    sorting_center: SandboxDeliveryPoint | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"type": self.type}
        if self.terminal is not None:
            payload["terminal"] = self.terminal.to_payload()
        if self.sorting_center is not None:
            payload["sortingCenter"] = self.sorting_center.to_payload()
        return payload


@dataclass(slots=True, frozen=True)
class SandboxAnnouncementParticipant:
    """Участник тестового анонса."""

    type: str
    phones: list[str]
    email: str
    name: str
    delivery: SandboxAnnouncementDelivery

    def to_payload(self) -> dict[str, object]:
        return {
            "type": self.type,
            "phones": list(self.phones),
            "email": self.email,
            "name": self.name,
            "delivery": self.delivery.to_payload(),
        }


@dataclass(slots=True, frozen=True)
class SandboxAnnouncementPackage:
    """Грузоместо в тестовом анонсе."""

    package_id: str
    parcel_ids: list[str]
    seal_id: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.package_id,
            "parcelIDs": list(self.parcel_ids),
        }
        if self.seal_id is not None:
            payload["sealID"] = self.seal_id
        return payload


@dataclass(slots=True, frozen=True)
class SandboxCreateAnnouncementRequest:
    """Запрос создания тестового анонса."""

    announcement_id: str
    barcode: str
    sender: SandboxAnnouncementParticipant
    receiver: SandboxAnnouncementParticipant
    announcement_type: str
    date: DateInput
    packages: list[SandboxAnnouncementPackage]
    options: SandboxCreateAnnouncementOptions

    def to_payload(self) -> dict[str, object]:
        return {
            "announcementID": self.announcement_id,
            "barcode": self.barcode,
            "sender": self.sender.to_payload(),
            "receiver": self.receiver.to_payload(),
            "announcementType": self.announcement_type,
            "date": serialize_iso_datetime("date", self.date),
            "packages": [package.to_payload() for package in self.packages],
            "options": self.options.to_payload(),
        }


@dataclass(slots=True, frozen=True)
class SandboxGetAnnouncementEventRequest:
    """Запрос последнего события тестового анонса."""

    announcement_id: str

    def to_payload(self) -> dict[str, object]:
        return {"announcementID": self.announcement_id}


@dataclass(slots=True, frozen=True)
class GetChangeParcelInfoRequest:
    """Запрос информации о заявке на изменение посылки."""

    application_id: str

    def to_payload(self) -> dict[str, object]:
        return {"applicationID": self.application_id}


@dataclass(slots=True, frozen=True)
class GetSandboxParcelInfoRequest:
    """Запрос информации о тестовой посылке."""

    parcel_id: str

    def to_payload(self) -> dict[str, object]:
        return {"parcelID": self.parcel_id}


@dataclass(slots=True, frozen=True)
class GetRegisteredParcelIdRequest:
    """Запрос ID зарегистрированной тестовой посылки."""

    order_id: str

    def to_payload(self) -> dict[str, object]:
        return {"orderID": self.order_id}


@dataclass(slots=True, frozen=True)
class SandboxAreasRequest:
    """Запрос добавления зон sandbox-доставки."""

    areas: list[SandboxArea]

    def to_payload(self) -> list[dict[str, object]]:
        return [area.to_payload() for area in self.areas]


@dataclass(slots=True, frozen=True)
class StockInfoRequest:
    """Запрос текущих остатков."""

    item_ids: list[int]
    strong_consistency: bool | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"item_ids": list(self.item_ids)}
        if self.strong_consistency is not None:
            payload["strong_consistency"] = self.strong_consistency
        return payload


@dataclass(slots=True, frozen=True)
class StockUpdateEntry:
    """Остаток по одному объявлению."""

    item_id: int
    quantity: int

    def to_payload(self) -> dict[str, object]:
        return {"item_id": self.item_id, "quantity": self.quantity}


@dataclass(slots=True, frozen=True)
class StockUpdateRequest:
    """Запрос обновления остатков."""

    stocks: list[StockUpdateEntry]

    def to_payload(self) -> dict[str, object]:
        return {"stocks": [stock.to_payload() for stock in self.stocks]}


def _expect_mapping(payload: object) -> Payload:
    if not isinstance(payload, Mapping):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return cast(Payload, payload)


def _list(payload: Payload, *keys: str) -> list[Payload]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _mapping(payload: Payload, *keys: str) -> Payload:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return cast(Payload, value)
    return {}


def _str(payload: Payload, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
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


def _extract_errors(payload: Payload) -> list[str]:
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    return [str(error) for error in errors if isinstance(error, str)]


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


@dataclass(slots=True, frozen=True)
class OrderSummary(ApiModel):
    """Краткая информация о заказе."""

    order_id: str | None
    status: OrderStatus | None
    created_at: str | None
    buyer_name: str | None
    total_price: int | None


@dataclass(slots=True, frozen=True)
class OrdersResult(ApiModel):
    """Список заказов."""

    items: list[OrderSummary]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> OrdersResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                OrderSummary(
                    order_id=_str(item, "id", "order_id", "orderId"),
                    status=map_enum_or_unknown(
                        _str(item, "status"),
                        OrderStatus,
                        enum_name="orders.order_status",
                    ),
                    created_at=_str(item, "created", "created_at", "createdAt"),
                    buyer_name=_str(_mapping(item, "buyerInfo"), "fullName"),
                    total_price=_int(item, "totalPrice", "price"),
                )
                for item in _list(data, "orders", "items", "result")
            ],
            total=_int(data, "total", "count"),
        )


@dataclass(slots=True, frozen=True)
class OrderActionResult(ApiModel):
    """Результат операции над заказом."""

    success: bool
    order_id: str | None = None
    status: OrderActionStatus | None = None
    message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> OrderActionResult:
        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        source = result or data
        return cls(
            success=bool(source.get("success", data.get("success", True))),
            order_id=_str(source, "orderId", "order_id", "id"),
            status=map_enum_or_unknown(
                _str(source, "status"),
                OrderActionStatus,
                enum_name="orders.order_action_status",
            ),
            message=_str(source, "message"),
        )


@dataclass(slots=True, frozen=True)
class CourierRange(ApiModel):
    """Доступный интервал курьерской доставки."""

    interval_id: str | None
    date: str | None
    start_at: str | None
    end_at: str | None


@dataclass(slots=True, frozen=True)
class CourierRangesResult(ApiModel):
    """Список доступных интервалов курьерской доставки."""

    items: list[CourierRange]
    address: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CourierRangesResult:
        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        source = result or data
        return cls(
            items=[
                CourierRange(
                    interval_id=_str(item, "id", "intervalId"),
                    date=_str(item, "date"),
                    start_at=_str(item, "startAt", "startDate"),
                    end_at=_str(item, "endAt", "endDate"),
                )
                for item in _list(source, "timeIntervals", "intervals", "items", "result")
            ],
            address=_str(source, "address"),
        )


@dataclass(slots=True, frozen=True)
class LabelTaskResult(ApiModel):
    """Результат генерации этикеток."""

    task_id: str | None
    status: LabelTaskStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> LabelTaskResult:
        data = _expect_mapping(payload)
        result = _mapping(data, "result", "data")
        source = result or data
        task_id = _str(source, "taskId", "taskID", "id")
        task_int = _int(source, "taskId", "taskID")
        return cls(
            task_id=task_id or (str(task_int) if task_int is not None else None),
            status=map_enum_or_unknown(
                _str(source, "status"),
                LabelTaskStatus,
                enum_name="orders.label_task_status",
            ),
        )


@dataclass(slots=True, frozen=True)
class LabelPdfResult:
    """PDF-этикетка заказа."""

    binary: BinaryResponse

    @property
    def filename(self) -> str | None:
        """Имя PDF-файла."""

        return self.binary.filename

    def to_dict(self) -> dict[str, object]:
        """Сериализует бинарный результат без transport-объекта."""

        return {
            "filename": self.binary.filename,
            "content_type": self.binary.content_type,
            "content_base64": b64encode(self.binary.content).decode("ascii"),
        }

    def model_dump(self) -> dict[str, object]:
        return self.to_dict()


@dataclass(slots=True, frozen=True)
class DeliveryEntityResult(ApiModel):
    """Результат операции delivery API."""

    success: bool
    task_id: str | None = None
    order_id: str | None = None
    parcel_id: str | None = None
    status: DeliveryOperationStatus | None = None
    message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> DeliveryEntityResult:
        data = _expect_mapping(payload)
        result = _mapping(data, "result", "data")
        source = result or data
        task_id = _str(source, "taskId", "taskID")
        task_int = _int(source, "taskId", "taskID")
        return cls(
            success=bool(source.get("success", data.get("success", True))),
            task_id=task_id or (str(task_int) if task_int is not None else None),
            order_id=_str(source, "orderId", "orderID"),
            parcel_id=_str(source, "parcelId", "parcelID"),
            status=map_enum_or_unknown(
                _str(source, "status"),
                DeliveryOperationStatus,
                enum_name="orders.delivery_operation_status",
            ),
            message=_str(_mapping(data, "error"), "message") or _str(source, "message"),
        )


@dataclass(slots=True, frozen=True)
class DeliverySortingCenter(ApiModel):
    """Сортировочный центр доставки."""

    sorting_center_id: str | None
    name: str | None
    city: str | None


@dataclass(slots=True, frozen=True)
class DeliverySortingCentersResult(ApiModel):
    """Список сортировочных центров доставки."""

    items: list[DeliverySortingCenter]

    @classmethod
    def from_payload(cls, payload: object) -> DeliverySortingCentersResult:
        data = _expect_mapping(payload)
        result = _mapping(data, "result", "data")
        source = result or data
        return cls(
            items=[
                DeliverySortingCenter(
                    sorting_center_id=_str(item, "id", "sortingCenterId", "sorting_center_id"),
                    name=_str(item, "name"),
                    city=_str(item, "city"),
                )
                for item in _list(source, "sortingCenters", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class DeliveryTaskInfo(ApiModel):
    """Информация о задаче доставки."""

    task_id: str | None
    status: DeliveryTaskState | None
    error: str | None

    @classmethod
    def from_payload(cls, payload: object) -> DeliveryTaskInfo:
        data = _expect_mapping(payload)
        result = _mapping(data, "result", "data")
        source = result or data
        task_id = _str(source, "taskId", "taskID", "id")
        task_int = _int(source, "taskId", "taskID")
        return cls(
            task_id=task_id or (str(task_int) if task_int is not None else None),
            status=map_enum_or_unknown(
                _str(source, "status"),
                DeliveryTaskState,
                enum_name="orders.delivery_task_state",
            ),
            error=_str(_mapping(data, "error"), "message") or _str(source, "error"),
        )


@dataclass(slots=True, frozen=True)
class StockInfo(ApiModel):
    """Информация по остаткам объявления."""

    item_id: int | None
    quantity: int | None
    is_multiple: bool | None
    is_unlimited: bool | None
    is_out_of_stock: bool | None


@dataclass(slots=True, frozen=True)
class StockInfoResult(ApiModel):
    """Список текущих остатков."""

    items: list[StockInfo]

    @classmethod
    def from_payload(cls, payload: object) -> StockInfoResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                StockInfo(
                    item_id=_int(item, "item_id", "itemId"),
                    quantity=_int(item, "quantity"),
                    is_multiple=_bool(item, "is_multiple", "isMultiple"),
                    is_unlimited=_bool(item, "is_unlimited", "isUnlimited"),
                    is_out_of_stock=_bool(item, "is_out_of_stock", "isOutOfStock"),
                )
                for item in _list(data, "stocks", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class StockUpdateItem(ApiModel):
    """Результат обновления остатков объявления."""

    item_id: int | None
    external_id: str | None
    success: bool
    errors: list[str]


@dataclass(slots=True, frozen=True)
class StockUpdateResult(ApiModel):
    """Результат изменения остатков."""

    items: list[StockUpdateItem]

    @classmethod
    def from_payload(cls, payload: object) -> StockUpdateResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                StockUpdateItem(
                    item_id=_int(item, "item_id", "itemId"),
                    external_id=_str(item, "external_id", "externalId"),
                    success=bool(item.get("success", True)),
                    errors=_extract_errors(item),
                )
                for item in _list(data, "stocks", "items", "result")
            ],
        )
