from __future__ import annotations

import json
import logging
from datetime import date, datetime

import httpx
import pytest

from avito.ads import Ad, AdPromotion, AdStats
from avito.ads.models import AdAnalyticsGrouping, AdSpendingsGrouping, ListingStatus
from avito.core import ValidationError
from tests.helpers.transport import make_transport


def test_ads_list_uses_lazy_pagination_with_list_like_items() -> None:
    seen_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/items"
        assert request.url.params["user_id"] == "7"
        assert request.url.params["status"] == "active"
        assert request.url.params["per_page"] == "2"

        page = request.url.params["page"]
        seen_offsets.append(page)
        page_items = {
            "1": [{"id": 101, "title": "Смартфон"}, {"id": 102, "title": "Ноутбук"}],
            "2": [{"id": 103, "title": "Планшет"}, {"id": 104, "title": "Наушники"}],
            "3": [{"id": 105, "title": "Камера"}],
        }
        return httpx.Response(200, json={"items": page_items[page], "total": 5})

    ad = Ad(make_transport(httpx.MockTransport(handler)), user_id=7)

    items = ad.list(status="active", page_size=2)

    assert seen_offsets == ["1"]
    assert items[3].item_id == 104
    assert seen_offsets == ["1", "2"]
    assert [item.title for item in items.materialize()] == [
        "Смартфон",
        "Ноутбук",
        "Планшет",
        "Наушники",
        "Камера",
    ]
    assert seen_offsets == ["1", "2", "3"]


def test_ads_list_limit_is_total_cap_not_page_size() -> None:
    seen_limits: list[str] = []
    seen_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/items"
        seen_limits.append(request.url.params["per_page"])
        page = request.url.params["page"]
        seen_offsets.append(page)
        page_items = {
            "1": [{"id": 101}, {"id": 102}],
            "2": [{"id": 103}],
        }
        return httpx.Response(200, json={"items": page_items[page], "total": 5})

    ad = Ad(make_transport(httpx.MockTransport(handler)), user_id=7)

    items = ad.list(limit=3, page_size=2)

    assert [item.item_id for item in items.materialize()] == [101, 102, 103]
    assert seen_limits == ["2", "1"]
    assert seen_offsets == ["1", "2"]


def test_ads_list_does_not_treat_limit_as_total_when_api_omits_total() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/items"
        assert request.url.params["per_page"] == "50"
        assert request.url.params["page"] == "1"
        return httpx.Response(200, json={"items": [{"id": item_id} for item_id in range(101, 126)]})

    ad = Ad(make_transport(httpx.MockTransport(handler)), user_id=7)

    items = ad.list(limit=50)

    assert len(items) == 25
    assert items.loaded_count == 25
    assert items.known_total is None
    assert items.source_total is None
    assert [item.item_id for item in items.materialize()] == list(range(101, 126))


def test_ads_domain_covers_item_stats_spendings_and_promotion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/core/v1/accounts/7/items/101/":
            return httpx.Response(
                200,
                json={"id": 101, "user_id": 7, "title": "Смартфон", "price": 1000, "status": "active"},
            )
        if request.url.path == "/stats/v1/accounts/7/items":
            return httpx.Response(
                200, json={"items": [{"item_id": 101, "views": 45, "contacts": 5, "favorites": 2}]}
            )
        if request.url.path == "/core/v1/accounts/7/calls/stats/":
            return httpx.Response(
                200,
                json={"items": [{"item_id": 101, "calls": 3, "answered_calls": 2, "missed_calls": 1}]},
            )
        if request.url.path == "/stats/v2/accounts/7/spendings":
            return httpx.Response(
                200, json={"items": [{"item_id": 101, "amount": 77.5, "service": "xl"}]}
            )
        if request.url.path == "/core/v1/accounts/7/items/101/vas":
            assert json.loads(request.content.decode()) == {"vas_id": "xl"}
            return httpx.Response(200, json={"success": True, "status": "applied"})
        assert request.url.path == "/core/v1/items/101/update_price"
        assert json.loads(request.content.decode()) == {"price": 1500}
        return httpx.Response(200, json={"item_id": 101, "price": 1500, "status": "updated"})

    transport = make_transport(httpx.MockTransport(handler))
    ad = Ad(transport, item_id=101, user_id=7)
    stats = AdStats(transport, item_id=101, user_id=7)
    promotion = AdPromotion(transport, item_id=101, user_id=7)

    item = ad.get()
    updated = ad.update_price(price=1500)
    item_stats = stats.get_item_stats(date_from="2026-04-01", date_to="2026-04-02")
    calls = stats.get_calls_stats(date_from="2026-04-01", date_to="2026-04-02")
    spendings = stats.get_account_spendings(
        date_from="2026-04-01",
        date_to="2026-04-02",
        spending_types=["promotion"],
        grouping=AdSpendingsGrouping.DAY,
    )
    applied = promotion.apply_vas(vas_id="xl")

    assert item.title == "Смартфон"
    assert updated.status == "updated"
    assert item_stats.items[0].views == 45
    assert calls.items[0].answered_calls == 2
    assert spendings.total == 77.5
    assert applied.status == "applied"


def test_ad_stats_accept_datetime_filters_and_serialize_isoformat() -> None:
    seen_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"items": [{"item_id": 101, "views": 10}]})

    stats = AdStats(make_transport(httpx.MockTransport(handler)), item_id=101, user_id=7)
    started_at = datetime.fromisoformat("2026-04-18T00:00:00+03:00")
    finished_at = datetime.fromisoformat("2026-04-18T23:59:59+03:00")

    stats.get_item_analytics(
        item_ids=[101],
        date_from=started_at,
        date_to=finished_at,
        metrics=["views"],
        grouping=AdAnalyticsGrouping.DAY,
        limit=100,
        offset=0,
    )

    assert seen_payloads[0]["dateFrom"] == "2026-04-18"
    assert seen_payloads[0]["dateTo"] == "2026-04-18"
    assert seen_payloads[0]["grouping"] == "day"


def test_ad_stats_accept_date_and_iso_string_filters() -> None:
    seen_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/core/v1/accounts/self":
            return httpx.Response(200, json={"id": 7})
        seen_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"items": [{"item_id": 101, "views": 10}]})

    stats = AdStats(make_transport(httpx.MockTransport(handler)), item_id=101)

    stats.get_item_stats(date_from=date.fromisoformat("2026-04-18"), date_to="2026-04-19T10:15:00+03:00")

    assert seen_payloads[0]["dateFrom"] == "2026-04-18"
    assert seen_payloads[0]["dateTo"] == "2026-04-19"


def test_ad_stats_reject_unknown_grouping_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    stats = AdStats(make_transport(httpx.MockTransport(handler)), item_id=101, user_id=7)

    with pytest.raises(ValidationError, match="grouping"):
        stats.get_item_analytics(
            date_from="2026-04-18",
            date_to="2026-04-19",
            metrics=["views"],
            grouping="unknown",
            limit=100,
            offset=0,
        )
    with pytest.raises(ValidationError, match="grouping"):
        stats.get_account_spendings(
            date_from="2026-04-18",
            date_to="2026-04-19",
            spending_types=["promotion"],
            grouping="totals",
        )


def test_ad_mapper_reads_nested_listing_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/accounts/7/items/101/"
        return httpx.Response(
            200,
            json={
                "id": 101,
                "userId": 7,
                "title": "Смартфон",
                "description": "Хорошее состояние",
                "price": {"value": 1000},
                "status": {"value": "active"},
                "url": "https://www.avito.ru/item",
                "category": {"name": "Телефоны"},
                "location": {"name": "Москва"},
                "publishedAt": "2026-04-18T09:00:00Z",
                "updatedAt": "2026-04-19T10:00:00Z",
                "isModerated": True,
                "visible": True,
            },
        )

    ad = Ad(make_transport(httpx.MockTransport(handler)), item_id=101, user_id=7)

    item = ad.get()

    assert item.status is ListingStatus.ACTIVE
    assert item.price == 1000
    assert item.category == "Телефоны"
    assert item.city == "Москва"
    assert item.published_at is not None
    assert item.updated_at is not None
    assert item.is_moderated is True
    assert item.is_visible is True


def test_ad_mapper_reads_wrapped_item_payload_and_full_status_set() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/accounts/7/items/101/"
        return httpx.Response(
            200,
            json={
                "item": {
                    "itemId": "101",
                    "title": "Архивное объявление",
                    "price": 100,
                    "status": "removed",
                    "link": "https://www.avito.ru/item",
                }
            },
        )

    ad = Ad(make_transport(httpx.MockTransport(handler)), item_id=101, user_id=7)

    item = ad.get()

    assert item.item_id == 101
    assert item.title == "Архивное объявление"
    assert item.status is ListingStatus.REMOVED
    assert item.is_visible is False


def test_ads_unknown_enum_maps_to_unknown_and_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/core/v1/accounts/7/items/101/"
        return httpx.Response(
            200,
            json={
                "id": 101,
                "user_id": 7,
                "title": "Смартфон",
                "price": 1000,
                "status": "mystery-status",
            },
        )

    caplog.set_level(logging.WARNING, logger="avito.core.enums")
    ad = Ad(make_transport(httpx.MockTransport(handler)), item_id=101, user_id=7)

    first = ad.get()
    second = ad.get()

    assert first.status is ListingStatus.UNKNOWN
    assert second.status is ListingStatus.UNKNOWN
    records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "ads.listing_status"
        and getattr(record, "value", None) == "mystery-status"
    ]
    assert len(records) == 1
