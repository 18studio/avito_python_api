"""Operation specs for ads domain."""

from __future__ import annotations

from avito.ads.models import (
    AccountSpendings,
    AdsActionResult,
    AdsListResult,
    ApplyVasDirectRequest,
    ApplyVasPackageRequest,
    ApplyVasRequest,
    AutoloadFeesResult,
    AutoloadFieldsResult,
    AutoloadProfileSettings,
    AutoloadProfileUpdateRequest,
    AutoloadReportDetails,
    AutoloadReportItemsResult,
    AutoloadReportsResult,
    AutoloadTreeResult,
    CallsStatsRequest,
    CallsStatsResult,
    IdMappingResult,
    ItemAnalyticsRequest,
    ItemAnalyticsResult,
    ItemStatsRequest,
    ItemStatsResult,
    LegacyAutoloadReport,
    Listing,
    SpendingsRequest,
    UpdatePriceRequest,
    UpdatePriceResult,
    UploadByUrlRequest,
    UploadResult,
    VasPricesRequest,
    VasPricesResult,
)
from avito.core import OperationSpec
from avito.promotion.models import PromotionActionPayload

GET_ITEM = OperationSpec(
    name="ads.get_item",
    method="GET",
    path="/core/v1/accounts/{user_id}/items/{item_id}/",
    response_model=Listing,
)
LIST_ITEMS = OperationSpec(
    name="ads.list_items",
    method="GET",
    path="/core/v1/items",
    response_model=AdsListResult,
)
UPDATE_PRICE = OperationSpec(
    name="ads.update_price",
    method="POST",
    path="/core/v1/items/{item_id}/update_price",
    request_model=UpdatePriceRequest,
    response_model=UpdatePriceResult,
    retry_mode="enabled",
)
GET_CALLS_STATS = OperationSpec(
    name="ads.stats.calls",
    method="POST",
    path="/core/v1/accounts/{user_id}/calls/stats/",
    request_model=CallsStatsRequest,
    response_model=CallsStatsResult,
    retry_mode="enabled",
)
GET_ITEM_STATS = OperationSpec(
    name="ads.stats.items",
    method="POST",
    path="/stats/v1/accounts/{user_id}/items",
    request_model=ItemStatsRequest,
    response_model=ItemStatsResult,
    retry_mode="enabled",
)
GET_ITEM_ANALYTICS = OperationSpec(
    name="ads.stats.analytics",
    method="POST",
    path="/stats/v2/accounts/{user_id}/items",
    request_model=ItemAnalyticsRequest,
    response_model=ItemAnalyticsResult,
    retry_mode="enabled",
)
GET_ACCOUNT_SPENDINGS = OperationSpec(
    name="ads.stats.spendings",
    method="POST",
    path="/stats/v2/accounts/{user_id}/spendings",
    request_model=SpendingsRequest,
    response_model=AccountSpendings,
    retry_mode="enabled",
)
GET_VAS_PRICES = OperationSpec(
    name="ads.vas.prices",
    method="POST",
    path="/core/v1/accounts/{user_id}/vas/prices",
    request_model=VasPricesRequest,
    response_model=VasPricesResult,
    retry_mode="enabled",
)
APPLY_ITEM_VAS: OperationSpec[object] = OperationSpec(
    name="ads.vas.apply_item_vas",
    method="PUT",
    path="/core/v1/accounts/{user_id}/items/{item_id}/vas",
    request_model=ApplyVasRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
APPLY_ITEM_VAS_PACKAGE: OperationSpec[object] = OperationSpec(
    name="ads.vas.apply_item_vas_package",
    method="PUT",
    path="/core/v2/accounts/{user_id}/items/{item_id}/vas_packages",
    request_model=ApplyVasPackageRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
APPLY_VAS_DIRECT: OperationSpec[object] = OperationSpec(
    name="ads.vas.apply_direct",
    method="PUT",
    path="/core/v2/items/{item_id}/vas/",
    request_model=ApplyVasDirectRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
GET_AUTOLOAD_PROFILE = OperationSpec(
    name="ads.autoload.get_profile",
    method="GET",
    path="/autoload/v2/profile",
    response_model=AutoloadProfileSettings,
)
SAVE_AUTOLOAD_PROFILE = OperationSpec(
    name="ads.autoload.save_profile",
    method="POST",
    path="/autoload/v2/profile",
    request_model=AutoloadProfileUpdateRequest,
    response_model=AdsActionResult,
    retry_mode="enabled",
)
UPLOAD_BY_URL = OperationSpec(
    name="ads.autoload.upload_by_url",
    method="POST",
    path="/autoload/v1/upload",
    request_model=UploadByUrlRequest,
    response_model=UploadResult,
    retry_mode="enabled",
)
GET_AUTOLOAD_NODE_FIELDS = OperationSpec(
    name="ads.autoload.get_node_fields",
    method="GET",
    path="/autoload/v1/user-docs/node/{node_slug}/fields",
    response_model=AutoloadFieldsResult,
)
GET_AUTOLOAD_TREE = OperationSpec(
    name="ads.autoload.get_tree",
    method="GET",
    path="/autoload/v1/user-docs/tree",
    response_model=AutoloadTreeResult,
)
GET_AD_IDS_BY_AVITO_IDS = OperationSpec(
    name="ads.autoload.get_ad_ids_by_avito_ids",
    method="GET",
    path="/autoload/v2/items/ad_ids",
    response_model=IdMappingResult,
)
GET_AVITO_IDS_BY_AD_IDS = OperationSpec(
    name="ads.autoload.get_avito_ids_by_ad_ids",
    method="GET",
    path="/autoload/v2/items/avito_ids",
    response_model=IdMappingResult,
)
LIST_AUTOLOAD_REPORTS = OperationSpec(
    name="ads.autoload.list_reports",
    method="GET",
    path="/autoload/v2/reports",
    response_model=AutoloadReportsResult,
)
GET_AUTOLOAD_ITEMS_INFO = OperationSpec(
    name="ads.autoload.get_items_info",
    method="GET",
    path="/autoload/v2/reports/items",
    response_model=AutoloadReportItemsResult,
)
GET_AUTOLOAD_REPORT = OperationSpec(
    name="ads.autoload.get_report",
    method="GET",
    path="/autoload/v3/reports/{report_id}",
    response_model=AutoloadReportDetails,
)
GET_AUTOLOAD_LAST_COMPLETED_REPORT = OperationSpec(
    name="ads.autoload.get_last_completed_report",
    method="GET",
    path="/autoload/v3/reports/last_completed_report",
    response_model=AutoloadReportDetails,
)
GET_AUTOLOAD_REPORT_ITEMS = OperationSpec(
    name="ads.autoload.get_report_items",
    method="GET",
    path="/autoload/v2/reports/{report_id}/items",
    response_model=AutoloadReportItemsResult,
)
GET_AUTOLOAD_REPORT_FEES = OperationSpec(
    name="ads.autoload.get_report_fees",
    method="GET",
    path="/autoload/v2/reports/{report_id}/items/fees",
    response_model=AutoloadFeesResult,
)
GET_ARCHIVE_PROFILE = OperationSpec(
    name="ads.autoload_archive.get_profile",
    method="GET",
    path="/autoload/v1/profile",
    response_model=AutoloadProfileSettings,
)
SAVE_ARCHIVE_PROFILE = OperationSpec(
    name="ads.autoload_archive.save_profile",
    method="POST",
    path="/autoload/v1/profile",
    request_model=AutoloadProfileUpdateRequest,
    response_model=AdsActionResult,
    retry_mode="enabled",
)
GET_ARCHIVE_LAST_COMPLETED_REPORT = OperationSpec(
    name="ads.autoload_archive.get_last_completed_report",
    method="GET",
    path="/autoload/v2/reports/last_completed_report",
    response_model=LegacyAutoloadReport,
)
GET_ARCHIVE_REPORT = OperationSpec(
    name="ads.autoload_archive.get_report",
    method="GET",
    path="/autoload/v2/reports/{report_id}",
    response_model=LegacyAutoloadReport,
)
