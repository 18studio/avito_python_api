"""Operation specs for orders domain."""

from __future__ import annotations

from avito.core import BinaryResponse, OperationSpec
from avito.orders.models import (
    AddSortingCentersRequest,
    AddTariffV2Request,
    AddTerminalsRequest,
    CancelParcelRequest,
    CancelSandboxParcelRequest,
    ChangeParcelRequest,
    CourierRangesResult,
    CustomAreaScheduleRequest,
    DeliveryAnnouncementRequest,
    DeliveryAnnouncementTrackRequest,
    DeliveryCancelAnnouncementRequest,
    DeliveryEntityResult,
    DeliveryParcelIdsRequest,
    DeliveryParcelRequest,
    DeliveryParcelResultRequest,
    DeliverySandboxAnnouncementRequest,
    DeliverySortingCentersResult,
    DeliveryTaskInfo,
    DeliveryTrackingRequest,
    GetChangeParcelInfoRequest,
    GetRegisteredParcelIdRequest,
    GetSandboxParcelInfoRequest,
    LabelTaskResult,
    OrderAcceptReturnRequest,
    OrderActionResult,
    OrderApplyTransitionRequest,
    OrderCncDetailsRequest,
    OrderConfirmationCodeRequest,
    OrderCourierRangeRequest,
    OrderLabelsRequest,
    OrderMarkingsRequest,
    OrdersResult,
    OrderTrackingNumberRequest,
    ProhibitOrderAcceptanceRequest,
    SandboxAreasRequest,
    SandboxCancelAnnouncementRequest,
    SandboxConfirmationCodeRequest,
    SandboxCreateAnnouncementRequest,
    SandboxGetAnnouncementEventRequest,
    SandboxParcelRequest,
    SetOrderPropertiesRequest,
    SetOrderRealAddressRequest,
    StockInfoRequest,
    StockInfoResult,
    StockUpdateRequest,
    StockUpdateResult,
    TaggedSortingCentersRequest,
    UpdateTermsRequest,
)

LIST_ORDERS = OperationSpec(
    name="orders.list_orders",
    method="GET",
    path="/order-management/1/orders",
    response_model=OrdersResult,
)
UPDATE_MARKINGS = OperationSpec(
    name="orders.update_markings",
    method="POST",
    path="/order-management/1/markings",
    request_model=OrderMarkingsRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
ACCEPT_RETURN_ORDER = OperationSpec(
    name="orders.accept_return_order",
    method="POST",
    path="/order-management/1/order/acceptReturnOrder",
    request_model=OrderAcceptReturnRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
APPLY_TRANSITION = OperationSpec(
    name="orders.apply_transition",
    method="POST",
    path="/order-management/1/order/applyTransition",
    request_model=OrderApplyTransitionRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
CHECK_CONFIRMATION_CODE = OperationSpec(
    name="orders.check_confirmation_code",
    method="POST",
    path="/order-management/1/order/checkConfirmationCode",
    request_model=OrderConfirmationCodeRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
SET_CNC_DETAILS = OperationSpec(
    name="orders.set_cnc_details",
    method="POST",
    path="/order-management/1/order/cncSetDetails",
    request_model=OrderCncDetailsRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
GET_COURIER_DELIVERY_RANGE = OperationSpec(
    name="orders.get_courier_delivery_range",
    method="GET",
    path="/order-management/1/order/getCourierDeliveryRange",
    response_model=CourierRangesResult,
)
SET_COURIER_DELIVERY_RANGE = OperationSpec(
    name="orders.set_courier_delivery_range",
    method="POST",
    path="/order-management/1/order/setCourierDeliveryRange",
    request_model=OrderCourierRangeRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
SET_TRACKING_NUMBER = OperationSpec(
    name="orders.set_tracking_number",
    method="POST",
    path="/order-management/1/order/setTrackingNumber",
    request_model=OrderTrackingNumberRequest,
    response_model=OrderActionResult,
    retry_mode="enabled",
)
CREATE_LABELS = OperationSpec(
    name="orders.labels.create",
    method="POST",
    path="/order-management/1/orders/labels",
    request_model=OrderLabelsRequest,
    response_model=LabelTaskResult,
    retry_mode="enabled",
)
CREATE_LABELS_EXTENDED = OperationSpec(
    name="orders.labels.create_extended",
    method="POST",
    path="/order-management/1/orders/labels/extended",
    request_model=OrderLabelsRequest,
    response_model=LabelTaskResult,
    retry_mode="enabled",
)
DOWNLOAD_LABEL: OperationSpec[BinaryResponse] = OperationSpec(
    name="orders.labels.download",
    method="GET",
    path="/order-management/1/orders/labels/{taskID}/download",
    response_kind="binary",
)
DELIVERY_CREATE_ANNOUNCEMENT = OperationSpec(
    name="orders.delivery.create_announcement",
    method="POST",
    path="/createAnnouncement",
    request_model=DeliveryAnnouncementRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
DELIVERY_CANCEL_ANNOUNCEMENT = OperationSpec(
    name="orders.delivery.cancel_announcement",
    method="POST",
    path="/cancelAnnouncement",
    request_model=DeliveryCancelAnnouncementRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
DELIVERY_CREATE_PARCEL = OperationSpec(
    name="orders.delivery.create_parcel",
    method="POST",
    path="/createParcel",
    request_model=DeliveryParcelRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
DELIVERY_UPDATE_CHANGE_PARCELS = OperationSpec(
    name="orders.delivery.update_change_parcels",
    method="POST",
    path="/sandbox/changeParcels",
    request_model=DeliveryParcelIdsRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
DELIVERY_CHANGE_PARCEL_RESULT = OperationSpec(
    name="orders.delivery.change_parcel_result",
    method="POST",
    path="/delivery/order/changeParcelResult",
    request_model=DeliveryParcelResultRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CREATE_ANNOUNCEMENT = OperationSpec(
    name="orders.sandbox.create_announcement",
    method="POST",
    path="/delivery-sandbox/announcements/create",
    request_model=DeliverySandboxAnnouncementRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_TRACK_ANNOUNCEMENT = OperationSpec(
    name="orders.sandbox.track_announcement",
    method="POST",
    path="/delivery-sandbox/announcements/track",
    request_model=DeliveryAnnouncementTrackRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_UPDATE_CUSTOM_AREA_SCHEDULE = OperationSpec(
    name="orders.sandbox.update_custom_area_schedule",
    method="POST",
    path="/delivery-sandbox/areas/custom-schedule",
    request_model=CustomAreaScheduleRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CANCEL_PARCEL = OperationSpec(
    name="orders.sandbox.cancel_parcel",
    method="POST",
    path="/delivery-sandbox/cancelParcel",
    request_model=CancelParcelRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CHECK_CONFIRMATION_CODE = OperationSpec(
    name="orders.sandbox.check_confirmation_code",
    method="POST",
    path="/delivery-sandbox/order/checkConfirmationCode",
    request_model=SandboxConfirmationCodeRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_SET_ORDER_PROPERTIES = OperationSpec(
    name="orders.sandbox.set_order_properties",
    method="POST",
    path="/delivery-sandbox/order/properties",
    request_model=SetOrderPropertiesRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_SET_ORDER_REAL_ADDRESS = OperationSpec(
    name="orders.sandbox.set_order_real_address",
    method="POST",
    path="/delivery-sandbox/order/realAddress",
    request_model=SetOrderRealAddressRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_TRACKING = OperationSpec(
    name="orders.sandbox.tracking",
    method="POST",
    path="/delivery-sandbox/order/tracking",
    request_model=DeliveryTrackingRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_PROHIBIT_ORDER_ACCEPTANCE = OperationSpec(
    name="orders.sandbox.prohibit_order_acceptance",
    method="POST",
    path="/delivery-sandbox/prohibitOrderAcceptance",
    request_model=ProhibitOrderAcceptanceRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_LIST_SORTING_CENTER = OperationSpec(
    name="orders.sandbox.list_sorting_center",
    method="GET",
    path="/delivery-sandbox/sorting-center",
    response_model=DeliverySortingCentersResult,
)
SANDBOX_ADD_SORTING_CENTER = OperationSpec(
    name="orders.sandbox.add_sorting_center",
    method="POST",
    path="/delivery-sandbox/tariffs/sorting-center",
    request_model=AddSortingCentersRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_ADD_AREAS = OperationSpec(
    name="orders.sandbox.add_areas",
    method="POST",
    path="/delivery-sandbox/tariffs/{tariff_id}/areas",
    request_model=SandboxAreasRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_ADD_TAGS_TO_SORTING_CENTER = OperationSpec(
    name="orders.sandbox.add_tags_to_sorting_center",
    method="POST",
    path="/delivery-sandbox/tariffs/{tariff_id}/tagged-sorting-centers",
    request_model=TaggedSortingCentersRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_ADD_TERMINALS = OperationSpec(
    name="orders.sandbox.add_terminals",
    method="POST",
    path="/delivery-sandbox/tariffs/{tariff_id}/terminals",
    request_model=AddTerminalsRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_UPDATE_TERMS = OperationSpec(
    name="orders.sandbox.update_terms",
    method="POST",
    path="/delivery-sandbox/tariffs/{tariff_id}/terms",
    request_model=UpdateTermsRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_ADD_TARIFF = OperationSpec(
    name="orders.sandbox.add_tariff",
    method="POST",
    path="/delivery-sandbox/tariffsV2",
    request_model=AddTariffV2Request,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CREATE_PARCEL = OperationSpec(
    name="orders.sandbox.create_parcel",
    method="POST",
    path="/delivery-sandbox/v2/createParcel",
    request_model=SandboxParcelRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CANCEL_SANDBOX_ANNOUNCEMENT = OperationSpec(
    name="orders.sandbox.cancel_sandbox_announcement",
    method="POST",
    path="/delivery-sandbox/v1/cancelAnnouncement",
    request_model=SandboxCancelAnnouncementRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CANCEL_SANDBOX_PARCEL = OperationSpec(
    name="orders.sandbox.cancel_sandbox_parcel",
    method="POST",
    path="/delivery-sandbox/v1/cancelParcel",
    request_model=CancelSandboxParcelRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CHANGE_SANDBOX_PARCEL = OperationSpec(
    name="orders.sandbox.change_sandbox_parcel",
    method="POST",
    path="/delivery-sandbox/v1/changeParcel",
    request_model=ChangeParcelRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_CREATE_SANDBOX_ANNOUNCEMENT = OperationSpec(
    name="orders.sandbox.create_sandbox_announcement",
    method="POST",
    path="/delivery-sandbox/v1/createAnnouncement",
    request_model=SandboxCreateAnnouncementRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_GET_ANNOUNCEMENT_EVENT = OperationSpec(
    name="orders.sandbox.get_sandbox_announcement_event",
    method="POST",
    path="/delivery-sandbox/v1/getAnnouncementEvent",
    request_model=SandboxGetAnnouncementEventRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_GET_CHANGE_PARCEL_INFO = OperationSpec(
    name="orders.sandbox.get_sandbox_change_parcel_info",
    method="POST",
    path="/delivery-sandbox/v1/getChangeParcelInfo",
    request_model=GetChangeParcelInfoRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_GET_PARCEL_INFO = OperationSpec(
    name="orders.sandbox.get_sandbox_parcel_info",
    method="POST",
    path="/delivery-sandbox/v1/getParcelInfo",
    request_model=GetSandboxParcelInfoRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
SANDBOX_GET_REGISTERED_PARCEL_ID = OperationSpec(
    name="orders.sandbox.get_sandbox_registered_parcel_id",
    method="POST",
    path="/delivery-sandbox/v1/getRegisteredParcelID",
    request_model=GetRegisteredParcelIdRequest,
    response_model=DeliveryEntityResult,
    retry_mode="enabled",
)
GET_DELIVERY_TASK = OperationSpec(
    name="orders.delivery_task.get_task",
    method="GET",
    path="/delivery-sandbox/tasks/{task_id}",
    response_model=DeliveryTaskInfo,
    retry_mode="enabled",
)
GET_STOCK_INFO = OperationSpec(
    name="orders.stock.get_info",
    method="POST",
    path="/stock-management/1/info",
    request_model=StockInfoRequest,
    response_model=StockInfoResult,
    retry_mode="enabled",
)
UPDATE_STOCKS = OperationSpec(
    name="orders.stock.update_stocks",
    method="PUT",
    path="/stock-management/1/stocks",
    request_model=StockUpdateRequest,
    response_model=StockUpdateResult,
    retry_mode="enabled",
)
