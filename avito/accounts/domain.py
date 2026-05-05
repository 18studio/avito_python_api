"""Доменные объекты пакета accounts."""

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
    JsonPage,
    PaginatedList,
    Paginator,
    RetryOverride,
    ValidationError,
)
from avito.core.domain import DomainObject
from avito.core.swagger import swagger_operation


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


@dataclass(slots=True, frozen=True)
class Account(DomainObject):
    """Доменный объект операций аккаунта."""

    __swagger_domain__ = "accounts"
    __sdk_factory__ = "account"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/core/v1/accounts/self",
        spec="Информацияопользователе.json",
        operation_id="getUserInfoSelf",
    )
    def get_self(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AccountProfile:
        """Получает профиль авторизованного пользователя.

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

        return self._execute(GET_SELF, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/core/v1/accounts/{user_id}/balance",
        spec="Информацияопользователе.json",
        operation_id="getUserBalance",
    )
    def get_balance(
        self,
        *,
        user_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AccountBalance:
        """Получает баланс пользователя по явно заданному или настроенному `user_id`.

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

        resolved_user_id = self._resolve_account_user_id(user_id)
        return self._execute(
            GET_BALANCE, path_params={"user_id": resolved_user_id}, timeout=timeout, retry=retry
        )

    @swagger_operation(
        "POST",
        "/core/v1/accounts/operations_history",
        spec="Информацияопользователе.json",
        operation_id="postOperationsHistory",
        method_args={"date_from": "body.dateTimeFrom", "date_to": "body.dateTimeTo"},
    )
    def get_operations_history(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PaginatedList[OperationRecord]:
        """Возвращает историю операций аккаунта за выбранный период.

        Аргументы:
            date_from: задает начальную дату периода.
            date_to: задает конечную дату периода.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `PaginatedList[OperationRecord]`; первая страница загружается при создании, следующие страницы - при итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        def fetch_page(page: int | None, _cursor: str | None) -> JsonPage[OperationRecord]:
            result = self._execute(
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

        return Paginator(fetch_page).as_list(first_page=fetch_page(1, None))

    def _resolve_account_user_id(self, user_id: int | None) -> int:
        if user_id is not None or self.user_id is not None:
            return self._resolve_user_id(user_id or self.user_id)
        profile = self.get_self()
        if profile.user_id is None:
            raise ValidationError(
                "Для операции требуется `user_id`: передайте его в фабрику клиента, "
                "в метод операции или задайте `AVITO_USER_ID`."
            )
        return profile.user_id


@dataclass(slots=True, frozen=True)
class AccountHierarchy(DomainObject):
    """Доменный объект иерархии аккаунтов."""

    __swagger_domain__ = "accounts"
    __sdk_factory__ = "account_hierarchy"
    __sdk_factory_args__ = {"user_id": "path.user_id"}

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/checkAhUserV1",
        spec="ИерархияАккаунтов.json",
        operation_id="checkAhUserV1",
    )
    def get_status(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> AhUserStatus:
        """Получает статус пользователя в ИА.

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

        return self._execute(GET_AH_USER_STATUS, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/getEmployeesV1",
        spec="ИерархияАккаунтов.json",
        operation_id="getEmployeesV1",
    )
    def list_employees(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> EmployeesResult:
        """Возвращает сотрудников компании в иерархии аккаунта.

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

        return self._execute(LIST_EMPLOYEES, timeout=timeout, retry=retry)

    @swagger_operation(
        "GET",
        "/listCompanyPhonesV1",
        spec="ИерархияАккаунтов.json",
        operation_id="listCompanyPhonesV1",
    )
    def list_company_phones(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> CompanyPhonesResult:
        """Возвращает телефоны компании из иерархии аккаунта.

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

        return self._execute(LIST_COMPANY_PHONES, timeout=timeout, retry=retry)

    @swagger_operation(
        "POST",
        "/linkItemsV1",
        spec="ИерархияАккаунтов.json",
        operation_id="linkItemsV1",
        method_args={"employee_id": "body.employee_id", "item_ids": "body.item_ids"},
    )
    def link_items(
        self,
        *,
        employee_id: int,
        item_ids: Sequence[int],
        source_employee_id: int | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> AccountActionResult:
        """Прикрепляет объявления к сотруднику.

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

        return self._execute(
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
    )
    def list_items_by_employee(
        self,
        *,
        employee_id: int,
        category_id: int,
        last_item_id: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> PaginatedList[EmployeeItem]:
        """Возвращает объявления, закрепленные за сотрудником компании.

        Аргументы:
            employee_id: идентифицирует сотрудника аккаунта.
            category_id: ограничивает объявления категорией из справочника Авито.
            last_item_id: задает курсор для продолжения выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            Ленивый `PaginatedList[EmployeeItem]`; первая страница загружается при создании, следующие страницы - при итерации.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        def fetch_page(page: int | None, _cursor: str | None) -> JsonPage[EmployeeItem]:
            current_page = page or 1
            result = self._execute(
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

        return Paginator(fetch_page).as_list(first_page=fetch_page(1, None))


__all__ = ("Account", "AccountHierarchy")
