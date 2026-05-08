from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from avito.accounts import AsyncAccount, AsyncAccountHierarchy
from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import AsyncPaginatedList
from avito.core.exceptions import AuthenticationError, RateLimitError, TransportError
from avito.core.retries import RetryPolicy
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


def _profile_payload() -> dict[str, object]:
    return {"id": 7, "name": "Иван", "email": "user@example.com", "phone": "+7999"}


def _balance_payload() -> dict[str, object]:
    return {"user_id": 7, "balance": {"real": 150.5, "bonus": 20.0, "currency": "RUB"}}


def _operations_payload() -> dict[str, object]:
    return {
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
    }


@pytest.mark.asyncio
async def test_async_account_domain_maps_profile_balance_and_operations() -> None:
    def operations_history(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dateTimeFrom": "2025-01-01T00:00:00+00:00",
            "dateTimeTo": "2025-01-31T00:00:00+00:00",
        }
        return httpx.Response(200, json=_operations_payload())

    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/core/v1/accounts/self", _profile_payload())
        .add_json("GET", "/core/v1/accounts/7/balance/", _balance_payload())
        .add("POST", "/core/v1/accounts/operations_history/", operations_history)
    )
    transport = fake.build()
    account = AsyncAccount(transport, user_id=7)

    profile = await account.get_self()
    balance = await account.get_balance()
    history = await account.get_operations_history(
        date_from=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
        date_to=datetime.fromisoformat("2025-01-31T00:00:00+00:00"),
    )

    assert profile.user_id == 7
    assert balance.total == 170.5
    assert isinstance(history, AsyncPaginatedList)
    assert history.loaded_count == 1
    materialized = await history.materialize()
    assert len(materialized) == 1
    assert materialized[0].operation_type == "payment"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_account_balance_resolves_user_id_from_self_when_not_configured() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/core/v1/accounts/self", {"id": 7})
        .add_json("GET", "/core/v1/accounts/7/balance/", {"user_id": 7, "balance": {"real": 150.0}})
    )
    transport = fake.build()
    account = AsyncAccount(transport)

    balance = await account.get_balance()

    assert balance.user_id == 7
    assert [request.path for request in fake.requests] == [
        "/core/v1/accounts/self",
        "/core/v1/accounts/7/balance/",
    ]
    await transport.aclose()


def test_async_account_balance_requires_keyword_user_id() -> None:
    account = AsyncAccount(AsyncFakeTransport().build())

    try:
        account.get_balance(7)  # type: ignore[misc]
    except TypeError as error:
        assert "positional" in str(error)
    else:  # pragma: no cover
        raise AssertionError("get_balance accepted positional user_id")


@pytest.mark.asyncio
async def test_async_account_hierarchy_domain_maps_employees_phones_and_items() -> None:
    def link_items(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"employeeId": 10, "itemIds": [1, 2]}
        assert request.headers["idempotency-key"] == "link-1"
        return httpx.Response(200, json={"success": True, "message": "linked"})

    def list_items(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"employeeId": 10, "categoryId": 24}
        return httpx.Response(
            200,
            json={
                "items": [{"item_id": 1, "title": "Объявление", "status": "active", "price": 99}],
                "total": 1,
            },
        )

    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/checkAhUserV1", {"user_id": 7, "is_active": True, "role": "manager"})
        .add_json(
            "GET",
            "/getEmployeesV1",
            {"employees": [{"employee_id": 10, "user_id": 7, "name": "Пётр"}], "total": 1},
        )
        .add_json(
            "GET",
            "/listCompanyPhonesV1",
            {"phones": [{"id": 1, "phone": "+7000", "comment": "Основной"}]},
        )
        .add("POST", "/linkItemsV1", link_items)
        .add("POST", "/listItemsByEmployeeIdV1", list_items)
    )
    transport = fake.build()
    hierarchy = AsyncAccountHierarchy(transport, user_id=7)

    status = await hierarchy.get_status()
    employees = await hierarchy.list_employees()
    phones = await hierarchy.list_company_phones()
    linked = await hierarchy.link_items(employee_id=10, item_ids=[1, 2], idempotency_key="link-1")
    items = await hierarchy.list_items_by_employee(employee_id=10, category_id=24)

    assert status.is_active is True
    assert employees.items[0].employee_id == 10
    assert phones.items[0].phone == "+7000"
    assert linked.success is True
    assert isinstance(items, AsyncPaginatedList)
    assert items.loaded_count == 1
    materialized = await items.materialize()
    assert materialized[0].title == "Объявление"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_account_factories_return_async_domains() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/core/v1/accounts/self", _profile_payload())
        .add_json("GET", "/checkAhUserV1", {"user_id": 7, "is_active": True, "role": "manager"})
    )
    client = fake.as_client()

    account = client.account(user_id=7)
    hierarchy = client.account_hierarchy(user_id=7)

    assert isinstance(account, AsyncAccount)
    assert isinstance(hierarchy, AsyncAccountHierarchy)
    assert (await account.get_self()).user_id == 7
    assert (await hierarchy.get_status()).is_active is True
    await client.aclose()


@pytest.mark.asyncio
async def test_async_accounts_maps_401() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/core/v1/accounts/self",
        {"error": "unauthorized"},
        status_code=401,
    )
    transport = fake.build()

    with pytest.raises(AuthenticationError):
        await AsyncAccount(transport).get_self()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_accounts_maps_429() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/core/v1/accounts/self",
        {"error": "rate limit"},
        status_code=429,
    )
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(RateLimitError):
        await AsyncAccount(transport).get_self()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_accounts_maps_transport_error() -> None:
    def raise_network_error(request: object) -> httpx.Response:
        raise httpx.NetworkError("connection failed")

    fake = AsyncFakeTransport().add("GET", "/core/v1/accounts/self", raise_network_error)
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(TransportError):
        await AsyncAccount(transport).get_self()

    await transport.aclose()


def test_async_client_account_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.account()
    with pytest.raises(RuntimeError):
        client.account_hierarchy()
