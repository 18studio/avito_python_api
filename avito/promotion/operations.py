"""Operation specs for promotion domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.promotion.models import (
    AutostrategyBudget,
    AutostrategyStat,
    BbipForecastsResult,
    BbipSuggestsResult,
    CampaignActionResult,
    CampaignDetailsResult,
    CampaignsResult,
    CancelTrxPromotionRequest,
    CpaAuctionBidsResult,
    CreateAutostrategyBudgetRequest,
    CreateAutostrategyCampaignRequest,
    CreateBbipForecastsRequest,
    CreateBbipOrderRequest,
    CreateBbipSuggestsRequest,
    CreateItemBidsRequest,
    CreateTrxPromotionApplyRequest,
    DeletePromotionRequest,
    GetAutostrategyCampaignInfoRequest,
    GetAutostrategyStatRequest,
    GetPromotionOrderStatusRequest,
    GetPromotionsByItemIdsRequest,
    GetTrxCommissionsRequest,
    ListAutostrategyCampaignsRequest,
    ListPromotionOrdersRequest,
    ListPromotionServicesRequest,
    PromotionActionPayload,
    PromotionOrdersResult,
    PromotionOrderStatusResult,
    PromotionServiceDictionary,
    PromotionServicesResult,
    StopAutostrategyCampaignRequest,
    TargetActionGetBidsResult,
    TargetActionPromotionsByItemIdsResult,
    TrxCommissionsResult,
    UpdateAutoBidRequest,
    UpdateAutostrategyCampaignRequest,
    UpdateManualBidRequest,
)

GET_SERVICE_DICTIONARY = OperationSpec(
    name="promotion.get_service_dictionary",
    method="POST",
    path="/promotion/v1/items/services/dict",
    response_model=PromotionServiceDictionary,
    retry_mode="enabled",
)
LIST_SERVICES = OperationSpec(
    name="promotion.list_services",
    method="POST",
    path="/promotion/v1/items/services/get",
    request_model=ListPromotionServicesRequest,
    response_model=PromotionServicesResult,
    retry_mode="enabled",
)
LIST_ORDERS = OperationSpec(
    name="promotion.list_orders",
    method="POST",
    path="/promotion/v1/items/services/orders/get",
    request_model=ListPromotionOrdersRequest,
    response_model=PromotionOrdersResult,
    retry_mode="enabled",
)
GET_ORDER_STATUS = OperationSpec(
    name="promotion.get_order_status",
    method="POST",
    path="/promotion/v1/items/services/orders/status",
    request_model=GetPromotionOrderStatusRequest,
    response_model=PromotionOrderStatusResult,
    retry_mode="enabled",
)
GET_BBIP_FORECASTS = OperationSpec(
    name="promotion.bbip.get_forecasts",
    method="POST",
    path="/promotion/v1/items/services/bbip/forecasts/get",
    request_model=CreateBbipForecastsRequest,
    response_model=BbipForecastsResult,
    retry_mode="enabled",
)
CREATE_BBIP_ORDER: OperationSpec[object] = OperationSpec(
    name="promotion.bbip.create_order",
    method="PUT",
    path="/promotion/v1/items/services/bbip/orders/create",
    request_model=CreateBbipOrderRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
GET_BBIP_SUGGESTS = OperationSpec(
    name="promotion.bbip.get_suggests",
    method="POST",
    path="/promotion/v1/items/services/bbip/suggests/get",
    request_model=CreateBbipSuggestsRequest,
    response_model=BbipSuggestsResult,
    retry_mode="enabled",
)
APPLY_TRX: OperationSpec[object] = OperationSpec(
    name="promotion.trx.apply",
    method="POST",
    path="/trx-promo/1/apply",
    request_model=CreateTrxPromotionApplyRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
CANCEL_TRX: OperationSpec[object] = OperationSpec(
    name="promotion.trx.cancel",
    method="POST",
    path="/trx-promo/1/cancel",
    request_model=CancelTrxPromotionRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
GET_TRX_COMMISSIONS = OperationSpec(
    name="promotion.trx.get_commissions",
    method="GET",
    path="/trx-promo/1/commissions",
    request_model=GetTrxCommissionsRequest,
    response_model=TrxCommissionsResult,
)
GET_CPA_AUCTION_BIDS = OperationSpec(
    name="promotion.cpa_auction.get_user_bids",
    method="GET",
    path="/auction/1/bids",
    response_model=CpaAuctionBidsResult,
)
CREATE_CPA_AUCTION_BIDS: OperationSpec[object] = OperationSpec(
    name="promotion.cpa_auction.create_item_bids",
    method="POST",
    path="/auction/1/bids",
    request_model=CreateItemBidsRequest,
    retry_mode="enabled",
)
GET_TARGET_ACTION_BIDS = OperationSpec(
    name="promotion.target_action.get_bids",
    method="GET",
    path="/cpxpromo/1/getBids/{itemId}",
    response_model=TargetActionGetBidsResult,
)
GET_TARGET_ACTION_PROMOTIONS = OperationSpec(
    name="promotion.target_action.get_promotions_by_item_ids",
    method="POST",
    path="/cpxpromo/1/getPromotionsByItemIds",
    request_model=GetPromotionsByItemIdsRequest,
    response_model=TargetActionPromotionsByItemIdsResult,
    retry_mode="enabled",
)
DELETE_TARGET_ACTION_PROMOTION: OperationSpec[object] = OperationSpec(
    name="promotion.target_action.delete_promotion",
    method="POST",
    path="/cpxpromo/1/remove",
    request_model=DeletePromotionRequest,
    response_model=PromotionActionPayload,
    retry_mode="enabled",
)
UPDATE_TARGET_ACTION_AUTO: OperationSpec[object] = OperationSpec(
    name="promotion.target_action.update_auto_bid",
    method="POST",
    path="/cpxpromo/1/setAuto",
    request_model=UpdateAutoBidRequest,
    retry_mode="enabled",
)
UPDATE_TARGET_ACTION_MANUAL: OperationSpec[object] = OperationSpec(
    name="promotion.target_action.update_manual_bid",
    method="POST",
    path="/cpxpromo/1/setManual",
    request_model=UpdateManualBidRequest,
    retry_mode="enabled",
)
CREATE_AUTOSTRATEGY_BUDGET = OperationSpec(
    name="promotion.autostrategy.create_budget",
    method="POST",
    path="/autostrategy/v1/budget",
    request_model=CreateAutostrategyBudgetRequest,
    response_model=AutostrategyBudget,
    retry_mode="enabled",
)
CREATE_AUTOSTRATEGY_CAMPAIGN = OperationSpec(
    name="promotion.autostrategy.create_campaign",
    method="POST",
    path="/autostrategy/v1/campaign/create",
    request_model=CreateAutostrategyCampaignRequest,
    response_model=CampaignActionResult,
    retry_mode="enabled",
)
UPDATE_AUTOSTRATEGY_CAMPAIGN = OperationSpec(
    name="promotion.autostrategy.edit_campaign",
    method="POST",
    path="/autostrategy/v1/campaign/edit",
    request_model=UpdateAutostrategyCampaignRequest,
    response_model=CampaignActionResult,
    retry_mode="enabled",
)
GET_AUTOSTRATEGY_CAMPAIGN = OperationSpec(
    name="promotion.autostrategy.get_campaign_info",
    method="POST",
    path="/autostrategy/v1/campaign/info",
    request_model=GetAutostrategyCampaignInfoRequest,
    response_model=CampaignDetailsResult,
    retry_mode="enabled",
)
DELETE_AUTOSTRATEGY_CAMPAIGN = OperationSpec(
    name="promotion.autostrategy.stop_campaign",
    method="POST",
    path="/autostrategy/v1/campaign/stop",
    request_model=StopAutostrategyCampaignRequest,
    response_model=CampaignActionResult,
    retry_mode="enabled",
)
LIST_AUTOSTRATEGY_CAMPAIGNS = OperationSpec(
    name="promotion.autostrategy.list_campaigns",
    method="POST",
    path="/autostrategy/v1/campaigns",
    request_model=ListAutostrategyCampaignsRequest,
    response_model=CampaignsResult,
    retry_mode="enabled",
)
GET_AUTOSTRATEGY_STAT = OperationSpec(
    name="promotion.autostrategy.get_stat",
    method="POST",
    path="/autostrategy/v1/stat",
    request_model=GetAutostrategyStatRequest,
    response_model=AutostrategyStat,
    retry_mode="enabled",
)

TRX_HEADERS = {
    "x-authenticated-userid": "7",
    "x-oauth-flow": "client_credentials",
}
