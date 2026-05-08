from __future__ import annotations

from avito.core.swagger_discovery import discover_swagger_bindings
from avito.core.swagger_registry import load_swagger_registry


def test_async_swagger_bindings_are_discoverable_for_ported_domains() -> None:
    discovery = discover_swagger_bindings(registry=load_swagger_registry())
    async_bindings = [binding for binding in discovery.bindings if binding.variant == "async"]

    assert {binding.class_name for binding in async_bindings} == {
        "AsyncAccount",
        "AsyncAccountHierarchy",
        "AsyncAlternateTokenClient",
        "AsyncCallTrackingCall",
        "AsyncCpaArchive",
        "AsyncCpaCall",
        "AsyncCpaChat",
        "AsyncCpaLead",
        "AsyncRatingProfile",
        "AsyncRealtyAnalyticsReport",
        "AsyncRealtyBooking",
        "AsyncRealtyListing",
        "AsyncRealtyPricing",
        "AsyncReview",
        "AsyncReviewAnswer",
        "AsyncTariff",
        "AsyncTokenClient",
    }
    assert len(async_bindings) == 38
