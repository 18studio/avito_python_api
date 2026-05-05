"""Типизированные модели раздела messenger."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import BinaryIO

from avito.core import ApiModel, RequestModel
from avito.core.exceptions import ResponseMappingError

Payload = Mapping[str, object]


class MessageDirection(str, Enum):
    """Направление сообщения."""

    UNKNOWN = "__unknown__"
    IN = "in"
    OUT = "out"


class MessageType(str, Enum):
    """Тип сообщения."""

    UNKNOWN = "__unknown__"
    TEXT = "text"
    IMAGE = "image"


class MessageActionStatus(str, Enum):
    """Статус операции с сообщением или чатом."""

    UNKNOWN = "__unknown__"
    SENT = "sent"
    CONFIRMED = "confirmed"


class SubscriptionStatus(str, Enum):
    """Статус webhook-подписки."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"


class WebhookStatus(str, Enum):
    """Статус действия с webhook."""

    UNKNOWN = "__unknown__"
    SUBSCRIBED = "subscribed"
    CONFIRMED = "confirmed"


class SpecialOfferCampaignStatus(str, Enum):
    """Статус кампании спецпредложений."""

    UNKNOWN = "__unknown__"
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    NOT_CREATED = "notCreated"
    CREATED = "created"


class SpecialOfferDispatchStatus(str, Enum):
    """Статус рассылки спецпредложений."""

    UNKNOWN = "__unknown__"
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    NOT_CREATED = "notCreated"
    CREATED = "created"


@dataclass(slots=True, frozen=True)
class ChatInfo(ApiModel):
    """Информация о чате."""

    chat_id: str | None
    user_id: int | None
    title: str | None
    unread_count: int | None
    last_message_text: str | None

    @classmethod
    def from_payload(cls, payload: object) -> ChatInfo:
        """Преобразует объект чата в SDK-модель."""

        data = _expect_mapping(payload)
        last_message = data.get("last_message")
        last_message_data = last_message if isinstance(last_message, Mapping) else {}
        return cls(
            chat_id=_str(data, "id", "chat_id", "chatId"),
            user_id=_int(data, "user_id", "userId"),
            title=_str(data, "title", "name"),
            unread_count=_int(data, "unread_count", "unreadCount"),
            last_message_text=_str(last_message_data, "text", "message"),
        )


@dataclass(slots=True, frozen=True)
class ChatsResult(ApiModel):
    """Список чатов."""

    items: list[ChatInfo]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ChatsResult:
        """Преобразует список чатов в SDK-модель."""

        data = _expect_mapping(payload)
        return cls(
            items=[ChatInfo.from_payload(item) for item in _list(data, "chats", "items", "result")],
            total=_int(data, "total", "count"),
        )


@dataclass(slots=True, frozen=True)
class SendMessageRequest(RequestModel):
    """Запрос отправки текстового сообщения."""

    message: str
    type: MessageType | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует сообщение для API."""

        return {
            key: value
            for key, value in {
                "message": {"text": self.message},
                "type": (self.type or MessageType.TEXT).value,
            }.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class SendImageMessageRequest(RequestModel):
    """Запрос отправки сообщения с изображением."""

    image_id: str
    caption: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует сообщение с изображением."""

        return {
            key: value
            for key, value in {"image_id": self.image_id, "caption": self.caption}.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class MessageInfo(ApiModel):
    """Информация о сообщении чата."""

    message_id: str | None
    chat_id: str | None
    author_id: int | None
    text: str | None
    created_at: datetime | None
    direction: MessageDirection | None
    type: MessageType | None

    @classmethod
    def from_payload(cls, payload: object) -> MessageInfo:
        """Преобразует сообщение в SDK-модель."""

        data = _expect_mapping(payload)
        return cls(
            message_id=_str(data, "id", "message_id", "messageId"),
            chat_id=_str(data, "chat_id", "chatId"),
            author_id=_int(data, "author_id", "authorId", "user_id", "userId"),
            text=_str(data, "text", "message"),
            created_at=_datetime(data, "created_at", "createdAt"),
            direction=_enum(MessageDirection, _str(data, "direction")),
            type=_enum(MessageType, _str(data, "type")),
        )


@dataclass(slots=True, frozen=True)
class MessagesResult(ApiModel):
    """Список сообщений чата."""

    items: list[MessageInfo]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> MessagesResult:
        """Преобразует список сообщений в SDK-модель."""

        if isinstance(payload, list):
            return cls(
                items=[
                    MessageInfo.from_payload(item)
                    for item in payload
                    if isinstance(item, Mapping)
                ]
            )

        data = _expect_mapping(payload)
        return cls(
            items=[
                MessageInfo.from_payload(item)
                for item in _list(data, "messages", "items", "result")
            ],
            total=_int(data, "total", "count"),
        )


@dataclass(slots=True, frozen=True)
class MessageActionResult(ApiModel):
    """Результат операции с сообщением или чатом."""

    success: bool
    message_id: str | None = None
    status: MessageActionStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> MessageActionResult:
        """Преобразует результат операции с сообщением."""

        data = _expect_mapping(payload)
        return cls(
            success=bool(data.get("success", True)),
            message_id=_str(data, "message_id", "messageId", "id"),
            status=_enum(MessageActionStatus, _str(data, "status", "message")),
        )


@dataclass(slots=True, frozen=True)
class VoiceFile(ApiModel):
    """Голосовое сообщение."""

    id: str | None
    url: str | None
    duration: int | None
    transcript: str | None


@dataclass(slots=True, frozen=True)
class VoiceFilesResult(ApiModel):
    """Список голосовых сообщений."""

    items: list[VoiceFile]

    @classmethod
    def from_payload(cls, payload: object) -> VoiceFilesResult:
        """Преобразует список голосовых сообщений."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                VoiceFile(
                    id=_str(item, "id", "voice_id", "voiceId"),
                    url=_str(item, "url"),
                    duration=_int(item, "duration"),
                    transcript=_str(item, "transcript", "text"),
                )
                for item in _list(data, "voice_files", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class UploadImageResult(ApiModel):
    """Результат загрузки изображения."""

    image_id: str | None
    url: str | None


@dataclass(slots=True, frozen=True)
class UploadImagesResult(ApiModel):
    """Список загруженных изображений."""

    items: list[UploadImageResult]

    @classmethod
    def from_payload(cls, payload: object) -> UploadImagesResult:
        """Преобразует результат загрузки изображений."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                UploadImageResult(
                    image_id=_str(item, "image_id", "imageId", "id"),
                    url=_str(item, "url"),
                )
                for item in _list(data, "images", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class UploadImageFile:
    """Файл изображения для загрузки в мессенджер."""

    field_name: str
    filename: str
    content: bytes | BinaryIO
    content_type: str


@dataclass(slots=True, frozen=True)
class UploadImagesRequest:
    """Запрос загрузки изображений для сообщений."""

    files: list[UploadImageFile]

    def to_files(self) -> dict[str, object]:
        """Сериализует multipart-структуру для transport."""

        return {
            file.field_name: (file.filename, file.content, file.content_type) for file in self.files
        }


@dataclass(slots=True, frozen=True)
class SubscriptionInfo(ApiModel):
    """Подписка webhook мессенджера."""

    url: str | None
    version: str | None
    status: SubscriptionStatus | None


@dataclass(slots=True, frozen=True)
class SubscriptionsResult(ApiModel):
    """Список webhook-подписок."""

    items: list[SubscriptionInfo]

    @classmethod
    def from_payload(cls, payload: object) -> SubscriptionsResult:
        """Преобразует список подписок webhook."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                SubscriptionInfo(
                    url=_str(item, "url"),
                    version=_str(item, "version"),
                    status=_enum(SubscriptionStatus, _str(item, "status")),
                )
                for item in _list(data, "subscriptions", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class UnsubscribeWebhookRequest(RequestModel):
    """Запрос отключения webhook."""

    url: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос отключения webhook."""

        return {"url": self.url}


@dataclass(slots=True, frozen=True)
class UpdateWebhookRequest(RequestModel):
    """Запрос включения webhook v3."""

    url: str
    secret: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос включения webhook."""

        return {
            key: value
            for key, value in {"url": self.url, "secret": self.secret}.items()
            if value is not None
        }


@dataclass(slots=True, frozen=True)
class WebhookActionResult(ApiModel):
    """Результат операции с webhook."""

    success: bool
    status: WebhookStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> WebhookActionResult:
        """Преобразует результат операции с webhook."""

        data = _expect_mapping(payload)
        return cls(
            success=bool(data.get("success", True)),
            status=_enum(WebhookStatus, _str(data, "status", "message")),
        )


@dataclass(slots=True, frozen=True)
class BlacklistRequest(RequestModel):
    """Запрос добавления пользователя в blacklist."""

    blacklisted_user_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос blacklist."""

        return {"users": [{"user_id": self.blacklisted_user_id}]}


@dataclass(slots=True, frozen=True)
class SpecialOfferAvailableRequest(RequestModel):
    """Запрос доступных объявлений для спецпредложений."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос доступных объявлений."""

        return {"itemIds": self.item_ids}


@dataclass(slots=True, frozen=True)
class SpecialOfferAvailableItem(ApiModel):
    """Доступное объявление для рассылки спецпредложений."""

    item_id: int | None
    title: str | None
    is_available: bool | None


@dataclass(slots=True, frozen=True)
class SpecialOfferAvailableResult(ApiModel):
    """Результат получения доступных объявлений."""

    items: list[SpecialOfferAvailableItem]

    @classmethod
    def from_payload(cls, payload: object) -> SpecialOfferAvailableResult:
        """Преобразует доступные объявления спецпредложений."""

        data = _expect_mapping(payload)
        return cls(
            items=[
                SpecialOfferAvailableItem(
                    item_id=_int(item, "item_id", "itemId", "id"),
                    title=_str(item, "title"),
                    is_available=_bool(item, "is_available", "isAvailable", "available"),
                )
                for item in _list(data, "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class MultiCreateSpecialOfferRequest(RequestModel):
    """Запрос создания рассылки."""

    item_ids: list[int]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос создания рассылки."""

        return {"itemIds": self.item_ids}


@dataclass(slots=True, frozen=True)
class MultiCreateSpecialOfferResult(ApiModel):
    """Результат создания рассылки."""

    campaign_id: str | None
    status: SpecialOfferDispatchStatus | None

    @classmethod
    def from_payload(cls, payload: object) -> MultiCreateSpecialOfferResult:
        """Преобразует результат создания рассылки."""

        data = _expect_mapping(payload)
        return cls(
            campaign_id=_str(data, "campaign_id", "campaignId", "id"),
            status=_enum(SpecialOfferDispatchStatus, _str(data, "status")),
        )


@dataclass(slots=True, frozen=True)
class MultiConfirmSpecialOfferRequest(RequestModel):
    """Запрос подтверждения и оплаты рассылки."""

    dispatch_id: int
    recipients_count: int
    offer_slug: str
    discount_value: int | None = None
    expires_at: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос подтверждения рассылки."""

        dispatch = {
            key: value
            for key, value in {
                "dispatchId": self.dispatch_id,
                "recipientsCount": self.recipients_count,
                "offerSlug": self.offer_slug,
                "discountValue": self.discount_value,
            }.items()
            if value is not None
        }
        payload: dict[str, object] = {"dispatches": [dispatch]}
        if self.expires_at is not None:
            payload["expiresAt"] = self.expires_at
        return payload


@dataclass(slots=True, frozen=True)
class SpecialOfferStatsRequest(RequestModel):
    """Запрос статистики рассылки."""

    date_time_from: str
    date_time_to: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос статистики рассылки."""

        return {"dateTimeFrom": self.date_time_from, "dateTimeTo": self.date_time_to}


@dataclass(slots=True, frozen=True)
class SpecialOfferStatsResult(ApiModel):
    """Статистика рассылки."""

    campaign_id: str | None
    sent_count: int | None
    delivered_count: int | None
    read_count: int | None

    @classmethod
    def from_payload(cls, payload: object) -> SpecialOfferStatsResult:
        """Преобразует статистику рассылки."""

        data = _expect_mapping(payload)
        return cls(
            campaign_id=_str(data, "campaign_id", "campaignId", "id"),
            sent_count=_int(data, "sent_count", "sentCount"),
            delivered_count=_int(data, "delivered_count", "deliveredCount"),
            read_count=_int(data, "read_count", "readCount"),
        )


@dataclass(slots=True, frozen=True)
class TariffInfo(ApiModel):
    """Информация о тарифе рассылок."""

    price: float | None
    currency: str | None
    daily_limit: int | None

    @classmethod
    def from_payload(cls, payload: object) -> TariffInfo:
        """Преобразует информацию о тарифе."""

        data = _expect_mapping(payload)
        return cls(
            price=_float(data, "price", "amount"),
            currency=_str(data, "currency"),
            daily_limit=_int(data, "daily_limit", "dailyLimit", "limit"),
        )


def _expect_mapping(payload: object) -> Payload:
    if not isinstance(payload, Mapping):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return payload


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
    return None


def _datetime(payload: Payload, *keys: str) -> datetime | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
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


def _enum[EnumT: Enum](enum_type: type[EnumT], value: str | None) -> EnumT | None:
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return enum_type("__unknown__")


__all__ = (
    "BlacklistRequest",
    "ChatInfo",
    "ChatsResult",
    "MessageActionResult",
    "MessageActionStatus",
    "MessageDirection",
    "MessageInfo",
    "MessagesResult",
    "MessageType",
    "MultiConfirmSpecialOfferRequest",
    "MultiCreateSpecialOfferRequest",
    "MultiCreateSpecialOfferResult",
    "SendImageMessageRequest",
    "SendMessageRequest",
    "SpecialOfferAvailableItem",
    "SpecialOfferAvailableRequest",
    "SpecialOfferAvailableResult",
    "SpecialOfferCampaignStatus",
    "SpecialOfferDispatchStatus",
    "SpecialOfferStatsRequest",
    "SpecialOfferStatsResult",
    "SubscriptionInfo",
    "SubscriptionStatus",
    "SubscriptionsResult",
    "TariffInfo",
    "UnsubscribeWebhookRequest",
    "UpdateWebhookRequest",
    "UploadImageFile",
    "UploadImagesRequest",
    "UploadImageResult",
    "UploadImagesResult",
    "VoiceFile",
    "VoiceFilesResult",
    "WebhookActionResult",
    "WebhookStatus",
)
