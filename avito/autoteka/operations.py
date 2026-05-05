"""Operation specs for autoteka domain."""

from __future__ import annotations

from avito.autoteka.models import (
    AutotekaLeadsResult,
    AutotekaPackageInfo,
    AutotekaPreviewInfo,
    AutotekaReportInfo,
    AutotekaReportsResult,
    AutotekaScoringInfo,
    AutotekaSpecificationInfo,
    AutotekaTeaserInfo,
    AutotekaValuationInfo,
    CatalogResolveRequest,
    CatalogResolveResult,
    ExternalItemPreviewRequest,
    ItemIdRequest,
    LeadsRequest,
    MonitoringBucketRequest,
    MonitoringBucketResult,
    MonitoringEventsQuery,
    MonitoringEventsResult,
    PlateNumberRequest,
    PreviewReportRequest,
    RegNumberRequest,
    TeaserCreateRequest,
    ValuationBySpecificationRequest,
    VehicleIdRequest,
    VinRequest,
)
from avito.core import OperationSpec

CATALOG_RESOLVE = OperationSpec(
    name="autoteka.catalog.resolve",
    method="POST",
    path="/autoteka/v1/catalogs/resolve",
    request_model=CatalogResolveRequest,
    response_model=CatalogResolveResult,
    requires_auth=False,
    retry_mode="enabled",
)
GET_LEADS = OperationSpec(
    name="autoteka.leads.get",
    method="POST",
    path="/autoteka/v1/get-leads/",
    request_model=LeadsRequest,
    response_model=AutotekaLeadsResult,
    requires_auth=False,
    retry_mode="enabled",
)
CREATE_PREVIEW_BY_VIN = OperationSpec(
    name="autoteka.preview.create_by_vin",
    method="POST",
    path="/autoteka/v1/previews",
    request_model=VinRequest,
    response_model=AutotekaPreviewInfo,
    requires_auth=False,
)
CREATE_PREVIEW_BY_EXTERNAL_ITEM = OperationSpec(
    name="autoteka.preview.create_by_external_item",
    method="POST",
    path="/autoteka/v1/request-preview-by-external-item",
    request_model=ExternalItemPreviewRequest,
    response_model=AutotekaPreviewInfo,
    requires_auth=False,
)
CREATE_PREVIEW_BY_ITEM_ID = OperationSpec(
    name="autoteka.preview.create_by_item_id",
    method="POST",
    path="/autoteka/v1/request-preview-by-item-id",
    request_model=ItemIdRequest,
    response_model=AutotekaPreviewInfo,
    requires_auth=False,
)
CREATE_PREVIEW_BY_REG_NUMBER = OperationSpec(
    name="autoteka.preview.create_by_reg_number",
    method="POST",
    path="/autoteka/v1/request-preview-by-regnumber",
    request_model=RegNumberRequest,
    response_model=AutotekaPreviewInfo,
    requires_auth=False,
)
GET_PREVIEW = OperationSpec(
    name="autoteka.preview.get",
    method="GET",
    path="/autoteka/v1/previews/{previewId}",
    response_model=AutotekaPreviewInfo,
    requires_auth=False,
)
GET_ACTIVE_PACKAGE = OperationSpec(
    name="autoteka.report.get_active_package",
    method="GET",
    path="/autoteka/v1/packages/active_package",
    response_model=AutotekaPackageInfo,
    requires_auth=False,
)
CREATE_REPORT = OperationSpec(
    name="autoteka.report.create",
    method="POST",
    path="/autoteka/v1/reports",
    request_model=PreviewReportRequest,
    response_model=AutotekaReportInfo,
    requires_auth=False,
)
CREATE_REPORT_BY_VEHICLE_ID = OperationSpec(
    name="autoteka.report.create_by_vehicle_id",
    method="POST",
    path="/autoteka/v1/reports-by-vehicle-id",
    request_model=VehicleIdRequest,
    response_model=AutotekaReportInfo,
    requires_auth=False,
)
LIST_REPORTS = OperationSpec(
    name="autoteka.report.list",
    method="GET",
    path="/autoteka/v1/reports/list/",
    response_model=AutotekaReportsResult,
    requires_auth=False,
)
GET_REPORT = OperationSpec(
    name="autoteka.report.get",
    method="GET",
    path="/autoteka/v1/reports/{report_id}",
    response_model=AutotekaReportInfo,
    requires_auth=False,
)
CREATE_SYNC_REPORT_BY_REG_NUMBER = OperationSpec(
    name="autoteka.report.create_sync_by_reg_number",
    method="POST",
    path="/autoteka/v1/sync/create-by-regnumber",
    request_model=RegNumberRequest,
    response_model=AutotekaReportInfo,
    requires_auth=False,
)
CREATE_SYNC_REPORT_BY_VIN = OperationSpec(
    name="autoteka.report.create_sync_by_vin",
    method="POST",
    path="/autoteka/v1/sync/create-by-vin",
    request_model=VinRequest,
    response_model=AutotekaReportInfo,
    requires_auth=False,
)
ADD_MONITORING_BUCKET = OperationSpec(
    name="autoteka.monitoring.bucket_add",
    method="POST",
    path="/autoteka/v1/monitoring/bucket/add",
    request_model=MonitoringBucketRequest,
    response_model=MonitoringBucketResult,
    requires_auth=False,
)
DELETE_MONITORING_BUCKET = OperationSpec(
    name="autoteka.monitoring.bucket_delete",
    method="POST",
    path="/autoteka/v1/monitoring/bucket/delete",
    response_model=MonitoringBucketResult,
    requires_auth=False,
)
REMOVE_MONITORING_BUCKET = OperationSpec(
    name="autoteka.monitoring.bucket_remove",
    method="POST",
    path="/autoteka/v1/monitoring/bucket/remove",
    request_model=MonitoringBucketRequest,
    response_model=MonitoringBucketResult,
    requires_auth=False,
)
GET_MONITORING_REG_ACTIONS = OperationSpec(
    name="autoteka.monitoring.get_reg_actions",
    method="GET",
    path="/autoteka/v1/monitoring/get-reg-actions/",
    query_model=MonitoringEventsQuery,
    response_model=MonitoringEventsResult,
    requires_auth=False,
)
CREATE_SCORING_BY_VEHICLE_ID = OperationSpec(
    name="autoteka.scoring.create_by_vehicle_id",
    method="POST",
    path="/autoteka/v1/scoring/by-vehicle-id",
    request_model=VehicleIdRequest,
    response_model=AutotekaScoringInfo,
    requires_auth=False,
)
GET_SCORING_BY_ID = OperationSpec(
    name="autoteka.scoring.get_by_id",
    method="GET",
    path="/autoteka/v1/scoring/{scoring_id}",
    response_model=AutotekaScoringInfo,
    requires_auth=False,
)
CREATE_SPECIFICATION_BY_PLATE_NUMBER = OperationSpec(
    name="autoteka.specification.create_by_plate_number",
    method="POST",
    path="/autoteka/v1/specifications/by-plate-number",
    request_model=PlateNumberRequest,
    response_model=AutotekaSpecificationInfo,
    requires_auth=False,
)
CREATE_SPECIFICATION_BY_VEHICLE_ID = OperationSpec(
    name="autoteka.specification.create_by_vehicle_id",
    method="POST",
    path="/autoteka/v1/specifications/by-vehicle-id",
    request_model=VehicleIdRequest,
    response_model=AutotekaSpecificationInfo,
    requires_auth=False,
)
GET_SPECIFICATION_BY_ID = OperationSpec(
    name="autoteka.specification.get_by_id",
    method="GET",
    path="/autoteka/v1/specifications/specification/{specificationID}",
    response_model=AutotekaSpecificationInfo,
    requires_auth=False,
)
CREATE_TEASER = OperationSpec(
    name="autoteka.teaser.create",
    method="POST",
    path="/autoteka/v1/teasers",
    request_model=TeaserCreateRequest,
    response_model=AutotekaTeaserInfo,
    requires_auth=False,
)
GET_TEASER = OperationSpec(
    name="autoteka.teaser.get",
    method="GET",
    path="/autoteka/v1/teasers/{teaser_id}",
    response_model=AutotekaTeaserInfo,
    requires_auth=False,
)
GET_VALUATION_BY_SPECIFICATION = OperationSpec(
    name="autoteka.valuation.by_specification",
    method="POST",
    path="/autoteka/v1/valuation/by-specification",
    request_model=ValuationBySpecificationRequest,
    response_model=AutotekaValuationInfo,
    requires_auth=False,
    retry_mode="enabled",
)

__all__ = (
    "ADD_MONITORING_BUCKET",
    "CATALOG_RESOLVE",
    "CREATE_PREVIEW_BY_EXTERNAL_ITEM",
    "CREATE_PREVIEW_BY_ITEM_ID",
    "CREATE_PREVIEW_BY_REG_NUMBER",
    "CREATE_PREVIEW_BY_VIN",
    "CREATE_REPORT",
    "CREATE_REPORT_BY_VEHICLE_ID",
    "CREATE_SCORING_BY_VEHICLE_ID",
    "CREATE_SPECIFICATION_BY_PLATE_NUMBER",
    "CREATE_SPECIFICATION_BY_VEHICLE_ID",
    "CREATE_SYNC_REPORT_BY_REG_NUMBER",
    "CREATE_SYNC_REPORT_BY_VIN",
    "CREATE_TEASER",
    "DELETE_MONITORING_BUCKET",
    "GET_ACTIVE_PACKAGE",
    "GET_LEADS",
    "GET_MONITORING_REG_ACTIONS",
    "GET_PREVIEW",
    "GET_REPORT",
    "GET_SCORING_BY_ID",
    "GET_SPECIFICATION_BY_ID",
    "GET_TEASER",
    "GET_VALUATION_BY_SPECIFICATION",
    "LIST_REPORTS",
    "REMOVE_MONITORING_BUCKET",
)
