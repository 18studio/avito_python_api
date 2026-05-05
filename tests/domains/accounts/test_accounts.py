from __future__ import annotations

import json
from datetime import datetime

import httpx

from avito.accounts import Account, AccountHierarchy
from tests.helpers.transport import make_transport


def test_account_domain_maps_profile_balance_and_operations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/core/v1/accounts/self":
            return httpx.Response(
                200, json={"id": 7, "name": "Иван", "email": "user@example.com", "phone": "+7999"}
            )
        if request.url.path == "/core/v1/accounts/7/balance/":
            return httpx.Response(
                200,
                json={"user_id": 7, "balance": {"real": 150.5, "bonus": 20.0, "currency": "RUB"}},
            )
        assert request.url.path == "/core/v1/accounts/operations_history/"
        assert json.loads(request.content.decode()) == {
            "dateTimeFrom": "2025-01-01T00:00:00+00:00",
            "dateTimeTo": "2025-01-31T00:00:00+00:00",
        }
        return httpx.Response(
            200,
            json={
                "total": 1,
                "operations": [
                    {
                        "id": "op-1",
                        "created_at": "2025-01-02T12:00:00Z",
                        "amount": 120.0,
                        "type": "payment",
                        "status": "done",
                    }
                ],
            },
        )

    transport = make_transport(httpx.MockTransport(handler))
    account = Account(transport, user_id=7)

    profile = account.get_self()
    balance = account.get_balance()
    history = account.get_operations_history(
        date_from=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
        date_to=datetime.fromisoformat("2025-01-31T00:00:00+00:00"),
    )

    assert profile.user_id == 7
    assert balance.total == 170.5
    assert len(history.materialize()) == 1
    assert history[0].operation_type == "payment"


def test_account_balance_resolves_user_id_from_self_when_not_configured() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/core/v1/accounts/self":
            return httpx.Response(200, json={"id": 7})
        return httpx.Response(200, json={"user_id": 7, "balance": {"real": 150.0}})

    account = Account(make_transport(httpx.MockTransport(handler)))

    balance = account.get_balance()

    assert balance.user_id == 7
    assert seen_paths == ["/core/v1/accounts/self", "/core/v1/accounts/7/balance/"]


def test_account_balance_requires_keyword_user_id() -> None:
    account = Account(make_transport(httpx.MockTransport(lambda request: httpx.Response(200))))

    try:
        account.get_balance(7)  # type: ignore[misc]
    except TypeError as error:
        assert "positional" in str(error)
    else:  # pragma: no cover
        raise AssertionError("get_balance accepted positional user_id")


def test_account_hierarchy_domain_maps_employees_phones_and_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/checkAhUserV1":
            return httpx.Response(200, json={"user_id": 7, "is_active": True, "role": "manager"})
        if request.url.path == "/getEmployeesV1":
            return httpx.Response(
                200,
                json={"employees": [{"employee_id": 10, "user_id": 7, "name": "Пётр"}], "total": 1},
            )
        if request.url.path == "/listCompanyPhonesV1":
            return httpx.Response(
                200, json={"phones": [{"id": 1, "phone": "+7000", "comment": "Основной"}]}
            )
        if request.url.path == "/linkItemsV1":
            assert json.loads(request.content.decode()) == {"employeeId": 10, "itemIds": [1, 2]}
            return httpx.Response(200, json={"success": True, "message": "linked"})
        assert request.url.path == "/listItemsByEmployeeIdV1"
        assert json.loads(request.content.decode()) == {"employeeId": 10, "categoryId": 24}
        return httpx.Response(
            200,
            json={
                "items": [{"item_id": 1, "title": "Объявление", "status": "active", "price": 99}],
                "total": 1,
            },
        )

    hierarchy = AccountHierarchy(make_transport(httpx.MockTransport(handler)), user_id=7)

    status = hierarchy.get_status()
    employees = hierarchy.list_employees()
    phones = hierarchy.list_company_phones()
    linked = hierarchy.link_items(employee_id=10, item_ids=[1, 2])
    items = hierarchy.list_items_by_employee(employee_id=10, category_id=24)

    assert status.is_active is True
    assert employees.items[0].employee_id == 10
    assert phones.items[0].phone == "+7000"
    assert linked.success is True
    assert items[0].title == "Объявление"
