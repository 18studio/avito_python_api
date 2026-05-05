from __future__ import annotations

import json

import httpx
import pytest

from avito.core import ValidationError
from avito.realty import RealtyAnalyticsReport, RealtyBooking, RealtyListing, RealtyPricing
from avito.realty.models import (
    RealtyInterval,
    RealtyPricePeriod,
)
from tests.helpers.transport import make_transport


def test_realty_bookings_require_expected_params_and_map_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/core/v1/accounts/10/items/20/bookings":
            assert payload == {
                "bookings": [
                    {"date_start": "2026-04-18", "date_end": "2026-04-18"}
                ]
            }
            return httpx.Response(200, json={"result": "success"})
        if path == "/realty/v1/accounts/10/items/20/bookings":
            assert request.url.params["date_start"] == "2026-05-01"
            assert request.url.params["date_end"] == "2026-05-05"
            assert request.url.params["with_unpaid"] == "true"
            return httpx.Response(200, json={"bookings": [{"avito_booking_id": 777, "status": "active", "check_in": "2026-05-01", "check_out": "2026-05-05", "guest_count": 2, "nights": 4, "base_price": 12000, "contact": {"name": "Иван", "email": "ivan@example.com", "phone": "9997770000"}, "safe_deposit": {"owner_amount": 4500, "tax": 500, "total_amount": 5000}}]})
        if path == "/realty/v1/accounts/10/items/20/prices":
            assert payload == {"prices": [{"date_from": "2026-05-01", "night_price": 5000}]}
            return httpx.Response(200, json={"result": "success"})
        if path == "/realty/v1/items/intervals":
            assert payload == {
                "item_id": 20,
                "intervals": [
                    {"date_start": "2026-05-01", "date_end": "2026-05-01", "open": 1}
                ],
            }
            return httpx.Response(200, json={"result": "success"})
        if path == "/realty/v1/items/20/base":
            assert payload == {"minimal_duration": 2}
            return httpx.Response(200, json={"result": "success"})
        if path == "/realty/v1/marketPriceCorrespondence/20/5000000":
            return httpx.Response(200, json={"correspondence": "normal"})
        return httpx.Response(200, json={"success": {"success": {"reportLink": "https://example.com/realty-report/20"}}})

    transport = make_transport(httpx.MockTransport(handler))
    booking = RealtyBooking(transport, item_id="20", user_id="10")
    pricing = RealtyPricing(transport, item_id="20", user_id="10")
    listing = RealtyListing(transport, item_id="20")
    analytics = RealtyAnalyticsReport(transport, item_id="20")

    assert booking.update_bookings_info(blocked_dates=["2026-04-18"]).success is True
    bookings = booking.list_realty_bookings(date_start="2026-05-01", date_end="2026-05-05", with_unpaid=True)
    assert bookings.items[0].contact is not None
    assert bookings.items[0].contact.name == "Иван"
    assert pricing.update_realty_prices(periods=[RealtyPricePeriod(date_from="2026-05-01", price=5000)]).status == "success"
    assert listing.get_intervals(intervals=[RealtyInterval(date="2026-05-01", available=True)]).success is True
    assert listing.update_base_params(min_stay_days=2).success is True
    assert analytics.get_market_price_correspondence(price=5000000).correspondence == "normal"
    assert analytics.get_report_for_classified().report_link == "https://example.com/realty-report/20"


def test_realty_write_operation_forwards_idempotency_key() -> None:
    seen_keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("Idempotency-Key"))
        assert request.url.path == "/realty/v1/accounts/10/items/20/prices"
        assert json.loads(request.content.decode()) == {
            "prices": [{"date_from": "2026-05-01", "night_price": 5000}]
        }
        return httpx.Response(200, json={"result": "success"})

    pricing = RealtyPricing(
        make_transport(httpx.MockTransport(handler)),
        item_id="20",
        user_id="10",
    )

    result = pricing.update_realty_prices(
        periods=[RealtyPricePeriod(date_from="2026-05-01", price=5000)],
        idempotency_key="idem-realty-prices",
    )

    assert result.status == "success"
    assert seen_keys == ["idem-realty-prices"]


def test_realty_rejects_invalid_dates_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    transport = make_transport(httpx.MockTransport(handler))
    booking = RealtyBooking(transport, item_id="20", user_id="10")
    pricing = RealtyPricing(transport, item_id="20", user_id="10")
    listing = RealtyListing(transport, item_id="20")

    with pytest.raises(ValidationError, match="date_start"):
        booking.list_realty_bookings(date_start="01.05.2026", date_end="2026-05-05")
    with pytest.raises(ValidationError, match="blocked_dates"):
        booking.update_bookings_info(blocked_dates=["not-a-date"])
    with pytest.raises(ValidationError, match="date_from"):
        pricing.update_realty_prices(periods=[RealtyPricePeriod(date_from="not-a-date", price=5000)])
    with pytest.raises(ValidationError, match="date"):
        listing.get_intervals(intervals=[RealtyInterval(date="not-a-date", available=True)])
