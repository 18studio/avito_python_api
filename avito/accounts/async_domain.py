"""Async-доменные объекты пакета accounts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from avito.accounts.models import (
    AccountActionResult,
    AccountBalance,
    AccountProfile,
    AhUserStatus,
    CompanyPhonesResult,
    EmployeeItem,
    EmployeeItemLinkRequest,
    EmployeeItemsRequest,
    EmployeesResult,
    OperationRecord,
    OperationsHistoryRequest,
)
from avito.accounts.operations import (
    GET_AH_USER_STATUS,
    GET_BALANCE,
    GET_OPERATIONS_HISTORY,
    GET_SELF,
    LINK_ITEMS,
    LIST_COMPANY_PHONES,
    LIST_EMPLOYEES,
    LIST_ITEMS_BY_EMPLOYEE,
)
from avito.core import (
    ApiTimeouts,
    AsyncPaginatedList,
    AsyncPaginator,
    JsonPage,
    RetryOverride,
    ValidationError,
)
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


@dataclass(slots=True, frozen=True)
class AsyncAccount(AsyncDomainObject):
    """Async-доменный объект операций аккаунта."""

    __swagger_domain__ = "accounts"
    __sdk_factory__ = "account"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/core/v1/accounts/self",
        spec="Информацияопользователе.json",
        operation_id="getUserInfoSelf",
        variant="async",
    )
    async def get_self(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AccountProfile:
        """Получает профиль авторизованного пользователя асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AccountProfile` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_SELF, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/core/v1/accounts/{user_id}/balance",
        spec="Информацияопользователе.json",
        operation_id="getUserBalance",
        variant="async",
    )
    async def get_balance(
        self,
        *,
        user_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AccountBalance:
        """Получает баланс пользователя по явно заданному или настроенному `user_id` асинхронно.

        Аргументы:
            user_id: идентификатор пользователя; если не передан, используется `user_id` фабрики, `AVITO_USER_ID` или `get_self()`.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AccountBalance` с реальным, бонусным и суммарным балансом.

        Поведение:
            `user_id` является keyword-only, чтобы вызов явно показывал источник аккаунта.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_user_id = await self._resolve_account_user_id(user_id)
        return await self._execute(
            GET_BALANCE,
            path_params={"user_id": resolved_user_id},
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/core/v1/accounts/operations_history",
        spec="Информацияопользователе.json",
        operation_id="postOperationsHistory",
        method_args={"date_from": "body.dateTimeFrom", "date_to": "body.dateTimeTo"},
        variant="async",
    )
    async def get_operations_history(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AsyncPaginatedList[OperationRecord]:
        """Возвращает историю операций аккаунта за выбранный период асинхронно.

        Аргументы:
            date_from: задает начальную дату периода.
            date_to: задает конечную дату периода.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `AsyncPaginatedList[OperationRecord]`; первая страница загружается при создании, следующие страницы - при async-итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        async def fetch_page(page: int | None, _cursor: str | None) -> JsonPage[OperationRecord]:
            result = await self._execute(
                GET_OPERATIONS_HISTORY,
                request=OperationsHistoryRequest(
                    date_from=_serialize_datetime(date_from),
                    date_to=_serialize_datetime(date_to),
                ),
                timeout=timeout,
                retry=retry,
            )
            return JsonPage(
                items=result.operations,
                total=result.total,
            )

        return AsyncPaginator(fetch_page).as_list(first_page=await fetch_page(1, None))

    async def _resolve_account_user_id(self, user_id: int | None) -> int:
        if user_id is not None or self.user_id is not None:
            return await self._resolve_user_id(user_id or self.user_id)
        profile = await self.get_self()
        if profile.user_id is None:
            raise ValidationError(
                "Для операции требуется `user_id`: передайте его в фабрику клиента, "
                "в метод операции или задайте `AVITO_USER_ID`."
            )
        return profile.user_id


@dataclass(slots=True, frozen=True)
class AsyncAccountHierarchy(AsyncDomainObject):
    """Async-доменный объект иерархии аккаунтов."""

    __swagger_domain__ = "accounts"
    __sdk_factory__ = "account_hierarchy"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/checkAhUserV1",
        spec="ИерархияАккаунтов.json",
        operation_id="checkAhUserV1",
        variant="async",
    )
    async def get_status(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AhUserStatus:
        """Получает статус пользователя в ИА асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AhUserStatus` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(GET_AH_USER_STATUS, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/getEmployeesV1",
        spec="ИерархияАккаунтов.json",
        operation_id="getEmployeesV1",
        variant="async",
    )
    async def list_employees(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> EmployeesResult:
        """Возвращает сотрудников компании в иерархии аккаунта асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `EmployeesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(LIST_EMPLOYEES, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/listCompanyPhonesV1",
        spec="ИерархияАккаунтов.json",
        operation_id="listCompanyPhonesV1",
        variant="async",
    )
    async def list_company_phones(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> CompanyPhonesResult:
        """Возвращает телефоны компании из иерархии аккаунта асинхронно.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `CompanyPhonesResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(LIST_COMPANY_PHONES, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/linkItemsV1",
        spec="ИерархияАккаунтов.json",
        operation_id="linkItemsV1",
        method_args={"employee_id": "body.employee_id", "item_ids": "body.item_ids"},
        variant="async",
    )
    async def link_items(
        self,
        *,
        employee_id: int,
        item_ids: Sequence[int],
        source_employee_id: int | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AccountActionResult:
        """Прикрепляет объявления к сотруднику асинхронно.

        Аргументы:
            employee_id: идентификатор сотрудника, к которому прикрепляются объявления.
            item_ids: список идентификаторов объявлений.
            source_employee_id: идентификатор сотрудника-источника, если объявления переносятся между сотрудниками.
            idempotency_key: ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `AccountActionResult` с типизированными данными ответа.

        Поведение:
            `idempotency_key` передается в `Idempotency-Key` и должен быть стабильным для одного логического write-вызова.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return await self._execute(
            LINK_ITEMS,
            request=EmployeeItemLinkRequest(
                employee_id=employee_id,
                item_ids=list(item_ids),
                source_employee_id=source_employee_id,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/listItemsByEmployeeIdV1",
        spec="ИерархияАккаунтов.json",
        operation_id="listItemsByEmployeeIdV1",
        method_args={
            "employee_id": "body.employee_id",
            "category_id": "body.category_id",
        },
        variant="async",
    )
    async def list_items_by_employee(
        self,
        *,
        employee_id: int,
        category_id: int,
        last_item_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AsyncPaginatedList[EmployeeItem]:
        """Возвращает объявления, закрепленные за сотрудником компании, асинхронно.

        Аргументы:
            employee_id: идентифицирует сотрудника аккаунта.
            category_id: ограничивает объявления категорией из справочника Авито.
            last_item_id: задает курсор для продолжения выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `AsyncPaginatedList[EmployeeItem]`; первая страница загружается при создании, следующие страницы - при async-итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        async def fetch_page(page: int | None, _cursor: str | None) -> JsonPage[EmployeeItem]:
            current_page = page or 1
            result = await self._execute(
                LIST_ITEMS_BY_EMPLOYEE,
                request=EmployeeItemsRequest(
                    employee_id=employee_id,
                    category_id=category_id,
                    last_item_id=last_item_id,
                ),
                timeout=timeout,
                retry=retry,
            )
            return JsonPage(
                items=result.items,
                total=result.total,
                page=current_page,
                per_page=len(result.items),
            )

        return AsyncPaginator(fetch_page).as_list(first_page=await fetch_page(1, None))


__all__ = ("AsyncAccount", "AsyncAccountHierarchy")
