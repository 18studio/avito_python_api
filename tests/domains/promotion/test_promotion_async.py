from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import ResponseMappingError, ValidationError
from avito.promotion import (
    AsyncAutostrategyCampaign,
    AsyncBbipPromotion,
    AsyncCpaAuction,
    AsyncPromotionOrder,
    AsyncTargetActionPricing,
    AsyncTrxPromotion,
)
from avito.promotion.models import (
    BbipItem,
    CpaAuctionBidInput,
    TrxItem,
)
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_promotion_service_dictionary_and_orders_flow() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/promotion/v1/items/services/dict",
            {"items": [{"code": "x2", "title": "X2"}]},
        )
        .add_json(
            "POST",
            "/promotion/v1/items/services/get",
            {
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
        .add_json(
            "POST",
            "/promotion/v1/items/services/orders/get",
            {
                "items": [
                    {
                        "orderId": "ord-1",
                        "itemId": 101,
                        "serviceCode": "x2",
                        "status": "created",
                    }
                ]
            },
        )
        .add_json(
            "POST",
            "/promotion/v1/items/services/orders/status",
            {"orderId": "ord-1", "status": "processed", "items": [], "errors": []},
        )
    )
    transport = fake.build()
    promotion = AsyncPromotionOrder(transport, order_id="ord-1")

    assert (await promotion.get_service_dictionary()).items[0].code == "x2"
    assert (await promotion.list_services(item_ids=[101])).items[0].price == 9900
    assert (await promotion.list_orders(item_ids=[101])).items[0].order_id == "ord-1"
    assert (await promotion.get_order_status()).status == "processed"
    assert fake.last(method="POST", path="/promotion/v1/items/services/get").json_body == {
        "itemIds": [101]
    }
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_bbip_trx_cpa_and_target_action_flows() -> None:
    def create_cpa_bids(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"items": [{"itemID": 101, "pricePenny": 1500}]}
        return httpx.Response(200, json={"items": [{"itemID": 101, "success": True}]})

    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/promotion/v1/items/services/bbip/forecasts/get",
            {
                "items": [
                    {
                        "itemId": 101,
                        "min": 10,
                        "max": 25,
                        "totalPrice": 7000,
                        "totalOldPrice": 8400,
                    }
                ]
            },
        )
        .add_json(
            "PUT",
            "/promotion/v1/items/services/bbip/orders/create",
            {"items": [{"itemId": 101, "success": True, "status": "created"}]},
        )
        .add_json(
            "POST",
            "/promotion/v1/items/services/bbip/suggests/get",
            {
                "items": [
                    {
                        "itemId": 101,
                        "duration": {"from": 1, "to": 7, "recommended": 5},
                        "budgets": [{"price": 1000, "oldPrice": 1200, "isRecommended": True}],
                    }
                ]
            },
        )
        .add_json(
            "POST",
            "/trx-promo/1/apply",
            {"success": {"items": [{"itemID": 101, "success": True}]}},
        )
        .add_json(
            "POST",
            "/trx-promo/1/cancel",
            {"success": {"items": [{"itemID": 101, "success": True}]}},
        )
        .add_json(
            "GET",
            "/trx-promo/1/commissions",
            {
                "success": {
                    "items": [
                        {
                            "itemID": 101,
                            "commission": 1500,
                            "isActive": True,
                            "validCommissionRange": {
                                "valueMin": 100,
                                "valueMax": 2000,
                                "step": 100,
                            },
                        }
                    ]
                }
            },
        )
        .add_json(
            "GET",
            "/auction/1/bids",
            {
                "items": [
                    {
                        "itemID": 101,
                        "pricePenny": 1300,
                        "availablePrices": [{"pricePenny": 1200, "goodness": 1}],
                    }
                ]
            },
        )
        .add("POST", "/auction/1/bids", create_cpa_bids)
        .add_json(
            "GET",
            "/cpxpromo/1/getBids/101",
            {
                "actionTypeID": 5,
                "selectedType": "manual",
                "manual": {
                    "bidPenny": 1400,
                    "limitPenny": 15000,
                    "recBidPenny": 1500,
                    "minBidPenny": 1000,
                    "maxBidPenny": 2000,
                    "minLimitPenny": 5000,
                    "maxLimitPenny": 50000,
                    "bids": [{"valuePenny": 1500, "minForecast": 2, "maxForecast": 5}],
                },
            },
        )
        .add_json(
            "POST",
            "/cpxpromo/1/getPromotionsByItemIds",
            {
                "items": [
                    {
                        "itemID": 102,
                        "actionTypeID": 7,
                        "autoPromotion": {"budgetPenny": 9000, "budgetType": "7d"},
                    }
                ]
            },
        )
        .add_json(
            "POST",
            "/cpxpromo/1/remove",
            {"items": [{"itemID": 101, "success": True, "status": "removed"}]},
        )
        .add_json(
            "POST",
            "/cpxpromo/1/setAuto",
            {"items": [{"itemID": 101, "success": True, "status": "auto"}]},
        )
        .add_json(
            "POST",
            "/cpxpromo/1/setManual",
            {"items": [{"itemID": 101, "success": True, "status": "manual"}]},
        )
    )
    transport = fake.build()
    bbip = AsyncBbipPromotion(transport, item_id=101)
    trx = AsyncTrxPromotion(transport, item_id=101)
    auction = AsyncCpaAuction(transport)
    pricing = AsyncTargetActionPricing(transport, item_id=101)
    bbip_item = BbipItem(item_id=101, duration=7, price=1000, old_price=1200)
    trx_item = TrxItem(
        item_id=101,
        commission=1500,
        date_from=datetime.fromisoformat("2026-04-18T00:00:00+00:00"),
    )

    assert (await bbip.get_forecasts(items=[bbip_item])).items[0].max_views == 25
    assert (await bbip.create_order(items=[bbip_item])).status == "created"
    assert (await bbip.get_suggests()).items[0].duration is not None
    assert (await trx.apply(items=[trx_item])).applied is True
    assert (await trx.delete()).applied is True
    assert (await trx.get_commissions()).items[0].valid_commission_range is not None
    assert (await auction.get_user_bids(from_item_id=100, batch_size=50)).items[0].available_prices[
        0
    ].price_penny == 1200
    assert (
        await auction.create_item_bids(items=[CpaAuctionBidInput(item_id=101, price_penny=1500)])
    ).applied is True
    assert (await pricing.get_bids()).manual is not None
    assert (await pricing.get_promotions_by_item_ids(item_ids=[101, 102])).items[0].auto is not None
    assert (await pricing.delete()).status == "removed"
    assert (
        await pricing.update_auto(action_type_id=5, budget_penny=8000, budget_type="7d")
    ).status == "auto"
    assert (await pricing.update_manual(action_type_id=5, bid_penny=1500)).status == "manual"
    assert fake.last(method="GET", path="/auction/1/bids").params == {
        "fromItemID": "100",
        "batchSize": "50",
    }
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_autostrategy_flows() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/autostrategy/v1/budget",
            {
                "calcId": 501,
                "budget": {
                    "recommended": {"total": 10100},
                    "minimal": {"total": 5100},
                    "priceRanges": [],
                },
            },
        )
        .add_json(
            "POST",
            "/autostrategy/v1/campaign/create",
            {"campaign": {"campaignId": 77, "campaignType": "AS", "version": 3}},
        )
        .add_json(
            "POST",
            "/autostrategy/v1/campaign/edit",
            {"campaign": {"campaignId": 77, "campaignType": "AS", "version": 4}},
        )
        .add_json(
            "POST",
            "/autostrategy/v1/campaign/info",
            {
                "campaign": {
                    "campaignId": 77,
                    "campaignType": "AS",
                    "statusId": 1,
                    "budget": 10000,
                    "balance": 9000,
                    "title": "Весенняя кампания",
                    "version": 4,
                },
                "forecast": {"calls": {"from": 2, "to": 5}, "views": {"from": 30, "to": 50}},
                "items": [{"itemId": 101, "isActive": True}],
            },
        )
        .add_json(
            "POST",
            "/autostrategy/v1/campaign/stop",
            {"campaign": {"campaignId": 77, "campaignType": "AS", "version": 5}},
        )
        .add_json(
            "POST",
            "/autostrategy/v1/campaigns",
            {
                "campaigns": [{"campaignId": 77, "campaignType": "AS", "statusId": 1}],
                "totalCount": 1,
            },
        )
        .add_json(
            "POST",
            "/autostrategy/v1/stat",
            {"stat": [{"date": "2026-04-18", "calls": 30}], "totals": {"calls": 30}},
        )
    )
    transport = fake.build()
    campaign = AsyncAutostrategyCampaign(transport, campaign_id=77)
    start_time = datetime.fromisoformat("2026-04-20T00:00:00+00:00")
    finish_time = datetime.fromisoformat("2026-04-27T00:00:00+00:00")

    assert (
        await campaign.create_budget(
            campaign_type="AS",
            start_time=start_time,
            finish_time=finish_time,
            items=[101, 102],
        )
    ).calc_id == 501
    assert (
        await campaign.create(
            campaign_type="AS",
            title="Весенняя кампания",
            budget=10000,
            calc_id=501,
            items=[101, 102],
            start_time=start_time,
            finish_time=finish_time,
        )
    ).campaign is not None
    assert (await campaign.update(campaign_id=77, version=3, title="Обновленная кампания")).campaign
    assert (await campaign.get()).campaign is not None
    assert (await campaign.delete(version=4)).campaign is not None
    assert (
        await campaign.list(
            limit=20,
            offset=10,
            status_id=[1, 2],
            order_by=[("startTime", "asc")],
            updated_from=datetime.fromisoformat("2026-04-01T00:00:00+00:00"),
            updated_to=datetime.fromisoformat("2026-04-30T00:00:00+00:00"),
        )
    ).total_count == 1
    assert (await campaign.get_stat()).totals is not None
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_promotion_dry_run_does_not_call_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    bbip = AsyncBbipPromotion(transport, item_id=101)
    trx = AsyncTrxPromotion(transport, item_id=101)
    pricing = AsyncTargetActionPricing(transport, item_id=101)
    bbip_item = BbipItem(item_id=101, duration=7, price=1000, old_price=1200)
    trx_item = TrxItem(
        item_id=101,
        commission=1500,
        date_from=datetime.fromisoformat("2026-04-18T00:00:00+00:00"),
    )

    assert (await bbip.create_order(items=[bbip_item], dry_run=True)).status == "preview"
    assert (await trx.apply(items=[trx_item], dry_run=True)).status == "preview"
    assert (
        await pricing.update_manual(action_type_id=5, bid_penny=1500, dry_run=True)
    ).status == "preview"
    assert fake.requests == []
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_autostrategy_datetime_parameters_fail_fast_on_invalid_type() -> None:
    transport = AsyncFakeTransport().build()
    campaign = AsyncAutostrategyCampaign(transport, campaign_id=77)

    with pytest.raises(ValidationError, match="`start_time` должен быть datetime."):
        await campaign.create_budget(campaign_type="AS", start_time="2026-04-20T00:00:00+00:00")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="`finish_time` должен быть datetime."):
        await campaign.create(
            campaign_type="AS",
            title="Весенняя кампания",
            finish_time="2026-04-27T00:00:00+00:00",  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError, match="`start_time` должен быть datetime."):
        await campaign.update(
            version=3,
            start_time="2026-04-20T00:00:00+00:00",  # type: ignore[arg-type]
        )
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_idempotency_key_forwarded_once_per_retry_chain() -> None:
    seen_keys: list[str | None] = []

    def fail_once(request: RecordedRequest) -> httpx.Response:
        seen_keys.append(request.headers.get("idempotency-key"))
        raise httpx.ConnectError(
            "offline",
            request=httpx.Request("POST", "https://api.avito.ru/cpxpromo/1/setManual"),
        )

    def succeed(request: RecordedRequest) -> httpx.Response:
        seen_keys.append(request.headers.get("idempotency-key"))
        return httpx.Response(
            200,
            json={"items": [{"itemID": 101, "success": True, "status": "manual"}]},
        )

    fake = AsyncFakeTransport().add("POST", "/cpxpromo/1/setManual", fail_once, succeed)
    transport = fake.build()
    pricing = AsyncTargetActionPricing(transport, item_id=101)

    result = await pricing.update_manual(
        action_type_id=5,
        bid_penny=1500,
        idempotency_key="idem-123",
    )

    assert result.status == "manual"
    assert seen_keys == ["idem-123", "idem-123"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_promotion_read_mappers_raise_on_invalid_shape() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("POST", "/promotion/v1/items/services/orders/status", {"items": []})
        .add_json("GET", "/cpxpromo/1/getBids/101", {"items": []})
        .add_json("POST", "/cpxpromo/1/getPromotionsByItemIds", {"items": [{"itemID": 102}]})
    )
    transport = fake.build()

    with pytest.raises(ResponseMappingError):
        await AsyncPromotionOrder(transport, order_id="ord-2").get_order_status()
    with pytest.raises(ResponseMappingError):
        await AsyncTargetActionPricing(transport, item_id=101).get_bids()
    with pytest.raises(ResponseMappingError):
        await AsyncTargetActionPricing(transport, item_id=101).get_promotions_by_item_ids(
            item_ids=[102]
        )
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_promotion_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.promotion_order(order_id="ord-1"), AsyncPromotionOrder)
    assert isinstance(client.bbip_promotion(item_id=101), AsyncBbipPromotion)
    assert isinstance(client.trx_promotion(item_id=101), AsyncTrxPromotion)
    assert isinstance(client.cpa_auction(item_id=101), AsyncCpaAuction)
    assert isinstance(client.target_action_pricing(item_id=101), AsyncTargetActionPricing)
    assert isinstance(client.autostrategy_campaign(campaign_id=77), AsyncAutostrategyCampaign)
    await client.aclose()


def test_async_client_promotion_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.promotion_order()
    with pytest.raises(RuntimeError):
        client.bbip_promotion()
    with pytest.raises(RuntimeError):
        client.trx_promotion()
    with pytest.raises(RuntimeError):
        client.cpa_auction()
    with pytest.raises(RuntimeError):
        client.target_action_pricing()
    with pytest.raises(RuntimeError):
        client.autostrategy_campaign()
