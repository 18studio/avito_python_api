from __future__ import annotations

import logging
from datetime import date, datetime

import httpx
import pytest

from avito.ads import (
    AsyncAd,
    AsyncAdPromotion,
    AsyncAdStats,
    AsyncAutoloadArchive,
    AsyncAutoloadProfile,
    AsyncAutoloadReport,
)
from avito.ads.models import AdAnalyticsGrouping, AdSpendingsGrouping, ListingStatus
from avito.core import AsyncPaginatedList, ValidationError
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_ads_list_uses_lazy_pagination_with_first_page_reuse() -> None:
    seen_pages: list[str] = []

    def handler(request: RecordedRequest) -> httpx.Response:
        assert request.params["user_id"] == "7"
        assert request.params["status"] == "active"
        assert request.params["per_page"] == "2"
        page = request.params["page"]
        seen_pages.append(page)
        page_items = {
            "1": [{"id": 101, "title": "Смартфон"}, {"id": 102, "title": "Ноутбук"}],
            "2": [{"id": 103, "title": "Планшет"}, {"id": 104, "title": "Наушники"}],
            "3": [{"id": 105, "title": "Камера"}],
        }
        return httpx.Response(200, json={"items": page_items[page], "total": 5})

    fake = AsyncFakeTransport().add("GET", "/core/v1/items", handler)
    transport = fake.build()
    ad = AsyncAd(transport, user_id=7)

    items = await ad.list(status="active", page_size=2)

    assert isinstance(items, AsyncPaginatedList)
    assert seen_pages == ["1"]
    assert items.loaded_count == 2
    materialized = await items.materialize()
    assert [item.title for item in materialized] == [
        "Смартфон",
        "Ноутбук",
        "Планшет",
        "Наушники",
        "Камера",
    ]
    assert seen_pages == ["1", "2", "3"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ads_list_limit_is_total_cap_not_page_size() -> None:
    seen_limits: list[str] = []
    seen_pages: list[str] = []

    def handler(request: RecordedRequest) -> httpx.Response:
        seen_limits.append(request.params["per_page"])
        page = request.params["page"]
        seen_pages.append(page)
        page_items = {
            "1": [{"id": 101}, {"id": 102}],
            "2": [{"id": 103}],
        }
        return httpx.Response(200, json={"items": page_items[page], "total": 5})

    fake = AsyncFakeTransport().add("GET", "/core/v1/items", handler)
    transport = fake.build()
    ad = AsyncAd(transport, user_id=7)

    items = await ad.list(limit=3, page_size=2)

    assert [item.item_id for item in await items.materialize()] == [101, 102, 103]
    assert seen_limits == ["2", "1"]
    assert seen_pages == ["1", "2"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ads_domain_covers_item_stats_spendings_and_promotion() -> None:
    def update_price(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"price": 1500}
        return httpx.Response(200, json={"item_id": 101, "price": 1500, "status": "updated"})

    def apply_vas(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"vas_id": "xl"}
        return httpx.Response(200, json={"success": True, "status": "applied"})

    fake = (
        AsyncFakeTransport()
        .add_json(
            "GET",
            "/core/v1/accounts/7/items/101/",
            {"id": 101, "user_id": 7, "title": "Смартфон", "price": 1000, "status": "active"},
        )
        .add("POST", "/core/v1/items/101/update_price", update_price)
        .add_json(
            "POST",
            "/stats/v1/accounts/7/items",
            {"items": [{"item_id": 101, "views": 45, "contacts": 5, "favorites": 2}]},
        )
        .add_json(
            "POST",
            "/core/v1/accounts/7/calls/stats/",
            {"items": [{"item_id": 101, "calls": 3, "answered_calls": 2, "missed_calls": 1}]},
        )
        .add_json(
            "POST",
            "/stats/v2/accounts/7/spendings",
            {"items": [{"item_id": 101, "amount": 77.5, "service": "xl"}]},
        )
        .add("PUT", "/core/v1/accounts/7/items/101/vas", apply_vas)
    )
    transport = fake.build()
    ad = AsyncAd(transport, item_id=101, user_id=7)
    stats = AsyncAdStats(transport, item_id=101, user_id=7)
    promotion = AsyncAdPromotion(transport, item_id=101, user_id=7)

    item = await ad.get()
    updated = await ad.update_price(price=1500)
    item_stats = await stats.get_item_stats(date_from="2026-04-01", date_to="2026-04-02")
    calls = await stats.get_calls_stats(date_from="2026-04-01", date_to="2026-04-02")
    spendings = await stats.get_account_spendings(
        date_from="2026-04-01",
        date_to="2026-04-02",
        spending_types=["promotion"],
        grouping=AdSpendingsGrouping.DAY,
    )
    applied = await promotion.apply_vas(vas_id="xl")

    assert item.title == "Смартфон"
    assert updated.status == "updated"
    assert item_stats.items[0].views == 45
    assert calls.items[0].answered_calls == 2
    assert spendings.total == 77.5
    assert applied.status == "applied"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ad_stats_accept_datetime_date_and_iso_string_filters() -> None:
    fake = AsyncFakeTransport().add_json(
        "POST",
        "/stats/v2/accounts/7/items",
        {"items": [{"item_id": 101, "views": 10}]},
    )
    transport = fake.build()
    stats = AsyncAdStats(transport, item_id=101, user_id=7)
    started_at = datetime.fromisoformat("2026-04-18T00:00:00+03:00")
    finished_at = date.fromisoformat("2026-04-19")

    await stats.get_item_analytics(
        item_ids=[101],
        date_from=started_at,
        date_to=finished_at,
        metrics=["views"],
        grouping=AdAnalyticsGrouping.DAY,
        limit=100,
        offset=0,
    )

    assert fake.last(method="POST", path="/stats/v2/accounts/7/items").json_body == {
        "dateFrom": "2026-04-18",
        "dateTo": "2026-04-19",
        "metrics": ["views"],
        "grouping": "day",
        "limit": 100,
        "offset": 0,
    }
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ad_stats_reject_unknown_grouping_before_transport() -> None:
    transport = AsyncFakeTransport().build()
    stats = AsyncAdStats(transport, item_id=101, user_id=7)

    with pytest.raises(ValidationError, match="grouping"):
        await stats.get_item_analytics(
            date_from="2026-04-18",
            date_to="2026-04-19",
            metrics=["views"],
            grouping="unknown",
            limit=100,
            offset=0,
        )
    with pytest.raises(ValidationError, match="grouping"):
        await stats.get_account_spendings(
            date_from="2026-04-18",
            date_to="2026-04-19",
            spending_types=["promotion"],
            grouping="totals",
        )
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ad_mapper_reads_nested_listing_fields() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/core/v1/accounts/7/items/101/",
        {
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
    transport = fake.build()

    item = await AsyncAd(transport, item_id=101, user_id=7).get()

    assert item.status is ListingStatus.ACTIVE
    assert item.price == 1000
    assert item.category == "Телефоны"
    assert item.city == "Москва"
    assert item.published_at is not None
    assert item.updated_at is not None
    assert item.is_moderated is True
    assert item.is_visible is True
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ads_unknown_enum_maps_to_unknown_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/core/v1/accounts/7/items/101/",
        {
            "id": 101,
            "user_id": 7,
            "title": "Смартфон",
            "price": 1000,
            "status": "async-mystery-status",
        },
    )
    transport = fake.build()
    caplog.set_level(logging.WARNING, logger="avito.core.enums")
    ad = AsyncAd(transport, item_id=101, user_id=7)

    first = await ad.get()
    second = await ad.get()

    assert first.status is ListingStatus.UNKNOWN
    assert second.status is ListingStatus.UNKNOWN
    records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "ads.listing_status"
        and getattr(record, "value", None) == "async-mystery-status"
    ]
    assert len(records) == 1
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_autoload_profile_report_and_archive_map_payloads() -> None:
    def save_profile(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "autoload_enabled": True,
            "report_email": "report@example.com",
            "schedule": [{"rate": 10, "weekdays": [1], "time_slots": [2]}],
            "feeds_data": [{"feed_name": "main", "feed_url": "https://example.com/feed.xml"}],
        }
        assert request.headers["idempotency-key"] == "profile-1"
        return httpx.Response(200, json={"success": True, "message": "saved"})

    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/autoload/v2/profile", {"user_id": 7, "is_enabled": True, "url": "x"})
        .add("POST", "/autoload/v2/profile", save_profile)
        .add_json("POST", "/autoload/v1/upload", {"success": True, "report_id": 44})
        .add_json("GET", "/autoload/v1/user-docs/tree", {"items": [{"slug": "cars", "title": "Авто"}]})
        .add_json(
            "GET",
            "/autoload/v1/user-docs/node/cars/fields",
            {"fields": [{"slug": "vin", "title": "VIN", "type": "string", "required": True}]},
        )
        .add_json("GET", "/autoload/v3/reports/44", {"id": 44, "status": "finished"})
        .add_json(
            "GET",
            "/autoload/v3/reports/last_completed_report",
            {"id": 45, "status": "finished"},
        )
        .add_json(
            "GET",
            "/autoload/v2/reports/44/items",
            {"items": [{"item_id": 101, "avito_id": 201, "status": "success", "title": "A"}]},
        )
        .add_json(
            "GET",
            "/autoload/v2/reports/44/items/fees",
            {"fees": [{"item_id": 101, "amount": 55.5, "service": "xl"}]},
        )
        .add_json("GET", "/autoload/v2/items/ad_ids", {"items": [{"ad_id": 1, "avito_id": 2}]})
        .add_json("GET", "/autoload/v2/items/avito_ids", {"items": [{"ad_id": 1, "avito_id": 2}]})
        .add_json(
            "GET",
            "/autoload/v2/reports/items",
            {"items": [{"item_id": 101, "avito_id": 201, "status": "success"}]},
        )
        .add_json("GET", "/autoload/v1/profile", {"user_id": 7, "enabled": True})
        .add_json("POST", "/autoload/v1/profile", {"success": True})
        .add_json("GET", "/autoload/v2/reports/last_completed_report", {"id": 46, "status": "finished"})
        .add_json("GET", "/autoload/v2/reports/44", {"id": 44, "status": "finished"})
    )
    transport = fake.build()
    profile = AsyncAutoloadProfile(transport, user_id=7)
    report = AsyncAutoloadReport(transport, report_id=44)
    archive = AsyncAutoloadArchive(transport, report_id=44)

    settings = await profile.get()
    saved = await profile.save(
        is_enabled=True,
        report_email="report@example.com",
        schedule_rate=10,
        feed_name="main",
        feed_url="https://example.com/feed.xml",
        schedule_weekdays=[1],
        schedule_time_slots=[2],
        idempotency_key="profile-1",
    )
    upload = await profile.upload_by_url(url="https://example.com/feed.xml")
    tree = await profile.get_tree()
    fields = await profile.get_node_fields(node_slug="cars")
    details = await report.get()
    last = await report.get_last_completed()
    items = await report.get_items()
    fees = await report.get_fees()
    ad_ids = await report.get_ad_ids_by_avito_ids(avito_ids=[2])
    avito_ids = await report.get_avito_ids_by_ad_ids(ad_ids=[1])
    info = await report.get_items_info(item_ids=[101])
    with pytest.warns(DeprecationWarning, match="AsyncAutoloadArchive.get_profile"):
        archive_profile = await archive.get_profile()
    with pytest.warns(DeprecationWarning, match="AsyncAutoloadArchive.save_profile"):
        archive_saved = await archive.save_profile(
            is_enabled=True,
            upload_url="https://example.com/feed.xml",
            report_email="report@example.com",
            schedule_rate=10,
        )
    with pytest.warns(
        DeprecationWarning,
        match="AsyncAutoloadArchive.get_last_completed_report",
    ):
        archive_last = await archive.get_last_completed_report()
    with pytest.warns(DeprecationWarning, match="AsyncAutoloadArchive.get_report"):
        archive_report = await archive.get_report()

    assert settings.user_id == 7
    assert saved.success is True
    assert upload.report_id == 44
    assert tree.items[0].slug == "cars"
    assert fields.items[0].required is True
    assert details.report_id == 44
    assert last.report_id == 45
    assert items.items[0].item_id == 101
    assert fees.total == 55.5
    assert ad_ids.mappings == [(1, 2)]
    assert avito_ids.mappings == [(1, 2)]
    assert info.items[0].avito_id == 201
    assert archive_profile.user_id == 7
    assert archive_saved.success is True
    assert archive_last.report_id == 46
    assert archive_report.report_id == 44
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_autoload_report_list_uses_async_pagination() -> None:
    seen_offsets: list[str] = []

    def handler(request: RecordedRequest) -> httpx.Response:
        seen_offsets.append(request.params["offset"])
        reports = {
            "5": [{"id": 44, "status": "finished"}],
            "6": [{"id": 45, "status": "started"}],
        }
        return httpx.Response(200, json={"reports": reports[request.params["offset"]], "total": 2})

    fake = AsyncFakeTransport().add("GET", "/autoload/v2/reports", handler)
    transport = fake.build()

    reports = await AsyncAutoloadReport(transport).list(limit=1, offset=5)

    assert isinstance(reports, AsyncPaginatedList)
    assert reports.loaded_count == 1
    assert [report.report_id for report in await reports.materialize()] == [44, 45]
    assert seen_offsets == ["5", "6"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_ads_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client(user_id=7)

    assert isinstance(client.ad(101), AsyncAd)
    assert isinstance(client.ad_stats(101), AsyncAdStats)
    assert isinstance(client.ad_promotion(101), AsyncAdPromotion)
    assert isinstance(client.autoload_profile(), AsyncAutoloadProfile)
    assert isinstance(client.autoload_report(44), AsyncAutoloadReport)
    assert isinstance(client.autoload_archive(44), AsyncAutoloadArchive)
    await client.aclose()
