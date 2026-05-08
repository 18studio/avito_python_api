"""Async-доменные объекты пакета messenger."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import DateInput, serialize_iso_datetime
from avito.messenger.models import (
    BlacklistRequest,
    ChatInfo,
    ChatsResult,
    MessageActionResult,
    MessagesResult,
    MultiConfirmSpecialOfferRequest,
    MultiCreateSpecialOfferRequest,
    MultiCreateSpecialOfferResult,
    SendImageMessageRequest,
    SendMessageRequest,
    SpecialOfferAvailableRequest,
    SpecialOfferAvailableResult,
    SpecialOfferStatsRequest,
    SpecialOfferStatsResult,
    SubscriptionsResult,
    TariffInfo,
    UnsubscribeWebhookRequest,
    UpdateWebhookRequest,
    UploadImageFile,
    UploadImagesRequest,
    UploadImagesResult,
    VoiceFilesResult,
    WebhookActionResult,
)
from avito.messenger.operations import (
    ADD_TO_BLACKLIST,
    CONFIRM_MULTI_SPECIAL_OFFER,
    CREATE_MULTI_SPECIAL_OFFER,
    DELETE_MESSAGE,
    GET_AVAILABLE_SPECIAL_OFFERS,
    GET_CHAT,
    GET_SPECIAL_OFFER_STATS,
    GET_SPECIAL_OFFER_TARIFF_INFO,
    GET_SUBSCRIPTIONS,
    GET_VOICE_FILES,
    LIST_CHATS,
    LIST_MESSAGES,
    READ_CHAT,
    SEND_IMAGE_MESSAGE,
    SEND_MESSAGE,
    UNSUBSCRIBE_WEBHOOK,
    UPDATE_WEBHOOK_V3,
    UPLOAD_IMAGES,
)


@dataclass(slots=True, frozen=True)
class AsyncChat(AsyncDomainObject):
    """Async-доменный объект чата."""

    __swagger_domain__ = "messenger"
    __sdk_factory__ = "chat"
    __sdk_factory_args__ = {"chat_id": "path.chat_id", "user_id": "path.user_id"}

    chat_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/messenger/v2/accounts/{user_id}/chats/{chat_id}",
        spec="Мессенджер.json",
        operation_id="getChatByIdV2",
        variant="async",
    )
    async def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> ChatInfo:
        """Получает чат по `chat_id` асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ChatInfo` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CHAT,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": self._require_chat_id(),
            },
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/messenger/v2/accounts/{user_id}/chats",
        spec="Мессенджер.json",
        operation_id="getChatsV2",
        variant="async",
    )
    async def list(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> ChatsResult:
        """Возвращает список чатов асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ChatsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_CHATS,
            path_params={"user_id": self._require_user_id()},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v1/accounts/{user_id}/chats/{chat_id}/read",
        spec="Мессенджер.json",
        operation_id="chatRead",
        variant="async",
    )
    async def mark_read(
        self,
        *,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessageActionResult:
        """Помечает чат как прочитанный асинхронно.

        Аргументы:
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessageActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            READ_CHAT,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": self._require_chat_id(),
            },
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v2/accounts/{user_id}/blacklist",
        spec="Мессенджер.json",
        operation_id="postBlacklistV2",
        method_args={"blacklisted_user_id": "body.users[].user_id"},
        variant="async",
    )
    async def blacklist(
        self,
        *,
        blacklisted_user_id: int,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessageActionResult:
        """Добавляет пользователя в blacklist асинхронно.

        Аргументы:
            blacklisted_user_id: идентификатор пользователя, которого нужно добавить в черный список.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessageActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            ADD_TO_BLACKLIST,
            path_params={"user_id": self._require_user_id()},
            request=BlacklistRequest(blacklisted_user_id=blacklisted_user_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_user_id(self) -> int:
        """Validate required user id."""
        if self.user_id is None:
            raise ValidationError("Для операции требуется `user_id`.")
        return int(self.user_id)

    def _require_chat_id(self) -> str:
        """Validate required chat id."""
        if self.chat_id is None:
            raise ValidationError("Для операции требуется `chat_id`.")
        return str(self.chat_id)


@dataclass(slots=True, frozen=True)
class AsyncChatMessage(AsyncDomainObject):
    """Async-доменный объект сообщения чата."""

    __swagger_domain__ = "messenger"
    __sdk_factory__ = "chat_message"
    __sdk_factory_args__ = {
        "message_id": "path.message_id",
        "chat_id": "path.chat_id",
        "user_id": "path.user_id",
    }

    chat_id: int | str | None = None
    message_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/",
        spec="Мессенджер.json",
        operation_id="getMessagesV3",
        variant="async",
    )
    async def list(
        self,
        *,
        chat_id: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessagesResult:
        """Возвращает список сообщений чата асинхронно.

        Аргументы:
            chat_id: идентифицирует чат.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessagesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_MESSAGES,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": chat_id or self._require_chat_id(),
            },
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages",
        spec="Мессенджер.json",
        operation_id="postSendMessage",
        method_args={"message": "body.message"},
        variant="async",
    )
    async def send_message(
        self,
        *,
        chat_id: str | None = None,
        message: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessageActionResult:
        """Отправляет текстовое сообщение асинхронно.

        Аргументы:
            chat_id: идентификатор чата.
            message: текст отправляемого сообщения.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessageActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SEND_MESSAGE,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": chat_id or self._require_chat_id(),
            },
            request=SendMessageRequest(message=message),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/image",
        spec="Мессенджер.json",
        operation_id="postSendImageMessage",
        method_args={"image_id": "body.image_id"},
        variant="async",
    )
    async def send_image(
        self,
        *,
        chat_id: str | None = None,
        image_id: str,
        caption: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessageActionResult:
        """Отправляет сообщение с изображением асинхронно.

        Аргументы:
            chat_id: идентификатор чата.
            image_id: идентификатор изображения для отправки.
            caption: подпись к изображению, если поддерживается операцией.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessageActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SEND_IMAGE_MESSAGE,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": chat_id or self._require_chat_id(),
            },
            request=SendImageMessageRequest(image_id=image_id, caption=caption),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/{message_id}",
        spec="Мессенджер.json",
        operation_id="deleteMessage",
        variant="async",
    )
    async def delete(
        self,
        *,
        chat_id: str | None = None,
        message_id: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MessageActionResult:
        """Удаляет сообщение асинхронно.

        Аргументы:
            chat_id: идентификатор чата.
            message_id: идентификатор сообщения.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MessageActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_message_id = message_id or self._require_message_id()
        return await self._execute(
            DELETE_MESSAGE,
            path_params={
                "user_id": self._require_user_id(),
                "chat_id": chat_id or self._require_chat_id(),
                "message_id": resolved_message_id,
            },
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_user_id(self) -> int:
        """Validate required user id."""
        if self.user_id is None:
            raise ValidationError("Для операции требуется `user_id`.")
        return int(self.user_id)

    def _require_chat_id(self) -> str:
        """Validate required chat id."""
        if self.chat_id is None:
            raise ValidationError("Для операции требуется `chat_id`.")
        return str(self.chat_id)

    def _require_message_id(self) -> str:
        """Validate required message id."""
        if self.message_id is None:
            raise ValidationError("Для операции требуется `message_id`.")
        return str(self.message_id)


@dataclass(slots=True, frozen=True)
class AsyncChatWebhook(AsyncDomainObject):
    """Async-доменный объект webhook мессенджера."""

    __swagger_domain__ = "messenger"
    __sdk_factory__ = "chat_webhook"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/messenger/v1/subscriptions",
        spec="Мессенджер.json",
        operation_id="getSubscriptions",
        variant="async",
    )
    async def list(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> SubscriptionsResult:
        """Возвращает список webhook-подписок чатов асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `SubscriptionsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_SUBSCRIPTIONS, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/messenger/v1/webhook/unsubscribe",
        spec="Мессенджер.json",
        operation_id="postWebhookUnsubscribe",
        method_args={"url": "body.url"},
        variant="async",
    )
    async def unsubscribe(
        self,
        *,
        url: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> WebhookActionResult:
        """Отключает webhook асинхронно.

        Аргументы:
            url: URL источника данных.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `WebhookActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UNSUBSCRIBE_WEBHOOK,
            request=UnsubscribeWebhookRequest(url=url),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v3/webhook",
        spec="Мессенджер.json",
        operation_id="postWebhookV3",
        method_args={"url": "body.url"},
        variant="async",
    )
    async def subscribe(
        self,
        *,
        url: str,
        secret: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> WebhookActionResult:
        """Включает webhook v3 асинхронно.

        Аргументы:
            url: URL источника данных.
            secret: секрет webhook-подписки для проверки входящих событий.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `WebhookActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UPDATE_WEBHOOK_V3,
            request=UpdateWebhookRequest(url=url, secret=secret),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncChatMedia(AsyncDomainObject):
    """Async-доменный объект media-функций мессенджера."""

    __swagger_domain__ = "messenger"
    __sdk_factory__ = "chat_media"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/messenger/v1/accounts/{user_id}/getVoiceFiles",
        spec="Мессенджер.json",
        operation_id="getVoiceFiles",
        variant="async",
    )
    async def get_voice_files(
        self,
        *,
        voice_ids: Sequence[str] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> VoiceFilesResult:
        """Получает голосовые сообщения асинхронно.

        Аргументы:
            voice_ids: идентификаторы голосовых файлов.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `VoiceFilesResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_voice_ids = list(voice_ids or ["voice-1"])
        return await self._execute(
            GET_VOICE_FILES,
            path_params={"user_id": self._require_user_id()},
            query={"voice_ids": ",".join(resolved_voice_ids)},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/messenger/v1/accounts/{user_id}/uploadImages",
        spec="Мессенджер.json",
        operation_id="uploadImages",
        method_args={"files": "body.uploadfile[]"},
        variant="async",
    )
    async def upload_images(
        self,
        *,
        files: list[UploadImageFile],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> UploadImagesResult:
        """Загружает изображения для сообщений асинхронно.

        Аргументы:
            files: файлы изображений для загрузки.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `UploadImagesResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UPLOAD_IMAGES,
            path_params={"user_id": self._require_user_id()},
            files=UploadImagesRequest(files=files).to_files(),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_user_id(self) -> int:
        """Validate required user id."""
        if self.user_id is None:
            raise ValidationError("Для операции требуется `user_id`.")
        return int(self.user_id)


@dataclass(slots=True, frozen=True)
class AsyncSpecialOfferCampaign(AsyncDomainObject):
    """Async-доменный объект рассылки скидок и спецпредложений."""

    __swagger_domain__ = "messenger"
    __sdk_factory__ = "special_offer_campaign"
    __sdk_factory_args__ = {"campaign_id": "path.campaign_id"}

    campaign_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/special-offers/v1/available",
        spec="Рассылкаскидокиспецпредложенийвмессенджере.json",
        operation_id="openApiAvailable",
        method_args={"item_ids": "body.item_ids"},
        variant="async",
    )
    async def get_available(
        self,
        *,
        item_ids: list[int],
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> SpecialOfferAvailableResult:
        """Получает объявления, доступные для рассылки, асинхронно.

        Аргументы:
            item_ids: список идентификаторов объявлений.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `SpecialOfferAvailableResult` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_AVAILABLE_SPECIAL_OFFERS,
            request=SpecialOfferAvailableRequest(item_ids=item_ids),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/special-offers/v1/multiCreate",
        spec="Рассылкаскидокиспецпредложенийвмессенджере.json",
        operation_id="openApiMultiCreate",
        method_args={"item_ids": "body.itemIds"},
        variant="async",
    )
    async def create_multi(
        self,
        *,
        item_ids: list[int],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MultiCreateSpecialOfferResult:
        """Создает рассылку спецпредложений асинхронно.

        Аргументы:
            item_ids: передает список объявлений для рассылки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MultiCreateSpecialOfferResult` с идентификатором и статусом рассылки.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_MULTI_SPECIAL_OFFER,
            request=MultiCreateSpecialOfferRequest(item_ids=item_ids),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/special-offers/v1/multiConfirm",
        spec="Рассылкаскидокиспецпредложенийвмессенджере.json",
        operation_id="openApiMultiConfirm",
        method_args={
            "dispatch_id": "body.dispatches[].dispatchId",
            "recipients_count": "body.dispatches[].recipientsCount",
            "offer_slug": "body.dispatches[].offerSlug",
        },
        variant="async",
    )
    async def confirm_multi(
        self,
        *,
        dispatch_id: int,
        recipients_count: int,
        offer_slug: str,
        discount_value: int | None = None,
        expires_at: int | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> WebhookActionResult:
        """Подтверждает и оплачивает рассылку асинхронно.

        Аргументы:
            dispatch_id: идентифицирует рассылку.
            recipients_count: задает число получателей рассылки.
            offer_slug: задает выбранный вариант предложения.
            discount_value: задает финальный размер скидки, если он применим.
            expires_at: задает timestamp окончания предложения.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `WebhookActionResult` со статусом подтверждения.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CONFIRM_MULTI_SPECIAL_OFFER,
            request=MultiConfirmSpecialOfferRequest(
                dispatch_id=dispatch_id,
                recipients_count=recipients_count,
                offer_slug=offer_slug,
                discount_value=discount_value,
                expires_at=expires_at,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/special-offers/v1/stats",
        spec="Рассылкаскидокиспецпредложенийвмессенджере.json",
        operation_id="openApiStats",
        method_args={
            "date_time_from": "body.dateTimeFrom",
            "date_time_to": "body.dateTimeTo",
        },
        variant="async",
    )
    async def get_stats(
        self,
        *,
        date_time_from: DateInput,
        date_time_to: DateInput,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> SpecialOfferStatsResult:
        """Получает статистику рассылки асинхронно.

        Аргументы:
            date_time_from: задает начало периода в формате RFC3339.
            date_time_to: задает конец периода в формате RFC3339.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `SpecialOfferStatsResult` со статистикой рассылки.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_SPECIAL_OFFER_STATS,
            request=SpecialOfferStatsRequest(
                date_time_from=serialize_iso_datetime("date_time_from", date_time_from),
                date_time_to=serialize_iso_datetime("date_time_to", date_time_to),
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/special-offers/v1/tariffInfo",
        spec="Рассылкаскидокиспецпредложенийвмессенджере.json",
        operation_id="openApiTariffInfo",
        variant="async",
    )
    async def get_tariff_info(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> TariffInfo:
        """Получает информацию о тарифе спецпредложений асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `TariffInfo` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_SPECIAL_OFFER_TARIFF_INFO, timeout=timeout, retry=retry)

    def _require_campaign_id(self) -> str:
        """Validate required campaign id."""
        if self.campaign_id is None:
            raise ValidationError("Для операции требуется `campaign_id`.")
        return str(self.campaign_id)


__all__ = (
    "AsyncChat",
    "AsyncChatMedia",
    "AsyncChatMessage",
    "AsyncChatWebhook",
    "AsyncSpecialOfferCampaign",
)
