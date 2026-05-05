"""Типизированные модели раздела cpa."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum

from avito.core import ApiModel, BinaryResponse, RequestModel
from avito.core.enums import map_int_enum_or_unknown
from avito.core.exceptions import ResponseMappingError

Payload = Mapping[str, object]


class CpaCallStatusId(IntEnum):
    """Числовой статус CPA-звонка."""

    UNKNOWN = -1
    NEW = 0
    ACCEPTED = 1
    REJECTED = 2
    PAID = 3


@dataclass(slots=True, frozen=True)
class CpaChatsByTimeRequest(RequestModel):
    """Запрос списка CPA-чатов по времени."""

    created_at_from: str
    limit: int
    offset: int

    def to_payload(self) -> dict[str, object]:
        return {
            "dateTimeFrom": self.created_at_from,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(slots=True, frozen=True)
class CpaPhonesFromChatsRequest(RequestModel):
    """Запрос телефонов из целевых чатов."""

    date_time_from: str
    limit: int
    offset: int

    def to_payload(self) -> dict[str, object]:
        return {
            "dateTimeFrom": self.date_time_from,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(slots=True, frozen=True)
class CpaCallsByTimeRequest(RequestModel):
    """Запрос списка CPA-звонков по времени."""

    date_time_from: str
    limit: int
    offset: int | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "dateTimeFrom": self.date_time_from,
            "limit": self.limit,
        }
        if self.offset is not None:
            payload["offset"] = self.offset
        return payload


@dataclass(slots=True, frozen=True)
class CpaBalanceInfoRequest(RequestModel):
    """Запрос CPA-баланса со string body по Swagger."""

    def to_payload(self) -> object:
        return "{}"


@dataclass(slots=True, frozen=True)
class CpaCallComplaintRequest(RequestModel):
    """Запрос жалобы на CPA-звонок."""

    call_id: int
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {"callId": self.call_id, "message": self.reason}


@dataclass(slots=True, frozen=True)
class CpaLeadComplaintRequest(RequestModel):
    """Запрос жалобы по action id."""

    action_id: int
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {"actionId": self.action_id, "message": self.reason}


@dataclass(slots=True, frozen=True)
class CpaCallByIdRequest(RequestModel):
    """Запрос получения CPA-звонка по идентификатору."""

    call_id: int

    def to_payload(self) -> dict[str, object]:
        return {"callId": self.call_id}


@dataclass(slots=True, frozen=True)
class CallTrackingCallsRequest(RequestModel):
    """Запрос списка звонков CallTracking."""

    date_time_from: str
    date_time_to: str
    limit: int | None = None
    offset: int | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "dateTimeFrom": self.date_time_from,
            "dateTimeTo": self.date_time_to,
        }
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.offset is not None:
            payload["offset"] = self.offset
        return payload


@dataclass(slots=True, frozen=True)
class CpaErrorInfo(ApiModel):
    """Информация об ошибке CPA API."""

    code: int | None
    message: str | None

    @classmethod
    def from_payload(cls, payload: object) -> CpaErrorInfo:
        """Преобразует payload ошибки CPA API."""

        data = _expect_mapping(payload)
        return cls(code=_int(data, "code"), message=_str(data, "message", "error"))


@dataclass(slots=True, frozen=True)
class CpaActionResult(ApiModel):
    """Результат mutation-операции CPA."""

    success: bool
    error: CpaErrorInfo | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CpaActionResult:
        """Преобразует результат mutation-операции CPA."""

        data = _expect_mapping(payload)
        return cls(
            success=bool(data.get("success", False)),
            error=_map_cpa_error(data.get("error")),
        )


@dataclass(slots=True, frozen=True)
class CpaBalanceInfo(ApiModel):
    """Информация о CPA-балансе пользователя."""

    balance: int | None
    advance: int | None = None
    debt: int | None = None
    error: CpaErrorInfo | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CpaBalanceInfo:
        """Преобразует ответ баланса CPA."""

        data = _expect_mapping(payload)
        return cls(
            balance=_int(data, "balance"),
            advance=_int(data, "advance"),
            debt=_int(data, "debt"),
            error=_map_cpa_error(data.get("error")),
        )


@dataclass(slots=True, frozen=True)
class CpaCallInfo(ApiModel):
    """Информация о звонке CPA."""

    call_id: str | None
    item_id: str | None
    buyer_phone: str | None
    seller_phone: str | None
    virtual_phone: str | None
    status_id: CpaCallStatusId | None
    price: int | None
    duration: int | None
    waiting_duration: float | None
    created_at: str | None
    started_at: str | None
    group_title: str | None
    record_url: str | None
    is_arbitrage_available: bool | None

    @classmethod
    def from_payload(cls, payload: object) -> CpaCallInfo:
        """Преобразует один звонок CPA."""

        data = _expect_mapping(payload)
        call = _mapping(data, "calls", "call")
        return _map_cpa_call(call or data)


@dataclass(slots=True, frozen=True)
class CpaCallsResult(ApiModel):
    """Список звонков CPA."""

    items: list[CpaCallInfo]
    error: CpaErrorInfo | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CpaCallsResult:
        """Преобразует список звонков CPA."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_cpa_call(item) for item in _list(data, "calls", "items", "results")],
            error=_map_cpa_error(data.get("error")),
        )


@dataclass(slots=True, frozen=True)
class CpaChatInfo(ApiModel):
    """Информация о CPA-чате."""

    chat_id: str | None
    action_id: str | None
    item_id: str | None
    item_title: str | None
    buyer_user_id: str | None
    buyer_name: str | None
    created_at: str | None
    updated_at: str | None
    is_arbitrage_available: bool | None

    @classmethod
    def from_payload(cls, payload: object) -> CpaChatInfo:
        """Преобразует один чат CPA."""

        data = _expect_mapping(payload)
        chat = _mapping(data, "chat")
        if chat:
            return _map_cpa_chat(chat)
        return _map_cpa_chat(data)


@dataclass(slots=True, frozen=True)
class CpaChatsResult(ApiModel):
    """Список чатов CPA."""

    items: list[CpaChatInfo]

    @classmethod
    def from_payload(cls, payload: object) -> CpaChatsResult:
        """Преобразует список чатов CPA."""

        data = _expect_mapping(payload)
        return cls(
            items=[_map_cpa_chat(item) for item in _list(data, "chats", "items", "results")],
        )


@dataclass(slots=True, frozen=True)
class CpaPhoneInfo(ApiModel):
    """Информация по телефону, найденному в целевом чате."""

    action_id: str | None
    phone_number: str | None
    created_at: str | None
    price: int | None
    group: str | None
    preview_url: str | None


@dataclass(slots=True, frozen=True)
class CpaPhonesResult(ApiModel):
    """Список телефонных номеров из целевых чатов."""

    items: list[CpaPhoneInfo]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CpaPhonesResult:
        """Преобразует список телефонов из целевых чатов."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                CpaPhoneInfo(
                    action_id=_str(item, "id", "actionId"),
                    phone_number=_str(item, "phone_number", "phoneNumber"),
                    created_at=_str(item, "date", "createdAt"),
                    price=_int(item, "pricePenny", "price"),
                    group=_str(item, "group"),
                    preview_url=_str(item, "url", "previewUrl"),
                )
                for item in _list(data, "results", "items")
            ],
            total=_int(data, "total"),
        )


@dataclass(slots=True, frozen=True)
class CpaAudioRecord:
    """Бинарная запись звонка CPA."""

    binary: BinaryResponse

    @property
    def filename(self) -> str | None:
        """Имя файла записи звонка."""

        return self.binary.filename

    def to_dict(self) -> dict[str, object]:
        """Сериализует бинарную запись без transport-объекта."""

        return {
            "filename": self.binary.filename,
            "content_type": self.binary.content_type,
            "content_base64": b64encode(self.binary.content).decode("ascii"),
        }

    def model_dump(self) -> dict[str, object]:
        return self.to_dict()


@dataclass(slots=True, frozen=True)
class CallTrackingCallInfo(ApiModel):
    """Информация о звонке CallTracking."""

    call_id: str | None
    item_id: str | None
    buyer_phone: str | None
    seller_phone: str | None
    virtual_phone: str | None
    call_time: str | None
    talk_duration: int | None
    waiting_duration: float | None


@dataclass(slots=True, frozen=True)
class CallTrackingCallsResult(ApiModel):
    """Список звонков CallTracking."""

    items: list[CallTrackingCallInfo]
    error: CpaErrorInfo | None = None

    @classmethod
    def from_payload(cls, payload: object) -> CallTrackingCallsResult:
        """Преобразует список звонков CallTracking."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                _map_call_tracking_call(item) for item in _list(data, "calls", "items", "results")
            ],
            error=_map_cpa_error(data.get("error")),
        )


@dataclass(slots=True, frozen=True)
class CallTrackingGetCallByIdRequest(RequestModel):
    """Запрос получения звонка CallTracking по идентификатору."""

    call_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос звонка CallTracking."""

        return {"callId": self.call_id}


@dataclass(slots=True, frozen=True)
class CallTrackingCallResponse(ApiModel):
    """Ответ CallTracking get_call_by_id с объектом звонка и ошибкой."""

    call: CallTrackingCallInfo
    error: CpaErrorInfo

    @classmethod
    def from_payload(cls, payload: object) -> CallTrackingCallResponse:
        """Преобразует один звонок CallTracking."""

        data = _expect_mapping(payload)
        call = _mapping(data, "call")
        error = _map_cpa_error(data.get("error"))
        if not call or error is None:
            raise ResponseMappingError(
                "Ответ CallTracking getCallById должен содержать `call` и `error`.",
                payload=payload,
            )
        return cls(call=_map_call_tracking_call(call), error=error)


@dataclass(slots=True, frozen=True)
class CallTrackingRecord:
    """Бинарная запись звонка CallTracking."""

    binary: BinaryResponse

    @property
    def filename(self) -> str | None:
        """Имя файла записи звонка."""

        return self.binary.filename

    def to_dict(self) -> dict[str, object]:
        """Сериализует бинарную запись без transport-объекта."""

        return {
            "filename": self.binary.filename,
            "content_type": self.binary.content_type,
            "content_base64": b64encode(self.binary.content).decode("ascii"),
        }

    def model_dump(self) -> dict[str, object]:
        return self.to_dict()


def _expect_mapping(payload: object) -> Payload:
    if not isinstance(payload, Mapping):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return payload


def _mapping(payload: Payload, *keys: str) -> Payload:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _list(payload: Payload, *keys: str) -> list[Payload]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
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


def _float(payload: Payload, *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
    return None


def _bool(payload: Payload, *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _cpa_call_status_id(payload: Payload) -> CpaCallStatusId | None:
    return map_int_enum_or_unknown(
        _int(payload, "statusId"),
        CpaCallStatusId,
        enum_name="cpa.call_status_id",
    )


def _map_cpa_error(payload: object | None) -> CpaErrorInfo | None:
    if payload is None:
        return None
    data = _expect_mapping(payload)
    if not data:
        return None
    return CpaErrorInfo.from_payload(data)


def _map_cpa_call(item: Payload) -> CpaCallInfo:
    return CpaCallInfo(
        call_id=_str(item, "id", "callId"),
        item_id=_str(item, "itemId", "item_id"),
        buyer_phone=_str(item, "buyerPhone"),
        seller_phone=_str(item, "sellerPhone"),
        virtual_phone=_str(item, "virtualPhone"),
        status_id=_cpa_call_status_id(item),
        price=_int(item, "price"),
        duration=_int(item, "duration", "talkDuration"),
        waiting_duration=_float(item, "waitingDuration"),
        created_at=_str(item, "createTime", "createdAt", "callTime"),
        started_at=_str(item, "startTime"),
        group_title=_str(item, "groupTitle"),
        record_url=_str(item, "recordUrl"),
        is_arbitrage_available=_bool(item, "isArbitrageAvailable"),
    )


def _map_cpa_chat(item: Payload) -> CpaChatInfo:
    chat = _mapping(item, "chat")
    buyer = _mapping(item, "buyer")
    listing = _mapping(item, "item")
    source = chat or item
    return CpaChatInfo(
        chat_id=_str(source, "id", "chatId"),
        action_id=_str(source, "actionId", "action_id"),
        item_id=_str(listing, "id", "itemId"),
        item_title=_str(listing, "title", "subject"),
        buyer_user_id=_str(buyer, "userId", "id"),
        buyer_name=_str(buyer, "name"),
        created_at=_str(source, "createdAt", "created_at"),
        updated_at=_str(source, "updatedAt", "updated_at"),
        is_arbitrage_available=_bool(item, "isArbitrageAvailable"),
    )


def _map_call_tracking_call(item: Payload) -> CallTrackingCallInfo:
    return CallTrackingCallInfo(
        call_id=_str(item, "callId", "id"),
        item_id=_str(item, "itemId"),
        buyer_phone=_str(item, "buyerPhone"),
        seller_phone=_str(item, "sellerPhone"),
        virtual_phone=_str(item, "virtualPhone"),
        call_time=_str(item, "callTime", "createTime"),
        talk_duration=_int(item, "talkDuration", "duration"),
        waiting_duration=_float(item, "waitingDuration"),
    )


__all__ = (
    "CallTrackingCallInfo",
    "CallTrackingCallResponse",
    "CallTrackingCallsRequest",
    "CallTrackingCallsResult",
    "CallTrackingGetCallByIdRequest",
    "CallTrackingRecord",
    "CpaActionResult",
    "CpaAudioRecord",
    "CpaBalanceInfo",
    "CpaCallByIdRequest",
    "CpaCallComplaintRequest",
    "CpaCallInfo",
    "CpaCallStatusId",
    "CpaCallsByTimeRequest",
    "CpaCallsResult",
    "CpaChatInfo",
    "CpaChatsByTimeRequest",
    "CpaChatsResult",
    "CpaErrorInfo",
    "CpaLeadComplaintRequest",
    "CpaPhoneInfo",
    "CpaPhonesFromChatsRequest",
    "CpaPhonesResult",
)
