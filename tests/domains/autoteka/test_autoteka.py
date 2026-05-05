from __future__ import annotations

import json

import httpx

from avito.autoteka import (
    AutotekaMonitoring,
    AutotekaReport,
    AutotekaScoring,
    AutotekaValuation,
    AutotekaVehicle,
)
from tests.helpers.transport import make_transport


def test_autoteka_vehicle_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/autoteka/v1/catalogs/resolve":
            assert payload == {"fieldsValueIds": [{"id": 110000, "valueId": 1}]}
            return httpx.Response(
                200,
                json={
                    "result": {
                        "fields": [
                            {
                                "id": 110000,
                                "label": "Марка",
                                "dataType": "integer",
                                "values": [{"valueId": 1, "label": "Audi"}],
                            }
                        ]
                    }
                },
            )
        if path == "/autoteka/v1/get-leads/":
            return httpx.Response(
                200,
                json={
                    "pagination": {"lastId": 321},
                    "result": [
                        {
                            "id": 12,
                            "subscriptionId": 44,
                            "payload": {
                                "vin": "VIN-1",
                                "itemId": 901,
                                "brand": "Audi",
                                "model": "A4",
                            },
                        }
                    ],
                },
            )
        if path == "/autoteka/v1/previews":
            return httpx.Response(200, json={"result": {"preview": {"previewId": 77}}})
        if path == "/autoteka/v1/request-preview-by-item-id":
            return httpx.Response(200, json={"result": {"preview": {"previewId": 78}}})
        if path == "/autoteka/v1/request-preview-by-regnumber":
            return httpx.Response(200, json={"result": {"preview": {"previewId": 79}}})
        if path == "/autoteka/v1/request-preview-by-external-item":
            return httpx.Response(200, json={"result": {"preview": {"previewId": 80}}})
        if path == "/autoteka/v1/previews/77":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "preview": {
                            "previewId": 77,
                            "status": "success",
                            "vin": "VIN-1",
                            "regNumber": "A123AA77",
                        }
                    }
                },
            )
        if path == "/autoteka/v1/specifications/by-plate-number":
            return httpx.Response(200, json={"result": {"specification": {"specificationId": 501}}})
        if path == "/autoteka/v1/specifications/by-vehicle-id":
            return httpx.Response(200, json={"result": {"specification": {"specificationId": 502}}})
        if path == "/autoteka/v1/specifications/specification/501":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "specification": {
                            "specificationId": 501,
                            "status": "success",
                            "vehicleId": "VIN-1",
                        }
                    }
                },
            )
        if path == "/autoteka/v1/teasers":
            return httpx.Response(
                200, json={"result": {"teaser": {"teaserId": 601, "status": "processing"}}}
            )
        return httpx.Response(
            200,
            json={
                "teaserId": 601,
                "status": "success",
                "data": {"brand": "Audi", "model": "A4", "year": 2018},
            },
        )

    vehicle = AutotekaVehicle(make_transport(httpx.MockTransport(handler)), vehicle_id="77")

    assert vehicle.resolve_catalog(brand_id=1).items[0].values[0].label == "Audi"
    assert vehicle.get_leads(subscription_id=44, limit=1).last_id == 321
    assert vehicle.create_preview_by_vin(vin="VIN-1").preview_id == "77"
    assert vehicle.create_preview_by_item_id(item_id=901).preview_id == "78"
    assert vehicle.create_preview_by_reg_number(reg_number="A123AA77").preview_id == "79"
    assert (
        vehicle.create_preview_by_external_item(item_id="ext-1", site="cars.example").preview_id
        == "80"
    )
    assert vehicle.get_preview().vehicle_id == "VIN-1"
    assert (
        vehicle.create_specification_by_plate_number(plate_number="A123AA77").specification_id
        == "501"
    )
    assert vehicle.create_specification_by_vehicle_id(vehicle_id="VIN-1").specification_id == "502"
    assert vehicle.get_specification_by_id(specification_id="501").status == "success"
    assert vehicle.create_teaser(vehicle_id="VIN-1").teaser_id == "601"
    assert vehicle.get_teaser(teaser_id="601").brand == "Audi"


def test_autoteka_report_monitoring_scoring_and_valuation_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/autoteka/v1/packages/active_package":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "package": {
                            "createdTime": "2026-04-01",
                            "expireTime": "2026-05-01",
                            "reportsCnt": 100,
                            "reportsCntRemain": 77,
                        }
                    }
                },
            )
        if path == "/autoteka/v1/reports":
            return httpx.Response(
                200, json={"result": {"report": {"reportId": 701, "status": "processing"}}}
            )
        if path == "/autoteka/v1/reports-by-vehicle-id":
            return httpx.Response(
                200, json={"result": {"report": {"reportId": 702, "status": "processing"}}}
            )
        if path == "/autoteka/v1/reports/list/":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {"reportId": 701, "vin": "VIN-1", "createdAt": "2026-04-18 12:00:00"}
                    ]
                },
            )
        if path == "/autoteka/v1/reports/701":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "report": {
                            "reportId": 701,
                            "status": "success",
                            "webLink": "https://autoteka/web/701",
                            "pdfLink": "https://autoteka/pdf/701",
                            "data": {"vin": "VIN-1"},
                        }
                    }
                },
            )
        if path == "/autoteka/v1/sync/create-by-regnumber":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "report": {"reportId": 703, "status": "success", "data": {"vin": "VIN-1"}}
                    }
                },
            )
        if path == "/autoteka/v1/sync/create-by-vin":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "report": {"reportId": 704, "status": "success", "data": {"vin": "VIN-1"}}
                    }
                },
            )
        if path == "/autoteka/v1/monitoring/bucket/add":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "isOk": True,
                        "invalidVehicles": [{"vehicleID": "bad-vin", "description": "invalid"}],
                    }
                },
            )
        if path == "/autoteka/v1/monitoring/bucket/delete":
            return httpx.Response(200, json={"result": {"isOk": True}})
        if path == "/autoteka/v1/monitoring/bucket/remove":
            return httpx.Response(200, json={"result": {"isOk": True, "invalidVehicles": []}})
        if path == "/autoteka/v1/monitoring/get-reg-actions/":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "vin": "VIN-1",
                            "brand": "Audi",
                            "model": "A4",
                            "year": 2018,
                            "operationCode": 11,
                            "operationDateFrom": "2026-04-01T00:00:00+03:00",
                        }
                    ],
                    "pagination": {
                        "hasNext": True,
                        "nextCursor": "cursor-2",
                        "nextLink": "https://api.avito.ru/next",
                    },
                },
            )
        if path == "/autoteka/v1/scoring/by-vehicle-id":
            return httpx.Response(200, json={"result": {"scoring": {"scoringId": 801}}})
        if path == "/autoteka/v1/scoring/801":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "risksAssessment": {
                            "scoringId": 801,
                            "isCompleted": True,
                            "createdAt": 1713427200,
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "result": {
                    "status": "success",
                    "vehicleId": "VIN-1",
                    "brand": "Audi",
                    "model": "A4",
                    "year": 2018,
                    "ownersCount": "2",
                    "mileage": 30000,
                    "valuation": {"avgPriceWithCondition": 2100000, "avgMarketPrice": 2200000},
                }
            },
        )

    transport = make_transport(httpx.MockTransport(handler))
    report = AutotekaReport(transport, report_id="701")
    monitoring = AutotekaMonitoring(transport)
    scoring = AutotekaScoring(transport, scoring_id="801")
    valuation = AutotekaValuation(transport)

    assert report.get_active_package().reports_remaining == 77
    assert report.create_report(preview_id=77).report_id == "701"
    assert report.create_report_by_vehicle_id(vehicle_id="VIN-1").report_id == "702"
    assert report.list_reports().items[0].vehicle_id == "VIN-1"
    assert report.get_report().web_link == "https://autoteka/web/701"
    assert report.create_sync_report_by_reg_number(reg_number="A123AA77").status == "success"
    assert report.create_sync_report_by_vin(vin="VIN-1").report_id == "704"
    assert (
        monitoring.create_monitoring_bucket_add(vehicles=["VIN-1", "bad-vin"])
        .invalid_vehicles[0]
        .vehicle_id
        == "bad-vin"
    )
    assert monitoring.delete_bucket().success is True
    assert monitoring.remove_bucket(vehicles=["VIN-1"]).success is True
    assert monitoring.get_monitoring_reg_actions(limit=10).items[0].operation_code == 11
    assert scoring.create_scoring_by_vehicle_id(vehicle_id="VIN-1").scoring_id == "801"
    assert scoring.get_scoring_by_id().is_completed is True
    assert (
        valuation.get_valuation_by_specification(
            specification_id=501, mileage=30000
        ).avg_price_with_condition
        == 2100000
    )
