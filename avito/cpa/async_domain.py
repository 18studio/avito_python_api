"""Async-доменные объекты пакета cpa."""

from __future__ import annotations

from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.deprecation import deprecated_method, warn_deprecated_once
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import DateInput, serialize_iso_datetime
from avito.cpa.models import (
    CallTrackingCallResponse,
    CallTrackingCallsRequest,
    CallTrackingCallsResult,
    CallTrackingGetCallByIdRequest,
    CallTrackingRecord,
    CpaActionResult,
    CpaAudioRecord,
    CpaBalanceInfo,
    CpaBalanceInfoRequest,
    CpaCallByIdRequest,
    CpaCallComplaintRequest,
    CpaCallInfo,
    CpaCallsByTimeRequest,
    CpaCallsResult,
    CpaChatInfo,
    CpaChatsByTimeRequest,
    CpaChatsResult,
    CpaLeadComplaintRequest,
    CpaPhonesFromChatsRequest,
    CpaPhonesResult,
)
from avito.cpa.operations import (
    CPA_HEADERS,
    CREATE_CPA_CALL_COMPLAINT,
    CREATE_CPA_LEAD_COMPLAINT,
    GET_CALLTRACKING_CALL_BY_ID,
    GET_CALLTRACKING_CALLS,
    GET_CALLTRACKING_RECORD,
    GET_CPA_ARCHIVE_BALANCE,
    GET_CPA_ARCHIVE_CALL_BY_ID,
    GET_CPA_ARCHIVE_RECORD,
    GET_CPA_BALANCE,
    GET_CPA_CHAT_BY_ACTION_ID,
    GET_CPA_PHONES_INFO,
    LIST_CPA_CALLS,
    LIST_CPA_CHATS,
    LIST_CPA_CHATS_CLASSIC,
)


@dataclass(slots=True, frozen=True)
class AsyncCpaLead(AsyncDomainObject):
    """Доменный объект CPA-лида и связанных lead-операций."""

    __swagger_domain__ = "cpa"
    __sdk_factory__ = "cpa_lead"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/cpa/v1/createComplaintByActionId",
        spec="CPAАвито.json",
        operation_id="createComplaintByActionId",
        variant="async",
        method_args={"action_id": "body.action_id", "reason": "body.message"},
    )
    async def create_complaint_by_action_id(
        self,
        *,
        action_id: int,
        reason: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaActionResult:
        """Создает жалобу по идентификатору CPA-действия.

        Аргументы:
            action_id: идентифицирует CPA-действие.
            reason: передает причину жалобы или обращения.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_CPA_LEAD_COMPLAINT,
            request=CpaLeadComplaintRequest(action_id=action_id, reason=reason),
            headers=CPA_HEADERS,
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v3/balanceInfo",
        spec="CPAАвито.json",
        operation_id="balanceInfoV3",
        variant="async",
    )
    async def get_balance_info(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> CpaBalanceInfo:
        """Возвращает balance info для CPA-лидов.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaBalanceInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_BALANCE,
            request=CpaBalanceInfoRequest(),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncCpaChat(AsyncDomainObject):
    """Доменный объект CPA-чата."""

    __swagger_domain__ = "cpa"
    __sdk_factory__ = "cpa_chat"
    __sdk_factory_args__ = {"chat_id": "path.chat_id"}

    action_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/cpa/v1/chatByActionId/{actionId}",
        spec="CPAАвито.json",
        operation_id="chatByActionId",
        variant="async",
    )
    async def get(
        self,
        *,
        action_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaChatInfo:
        """Возвращает CPA-чатов.

        Аргументы:
            action_id: идентифицирует CPA-действие.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaChatInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_CHAT_BY_ACTION_ID,
            path_params={"actionId": action_id or self._require_action_id()},
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v2/chatsByTime",
        spec="CPAАвито.json",
        operation_id="chatsByTime",
        variant="async",
        method_args={
            "created_at_from": "body.dateTimeFrom",
            "limit": "body.limit",
            "offset": "body.offset",
        },
    )
    async def list(
        self,
        *,
        created_at_from: DateInput,
        limit: int,
        offset: int,
        version: int = 2,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaChatsResult:
        """Возвращает список CPA-чатов.

        Аргументы:
            created_at_from: задает нижнюю границу времени создания.
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            version: задает версию upstream-контракта, если операция ее поддерживает.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaChatsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        if version == 1:
            return await self.list_classic(
                created_at_from=created_at_from,
                limit=limit,
                offset=offset,
                timeout=timeout,
                retry=retry,
            )
        return await self._execute(
            LIST_CPA_CHATS,
            request=CpaChatsByTimeRequest(
                created_at_from=serialize_iso_datetime("created_at_from", created_at_from),
                limit=limit,
                offset=offset,
            ),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v1/chatsByTime",
        spec="CPAАвито.json",
        operation_id="chatsByTime",
        variant="async",
        method_args={
            "created_at_from": "body.dateTimeFrom",
            "limit": "body.limit",
            "offset": "body.offset",
        },
    )
    async def list_classic(
        self,
        *,
        created_at_from: DateInput,
        limit: int,
        offset: int,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaChatsResult:
        """Выполняет legacy-операцию списка CPA-чатов v1 и возвращает типизированную SDK-модель.

        Аргументы:
            created_at_from: фильтрует CPA-чаты по нижней границе даты создания.
            limit: задает максимальное число записей в ответе.
            offset: задает смещение выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaChatsResult` со списком CPA-чатов legacy API.

        Поведение:
            Метод оставлен для явного покрытия отдельной Swagger operation.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        warn_deprecated_once(
            symbol="AsyncCpaChat.list(version=1)",
            replacement="await cpa_chat().list(version=2)",
            removal_version="1.3.0",
            deprecated_since="1.1.0",
        )
        return await self._execute(
            LIST_CPA_CHATS_CLASSIC,
            request=CpaChatsByTimeRequest(
                created_at_from=serialize_iso_datetime("created_at_from", created_at_from),
                limit=limit,
                offset=offset,
            ),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v1/phonesInfoFromChats",
        spec="CPAАвито.json",
        operation_id="phonesInfoFromChats",
        variant="async",
        method_args={
            "date_time_from": "body.dateTimeFrom",
            "limit": "body.limit",
            "offset": "body.offset",
        },
    )
    async def get_phones_info_from_chats(
        self,
        *,
        date_time_from: DateInput,
        limit: int,
        offset: int,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaPhonesResult:
        """Возвращает phones info from chats для CPA-чатов.

        Аргументы:
            date_time_from: задает нижнюю границу времени поиска.
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaPhonesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_PHONES_INFO,
            request=CpaPhonesFromChatsRequest(
                date_time_from=serialize_iso_datetime("date_time_from", date_time_from),
                limit=limit,
                offset=offset,
            ),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    def _require_action_id(self) -> str:
        if self.action_id is None:
            raise ValidationError("Для операции требуется `action_id`.")
        return str(self.action_id)


@dataclass(slots=True, frozen=True)
class AsyncCpaCall(AsyncDomainObject):
    """Доменный объект CPA-звонка."""

    __swagger_domain__ = "cpa"
    __sdk_factory__ = "cpa_call"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/cpa/v2/callsByTime",
        spec="CPAАвито.json",
        operation_id="getCallsByTimeV2",
        variant="async",
        method_args={
            "date_time_from": "body.dateTimeFrom",
            "limit": "body.limit",
        },
    )
    async def list(
        self,
        *,
        date_time_from: DateInput,
        limit: int,
        offset: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaCallsResult:
        """Возвращает список CPA-звонков.

        Аргументы:
            date_time_from: задает начало временного интервала.
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaCallsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_CPA_CALLS,
            request=CpaCallsByTimeRequest(
                date_time_from=serialize_iso_datetime("date_time_from", date_time_from),
                limit=limit,
                offset=offset,
            ),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v1/createComplaint",
        spec="CPAАвито.json",
        operation_id="postCreateComplaint",
        variant="async",
        method_args={"call_id": "body.call_id", "reason": "body.message"},
    )
    async def create_complaint(
        self,
        *,
        call_id: int,
        reason: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaActionResult:
        """Создает жалобу по CPA-звонку.

        Аргументы:
            call_id: идентифицирует звонок.
            reason: передает причину жалобы или обращения.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_CPA_CALL_COMPLAINT,
            request=CpaCallComplaintRequest(call_id=call_id, reason=reason),
            headers=CPA_HEADERS,
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncCpaArchive(AsyncDomainObject):
    """Доменный объект архивных операций CPA."""

    __swagger_domain__ = "cpa"
    __sdk_factory__ = "cpa_archive"
    __sdk_factory_args__ = {"call_id": "path.call_id"}

    call_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/cpa/v1/call/{call_id}",
        spec="CPAАвито.json",
        operation_id="getCall",
        variant="async",
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncCpaArchive.get_call",
        replacement="await call_tracking_call().download",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_call(
        self,
        *,
        call_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaAudioRecord:
        """Получает архивную запись звонка.

        Deprecated: используйте `call_tracking_call().download`; удаление в версии 1.3.0.

        Аргументы:
            call_id: идентифицирует архивную запись звонка.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaAudioRecord` с бинарной записью звонка.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return CpaAudioRecord(
            await self._execute(
                GET_CPA_ARCHIVE_RECORD,
                path_params={"call_id": call_id or self._require_call_id()},
                headers=CPA_HEADERS,
                timeout=timeout,
                retry=retry,
            )
        )

    @swagger_operation(
        "POST",
        "/cpa/v2/balanceInfo",
        spec="CPAАвито.json",
        operation_id="balanceInfoV2",
        variant="async",
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncCpaArchive.get_balance_info",
        replacement="await cpa_lead().get_balance_info",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_balance_info(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> CpaBalanceInfo:
        """Получает архивный баланс CPA.

        Deprecated: используйте `cpa_lead().get_balance_info`; удаление в версии 1.3.0.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaBalanceInfo` с архивной информацией о балансе CPA.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_ARCHIVE_BALANCE,
            request=CpaBalanceInfoRequest(),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cpa/v2/callById",
        spec="CPAАвито.json",
        operation_id="getCallByIdV2",
        variant="async",
        method_args={"call_id": "body.call_id"},
        deprecated=True,
        legacy=True,
    )
    @deprecated_method(
        symbol="AsyncCpaArchive.get_call_by_id",
        replacement="await call_tracking_call().get",
        removal_version="1.3.0",
        deprecated_since="1.1.0",
    )
    async def get_call_by_id(
        self,
        *,
        call_id: int,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CpaCallInfo:
        """Получает архивные данные звонка.

        Deprecated: используйте `call_tracking_call().get`; удаление в версии 1.3.0.

        Аргументы:
            call_id: идентифицирует звонок.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CpaCallInfo` с архивными данными звонка.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CPA_ARCHIVE_CALL_BY_ID,
            request=CpaCallByIdRequest(call_id=call_id),
            headers=CPA_HEADERS,
            timeout=timeout,
            retry=retry,
        )

    def _require_call_id(self) -> str:
        if self.call_id is None:
            raise ValidationError("Для операции требуется `call_id`.")
        return str(self.call_id)


@dataclass(slots=True, frozen=True)
class AsyncCallTrackingCall(AsyncDomainObject):
    """Доменный объект CallTracking."""

    __swagger_domain__ = "cpa"
    __sdk_factory__ = "call_tracking_call"
    __sdk_factory_args__ = {"call_id": "path.call_id"}

    call_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/calltracking/v1/getCallById",
        spec="CallTracking[КТ].json",
        operation_id="get_call_by_id",
        variant="async",
    )
    async def get(
        self,
        *,
        call_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CallTrackingCallResponse:
        """Возвращает call tracking звонков.

        Аргументы:
            call_id: идентифицирует звонок.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CallTrackingCallResponse` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_call_id = call_id or (int(self.call_id) if self.call_id is not None else None)
        if resolved_call_id is None:
            raise ValidationError("Для операции требуется `call_id`.")
        return await self._execute(
            GET_CALLTRACKING_CALL_BY_ID,
            request=CallTrackingGetCallByIdRequest(call_id=resolved_call_id),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/calltracking/v1/getCalls",
        spec="CallTracking[КТ].json",
        operation_id="get_calls",
        variant="async",
        method_args={"date_time_from": "body.date_time_from", "date_time_to": "body.date_time_to"},
    )
    async def list(
        self,
        *,
        date_time_from: DateInput,
        date_time_to: DateInput,
        limit: int | None = None,
        offset: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CallTrackingCallsResult:
        """Возвращает список call tracking звонков.

        Аргументы:
            date_time_from: задает начало временного интервала.
            date_time_to: задает конец временного интервала.
            limit: ограничивает размер возвращаемой выборки.
            offset: задает смещение первой записи в выборке.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CallTrackingCallsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_CALLTRACKING_CALLS,
            request=CallTrackingCallsRequest(
                date_time_from=serialize_iso_datetime("date_time_from", date_time_from),
                date_time_to=serialize_iso_datetime("date_time_to", date_time_to),
                limit=limit,
                offset=offset,
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/calltracking/v1/getRecordByCallId",
        spec="CallTracking[КТ].json",
        operation_id="get_record_by_call_id",
        variant="async",
        method_args={"call_id": "query.callId"},
    )
    async def download(
        self,
        *,
        call_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CallTrackingRecord:
        """Скачивает запись call tracking звонка.

        Аргументы:
            call_id: идентифицирует звонок.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CallTrackingRecord` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return CallTrackingRecord(
            await self._execute(
                GET_CALLTRACKING_RECORD,
                query={"callId": call_id or self._require_call_id()},
                timeout=timeout,
                retry=retry,
            )
        )

    def _require_call_id(self) -> str:
        if self.call_id is None:
            raise ValidationError("Для операции требуется `call_id`.")
        return str(self.call_id)


__all__ = ("AsyncCallTrackingCall", "AsyncCpaArchive", "AsyncCpaCall", "AsyncCpaChat", "AsyncCpaLead")
