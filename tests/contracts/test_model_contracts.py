from __future__ import annotations

import importlib
import json
from dataclasses import is_dataclass
from datetime import datetime
from inspect import isclass

import httpx

from avito.accounts import Account
from avito.accounts.models import AccountProfile
from avito.ads import Ad, AdStats
from avito.ads.models import AccountSpendings, CallStats, Listing, ListingStats, SpendingRecord
from avito.autoteka.models import (
    CatalogField,
    CatalogFieldValue,
    CatalogResolveRequest,
    CatalogResolveResult,
    MonitoringBucketRequest,
)
from avito.core.serialization import SerializableModel
from avito.core.types import BinaryResponse
from avito.cpa.models import CallTrackingRecord, CpaAudioRecord
from avito.messenger.models import SendMessageRequest
from avito.orders.models import LabelPdfResult
from avito.promotion import BbipPromotion, PromotionOrder, PromotionService
from avito.promotion.models import (
    AutostrategyBudget,
    AutostrategyStat,
    AutostrategyStatItem,
    AutostrategyStatTotals,
    BbipItem,
    CampaignActionResult,
    CampaignListFilter,
    CampaignOrderBy,
    CampaignsResult,
    CampaignUpdateTimeFilter,
    CreateAutostrategyBudgetRequest,
    ListAutostrategyCampaignsRequest,
    PromotionForecast,
    PromotionOrderInfo,
)
from avito.tariffs.models import TariffContractInfo, TariffInfo
from tests.helpers.transport import make_transport

MODEL_MODULES = (
    "avito.accounts.models",
    "avito.ads.models",
    "avito.autoteka.models",
    "avito.cpa.models",
    "avito.jobs.models",
    "avito.messenger.models",
    "avito.orders.models",
    "avito.promotion.models",
    "avito.ratings.models",
    "avito.realty.models",
    "avito.tariffs.models",
)


def iter_model_classes() -> list[tuple[str, str, type[object]]]:
    classes: list[tuple[str, str, type[object]]] = []
    for module_name in MODEL_MODULES:
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if not isclass(value) or getattr(value, "__module__", None) != module_name:
                continue
            if not is_dataclass(value):
                continue
            classes.append((module_name, name, value))
    return classes


def test_all_model_dataclasses_expose_standard_serialization_methods() -> None:
    missing = [
        f"{module_name}:{name}"
        for module_name, name, cls in iter_model_classes()
        if issubclass(cls, SerializableModel)
        and (not hasattr(cls, "to_dict") or not hasattr(cls, "model_dump"))
    ]

    assert missing == []


def test_recursive_serialization_is_json_compatible_and_hides_transport_fields() -> None:
    tariff = TariffInfo(
        current=TariffContractInfo(
            level="Максимальный",
            is_active=True,
            start_time=1713427200,
            close_time=None,
            bonus=10,
            price=1990,
            original_price=2490,
            packages_count=2,
        ),
        scheduled=None,
    )
    catalog = CatalogResolveResult(
        items=[
            CatalogField(
                field_id="brand",
                label="Марка",
                data_type="integer",
                values=[CatalogFieldValue(value_id="1", label="Audi")],
            )
        ],
    )
    assert tariff.to_dict()["current"]["level"] == "Максимальный"
    assert catalog.model_dump()["items"][0]["field_id"] == "brand"
    json.dumps(tariff.to_dict())
    json.dumps(catalog.to_dict())
    request = SendMessageRequest(message="hello")
    assert request.message == "hello"
    assert request.type is None


def test_examples_and_binary_models_produce_expected_payloads() -> None:
    budget_request = CreateAutostrategyBudgetRequest(
        campaign_type="AS",
        start_time=datetime.fromisoformat("2026-04-20T00:00:00+00:00"),
        finish_time=datetime.fromisoformat("2026-04-27T00:00:00+00:00"),
        items=[42, 43],
    )
    campaigns_request = ListAutostrategyCampaignsRequest(
        limit=50,
        status_id=[1, 2],
        order_by=[CampaignOrderBy(column="startTime", direction="asc")],
        filter=CampaignListFilter(
            by_update_time=CampaignUpdateTimeFilter(
                from_time=datetime.fromisoformat("2026-04-01T00:00:00+00:00"),
                to_time=datetime.fromisoformat("2026-04-30T00:00:00+00:00"),
            )
        ),
    )
    assert budget_request.to_payload()["campaignType"] == "AS"
    assert campaigns_request.to_payload()["filter"]["byUpdateTime"]["from"].startswith("2026-04-01")
    assert CatalogResolveRequest(brand_id=1).to_payload() == {
        "fieldsValueIds": [{"id": 110000, "valueId": 1}]
    }
    assert MonitoringBucketRequest(vehicles=["VIN-1"]).to_payload() == {"data": ["VIN-1"]}

    response = BinaryResponse(
        content=b"\x00\x01payload",
        content_type="application/octet-stream",
        filename="artifact.bin",
        status_code=200,
        headers={"x-test": "1"},
    )
    expected = {
        "filename": "artifact.bin",
        "content_type": "application/octet-stream",
        "content_base64": "AAFwYXlsb2Fk",
    }
    assert LabelPdfResult(binary=response).to_dict() == expected
    assert CpaAudioRecord(binary=response).model_dump() == expected
    assert CallTrackingRecord(binary=response).to_dict() == expected


def test_primary_sdk_models_serialize_without_transport_fields() -> None:
    profile = AccountProfile(user_id=7, name="Иван", email=None, phone="+7999")
    listing = Listing(
        item_id=101,
        user_id=7,
        title="Смартфон",
        description=None,
        status="active",
        price=1000.0,
        url=None,
    )
    stats = ListingStats(item_id=101, views=42, contacts=None, favorites=3)
    calls = CallStats(item_id=101, calls=4, answered_calls=3, missed_calls=1)
    spendings = AccountSpendings(
        items=[SpendingRecord(item_id=101, amount=77.5, service="xl")],
        total=77.5,
    )
    service = PromotionService(
        item_id=101,
        service_code="x2",
        service_name="X2",
        price=9900,
        status="available",
    )
    order = PromotionOrderInfo(
        order_id="ord-1",
        item_id=101,
        service_code="x2",
        status="created",
        created_at=None,
    )
    forecast = PromotionForecast(
        item_id=101,
        min_views=10,
        max_views=25,
        total_price=7000,
        total_old_price=None,
    )

    assert profile.to_dict()["user_id"] == 7
    assert listing.to_dict()["item_id"] == 101
    assert stats.model_dump()["views"] == 42
    assert calls.to_dict()["calls"] == 4
    assert spendings.to_dict()["total"] == 77.5
    assert service.to_dict()["service_code"] == "x2"
    assert order.to_dict()["order_id"] == "ord-1"
    assert forecast.to_dict()["max_views"] == 25


def test_model_read_flows_return_stable_sdk_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/core/v1/accounts/self":
            return httpx.Response(200, json={"id": 7, "name": "Иван"})
        if path == "/core/v1/accounts/7/items/101/":
            return httpx.Response(200, json={"id": 101, "user_id": 7, "title": "Смартфон"})
        if path == "/stats/v1/accounts/7/items":
            return httpx.Response(
                200,
                json={"items": [{"item_id": 101, "views": 42, "contacts": 5, "favorites": 3}]},
            )
        if path == "/core/v1/accounts/7/calls/stats/":
            return httpx.Response(
                200,
                json={
                    "items": [{"item_id": 101, "calls": 4, "answered_calls": 3, "missed_calls": 1}]
                },
            )
        if path == "/stats/v2/accounts/7/spendings":
            return httpx.Response(
                200,
                json={"items": [{"item_id": 101, "amount": 77.5, "service": "xl"}]},
            )
        if path == "/promotion/v1/items/services/get":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "itemId": 101,
                            "serviceCode": "x2",
                            "serviceName": "X2",
                            "price": 9900,
                            "status": "available",
                        }
                    ]
                },
            )
        if path == "/promotion/v1/items/services/orders/get":
            return httpx.Response(
                200,
                json={"items": [{"orderId": "ord-1", "itemId": 101, "serviceCode": "x2"}]},
            )
        return httpx.Response(
            200,
            json={"items": [{"itemId": 101, "min": 10, "max": 25, "totalPrice": 7000}]},
        )

    transport = make_transport(httpx.MockTransport(handler))

    profile = Account(transport, user_id=7).get_self()
    listing = Ad(transport, item_id=101, user_id=7).get()
    stats = AdStats(transport, item_id=101, user_id=7).get_item_stats(
        date_from="2026-04-01",
        date_to="2026-04-02",
    )
    calls = AdStats(transport, item_id=101, user_id=7).get_calls_stats(
        date_from="2026-04-01",
        date_to="2026-04-02",
    )
    spendings = AdStats(transport, item_id=101, user_id=7).get_account_spendings(
        date_from="2026-04-01",
        date_to="2026-04-02",
        spending_types=["promotion"],
        grouping="day",
    )
    services = PromotionOrder(transport, order_id="ord-1").list_services(item_ids=[101])
    orders = PromotionOrder(transport, order_id="ord-1").list_orders(item_ids=[101])
    forecasts = BbipPromotion(transport, item_id=101).get_forecasts(
        items=[BbipItem(item_id=101, duration=7, price=1000, old_price=1200)]
    )

    assert isinstance(profile, AccountProfile)
    assert isinstance(listing, Listing)
    assert isinstance(stats.items[0], ListingStats)
    assert isinstance(calls.items[0], CallStats)
    assert isinstance(spendings, AccountSpendings)
    assert isinstance(services.items[0], PromotionService)
    assert isinstance(orders.items[0], PromotionOrderInfo)
    assert forecasts.items[0].max_views == 25


def test_autostrategy_models_serialize_correctly() -> None:
    budget = AutostrategyBudget(calc_id=1, recommended=None, minimal=None, maximal=None, price_ranges=[])
    result = CampaignActionResult(campaign=None)
    campaigns = CampaignsResult(items=[], total_count=0)
    stat = AutostrategyStat(
        items=[AutostrategyStatItem(date="2026-01-01", calls=5, views=10)],
        totals=AutostrategyStatTotals(calls=5, views=10),
    )

    assert budget.to_dict()["calc_id"] == 1
    assert result.to_dict() == {"campaign": None}
    assert campaigns.to_dict() == {"items": [], "total_count": 0}
    assert stat.to_dict()["totals"] == {"calls": 5, "views": 10}
