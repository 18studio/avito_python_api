"""Типизированные модели раздела accounts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from avito.core import ApiModel, JsonReader, RequestModel


class OperationType(str, Enum):
    """Тип операции по аккаунту."""

    UNKNOWN = "__unknown__"
    PAYMENT = "payment"


class OperationStatus(str, Enum):
    """Статус операции по аккаунту."""

    UNKNOWN = "__unknown__"
    DONE = "done"


class AccountHierarchyRole(str, Enum):
    """Роль пользователя в иерархии аккаунтов."""

    UNKNOWN = "__unknown__"
    MANAGER = "manager"


class EmployeeItemStatus(str, Enum):
    """Статус объявления сотрудника."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"


@dataclass(slots=True, frozen=True)
class AccountProfile(ApiModel):
    """Профиль авторизованного пользователя."""

    user_id: int | None
    name: str | None
    email: str | None
    phone: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AccountProfile:
        """Преобразует ответ API с профилем пользователя в SDK-модель."""

        reader = JsonReader(payload)
        return cls(
            user_id=reader.optional_int("id", "user_id"),
            name=reader.optional_str("name", "title"),
            email=reader.optional_str("email"),
            phone=reader.optional_str("phone"),
        )


@dataclass(slots=True, frozen=True)
class AccountBalance(ApiModel):
    """Баланс кошелька пользователя."""

    user_id: int | None
    real: float | None
    bonus: float | None
    total: float | None
    currency: str | None

    @classmethod
    def from_payload(cls, payload: object) -> AccountBalance:
        """Преобразует ответ API с балансом аккаунта в SDK-модель."""

        reader = JsonReader(payload)
        wallet = reader.mapping("balance")
        wallet_reader = JsonReader(wallet if wallet is not None else payload)
        real = wallet_reader.optional_float("real", "amount", "balance")
        bonus = wallet_reader.optional_float("bonus")
        total = wallet_reader.optional_float("total")
        if total is None and real is not None:
            total = real + bonus if bonus is not None else real
        return cls(
            user_id=reader.optional_int("user_id", "userId", "id"),
            real=real,
            bonus=bonus,
            total=total,
            currency=wallet_reader.optional_str("currency"),
        )


@dataclass(slots=True, frozen=True)
class OperationRecord(ApiModel):
    """Операция по аккаунту."""

    id: str | None
    created_at: datetime | None
    amount: float | None
    operation_type: OperationType | None
    status: OperationStatus | None
    description: str | None

    @classmethod
    def from_payload(cls, payload: object) -> OperationRecord:
        """Преобразует JSON-объект операции аккаунта в SDK-модель."""

        reader = JsonReader(payload)
        return cls(
            id=reader.optional_str("id", "operation_id"),
            created_at=reader.optional_datetime("created_at", "createdAt", "date"),
            amount=reader.optional_float("amount", "price", "sum"),
            operation_type=reader.enum(
                OperationType,
                "type",
                "operation_type",
                "operationType",
                unknown=OperationType.UNKNOWN,
            ),
            status=reader.enum(OperationStatus, "status", unknown=OperationStatus.UNKNOWN),
            description=reader.optional_str("description", "title"),
        )


@dataclass(slots=True, frozen=True)
class OperationsHistoryRequest(RequestModel):
    """Фильтр истории операций аккаунта."""

    date_from: str
    date_to: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует фильтр в JSON body."""

        return _without_none(
            {
                "dateTimeFrom": self.date_from,
                "dateTimeTo": self.date_to,
            }
        )


@dataclass(slots=True, frozen=True)
class OperationsHistoryResult(ApiModel):
    """История операций пользователя."""

    operations: list[OperationRecord]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> OperationsHistoryResult:
        """Преобразует ответ API с историей операций в SDK-модель."""

        reader = JsonReader(payload)
        result = reader.mapping("result")
        data_reader = JsonReader(result) if result is not None else reader
        return cls(
            operations=[
                OperationRecord.from_payload(item)
                for item in data_reader.list("operations", "items", "result")
                if isinstance(item, Mapping)
            ],
            total=data_reader.optional_int("total", "count"),
        )


@dataclass(slots=True, frozen=True)
class AhUserStatus(ApiModel):
    """Статус пользователя в иерархии аккаунтов."""

    user_id: int | None
    is_active: bool | None
    role: AccountHierarchyRole | None

    @classmethod
    def from_payload(cls, payload: object) -> AhUserStatus:
        """Преобразует ответ API со статусом пользователя в иерархии."""

        reader = JsonReader(payload)
        return cls(
            user_id=reader.optional_int("user_id", "userId", "id"),
            is_active=reader.optional_bool("is_active", "isActive", "active"),
            role=reader.enum(
                AccountHierarchyRole,
                "role",
                "status",
                unknown=AccountHierarchyRole.UNKNOWN,
            ),
        )


@dataclass(slots=True, frozen=True)
class Employee(ApiModel):
    """Сотрудник иерархии аккаунтов."""

    employee_id: int | None
    user_id: int | None
    name: str | None
    phone: str | None
    email: str | None

    @classmethod
    def from_payload(cls, payload: object) -> Employee:
        """Преобразует JSON-объект сотрудника в SDK-модель."""

        reader = JsonReader(payload)
        return cls(
            employee_id=reader.optional_int("employee_id", "employeeId", "id"),
            user_id=reader.optional_int("user_id", "userId"),
            name=reader.optional_str("name", "title"),
            phone=reader.optional_str("phone"),
            email=reader.optional_str("email"),
        )


@dataclass(slots=True, frozen=True)
class EmployeesResult(ApiModel):
    """Список сотрудников иерархии."""

    items: list[Employee]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> EmployeesResult:
        """Преобразует ответ API со списком сотрудников."""

        if isinstance(payload, list):
            return cls(
                items=[
                    Employee.from_payload(item)
                    for item in payload
                    if isinstance(item, Mapping)
                ]
            )

        reader = JsonReader(payload)
        return cls(
            items=[
                Employee.from_payload(item)
                for item in reader.list("employees", "items", "result")
                if isinstance(item, Mapping)
            ],
            total=reader.optional_int("total", "count"),
        )


@dataclass(slots=True, frozen=True)
class CompanyPhone(ApiModel):
    """Телефон компании."""

    phone_id: int | None
    phone: str | None
    comment: str | None

    @classmethod
    def from_payload(cls, payload: object) -> CompanyPhone:
        """Преобразует JSON-объект телефона компании."""

        if isinstance(payload, str):
            return cls(phone_id=None, phone=payload, comment=None)

        reader = JsonReader(payload)
        return cls(
            phone_id=reader.optional_int("id", "phone_id", "phoneId"),
            phone=reader.optional_str("phone", "value"),
            comment=reader.optional_str("comment", "description"),
        )


@dataclass(slots=True, frozen=True)
class CompanyPhonesResult(ApiModel):
    """Список телефонов компании."""

    items: list[CompanyPhone]

    @classmethod
    def from_payload(cls, payload: object) -> CompanyPhonesResult:
        """Преобразует ответ API со списком телефонов компании."""

        reader = JsonReader(payload)
        result = reader.mapping("result")
        data_reader = JsonReader(result) if result is not None else reader
        return cls(
            items=[
                CompanyPhone.from_payload(item)
                for item in data_reader.list("phones", "items", "result")
            ]
        )


@dataclass(slots=True, frozen=True)
class EmployeeItemLinkRequest(RequestModel):
    """Запрос на привязку объявлений к сотруднику."""

    employee_id: int
    item_ids: list[int]
    source_employee_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос привязки в JSON body."""

        return _without_none(
            {
                "employeeId": self.employee_id,
                "itemIds": self.item_ids,
                "sourceEmployeeId": self.source_employee_id,
            }
        )


@dataclass(slots=True, frozen=True)
class EmployeeItemsRequest(RequestModel):
    """Запрос списка объявлений сотрудника."""

    employee_id: int
    category_id: int
    last_item_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Сериализует фильтр объявлений сотрудника."""

        return _without_none(
            {
                "employeeId": self.employee_id,
                "categoryId": self.category_id,
                "lastItemId": self.last_item_id,
            }
        )


@dataclass(slots=True, frozen=True)
class EmployeeItem(ApiModel):
    """Объявление сотрудника в иерархии."""

    item_id: int | None
    title: str | None
    status: EmployeeItemStatus | None
    price: float | None

    @classmethod
    def from_payload(cls, payload: object) -> EmployeeItem:
        """Преобразует JSON-объект объявления сотрудника."""

        reader = JsonReader(payload)
        return cls(
            item_id=reader.optional_int("item_id", "itemId", "id"),
            title=reader.optional_str("title"),
            status=reader.enum(EmployeeItemStatus, "status", unknown=EmployeeItemStatus.UNKNOWN),
            price=reader.optional_float("price"),
        )


@dataclass(slots=True, frozen=True)
class EmployeeItemsResult(ApiModel):
    """Список объявлений сотрудника."""

    items: list[EmployeeItem]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> EmployeeItemsResult:
        """Преобразует ответ API со списком объявлений сотрудника."""

        reader = JsonReader(payload)
        return cls(
            items=[
                EmployeeItem.from_payload(item)
                for item in reader.list("items", "result")
                if isinstance(item, Mapping)
            ],
            total=reader.optional_int("total", "count"),
        )


@dataclass(slots=True, frozen=True)
class AccountActionResult(ApiModel):
    """Результат мутационной операции accounts."""

    success: bool
    message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> AccountActionResult:
        """Преобразует ответ API мутационной операции accounts."""

        if not isinstance(payload, Mapping):
            return cls(success=True)
        reader = JsonReader(payload)
        success = reader.optional_bool("success")
        return cls(
            success=True if success is None else success,
            message=reader.optional_str("message", "status"),
        )


def _without_none(payload: Mapping[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if value is not None}


__all__ = (
    "AccountActionResult",
    "AccountBalance",
    "AccountHierarchyRole",
    "AccountProfile",
    "AhUserStatus",
    "CompanyPhone",
    "CompanyPhonesResult",
    "Employee",
    "EmployeeItem",
    "EmployeeItemLinkRequest",
    "EmployeeItemStatus",
    "EmployeeItemsRequest",
    "EmployeeItemsResult",
    "EmployeesResult",
    "OperationRecord",
    "OperationStatus",
    "OperationType",
    "OperationsHistoryRequest",
    "OperationsHistoryResult",
)
