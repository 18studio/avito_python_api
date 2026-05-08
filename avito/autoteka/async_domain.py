"""Async-доменные объекты пакета autoteka."""

from __future__ import annotations

from dataclasses import dataclass

from avito.autoteka.models import (
    AutotekaLeadsResult,
    AutotekaPackageInfo,
    AutotekaPreviewInfo,
    AutotekaReportInfo,
    AutotekaReportsResult,
    AutotekaScoringInfo,
    AutotekaSpecificationInfo,
    AutotekaTeaserInfo,
    AutotekaValuationInfo,
    CatalogResolveRequest,
    CatalogResolveResult,
    ExternalItemPreviewRequest,
    ItemIdRequest,
    LeadsRequest,
    MonitoringBucketRequest,
    MonitoringBucketResult,
    MonitoringEventsQuery,
    MonitoringEventsResult,
    PlateNumberRequest,
    PreviewReportRequest,
    RegNumberRequest,
    TeaserCreateRequest,
    ValuationBySpecificationRequest,
    VehicleIdRequest,
    VinRequest,
)
from avito.autoteka.operations import (
    ADD_MONITORING_BUCKET,
    CATALOG_RESOLVE,
    CREATE_PREVIEW_BY_EXTERNAL_ITEM,
    CREATE_PREVIEW_BY_ITEM_ID,
    CREATE_PREVIEW_BY_REG_NUMBER,
    CREATE_PREVIEW_BY_VIN,
    CREATE_REPORT,
    CREATE_REPORT_BY_VEHICLE_ID,
    CREATE_SCORING_BY_VEHICLE_ID,
    CREATE_SPECIFICATION_BY_PLATE_NUMBER,
    CREATE_SPECIFICATION_BY_VEHICLE_ID,
    CREATE_SYNC_REPORT_BY_REG_NUMBER,
    CREATE_SYNC_REPORT_BY_VIN,
    CREATE_TEASER,
    DELETE_MONITORING_BUCKET,
    GET_ACTIVE_PACKAGE,
    GET_LEADS,
    GET_MONITORING_REG_ACTIONS,
    GET_PREVIEW,
    GET_REPORT,
    GET_SCORING_BY_ID,
    GET_SPECIFICATION_BY_ID,
    GET_TEASER,
    GET_VALUATION_BY_SPECIFICATION,
    LIST_REPORTS,
    REMOVE_MONITORING_BUCKET,
)
from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.async_transport import AsyncTransport
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation


async def _autoteka_headers(transport: AsyncTransport) -> dict[str, str]:
    """Run the autoteka headers helper."""
    auth_provider = transport.auth_provider
    if auth_provider is None:
        return {}
    return {"Authorization": f"Bearer {await auth_provider.get_autoteka_access_token()}"}


@dataclass(slots=True, frozen=True)
class AsyncAutotekaVehicle(AsyncDomainObject):
    """Доменный объект превью, спецификаций, тизеров и каталога."""

    __swagger_domain__ = "autoteka"
    __sdk_factory__ = "autoteka_vehicle"
    __sdk_factory_args__ = {"vehicle_id": "path.vehicle_id"}

    vehicle_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/autoteka/v1/catalogs/resolve",
        spec="Автотека.json",
        operation_id="catalogsResolve",
        variant="async",
        method_args={"brand_id": "body.fieldsValueIds[].valueId"},
    )
    async def resolve_catalog(
        self,
        *,
        brand_id: int,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> CatalogResolveResult:
        """Актуализирует параметры автокаталога.

        Аргументы:
            brand_id: идентифицирует марку автомобиля в каталоге.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CatalogResolveResult` с актуализированными параметрами каталога.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CATALOG_RESOLVE,
            request=CatalogResolveRequest(brand_id=brand_id),
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/get-leads",
        spec="Автотека.json",
        operation_id="getLeads",
        variant="async",
        method_args={"subscription_id": "body.subscriptionId", "limit": "body.limit"},
    )
    async def get_leads(
        self,
        *,
        subscription_id: int,
        limit: int,
        last_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaLeadsResult:
        """Возвращает leads для автомобилей Автотеки.

        Аргументы:
            subscription_id: идентифицирует подписку Сигнала.
            limit: ограничивает размер возвращаемой выборки.
            last_id: задает последний прочитанный идентификатор для постраничной выдачи.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaLeadsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_LEADS,
            request=LeadsRequest(subscription_id=subscription_id, limit=limit, last_id=last_id),
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/previews",
        spec="Автотека.json",
        operation_id="postPreviewByVin",
        variant="async",
        method_args={"vin": "body.vin"},
    )
    async def create_preview_by_vin(
        self,
        *,
        vin: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaPreviewInfo:
        """Создает preview автомобиля Автотеки по VIN.

        Аргументы:
            vin: передает VIN автомобиля.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPreviewInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_PREVIEW_BY_VIN,
            request=VinRequest(vin=vin),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/previews/{previewId}",
        spec="Автотека.json",
        operation_id="getPreview",
        variant="async",
    )
    async def get_preview(
        self,
        *,
        preview_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaPreviewInfo:
        """Возвращает preview для автомобилей Автотеки.

        Аргументы:
            preview_id: идентифицирует preview Автотеки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPreviewInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_PREVIEW,
            path_params={"previewId": preview_id or self._require_vehicle_id("preview_id")},
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/request-preview-by-external-item",
        spec="Автотека.json",
        operation_id="postPreviewByExternalItem",
        variant="async",
        method_args={"item_id": "body.itemId", "site": "body.site"},
    )
    async def create_preview_by_external_item(
        self,
        *,
        item_id: str,
        site: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaPreviewInfo:
        """Создает preview автомобиля Автотеки по внешнему объявлению.

        Аргументы:
            item_id: идентифицирует объявление Авито.
            site: задает площадку внешнего объявления.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPreviewInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_PREVIEW_BY_EXTERNAL_ITEM,
            request=ExternalItemPreviewRequest(item_id=item_id, site=site),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/request-preview-by-item-id",
        spec="Автотека.json",
        operation_id="postPreviewByItemId",
        variant="async",
        method_args={"item_id": "body.item_id"},
    )
    async def create_preview_by_item_id(
        self,
        *,
        item_id: int,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaPreviewInfo:
        """Создает preview автомобиля Автотеки по объявлению Авито.

        Аргументы:
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPreviewInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_PREVIEW_BY_ITEM_ID,
            request=ItemIdRequest(item_id=item_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/request-preview-by-regnumber",
        spec="Автотека.json",
        operation_id="postPreviewByRegNumber",
        variant="async",
        method_args={"reg_number": "body.reg_number"},
    )
    async def create_preview_by_reg_number(
        self,
        *,
        reg_number: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaPreviewInfo:
        """Создает preview автомобиля Автотеки по госномеру.

        Аргументы:
            reg_number: передает государственный номер автомобиля.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPreviewInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_PREVIEW_BY_REG_NUMBER,
            request=RegNumberRequest(reg_number=reg_number),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/specifications/by-plate-number",
        spec="Автотека.json",
        operation_id="specificationByPlateNumber",
        variant="async",
        method_args={"plate_number": "body.plate_number"},
    )
    async def create_specification_by_plate_number(
        self,
        *,
        plate_number: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaSpecificationInfo:
        """Создает спецификацию автомобиля Автотеки по номерному знаку.

        Аргументы:
            plate_number: передает номерной знак автомобиля.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaSpecificationInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_SPECIFICATION_BY_PLATE_NUMBER,
            request=PlateNumberRequest(plate_number=plate_number),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/specifications/by-vehicle-id",
        spec="Автотека.json",
        operation_id="specificationByVehicleId",
        variant="async",
        method_args={"vehicle_id": "body.vehicle_id"},
    )
    async def create_specification_by_vehicle_id(
        self,
        *,
        vehicle_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaSpecificationInfo:
        """Создает спецификацию автомобиля Автотеки по vehicle_id.

        Аргументы:
            vehicle_id: идентифицирует автомобиль в Автотеке.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaSpecificationInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_SPECIFICATION_BY_VEHICLE_ID,
            request=VehicleIdRequest(vehicle_id=vehicle_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/specifications/specification/{specificationID}",
        spec="Автотека.json",
        operation_id="specificationGetById",
        variant="async",
    )
    async def get_specification_by_id(
        self,
        *,
        specification_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaSpecificationInfo:
        """Возвращает спецификацию автомобиля Автотеки по идентификатору.

        Аргументы:
            specification_id: идентифицирует спецификацию автомобиля.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaSpecificationInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_SPECIFICATION_BY_ID,
            path_params={
                "specificationID": specification_id or self._require_vehicle_id("specification_id")
            },
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/teasers",
        spec="Автотека.json",
        operation_id="postTeaser",
        variant="async",
        method_args={"vehicle_id": "body.vehicle_id"},
    )
    async def create_teaser(
        self,
        *,
        vehicle_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaTeaserInfo:
        """Создает тизер автомобиля Автотеки.

        Аргументы:
            vehicle_id: идентифицирует автомобиль в Автотеке.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaTeaserInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_TEASER,
            request=TeaserCreateRequest(vehicle_id=vehicle_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/teasers/{teaser_id}",
        spec="Автотека.json",
        operation_id="getTeaser",
        variant="async",
    )
    async def get_teaser(
        self,
        *,
        teaser_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaTeaserInfo:
        """Возвращает teaser для автомобилей Автотеки.

        Аргументы:
            teaser_id: идентифицирует тизер Автотеки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaTeaserInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_TEASER,
            path_params={"teaser_id": teaser_id or self._require_vehicle_id("teaser_id")},
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    def _require_vehicle_id(self, field_name: str) -> str:
        """Validate required vehicle id."""
        if self.vehicle_id is None:
            raise ValidationError(f"Для операции требуется `{field_name}`.")
        return str(self.vehicle_id)


@dataclass(slots=True, frozen=True)
class AsyncAutotekaReport(AsyncDomainObject):
    """Доменный объект отчетов и пакетов Автотеки."""

    __swagger_domain__ = "autoteka"
    __sdk_factory__ = "autoteka_report"
    __sdk_factory_args__ = {"report_id": "path.report_id"}

    report_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/autoteka/v1/packages/active_package",
        spec="Автотека.json",
        operation_id="getActivePackage",
        variant="async",
    )
    async def get_active_package(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutotekaPackageInfo:
        """Возвращает active package для отчетов Автотеки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaPackageInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_ACTIVE_PACKAGE,
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/reports",
        spec="Автотека.json",
        operation_id="postReport",
        variant="async",
        method_args={"preview_id": "body.preview_id"},
    )
    async def create_report(
        self,
        *,
        preview_id: int,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaReportInfo:
        """Создает отчет Автотеки по preview.

        Аргументы:
            preview_id: идентифицирует preview Автотеки.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_REPORT,
            request=PreviewReportRequest(preview_id=preview_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/reports-by-vehicle-id",
        spec="Автотека.json",
        operation_id="postReportByVehicleId",
        variant="async",
        method_args={"vehicle_id": "body.vehicle_id"},
    )
    async def create_report_by_vehicle_id(
        self,
        *,
        vehicle_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaReportInfo:
        """Создает отчет Автотеки по vehicle_id.

        Аргументы:
            vehicle_id: идентифицирует автомобиль в Автотеке.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_REPORT_BY_VEHICLE_ID,
            request=VehicleIdRequest(vehicle_id=vehicle_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/reports/list",
        spec="Автотека.json",
        operation_id="getReportList",
        variant="async",
    )
    async def list_reports(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AutotekaReportsResult:
        """Возвращает список reports для отчетов Автотеки.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LIST_REPORTS,
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/reports/{report_id}",
        spec="Автотека.json",
        operation_id="getReport",
        variant="async",
    )
    async def get_report(
        self,
        *,
        report_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaReportInfo:
        """Возвращает report для отчетов Автотеки.

        Аргументы:
            report_id: идентифицирует отчет Автотеки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_REPORT,
            path_params={"report_id": report_id or self._require_report_id()},
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/sync/create-by-regnumber",
        spec="Автотека.json",
        operation_id="postSyncCreateReportByRegNumber",
        variant="async",
        method_args={"reg_number": "body.reg_number"},
    )
    async def create_sync_report_by_reg_number(
        self,
        *,
        reg_number: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaReportInfo:
        """Создает синхронный отчет Автотеки по госномеру.

        Аргументы:
            reg_number: передает государственный номер автомобиля.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_SYNC_REPORT_BY_REG_NUMBER,
            request=RegNumberRequest(reg_number=reg_number),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/sync/create-by-vin",
        spec="Автотека.json",
        operation_id="postSyncCreateReportByVin",
        variant="async",
        method_args={"vin": "body.vin"},
    )
    async def create_sync_report_by_vin(
        self,
        *,
        vin: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaReportInfo:
        """Создает синхронный отчет Автотеки по VIN.

        Аргументы:
            vin: передает VIN автомобиля.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaReportInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_SYNC_REPORT_BY_VIN,
            request=VinRequest(vin=vin),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_report_id(self) -> str:
        """Validate required report id."""
        if self.report_id is None:
            raise ValidationError("Для операции требуется `report_id`.")
        return str(self.report_id)


@dataclass(slots=True, frozen=True)
class AsyncAutotekaMonitoring(AsyncDomainObject):
    """Доменный объект мониторинга Автотеки."""

    __swagger_domain__ = "autoteka"
    __sdk_factory__ = "autoteka_monitoring"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/autoteka/v1/monitoring/bucket/add",
        spec="Автотека.json",
        operation_id="monitoringBucketAdd",
        variant="async",
        method_args={"vehicles": "body.data"},
    )
    async def create_monitoring_bucket_add(
        self,
        *,
        vehicles: list[str],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MonitoringBucketResult:
        """Создает monitoring bucket add для мониторинга Автотеки.

        Аргументы:
            vehicles: передает автомобили для добавления в мониторинг.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MonitoringBucketResult` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            ADD_MONITORING_BUCKET,
            request=MonitoringBucketRequest(vehicles=vehicles),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/monitoring/bucket/delete",
        spec="Автотека.json",
        operation_id="monitoringBucketDelete",
        variant="async",
    )
    async def delete_bucket(
        self,
        *,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MonitoringBucketResult:
        """Очищает bucket мониторинга.

        Аргументы:
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MonitoringBucketResult` со статусом операции над bucket мониторинга.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            DELETE_MONITORING_BUCKET,
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/autoteka/v1/monitoring/bucket/remove",
        spec="Автотека.json",
        operation_id="monitoringBucketRemove",
        variant="async",
        method_args={"vehicles": "body.data"},
    )
    async def remove_bucket(
        self,
        *,
        vehicles: list[str],
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MonitoringBucketResult:
        """Удаляет автомобили из bucket мониторинга.

        Аргументы:
            vehicles: передает идентификаторы автомобилей для удаления из bucket.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MonitoringBucketResult` со статусом операции над bucket мониторинга.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            REMOVE_MONITORING_BUCKET,
            request=MonitoringBucketRequest(vehicles=vehicles),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/monitoring/get-reg-actions",
        spec="Автотека.json",
        operation_id="monitoringGetRegActions",
        variant="async",
    )
    async def get_monitoring_reg_actions(
        self,
        *,
        limit: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> MonitoringEventsResult:
        """Возвращает monitoring reg actions для мониторинга Автотеки.

        Аргументы:
            limit: ограничивает размер возвращаемой выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `MonitoringEventsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_MONITORING_REG_ACTIONS,
            query=MonitoringEventsQuery(limit=limit),
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )


@dataclass(slots=True, frozen=True)
class AsyncAutotekaScoring(AsyncDomainObject):
    """Доменный объект скоринга рисков."""

    __swagger_domain__ = "autoteka"
    __sdk_factory__ = "autoteka_scoring"
    __sdk_factory_args__ = {"scoring_id": "path.scoring_id"}

    scoring_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/autoteka/v1/scoring/by-vehicle-id",
        spec="Автотека.json",
        operation_id="scoringByVehicleId",
        variant="async",
        method_args={"vehicle_id": "body.vehicle_id"},
    )
    async def create_scoring_by_vehicle_id(
        self,
        *,
        vehicle_id: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaScoringInfo:
        """Создает расчет скоринга Автотеки по vehicle_id.

        Аргументы:
            vehicle_id: идентифицирует автомобиль в Автотеке.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaScoringInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            CREATE_SCORING_BY_VEHICLE_ID,
            request=VehicleIdRequest(vehicle_id=vehicle_id),
            headers=await _autoteka_headers(self.transport),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/autoteka/v1/scoring/{scoring_id}",
        spec="Автотека.json",
        operation_id="scoringGetById",
        variant="async",
    )
    async def get_scoring_by_id(
        self,
        *,
        scoring_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaScoringInfo:
        """Возвращает расчет скоринга Автотеки по идентификатору.

        Аргументы:
            scoring_id: идентифицирует расчет скоринга.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaScoringInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_SCORING_BY_ID,
            path_params={"scoring_id": scoring_id or self._require_scoring_id()},
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )

    def _require_scoring_id(self) -> str:
        """Validate required scoring id."""
        if self.scoring_id is None:
            raise ValidationError("Для операции требуется `scoring_id`.")
        return str(self.scoring_id)


@dataclass(slots=True, frozen=True)
class AsyncAutotekaValuation(AsyncDomainObject):
    """Доменный объект оценки автомобиля."""

    __swagger_domain__ = "autoteka"
    __sdk_factory__ = "autoteka_valuation"

    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/autoteka/v1/valuation/by-specification",
        spec="Автотека.json",
        operation_id="valuationBySpecification",
        variant="async",
        method_args={
            "specification_id": "body.specification.brand.valueId",
            "mileage": "body.mileage",
        },
    )
    async def get_valuation_by_specification(
        self,
        *,
        specification_id: int,
        mileage: int,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AutotekaValuationInfo:
        """Возвращает оценку автомобиля Автотеки по спецификации.

        Аргументы:
            specification_id: идентифицирует спецификацию автомобиля.
            mileage: передает пробег автомобиля.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AutotekaValuationInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            GET_VALUATION_BY_SPECIFICATION,
            request=ValuationBySpecificationRequest(
                specification_id=specification_id,
                mileage=mileage,
            ),
            headers=await _autoteka_headers(self.transport),
            timeout=timeout,
            retry=retry,
        )


__all__ = (
    "AsyncAutotekaMonitoring",
    "AsyncAutotekaReport",
    "AsyncAutotekaScoring",
    "AsyncAutotekaValuation",
    "AsyncAutotekaVehicle",
)
