from __future__ import annotations

import pytest

from avito.summary import AccountHealthSummary, ListingHealthSummary, PromotionSummary
from avito.testing import AsyncFakeTransport, FanoutPeakRecorder


def _summary_fake(*, recorder: FanoutPeakRecorder) -> AsyncFakeTransport:
    return (
        AsyncFakeTransport(fanout_recorder=recorder)
        .add_json(
            "GET",
            "/core/v1/accounts/7/balance/",
            {"user_id": 7, "real": 100, "bonus": 25, "total": 125},
        )
        .add_json(
            "GET",
            "/core/v1/items",
            {"items": [{"id": 101, "title": "Смартфон", "status": "active"}], "total": 1},
        )
        .add_json(
            "POST",
            "/stats/v1/accounts/7/items",
            {"items": [{"item_id": 101, "views": 10}]},
        )
        .add_json(
            "POST",
            "/core/v1/accounts/7/calls/stats/",
            {"items": [{"item_id": 101, "calls": 2}]},
        )
        .add_json(
            "POST",
            "/stats/v2/accounts/7/spendings",
            {"items": [{"item_id": 101, "amount": 15.5}]},
        )
        .add_json(
            "GET",
            "/messenger/v2/accounts/7/chats",
            {"chats": [{"id": "c1", "unreadCount": 4}, {"id": "c2", "unreadCount": 0}]},
        )
        .add_json(
            "GET",
            "/order-management/1/orders",
            {"orders": [{"id": "o1", "status": "new"}, {"id": "o2", "status": "unknown"}]},
        )
        .add_json(
            "GET",
            "/ratings/v1/reviews",
            {
                "total": 2,
                "reviews": [
                    {"id": 1, "score": 5, "canAnswer": True},
                    {"id": 2, "score": 3, "canAnswer": False},
                ],
            },
        )
        .add_json("GET", "/ratings/v1/info", {"isEnabled": True, "rating": {"score": 4.5}})
        .add_json(
            "POST",
            "/promotion/v1/items/services/orders/get",
            {"orders": [{"orderId": "p1", "status": "applied"}]},
        )
        .add_json(
            "POST",
            "/promotion/v1/items/services/get",
            {"services": [{"itemId": 101, "status": "available"}]},
        )
    )


@pytest.mark.asyncio
async def test_account_health_fanout_does_not_exceed_six() -> None:
    recorder = FanoutPeakRecorder()
    client = _summary_fake(recorder=recorder).as_client(user_id=7)

    summary = await client.account_health()

    assert isinstance(summary, AccountHealthSummary)
    assert summary.balance_total == 125
    assert recorder.peak <= 6
    await client.aclose()


@pytest.mark.asyncio
async def test_listing_health_fanout_does_not_exceed_three() -> None:
    recorder = FanoutPeakRecorder()
    client = _summary_fake(recorder=recorder).as_client(user_id=7)

    summary = await client.listing_health()

    assert isinstance(summary, ListingHealthSummary)
    assert summary.total_views == 10
    assert recorder.peak <= 3
    await client.aclose()


@pytest.mark.asyncio
async def test_review_summary_is_sequential() -> None:
    recorder = FanoutPeakRecorder()
    client = _summary_fake(recorder=recorder).as_client(user_id=7)

    summary = await client.review_summary()

    assert summary.average_score == 4
    assert recorder.peak <= 1
    await client.aclose()


@pytest.mark.asyncio
async def test_promotion_summary_with_items_fanout_does_not_exceed_two() -> None:
    recorder = FanoutPeakRecorder()
    client = _summary_fake(recorder=recorder).as_client(user_id=7)

    summary = await client.promotion_summary(item_ids=[101])

    assert isinstance(summary, PromotionSummary)
    assert summary.available_services == 1
    assert recorder.peak <= 2
    await client.aclose()


@pytest.mark.asyncio
async def test_business_summary_delegates_to_account_health_fanout() -> None:
    recorder = FanoutPeakRecorder()
    client = _summary_fake(recorder=recorder).as_client(user_id=7)

    summary = await client.business_summary()

    assert isinstance(summary, AccountHealthSummary)
    assert summary.orders is not None
    assert recorder.peak <= 6
    await client.aclose()
