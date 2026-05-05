from __future__ import annotations

import json
import logging
from datetime import datetime

import httpx
import pytest

from avito.ads import AdPromotion
from avito.core import ResponseMappingError, ValidationError
from avito.promotion import (
    AutostrategyCampaign,
    BbipPromotion,
    CpaAuction,
    PromotionOrder,
    TargetActionPricing,
    TrxPromotion,
)
from avito.promotion.models import (
    BbipItem,
    CpaAuctionBidInput,
    PromotionOrderServiceStatus,
    TargetActionBudgetType,
    TargetActionSelectedType,
    TrxItem,
)
from tests.helpers.transport import make_transport


def test_promotion_service_dictionary_and_orders_flow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/promotion/v1/items/services/dict":
            return httpx.Response(200, json={"items": [{"code": "x2", "title": "X2"}]})
        if path == "/promotion/v1/items/services/get":
            assert payload == {"itemIds": [101]}
            return httpx.Response(200, json={"items": [{"itemId": 101, "serviceCode": "x2", "serviceName": "X2", "price": 9900, "status": "available"}]})
        if path == "/promotion/v1/items/services/orders/get":
            assert payload == {}
            return httpx.Response(200, json={"items": [{"orderId": "ord-1", "itemId": 101, "serviceCode": "x2", "status": "created"}]})
        assert path == "/promotion/v1/items/services/orders/status"
        return httpx.Response(200, json={"orderId": "ord-1", "status": "processed", "items": [], "errors": []})

    promotion = PromotionOrder(make_transport(httpx.MockTransport(handler)), order_id="ord-1")
    assert promotion.get_service_dictionary().items[0].code == "x2"
    assert promotion.list_services(item_ids=[101]).items[0].price == 9900
    assert promotion.list_orders(item_ids=[101]).items[0].order_id == "ord-1"
    assert promotion.get_order_status().status == "processed"


def test_bbip_trx_and_target_action_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/promotion/v1/items/services/bbip/forecasts/get":
            return httpx.Response(200, json={"items": [{"itemId": 101, "min": 10, "max": 25, "totalPrice": 7000, "totalOldPrice": 8400}]})
        if path == "/promotion/v1/items/services/bbip/orders/create":
            return httpx.Response(200, json={"items": [{"itemId": 101, "success": True, "status": "created"}]})
        if path == "/promotion/v1/items/services/bbip/suggests/get":
            return httpx.Response(200, json={"items": [{"itemId": 101, "duration": {"from": 1, "to": 7, "recommended": 5}, "budgets": [{"price": 1000, "oldPrice": 1200, "isRecommended": True}]}]})
        if path == "/trx-promo/1/apply":
            return httpx.Response(200, json={"success": {"items": [{"itemID": 101, "success": True}]}})
        if path == "/trx-promo/1/cancel":
            return httpx.Response(200, json={"success": {"items": [{"itemID": 101, "success": True}]}})
        if path == "/trx-promo/1/commissions":
            return httpx.Response(200, json={"success": {"items": [{"itemID": 101, "commission": 1500, "isActive": True, "validCommissionRange": {"valueMin": 100, "valueMax": 2000, "step": 100}}]}})
        if path == "/auction/1/bids" and request.method == "GET":
            return httpx.Response(200, json={"items": [{"itemID": 101, "pricePenny": 1300, "availablePrices": [{"pricePenny": 1200, "goodness": 1}]}]})
        if path == "/auction/1/bids":
            assert payload == {"items": [{"itemID": 101, "pricePenny": 1500}]}
            return httpx.Response(200, json={"items": [{"itemID": 101, "success": True}]})
        if path == "/cpxpromo/1/getBids/101":
            return httpx.Response(200, json={"actionTypeID": 5, "selectedType": "manual", "manual": {"bidPenny": 1400, "limitPenny": 15000, "recBidPenny": 1500, "minBidPenny": 1000, "maxBidPenny": 2000, "minLimitPenny": 5000, "maxLimitPenny": 50000, "bids": [{"valuePenny": 1500, "minForecast": 2, "maxForecast": 5, "compare": 10}]}})
        if path == "/cpxpromo/1/getPromotionsByItemIds":
            return httpx.Response(200, json={"items": [{"itemID": 102, "actionTypeID": 7, "autoPromotion": {"budgetPenny": 9000, "budgetType": "7d"}}]})
        if path == "/cpxpromo/1/remove":
            return httpx.Response(200, json={"items": [{"itemID": 101, "success": True, "status": "removed"}]})
        if path == "/cpxpromo/1/setAuto":
            return httpx.Response(200, json={"items": [{"itemID": 101, "success": True, "status": "auto"}]})
        return httpx.Response(200, json={"items": [{"itemID": 101, "success": True, "status": "manual"}]})

    transport = make_transport(httpx.MockTransport(handler))
    bbip = BbipPromotion(transport, item_id=101)
    trx = TrxPromotion(transport, item_id=101)
    auction = CpaAuction(transport)
    pricing = TargetActionPricing(transport, item_id=101)

    bbip_item = BbipItem(item_id=101, duration=7, price=1000, old_price=1200)
    trx_item = TrxItem(
        item_id=101,
        commission=1500,
        date_from=datetime.fromisoformat("2026-04-18T00:00:00+00:00"),
    )

    assert bbip.get_forecasts(items=[bbip_item]).items[0].max_views == 25
    assert bbip.create_order(items=[bbip_item]).status == "created"
    assert bbip.get_suggests().items[0].duration is not None
    assert trx.apply(items=[trx_item]).applied is True
    assert trx.delete().applied is True
    assert trx.get_commissions().items[0].valid_commission_range is not None
    assert auction.get_user_bids(from_item_id=100, batch_size=50).items[0].available_prices[0].price_penny == 1200
    assert auction.create_item_bids(items=[CpaAuctionBidInput(item_id=101, price_penny=1500)]).applied is True
    assert pricing.get_bids().manual is not None
    assert pricing.get_promotions_by_item_ids(item_ids=[101, 102]).items[0].auto is not None
    assert pricing.delete().status == "removed"
    assert pricing.update_auto(action_type_id=5, budget_penny=8000, budget_type="7d").status == "auto"
    assert pricing.update_manual(action_type_id=5, bid_penny=1500, limit_penny=15000).status == "manual"


def test_autostrategy_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/autostrategy/v1/budget":
            return httpx.Response(200, json={"calcId": 501, "budget": {"recommended": {"total": 10100}, "minimal": {"total": 5100}, "priceRanges": []}})
        if path == "/autostrategy/v1/campaign/create":
            return httpx.Response(200, json={"campaign": {"campaignId": 77, "campaignType": "AS", "version": 3}})
        if path == "/autostrategy/v1/campaign/edit":
            return httpx.Response(200, json={"campaign": {"campaignId": 77, "campaignType": "AS", "version": 4}})
        if path == "/autostrategy/v1/campaign/info":
            return httpx.Response(200, json={"campaign": {"campaignId": 77, "campaignType": "AS", "statusId": 1, "budget": 10000, "balance": 9000, "title": "Весенняя кампания", "version": 4}, "forecast": {"calls": {"from": 2, "to": 5}, "views": {"from": 30, "to": 50}}, "items": [{"itemId": 101, "isActive": True}]})
        if path == "/autostrategy/v1/campaign/stop":
            return httpx.Response(200, json={"campaign": {"campaignId": 77, "campaignType": "AS", "version": 5}})
        if path == "/autostrategy/v1/campaigns":
            return httpx.Response(200, json={"campaigns": [{"campaignId": 77, "campaignType": "AS", "statusId": 1, "budget": 10000}], "totalCount": 1})
        return httpx.Response(200, json={"stat": [{"date": "2026-04-18", "calls": 30, "views": 500}], "totals": {"calls": 30, "views": 500}})

    campaign = AutostrategyCampaign(make_transport(httpx.MockTransport(handler)), campaign_id=77)
    start_time = datetime.fromisoformat("2026-04-20T00:00:00+00:00")
    finish_time = datetime.fromisoformat("2026-04-27T00:00:00+00:00")
    assert campaign.create_budget(campaign_type="AS", start_time=start_time, finish_time=finish_time, items=[101, 102]).calc_id == 501
    assert campaign.create(campaign_type="AS", title="Весенняя кампания", budget=10000, calc_id=501, items=[101, 102], start_time=start_time, finish_time=finish_time).campaign is not None
    assert campaign.update(campaign_id=77, version=3, title="Обновленная кампания").campaign is not None
    assert campaign.get().campaign is not None
    assert campaign.delete(version=4).campaign is not None
    assert campaign.list(
        limit=20,
        offset=10,
        status_id=[1, 2],
        order_by=[("startTime", "asc")],
        updated_from=datetime.fromisoformat("2026-04-01T00:00:00+00:00"),
        updated_to=datetime.fromisoformat("2026-04-30T00:00:00+00:00"),
    ).total_count == 1
    assert campaign.get_stat().totals is not None


def test_autostrategy_datetime_parameters_fail_fast_on_invalid_type() -> None:
    campaign = AutostrategyCampaign(
        make_transport(httpx.MockTransport(lambda request: httpx.Response(500))),
        campaign_id=77,
    )

    with pytest.raises(ValidationError, match="`start_time` должен быть datetime."):
        campaign.create_budget(campaign_type="AS", start_time="2026-04-20T00:00:00+00:00")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="`finish_time` должен быть datetime."):
        campaign.create(
            campaign_type="AS",
            title="Весенняя кампания",
            finish_time="2026-04-27T00:00:00+00:00",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError, match="`start_time` должен быть datetime."):
        campaign.update(
            version=3,
            start_time="2026-04-20T00:00:00+00:00",  # type: ignore[arg-type]
        )


def test_promotion_write_methods_keep_same_payload_in_dry_run_mode() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode()) if request.content else {}
        seen.append((request.url.path, payload))
        if request.url.path == "/core/v1/accounts/7/items/101/vas":
            return httpx.Response(200, json={"success": True, "status": "applied"})
        if request.url.path == "/promotion/v1/items/services/bbip/orders/create":
            return httpx.Response(200, json={"items": [{"itemId": 101, "success": True, "status": "created", "orderId": "ord-1"}]})
        return httpx.Response(200, json={"success": {"items": [{"itemID": 101, "success": True}]}})

    transport = make_transport(httpx.MockTransport(handler))
    ad_promotion = AdPromotion(transport, item_id=101, user_id=7)
    bbip = BbipPromotion(transport, item_id=101)
    trx = TrxPromotion(transport, item_id=101)
    bbip_item = BbipItem(item_id=101, duration=7, price=1000, old_price=1200)
    trx_item = TrxItem(
        item_id=101,
        commission=1500,
        date_from=datetime.fromisoformat("2026-04-18T00:00:00+00:00"),
    )

    vas_preview = ad_promotion.apply_vas(vas_id="xl", dry_run=True)
    bbip_preview = bbip.create_order(items=[bbip_item], dry_run=True)
    trx_preview = trx.apply(items=[trx_item], dry_run=True)

    assert vas_preview.status == "preview"
    assert bbip_preview.status == "preview"
    assert trx_preview.status == "preview"

    vas_apply = ad_promotion.apply_vas(vas_id="xl")
    bbip_apply = bbip.create_order(items=[bbip_item])
    trx_apply = trx.apply(items=[trx_item])

    assert seen[0][1] == vas_preview.request_payload
    assert seen[1][1] == bbip_preview.request_payload
    assert seen[2][1] == trx_preview.request_payload
    assert vas_apply.request_payload == vas_preview.request_payload
    assert bbip_apply.request_payload == bbip_preview.request_payload
    assert trx_apply.request_payload == trx_preview.request_payload


def test_promotion_dry_run_does_not_call_transport() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json={"items": []})

    transport = make_transport(httpx.MockTransport(handler))
    bbip = BbipPromotion(transport, item_id=101)
    trx = TrxPromotion(transport, item_id=101)
    pricing = TargetActionPricing(transport, item_id=101)
    bbip_item = BbipItem(item_id=101, duration=7, price=1000, old_price=1200)
    trx_item = TrxItem(
        item_id=101,
        commission=1500,
        date_from=datetime.fromisoformat("2026-04-18T00:00:00+00:00"),
    )

    bbip.create_order(items=[bbip_item], dry_run=True)
    trx.apply(items=[trx_item], dry_run=True)
    pricing.update_manual(action_type_id=5, bid_penny=1500, dry_run=True)

    assert seen_paths == []


def test_promotion_unknown_enums_map_to_unknown_and_warn_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/promotion/v1/items/services/get":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "itemId": 101,
                            "serviceCode": "x2",
                            "serviceName": "X2",
                            "price": 9900,
                            "status": "mystery-promotion-status",
                        }
                    ]
                },
            )
        assert request.url.path == "/cpxpromo/1/getBids/101"
        return httpx.Response(
            200,
            json={
                "actionTypeID": 5,
                "selectedType": "mystery-selected-type",
                "auto": {
                    "budgetPenny": 1000,
                    "budgetType": "mystery-budget-type",
                    "dailyBudget": {"budgets": []},
                    "weeklyBudget": {"budgets": []},
                    "monthlyBudget": {"budgets": []},
                },
            },
        )

    caplog.set_level(logging.WARNING, logger="avito.core.enums")
    transport = make_transport(httpx.MockTransport(handler))
    order = PromotionOrder(transport, order_id="ord-1")
    pricing = TargetActionPricing(transport, item_id=101)

    first_service = order.list_services(item_ids=[101]).items[0]
    second_service = order.list_services(item_ids=[101]).items[0]
    first_bids = pricing.get_bids()
    second_bids = pricing.get_bids()

    assert first_service.status is PromotionOrderServiceStatus.UNKNOWN
    assert second_service.status is PromotionOrderServiceStatus.UNKNOWN
    assert first_bids.selected_type is TargetActionSelectedType.UNKNOWN
    assert second_bids.selected_type is TargetActionSelectedType.UNKNOWN
    assert first_bids.auto is not None
    assert second_bids.auto is not None
    assert first_bids.auto.budget_type is TargetActionBudgetType.UNKNOWN
    assert second_bids.auto.budget_type is TargetActionBudgetType.UNKNOWN

    status_records = [
        record
        for record in caplog.records
            if getattr(record, "enum", None) == "promotion.order_service_status"
        and getattr(record, "value", None) == "mystery-promotion-status"
    ]
    selected_type_records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "promotion.target_action_selected_type"
        and getattr(record, "value", None) == "mystery-selected-type"
    ]
    budget_type_records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "promotion.target_action_budget_type"
        and getattr(record, "value", None) == "mystery-budget-type"
    ]
    assert len(status_records) == 1
    assert len(selected_type_records) == 1
    assert len(budget_type_records) == 1


def test_idempotency_key_forwarded_once_per_retry_chain() -> None:
    calls = {"count": 0}
    seen_keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        seen_keys.append(request.headers.get("Idempotency-Key"))
        if calls["count"] == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json={"items": [{"itemID": 101, "success": True, "status": "manual"}]})

    transport = make_transport(httpx.MockTransport(handler))
    pricing = TargetActionPricing(transport, item_id=101)

    result = pricing.update_manual(
        action_type_id=5,
        bid_penny=1500,
        idempotency_key="idem-123",
    )

    assert result.status == "manual"
    assert seen_keys == ["idem-123", "idem-123"]


def test_promotion_read_mappers_raise_on_invalid_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/promotion/v1/items/services/orders/status":
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/cpxpromo/1/getBids/101":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"items": [{"itemID": 102}]})

    transport = make_transport(httpx.MockTransport(handler))

    with pytest.raises(ResponseMappingError):
        PromotionOrder(transport, order_id="ord-2").get_order_status()
    with pytest.raises(ResponseMappingError):
        TargetActionPricing(transport, item_id=101).get_bids()
    with pytest.raises(ResponseMappingError):
        TargetActionPricing(transport, item_id=101).get_promotions_by_item_ids(item_ids=[102])
