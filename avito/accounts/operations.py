"""Operation specs for accounts domain."""

from __future__ import annotations

from avito.accounts.models import (
    AccountActionResult,
    AccountBalance,
    AccountProfile,
    AhUserStatus,
    CompanyPhonesResult,
    EmployeeItemLinkRequest,
    EmployeeItemsRequest,
    EmployeeItemsResult,
    EmployeesResult,
    OperationsHistoryRequest,
    OperationsHistoryResult,
)
from avito.core import OperationSpec

GET_SELF = OperationSpec(
    name="accounts.get_self",
    method="GET",
    path="/core/v1/accounts/self",
    response_model=AccountProfile,
)
GET_BALANCE = OperationSpec(
    name="accounts.get_balance",
    method="GET",
    path="/core/v1/accounts/{user_id}/balance/",
    response_model=AccountBalance,
)
GET_OPERATIONS_HISTORY = OperationSpec(
    name="accounts.get_operations_history",
    method="POST",
    path="/core/v1/accounts/operations_history/",
    request_model=OperationsHistoryRequest,
    response_model=OperationsHistoryResult,
    retry_mode="enabled",
)
GET_AH_USER_STATUS = OperationSpec(
    name="accounts.hierarchy.get_status",
    method="GET",
    path="/checkAhUserV1",
    response_model=AhUserStatus,
)
LIST_EMPLOYEES = OperationSpec(
    name="accounts.hierarchy.list_employees",
    method="GET",
    path="/getEmployeesV1",
    response_model=EmployeesResult,
)
LIST_COMPANY_PHONES = OperationSpec(
    name="accounts.hierarchy.list_company_phones",
    method="GET",
    path="/listCompanyPhonesV1",
    response_model=CompanyPhonesResult,
)
LINK_ITEMS = OperationSpec(
    name="accounts.hierarchy.link_items",
    method="POST",
    path="/linkItemsV1",
    request_model=EmployeeItemLinkRequest,
    response_model=AccountActionResult,
    retry_mode="enabled",
)
LIST_ITEMS_BY_EMPLOYEE = OperationSpec(
    name="accounts.hierarchy.list_items_by_employee",
    method="POST",
    path="/listItemsByEmployeeIdV1",
    request_model=EmployeeItemsRequest,
    response_model=EmployeeItemsResult,
    retry_mode="enabled",
)

__all__ = (
    "GET_AH_USER_STATUS",
    "GET_BALANCE",
    "GET_OPERATIONS_HISTORY",
    "GET_SELF",
    "LINK_ITEMS",
    "LIST_COMPANY_PHONES",
    "LIST_EMPLOYEES",
    "LIST_ITEMS_BY_EMPLOYEE",
)
