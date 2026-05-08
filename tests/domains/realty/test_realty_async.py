from __future__ import annotations

import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import ValidationError
from avito.realty import (
    AsyncRealtyAnalyticsReport,
    AsyncRealtyBooking,
    AsyncRealtyListing,
    AsyncRealtyPricing,
)
from avito.realty.models import RealtyInterval, RealtyPricePeriod
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_realty_maps_bookings_pricing_listing_and_analytics() -> None:
    def update_bookings(request: RecordedRequest):
        assert request.json_body == {
            "bookings": [{"date_start": "2026-04-18", "date_end": "2026-04-18"}]
        }
        return _success_response()

    def update_prices(request: RecordedRequest):
        assert request.json_body == {
            "prices": [{"date_from": "2026-05-01", "night_price": 5000}]
        }
        return _success_response()

    def get_intervals(request: RecordedRequest):
        assert request.json_body == {
            "item_id": 20,
            "intervals": [{"date_start": "2026-05-01", "date_end": "2026-05-01", "open": 1}],
        }
        return _success_response()

    def update_base(request: RecordedRequest):
        assert request.json_body == {"minimal_duration": 2}
        return _success_response()

    fake = (
        AsyncFakeTransport()
        .add("POST", "/core/v1/accounts/10/items/20/bookings", update_bookings)
        .add_json(
            "GET",
            "/realty/v1/accounts/10/items/20/bookings",
            {
                "bookings": [
                    {
                        "avito_booking_id": 777,
                        "status": "active",
                        "check_in": "2026-05-01",
                        "check_out": "2026-05-05",
                        "guest_count": 2,
                        "nights": 4,
                        "base_price": 12000,
                        "contact": {
                            "name": "Иван",
                            "email": "ivan@example.com",
                            "phone": "9997770000",
                        },
                        "safe_deposit": {
                            "owner_amount": 4500,
                            "tax": 500,
                            "total_amount": 5000,
                        },
                    }
                ]
            },
        )
        .add("POST", "/realty/v1/accounts/10/items/20/prices", update_prices)
        .add("POST", "/realty/v1/items/intervals", get_intervals)
        .add("POST", "/realty/v1/items/20/base", update_base)
        .add_json(
            "GET",
            "/realty/v1/marketPriceCorrespondence/20/5000000",
            {"correspondence": "normal"},
        )
        .add_json(
            "POST",
            "/realty/v1/report/create/20",
            {"success": {"success": {"reportLink": "https://example.com/realty-report/20"}}},
        )
    )
    transport = fake.build()
    booking = AsyncRealtyBooking(transport, item_id="20", user_id="10")
    pricing = AsyncRealtyPricing(transport, item_id="20", user_id="10")
    listing = AsyncRealtyListing(transport, item_id="20")
    analytics = AsyncRealtyAnalyticsReport(transport, item_id="20")

    assert (await booking.update_bookings_info(blocked_dates=["2026-04-18"])).success is True
    bookings = await booking.list_realty_bookings(
        date_start="2026-05-01",
        date_end="2026-05-05",
        with_unpaid=True,
    )
    assert bookings.items[0].contact is not None
    assert bookings.items[0].contact.name == "Иван"
    assert (
        await pricing.update_realty_prices(
            periods=[RealtyPricePeriod(date_from="2026-05-01", price=5000)]
        )
    ).status == "success"
    assert (
        await listing.get_intervals(intervals=[RealtyInterval(date="2026-05-01", available=True)])
    ).success is True
    assert (await listing.update_base_params(min_stay_days=2)).success is True
    assert (await analytics.get_market_price_correspondence(price=5000000)).correspondence == "normal"
    assert (
        await analytics.get_report_for_classified()
    ).report_link == "https://example.com/realty-report/20"
    assert fake.last(method="GET", path="/realty/v1/accounts/10/items/20/bookings").params == {
        "date_start": "2026-05-01",
        "date_end": "2026-05-05",
        "with_unpaid": "true",
    }
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_realty_write_operation_forwards_idempotency_key() -> None:
    def update_prices(request: RecordedRequest):
        assert request.headers["idempotency-key"] == "idem-realty-prices"
        assert request.json_body == {
            "prices": [{"date_from": "2026-05-01", "night_price": 5000}]
        }
        return _success_response()

    fake = AsyncFakeTransport().add(
        "POST",
        "/realty/v1/accounts/10/items/20/prices",
        update_prices,
    )
    transport = fake.build()
    pricing = AsyncRealtyPricing(transport, item_id="20", user_id="10")

    result = await pricing.update_realty_prices(
        periods=[RealtyPricePeriod(date_from="2026-05-01", price=5000)],
        idempotency_key="idem-realty-prices",
    )

    assert result.status == "success"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_realty_rejects_invalid_dates_before_transport() -> None:
    transport = AsyncFakeTransport().build()
    booking = AsyncRealtyBooking(transport, item_id="20", user_id="10")
    pricing = AsyncRealtyPricing(transport, item_id="20", user_id="10")
    listing = AsyncRealtyListing(transport, item_id="20")

    with pytest.raises(ValidationError, match="date_start"):
        await booking.list_realty_bookings(date_start="01.05.2026", date_end="2026-05-05")
    with pytest.raises(ValidationError, match="blocked_dates"):
        await booking.update_bookings_info(blocked_dates=["not-a-date"])
    with pytest.raises(ValidationError, match="date_from"):
        await pricing.update_realty_prices(
            periods=[RealtyPricePeriod(date_from="not-a-date", price=5000)]
        )
    with pytest.raises(ValidationError, match="date"):
        await listing.get_intervals(intervals=[RealtyInterval(date="not-a-date", available=True)])
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_realty_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.realty_listing(item_id=20, user_id=10), AsyncRealtyListing)
    assert isinstance(client.realty_booking(item_id=20, user_id=10), AsyncRealtyBooking)
    assert isinstance(client.realty_pricing(item_id=20, user_id=10), AsyncRealtyPricing)
    assert isinstance(
        client.realty_analytics_report(item_id=20, user_id=10),
        AsyncRealtyAnalyticsReport,
    )
    await client.aclose()


def test_async_client_realty_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.realty_listing()
    with pytest.raises(RuntimeError):
        client.realty_booking()
    with pytest.raises(RuntimeError):
        client.realty_pricing()
    with pytest.raises(RuntimeError):
        client.realty_analytics_report()


def _success_response():
    import httpx

    return httpx.Response(200, json={"result": "success"})
