"""Async-доменные объекты пакета orders."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import DateInput, serialize_iso_datetime
from avito.orders.models import (
    AddSortingCentersRequest,
    AddTariffV2Request,
    AddTerminalsRequest,
    CancelParcelRequest,
    CancelSandboxParcelOptions,
    CancelSandboxParcelRequest,
    ChangeParcelApplication,
    ChangeParcelOptions,
    ChangeParcelRequest,
    CourierRangesResult,
    CustomAreaScheduleEntry,
    CustomAreaScheduleRequest,
    DeliveryAnnouncementRequest,
    DeliveryAnnouncementTrackRequest,
    DeliveryCancelAnnouncementRequest,
    DeliveryDirection,
    DeliveryEntityResult,
    DeliveryParcelIdsRequest,
    DeliveryParcelRequest,
    DeliveryParcelResultRequest,
    DeliverySandboxAnnouncementRequest,
    DeliverySortingCentersResult,
    DeliveryTariffZone,
    DeliveryTaskInfo,
    DeliveryTermsZone,
    DeliveryTrackingOptions,
    DeliveryTrackingRequest,
    GetChangeParcelInfoRequest,
    GetRegisteredParcelIdRequest,
    GetSandboxParcelInfoRequest,
    LabelPdfResult,
    LabelTaskResult,
    OrderAcceptReturnRequest,
    OrderActionResult,
    OrderApplyTransitionRequest,
    OrderCncDetailsRequest,
    OrderConfirmationCodeRequest,
    OrderCourierRangeRequest,
    OrderDeliveryProperties,
    OrderLabelsRequest,
    OrderMarkingsRequest,
    OrdersResult,
    OrderTrackingNumberRequest,
    OrderTransition,
    ProhibitOrderAcceptanceRequest,
    RealAddress,
    SandboxAnnouncementPackage,
    SandboxAnnouncementParticipant,
    SandboxArea,
    SandboxAreasRequest,
    SandboxCancelAnnouncementOptions,
    SandboxCancelAnnouncementRequest,
    SandboxConfirmationCodeRequest,
    SandboxCreateAnnouncementOptions,
    SandboxCreateAnnouncementRequest,
    SandboxGetAnnouncementEventRequest,
    SandboxParcelRequest,
    SetOrderPropertiesRequest,
    SetOrderRealAddressRequest,
    SortingCenterUpload,
    StockInfoRequest,
    StockInfoResult,
    StockUpdateEntry,
    StockUpdateRequest,
    StockUpdateResult,
    TaggedSortingCenter,
    TaggedSortingCentersRequest,
    TerminalUpload,
    TrackingAvitoEventType,
    TrackingAvitoStatus,
    UpdateTermsRequest,
)
from avito.orders.operations import (
    ACCEPT_RETURN_ORDER,
    APPLY_TRANSITION,
    CHECK_CONFIRMATION_CODE,
    CREATE_LABELS,
    CREATE_LABELS_EXTENDED,
    DELIVERY_CANCEL_ANNOUNCEMENT,
    DELIVERY_CHANGE_PARCEL_RESULT,
    DELIVERY_CREATE_ANNOUNCEMENT,
    DELIVERY_CREATE_PARCEL,
    DELIVERY_UPDATE_CHANGE_PARCELS,
    DOWNLOAD_LABEL,
    GET_COURIER_DELIVERY_RANGE,
    GET_DELIVERY_TASK,
    GET_STOCK_INFO,
    LIST_ORDERS,
    SANDBOX_ADD_AREAS,
    SANDBOX_ADD_SORTING_CENTER,
    SANDBOX_ADD_TAGS_TO_SORTING_CENTER,
    SANDBOX_ADD_TARIFF,
    SANDBOX_ADD_TERMINALS,
    SANDBOX_CANCEL_PARCEL,
    SANDBOX_CANCEL_SANDBOX_ANNOUNCEMENT,
    SANDBOX_CANCEL_SANDBOX_PARCEL,
    SANDBOX_CHANGE_SANDBOX_PARCEL,
    SANDBOX_CHECK_CONFIRMATION_CODE,
    SANDBOX_CREATE_ANNOUNCEMENT,
    SANDBOX_CREATE_PARCEL,
    SANDBOX_CREATE_SANDBOX_ANNOUNCEMENT,
    SANDBOX_GET_ANNOUNCEMENT_EVENT,
    SANDBOX_GET_CHANGE_PARCEL_INFO,
    SANDBOX_GET_PARCEL_INFO,
    SANDBOX_GET_REGISTERED_PARCEL_ID,
    SANDBOX_LIST_SORTING_CENTER,
    SANDBOX_PROHIBIT_ORDER_ACCEPTANCE,
    SANDBOX_SET_ORDER_PROPERTIES,
    SANDBOX_SET_ORDER_REAL_ADDRESS,
    SANDBOX_TRACK_ANNOUNCEMENT,
    SANDBOX_TRACKING,
    SANDBOX_UPDATE_CUSTOM_AREA_SCHEDULE,
    SANDBOX_UPDATE_TERMS,
    SET_CNC_DETAILS,
    SET_COURIER_DELIVERY_RANGE,
    SET_TRACKING_NUMBER,
    UPDATE_MARKINGS,
    UPDATE_STOCKS,
)


@dataclass(slots=True, frozen=True)
class AsyncOrder(AsyncDomainObject):
    """Доменный объект заказа."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "order"

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/order-management/1/orders",
        spec="Управлениезаказами.json",
        operation_id="getOrders",
        variant="async",
    )
    async def list(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> OrdersResult:
        """Возвращает список заказов.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrdersResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(LIST_ORDERS, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/order-management/1/markings",
        spec="Управлениезаказами.json",
        operation_id="markings",
        variant="async",
        method_args={"order_id": "body.markings", "codes": "body.markings"},
    )
    async def update_markings(
        self,
        *,
        order_id: str,
        codes: Sequence[str],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Обновляет коды маркировки заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            codes: передает коды маркировки заказа.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UPDATE_MARKINGS,
            request=OrderMarkingsRequest(order_id=order_id, codes=list(codes)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/acceptReturnOrder",
        spec="Управлениезаказами.json",
        operation_id="acceptReturnOrder",
        variant="async",
        method_args={"order_id": "body.order_id", "postal_office_id": "body.terminal_number"},
    )
    async def accept_return_order(
        self,
        *,
        order_id: str,
        postal_office_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Подтверждает return order для заказов.

        Аргументы:
            order_id: идентифицирует заказ.
            postal_office_id: идентифицирует почтовое отделение для возврата.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            ACCEPT_RETURN_ORDER,
            request=OrderAcceptReturnRequest(
                order_id=order_id,
                postal_office_id=postal_office_id,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/applyTransition",
        spec="Управлениезаказами.json",
        operation_id="applyTransition",
        variant="async",
        method_args={"order_id": "body.order_id", "transition": "body.transition"},
    )
    async def apply(
        self,
        *,
        order_id: str,
        transition: OrderTransition | str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Применяет действие к заказов.

        Аргументы:
            order_id: идентифицирует заказ.
            transition: задает переход статуса заказа.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            APPLY_TRANSITION,
            request=OrderApplyTransitionRequest(order_id=order_id, transition=transition),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/checkConfirmationCode",
        spec="Управлениезаказами.json",
        operation_id="checkConfirmationCode",
        variant="async",
        method_args={"order_id": "body.parcel_id", "code": "body.confirm_code"},
    )
    async def check_confirmation_code(
        self,
        *,
        order_id: str,
        code: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Проверяет confirmation code для заказов.

        Аргументы:
            order_id: идентифицирует заказ.
            code: передает код подтверждения.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CHECK_CONFIRMATION_CODE,
            request=OrderConfirmationCodeRequest(order_id=order_id, code=code),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/cncSetDetails",
        spec="Управлениезаказами.json",
        operation_id="cncSetDetails",
        variant="async",
        method_args={"order_id": "body.id", "pickup_point_id": "body.marketplace_id"},
    )
    async def set_cnc_details(
        self,
        *,
        order_id: str,
        pickup_point_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Устанавливает параметры click-and-collect для заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            pickup_point_id: идентифицирует пункт выдачи click-and-collect.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SET_CNC_DETAILS,
            request=OrderCncDetailsRequest(order_id=order_id, pickup_point_id=pickup_point_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/order-management/1/order/getCourierDeliveryRange",
        spec="Управлениезаказами.json",
        operation_id="getCourierDeliveryRange",
        variant="async",
    )
    async def get_courier_delivery_range(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> CourierRangesResult:
        """Возвращает courier delivery range для заказов.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CourierRangesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_COURIER_DELIVERY_RANGE,
            query={"orderId": "order-1"},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/setCourierDeliveryRange",
        spec="Управлениезаказами.json",
        operation_id="setCourierDeliveryRange",
        variant="async",
        method_args={"order_id": "body.order_id", "interval_id": "body.interval_type"},
    )
    async def set_courier_delivery_range(
        self,
        *,
        order_id: str,
        interval_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Устанавливает интервал курьерской доставки заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            interval_id: идентифицирует интервал курьерской доставки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SET_COURIER_DELIVERY_RANGE,
            request=OrderCourierRangeRequest(order_id=order_id, interval_id=interval_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/order/setTrackingNumber",
        spec="Управлениезаказами.json",
        operation_id="setOrderTrackingNumber",
        variant="async",
        method_args={"order_id": "body.order_id", "tracking_number": "body.tracking_number"},
    )
    async def update_tracking_number(
        self,
        *,
        order_id: str,
        tracking_number: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> OrderActionResult:
        """Обновляет трек-номер заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            tracking_number: передает трек-номер отправления.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `OrderActionResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SET_TRACKING_NUMBER,
            request=OrderTrackingNumberRequest(
                order_id=order_id,
                tracking_number=tracking_number,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncOrderLabel(AsyncDomainObject):
    """Доменный объект генерации и загрузки этикеток."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "order_label"
    __sdk_factory_args__ = {"task_id": "path.task_id"}

    task_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/order-management/1/orders/labels",
        spec="Управлениезаказами.json",
        operation_id="generateLabels",
        variant="async",
        method_args={"order_ids": "body.order_ids"},
    )
    async def create(
        self,
        *,
        order_ids: Sequence[str],
        extended: bool = False,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> LabelTaskResult:
        """Создает задачу генерации ярлыков заказов.

        Аргументы:
            order_ids: передает идентификаторы заказов.
            extended: запрашивает расширенный вариант результата, если поддерживается API.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `LabelTaskResult` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        if extended:
            return await self.create_extended(
                order_ids=order_ids,
                idempotency_key=idempotency_key,
                timeout=timeout,
                retry=retry,
            )
        return await self._execute(
            CREATE_LABELS,
            request=OrderLabelsRequest(order_ids=list(order_ids)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/order-management/1/orders/labels/extended",
        spec="Управлениезаказами.json",
        operation_id="generateLabelsExtended",
        variant="async",
        method_args={"order_ids": "body.order_ids"},
    )
    async def create_extended(
        self,
        *,
        order_ids: Sequence[str],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> LabelTaskResult:
        """Запускает генерацию расширенных этикеток и возвращает типизированную SDK-модель.

        Аргументы:
            order_ids: передает идентификаторы заказов для генерации этикеток.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `LabelTaskResult` с идентификатором задачи генерации расширенных этикеток.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_LABELS_EXTENDED,
            request=OrderLabelsRequest(order_ids=list(order_ids)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/order-management/1/orders/labels/{taskID}/download",
        spec="Управлениезаказами.json",
        operation_id="downloadLabel",
        variant="async",
    )
    async def download(
        self,
        *,
        task_id: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> LabelPdfResult:
        """Скачивает PDF с ярлыками заказов.

        Аргументы:
            task_id: идентифицирует асинхронную задачу.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `LabelPdfResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_task_id = task_id or self._require_task_id()
        binary = await self._execute(
            DOWNLOAD_LABEL,
            path_params={"taskID": resolved_task_id},
            timeout=timeout,
            retry=retry,
        )
        return LabelPdfResult(binary=binary)

    def _require_task_id(self) -> str:
        """Validate required task id."""
        if self.task_id is None:
            raise ValidationError("Для операции требуется `task_id`.")
        return str(self.task_id)


@dataclass(slots=True, frozen=True)
class AsyncDeliveryOrder(AsyncDomainObject):
    """Доменный объект production API доставки."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "delivery_order"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/createAnnouncement",
        spec="Доставка.json",
        operation_id="CreateAnnouncement3PL",
        variant="async",
        method_args={"order_id": "body.announcement_id"},
    )
    async def create_announcement(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает объявление доставки для заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELIVERY_CREATE_ANNOUNCEMENT,
            request=DeliveryAnnouncementRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/cancelAnnouncement",
        spec="Доставка.json",
        operation_id="CancelAnnouncement3PL",
        variant="async",
        method_args={"order_id": "body.announcement_id"},
    )
    async def delete(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Удаляет сущность доставки заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELIVERY_CANCEL_ANNOUNCEMENT,
            request=DeliveryCancelAnnouncementRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/createParcel",
        spec="Доставка.json",
        operation_id="createParcel",
        variant="async",
        method_args={"order_id": "body.order_id", "parcel_id": "body.parcel_id"},
    )
    async def create(
        self,
        *,
        order_id: str,
        parcel_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает сущность доставки заказа.

        Аргументы:
            order_id: идентифицирует заказ.
            parcel_id: идентифицирует отправление.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELIVERY_CREATE_PARCEL,
            request=DeliveryParcelRequest(order_id=order_id, parcel_id=parcel_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/sandbox/changeParcels",
        spec="Доставка.json",
        operation_id="ChangeParcels",
        variant="async",
        method_args={"parcel_ids": "body.applications"},
    )
    async def update_change_parcels(
        self,
        *,
        parcel_ids: Sequence[str],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Обновляет отправления для изменения доставки.

        Аргументы:
            parcel_ids: передает идентификаторы отправлений.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELIVERY_UPDATE_CHANGE_PARCELS,
            request=DeliveryParcelIdsRequest(parcel_ids=list(parcel_ids)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery/order/changeParcelResult",
        spec="Доставка.json",
        operation_id="ChangeParcelResult",
        variant="async",
        method_args={"parcel_id": "body.id", "result": "body.status"},
    )
    async def create_change_parcel_result(
        self,
        *,
        parcel_id: str,
        result: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает результат изменения отправления доставки.

        Аргументы:
            parcel_id: идентифицирует отправление.
            result: передает результат обработки изменения отправления.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELIVERY_CHANGE_PARCEL_RESULT,
            request=DeliveryParcelResultRequest(parcel_id=parcel_id, result=result),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncSandboxDelivery(AsyncDomainObject):
    """Доменный объект sandbox API доставки."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "sandbox_delivery"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/delivery-sandbox/announcements/create",
        spec="Доставка.json",
        operation_id="CreateAnnouncement",
        variant="async",
        method_args={"order_id": "body.announcement_id"},
    )
    async def create_announcement(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает announcement для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CREATE_ANNOUNCEMENT,
            request=DeliverySandboxAnnouncementRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/announcements/track",
        spec="Доставка.json",
        operation_id="TrackAnnouncement",
        variant="async",
        method_args={"order_id": "body.announcement_id"},
    )
    async def track_announcement(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Передает tracking-событие для announcement для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_TRACK_ANNOUNCEMENT,
            request=DeliveryAnnouncementTrackRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/areas/custom-schedule",
        spec="Доставка.json",
        operation_id="customAreaSchedule",
        variant="async",
        method_args={"items": "body"},
    )
    async def update_custom_area_schedule(
        self,
        *,
        items: Sequence[CustomAreaScheduleEntry],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Обновляет custom area schedule для sandbox-доставки.

        Аргументы:
            items: передает элементы пакетного запроса.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_UPDATE_CUSTOM_AREA_SCHEDULE,
            request=CustomAreaScheduleRequest(items=list(items)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/cancelParcel",
        spec="Доставка.json",
        operation_id="cancelParcel",
        variant="async",
        method_args={"parcel_id": "body.parcel_id", "actor": "body.actor"},
    )
    async def cancel_parcel(
        self,
        *,
        parcel_id: str,
        actor: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Отменяет parcel для sandbox-доставки.

        Аргументы:
            parcel_id: идентифицирует отправление.
            actor: задает участника, от имени которого выполняется отмена.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CANCEL_PARCEL,
            request=CancelParcelRequest(parcel_id=parcel_id, actor=actor),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/order/checkConfirmationCode",
        spec="Доставка.json",
        operation_id="checkConfirmationCode",
        variant="async",
        method_args={"parcel_id": "body.parcel_id", "confirm_code": "body.confirm_code"},
    )
    async def check_confirmation_code(
        self,
        *,
        parcel_id: str,
        confirm_code: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Проверяет confirmation code для sandbox-доставки.

        Аргументы:
            parcel_id: идентифицирует отправление.
            confirm_code: передает код подтверждения sandbox-доставки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CHECK_CONFIRMATION_CODE,
            request=SandboxConfirmationCodeRequest(
                parcel_id=parcel_id,
                confirm_code=confirm_code,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/order/properties",
        spec="Доставка.json",
        operation_id="setOrderProperties",
        variant="async",
        method_args={"order_id": "body.order_id", "properties": "body.properties"},
    )
    async def set_order_properties(
        self,
        *,
        order_id: str,
        properties: OrderDeliveryProperties,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Устанавливает order properties для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            properties: передает свойства заказа доставки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_SET_ORDER_PROPERTIES,
            request=SetOrderPropertiesRequest(order_id=order_id, properties=properties),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/order/realAddress",
        spec="Доставка.json",
        operation_id="setOrderRealAddress",
        variant="async",
        method_args={"order_id": "body.order_id", "address": "body.address"},
    )
    async def set_order_real_address(
        self,
        *,
        order_id: str,
        address: RealAddress,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Устанавливает order real address для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            address: передает фактический адрес заказа.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_SET_ORDER_REAL_ADDRESS,
            request=SetOrderRealAddressRequest(order_id=order_id, address=address),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/order/tracking",
        spec="Доставка.json",
        operation_id="tracking",
        variant="async",
        method_args={
            "order_id": "body.order_id",
            "avito_status": "body.avito_status",
            "avito_event_type": "body.avito_event_type",
            "provider_event_code": "body.provider_event_code",
            "date": "body.date",
            "location": "body.location",
        },
    )
    async def tracking(
        self,
        *,
        order_id: str,
        avito_status: TrackingAvitoStatus | str,
        avito_event_type: TrackingAvitoEventType | str,
        provider_event_code: str,
        date: DateInput,
        location: str,
        comment: str | None = None,
        options: DeliveryTrackingOptions | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Выполняет действие `tracking` для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            avito_status: передает статус события Авито.
            avito_event_type: передает тип события Авито.
            provider_event_code: передает код события провайдера.
            date: задает дату события.
            location: передает местоположение события.
            comment: передает комментарий к операции.
            options: передает дополнительные параметры операции.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_TRACKING,
            request=DeliveryTrackingRequest(
                order_id=order_id,
                avito_status=avito_status,
                avito_event_type=avito_event_type,
                provider_event_code=provider_event_code,
                date=serialize_iso_datetime("date", date),
                location=location,
                comment=comment,
                options=options,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/prohibitOrderAcceptance",
        spec="Доставка.json",
        operation_id="prohibitOrderAcceptance",
        variant="async",
        method_args={"order_id": "body.order_id"},
    )
    async def prohibit_order_acceptance(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Запрещает прием order acceptance для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_PROHIBIT_ORDER_ACCEPTANCE,
            request=ProhibitOrderAcceptanceRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/delivery-sandbox/sorting-center",
        spec="Доставка.json",
        operation_id="GetSortingCenter",
        variant="async",
    )
    async def list_sorting_center(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> DeliverySortingCentersResult:
        """Возвращает список sorting center для sandbox-доставки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliverySortingCentersResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_LIST_SORTING_CENTER,
            query={"deliveryProviders": "pochta"},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffs/sorting-center",
        spec="Доставка.json",
        operation_id="AddSortingCenter",
        variant="async",
        method_args={"items": "body"},
    )
    async def add_sorting_center(
        self,
        *,
        items: Sequence[SortingCenterUpload],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Добавляет sorting center для sandbox-доставки.

        Аргументы:
            items: передает элементы пакетного запроса.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_ADD_SORTING_CENTER,
            request=AddSortingCentersRequest(items=list(items)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffs/{tariff_id}/areas",
        spec="Доставка.json",
        operation_id="AddAreasSandbox",
        variant="async",
        method_args={"tariff_id": "path.tariff_id", "areas": "body"},
    )
    async def add_areas(
        self,
        *,
        tariff_id: str,
        areas: Sequence[SandboxArea],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Добавляет areas для sandbox-доставки.

        Аргументы:
            tariff_id: идентифицирует тариф доставки.
            areas: передает зоны доставки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_ADD_AREAS,
            path_params={"tariff_id": tariff_id},
            request=SandboxAreasRequest(areas=list(areas)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffs/{tariff_id}/tagged-sorting-centers",
        spec="Доставка.json",
        operation_id="AddTagsToSortingCenter",
        variant="async",
        method_args={"tariff_id": "path.tariff_id", "items": "body"},
    )
    async def add_tags_to_sorting_center(
        self,
        *,
        tariff_id: str,
        items: Sequence[TaggedSortingCenter],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Добавляет tags to sorting center для sandbox-доставки.

        Аргументы:
            tariff_id: идентифицирует тариф доставки.
            items: передает элементы пакетного запроса.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_ADD_TAGS_TO_SORTING_CENTER,
            path_params={"tariff_id": tariff_id},
            request=TaggedSortingCentersRequest(items=list(items)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffs/{tariff_id}/terminals",
        spec="Доставка.json",
        operation_id="AddTerminalsSandbox",
        variant="async",
        method_args={"tariff_id": "path.tariff_id", "items": "body"},
    )
    async def add_terminals(
        self,
        *,
        tariff_id: str,
        items: Sequence[TerminalUpload],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Добавляет terminals для sandbox-доставки.

        Аргументы:
            tariff_id: идентифицирует тариф доставки.
            items: передает элементы пакетного запроса.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_ADD_TERMINALS,
            path_params={"tariff_id": tariff_id},
            request=AddTerminalsRequest(items=list(items)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffs/{tariff_id}/terms",
        spec="Доставка.json",
        operation_id="UpdateTerms",
        variant="async",
        method_args={"tariff_id": "path.tariff_id", "items": "body"},
    )
    async def update_terms(
        self,
        *,
        tariff_id: str,
        items: Sequence[DeliveryTermsZone],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Обновляет terms для sandbox-доставки.

        Аргументы:
            tariff_id: идентифицирует тариф доставки.
            items: передает элементы пакетного запроса.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_UPDATE_TERMS,
            path_params={"tariff_id": tariff_id},
            request=UpdateTermsRequest(items=list(items)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/tariffsV2",
        spec="Доставка.json",
        operation_id="AddTariffSandboxV2",
        variant="async",
        method_args={
            "name": "body.name",
            "delivery_provider_tariff_id": "body.delivery_provider_tariff_id",
            "directions": "body.directions",
            "tariff_zones": "body.tariff_zones",
            "terms_zones": "body.terms_zones",
        },
    )
    async def add_tariff(
        self,
        *,
        name: str,
        delivery_provider_tariff_id: str,
        directions: Sequence[DeliveryDirection],
        tariff_zones: Sequence[DeliveryTariffZone],
        terms_zones: Sequence[DeliveryTermsZone],
        tariff_type: str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Добавляет tariff для sandbox-доставки.

        Аргументы:
            name: передает название сущности.
            delivery_provider_tariff_id: идентифицирует тариф провайдера доставки.
            directions: передает направления доставки.
            tariff_zones: передает тарифные зоны.
            terms_zones: передает зоны условий доставки.
            tariff_type: задает тип тарифа.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_ADD_TARIFF,
            request=AddTariffV2Request(
                name=name,
                delivery_provider_tariff_id=delivery_provider_tariff_id,
                directions=list(directions),
                tariff_zones=list(tariff_zones),
                terms_zones=list(terms_zones),
                tariff_type=tariff_type,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v2/createParcel",
        spec="Доставка.json",
        operation_id="CreateSandboxParcelV2",
        variant="async",
        method_args={"order_id": "body.items", "parcel_id": "body.items"},
    )
    async def create_parcel(
        self,
        *,
        order_id: str,
        parcel_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает parcel для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            parcel_id: идентифицирует отправление.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CREATE_PARCEL,
            request=SandboxParcelRequest(order_id=order_id, parcel_id=parcel_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/cancelAnnouncement",
        spec="Доставка.json",
        operation_id="v1cancelAnnouncement",
        variant="async",
        method_args={
            "announcement_id": "body.announcement_id",
            "date": "body.date",
            "options": "body.options",
        },
    )
    async def cancel_sandbox_announcement(
        self,
        *,
        announcement_id: str,
        date: DateInput,
        options: SandboxCancelAnnouncementOptions,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Отменяет sandbox announcement для sandbox-доставки.

        Аргументы:
            announcement_id: идентифицирует sandbox-объявление доставки.
            date: задает дату события.
            options: передает дополнительные параметры операции.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CANCEL_SANDBOX_ANNOUNCEMENT,
            request=SandboxCancelAnnouncementRequest(
                announcement_id=announcement_id,
                date=serialize_iso_datetime("date", date),
                options=options,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/cancelParcel",
        spec="Доставка.json",
        operation_id="v1CancelParcel",
        variant="async",
        method_args={"parcel_id": "body.parcel_id"},
    )
    async def cancel_sandbox_parcel(
        self,
        *,
        parcel_id: str,
        options: CancelSandboxParcelOptions | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Отменяет sandbox parcel для sandbox-доставки.

        Аргументы:
            parcel_id: идентифицирует отправление.
            options: передает дополнительные параметры операции.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CANCEL_SANDBOX_PARCEL,
            request=CancelSandboxParcelRequest(parcel_id=parcel_id, options=options),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/changeParcel",
        spec="Доставка.json",
        operation_id="v1changeParcel",
        variant="async",
        method_args={"type": "body.type", "parcel_id": "body.parcel_id"},
    )
    async def change_sandbox_parcel(
        self,
        *,
        type: str,
        parcel_id: str,
        application: ChangeParcelApplication | None = None,
        options: ChangeParcelOptions | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Изменяет sandbox parcel для sandbox-доставки.

        Аргументы:
            type: передает значение `type` в upstream API.
            parcel_id: идентифицирует отправление.
            application: передает значение `application` в upstream API.
            options: передает дополнительные параметры операции.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CHANGE_SANDBOX_PARCEL,
            request=ChangeParcelRequest(
                type=type,
                parcel_id=parcel_id,
                application=application,
                options=options,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/createAnnouncement",
        spec="Доставка.json",
        operation_id="v1createAnnouncement",
        variant="async",
        method_args={
            "announcement_id": "body.announcement_id",
            "barcode": "body.barcode",
            "sender": "body.sender",
            "receiver": "body.receiver",
            "announcement_type": "body.announcement_type",
            "date": "body.date",
            "packages": "body.packages",
            "options": "body.options",
        },
    )
    async def create_sandbox_announcement(
        self,
        *,
        announcement_id: str,
        barcode: str,
        sender: SandboxAnnouncementParticipant,
        receiver: SandboxAnnouncementParticipant,
        announcement_type: str,
        date: DateInput,
        packages: Sequence[SandboxAnnouncementPackage],
        options: SandboxCreateAnnouncementOptions,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Создает sandbox announcement для sandbox-доставки.

        Аргументы:
            announcement_id: идентифицирует sandbox-объявление доставки.
            barcode: передает штрихкод отправления.
            sender: передает данные отправителя.
            receiver: передает данные получателя.
            announcement_type: задает тип sandbox-объявления доставки.
            date: задает дату события.
            packages: передает грузовые места отправления.
            options: передает дополнительные параметры операции.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_CREATE_SANDBOX_ANNOUNCEMENT,
            request=SandboxCreateAnnouncementRequest(
                announcement_id=announcement_id,
                barcode=barcode,
                sender=sender,
                receiver=receiver,
                announcement_type=announcement_type,
                date=serialize_iso_datetime("date", date),
                packages=list(packages),
                options=options,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/getAnnouncementEvent",
        spec="Доставка.json",
        operation_id="v1getAnnouncementEvent",
        variant="async",
        method_args={"announcement_id": "body.announcement_id"},
    )
    async def get_sandbox_announcement_event(
        self,
        *,
        announcement_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Возвращает sandbox announcement event для sandbox-доставки.

        Аргументы:
            announcement_id: идентифицирует sandbox-объявление доставки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_GET_ANNOUNCEMENT_EVENT,
            request=SandboxGetAnnouncementEventRequest(announcement_id=announcement_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/getChangeParcelInfo",
        spec="Доставка.json",
        operation_id="v1getChangeParcelInfo",
        variant="async",
        method_args={"application_id": "body.application_id"},
    )
    async def get_sandbox_change_parcel_info(
        self,
        *,
        application_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Возвращает sandbox change parcel info для sandbox-доставки.

        Аргументы:
            application_id: идентифицирует заявку на изменение отправления.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_GET_CHANGE_PARCEL_INFO,
            request=GetChangeParcelInfoRequest(application_id=application_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/getParcelInfo",
        spec="Доставка.json",
        operation_id="v1getParcelInfo",
        variant="async",
        method_args={"parcel_id": "body.parcel_id"},
    )
    async def get_sandbox_parcel_info(
        self,
        *,
        parcel_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Возвращает sandbox parcel info для sandbox-доставки.

        Аргументы:
            parcel_id: идентифицирует отправление.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_GET_PARCEL_INFO,
            request=GetSandboxParcelInfoRequest(parcel_id=parcel_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/delivery-sandbox/v1/getRegisteredParcelID",
        spec="Доставка.json",
        operation_id="v1getRegisteredParcelID",
        variant="async",
        method_args={"order_id": "body.order_id"},
    )
    async def get_sandbox_registered_parcel_id(
        self,
        *,
        order_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryEntityResult:
        """Возвращает sandbox registered parcel id для sandbox-доставки.

        Аргументы:
            order_id: идентифицирует заказ.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryEntityResult` со статусом выполнения операции.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            SANDBOX_GET_REGISTERED_PARCEL_ID,
            request=GetRegisteredParcelIdRequest(order_id=order_id),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncDeliveryTask(AsyncDomainObject):
    """Доменный объект задачи доставки."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "delivery_task"
    __sdk_factory_args__ = {"task_id": "path.task_id"}

    task_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/delivery-sandbox/tasks/{task_id}",
        spec="Доставка.json",
        operation_id="GetTask",
        variant="async",
    )
    async def get(
        self,
        *,
        task_id: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> DeliveryTaskInfo:
        """Возвращает задач доставки.

        Аргументы:
            task_id: идентифицирует асинхронную задачу.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `DeliveryTaskInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_task_id = task_id or self._require_task_id()
        return await self._execute(
            GET_DELIVERY_TASK,
            path_params={"task_id": resolved_task_id},
            timeout=timeout,
            retry=retry,
        )

    def _require_task_id(self) -> str:
        """Validate required task id."""
        if self.task_id is None:
            raise ValidationError("Для операции требуется `task_id`.")
        return str(self.task_id)


@dataclass(slots=True, frozen=True)
class AsyncStock(AsyncDomainObject):
    """Доменный объект управления остатками."""

    __swagger_domain__ = "orders"
    __sdk_factory__ = "stock"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/stock-management/1/info",
        spec="Управлениеостатками.json",
        variant="async",
        method_args={"item_ids": "body.item_ids"},
    )
    async def get(
        self,
        *,
        item_ids: Sequence[int],
        strong_consistency: bool | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> StockInfoResult:
        """Возвращает остатков товаров.

        Аргументы:
            item_ids: передает идентификаторы объявлений или товаров.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `StockInfoResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_STOCK_INFO,
            request=StockInfoRequest(
                item_ids=list(item_ids),
                strong_consistency=strong_consistency,
            ),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "PUT",
        "/stock-management/1/stocks",
        spec="Управлениеостатками.json",
        variant="async",
        method_args={"stocks": "body.stocks"},
    )
    async def update(
        self,
        *,
        stocks: Sequence[StockUpdateEntry],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> StockUpdateResult:
        """Обновляет остатки товаров.

        Аргументы:
            stocks: передает остатки товаров для обновления.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `StockUpdateResult` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            UPDATE_STOCKS,
            request=StockUpdateRequest(stocks=list(stocks)),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )


__all__ = (
    "AsyncDeliveryOrder",
    "AsyncDeliveryTask",
    "AsyncOrder",
    "AsyncOrderLabel",
    "AsyncSandboxDelivery",
    "AsyncStock",
)
