"""Operation specs for realty domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.realty.models import (
    RealtyActionResult,
    RealtyAnalyticsInfo,
    RealtyBaseParamsUpdateRequest,
    RealtyBookingsQuery,
    RealtyBookingsResult,
    RealtyBookingsUpdateRequest,
    RealtyIntervalsRequest,
    RealtyMarketPriceInfo,
    RealtyPricesUpdateRequest,
)

UPDATE_BOOKINGS_INFO = OperationSpec(
    name="realty.bookings.update",
    method="POST",
    path="/core/v1/accounts/{user_id}/items/{item_id}/bookings",
    request_model=RealtyBookingsUpdateRequest,
    response_model=RealtyActionResult,
    retry_mode="enabled",
)
LIST_REALTY_BOOKINGS = OperationSpec(
    name="realty.bookings.list",
    method="GET",
    path="/realty/v1/accounts/{user_id}/items/{item_id}/bookings",
    query_model=RealtyBookingsQuery,
    response_model=RealtyBookingsResult,
)
UPDATE_REALTY_PRICES = OperationSpec(
    name="realty.prices.update",
    method="POST",
    path="/realty/v1/accounts/{user_id}/items/{item_id}/prices",
    request_model=RealtyPricesUpdateRequest,
    response_model=RealtyActionResult,
    retry_mode="enabled",
)
GET_INTERVALS = OperationSpec(
    name="realty.intervals.fill",
    method="POST",
    path="/realty/v1/items/intervals",
    request_model=RealtyIntervalsRequest,
    response_model=RealtyActionResult,
    retry_mode="enabled",
)
UPDATE_BASE_PARAMS = OperationSpec(
    name="realty.base_params.update",
    method="POST",
    path="/realty/v1/items/{item_id}/base",
    request_model=RealtyBaseParamsUpdateRequest,
    response_model=RealtyActionResult,
    retry_mode="enabled",
)
GET_MARKET_PRICE_CORRESPONDENCE = OperationSpec(
    name="realty.analytics.market_price",
    method="GET",
    path="/realty/v1/marketPriceCorrespondence/{itemId}/{price}",
    response_model=RealtyMarketPriceInfo,
)
GET_REPORT_FOR_CLASSIFIED = OperationSpec(
    name="realty.analytics.report",
    method="POST",
    path="/realty/v1/report/create/{itemId}",
    response_model=RealtyAnalyticsInfo,
    retry_mode="enabled",
)

__all__ = (
    "GET_INTERVALS",
    "GET_MARKET_PRICE_CORRESPONDENCE",
    "GET_REPORT_FOR_CLASSIFIED",
    "LIST_REALTY_BOOKINGS",
    "UPDATE_BASE_PARAMS",
    "UPDATE_BOOKINGS_INFO",
    "UPDATE_REALTY_PRICES",
)
