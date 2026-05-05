from __future__ import annotations

import json

import httpx
import pytest

from avito.core import ValidationError
from avito.orders import (
    DeliveryOrder,
    DeliveryTask,
    Order,
    OrderLabel,
    OrderTransition,
    SandboxDelivery,
    Stock,
)
from avito.orders.models import (
    StockUpdateEntry,
)
from tests.helpers.transport import make_transport


def test_order_management_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/order-management/1/orders":
            return httpx.Response(200, json={"orders": [{"id": "ord-1", "status": "new", "buyerInfo": {"fullName": "Иван"}}], "total": 1})
        if path == "/order-management/1/markings":
            assert payload == {"markings": [{"orderId": "ord-1", "markings": ["abc"]}]}
            return httpx.Response(200, json={"result": {"success": True, "orderId": "ord-1", "status": "marked"}})
        if path == "/order-management/1/order/applyTransition":
            return httpx.Response(200, json={"result": {"success": True, "orderId": "ord-1", "status": "confirmed"}})
        if path == "/order-management/1/order/checkConfirmationCode":
            return httpx.Response(200, json={"result": {"success": True, "orderId": "ord-1", "status": "code-valid"}})
        if path == "/order-management/1/order/getCourierDeliveryRange":
            return httpx.Response(200, json={"result": {"address": "Москва", "timeIntervals": [{"id": "int-1", "date": "2026-04-18", "startAt": "10:00", "endAt": "12:00"}]}})
        if path == "/order-management/1/order/setCourierDeliveryRange":
            return httpx.Response(200, json={"result": {"success": True, "status": "range-set"}})
        if path == "/order-management/1/order/setTrackingNumber":
            return httpx.Response(200, json={"result": {"success": True, "status": "tracking-set"}})
        return httpx.Response(200, json={"result": {"success": True, "status": "return-accepted"}})

    order = Order(make_transport(httpx.MockTransport(handler)))
    assert order.list().items[0].buyer_name == "Иван"
    assert order.update_markings(order_id="ord-1", codes=["abc"]).status == "marked"
    assert order.apply(order_id="ord-1", transition=OrderTransition.CONFIRM).status == "confirmed"
    assert order.check_confirmation_code(order_id="ord-1", code="1234").status == "code-valid"
    assert order.get_courier_delivery_range().items[0].interval_id == "int-1"
    assert order.set_courier_delivery_range(order_id="ord-1", interval_id="int-1").status == "range-set"
    assert order.update_tracking_number(order_id="ord-1", tracking_number="TRK-1").status == "tracking-set"
    assert order.accept_return_order(order_id="ord-1", postal_office_id="ops-1").status == "return-accepted"


def test_labels_delivery_and_stock_flows() -> None:
    pdf_bytes = b"%PDF-1.4 fake"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/order-management/1/orders/labels":
            return httpx.Response(200, json={"result": {"taskId": 42, "status": "created"}})
        if path == "/order-management/1/orders/labels/42/download":
            return httpx.Response(200, content=pdf_bytes, headers={"content-type": "application/pdf", "content-disposition": 'attachment; filename="label-42.pdf"'})
        if path == "/createAnnouncement":
            assert payload is not None
            assert payload["announcementID"] == "ord-1"
            assert "packages" in payload
            return httpx.Response(200, json={"data": {"taskId": 11, "status": "announcement-created"}})
        if path == "/createParcel":
            return httpx.Response(200, json={"data": {"parcelId": "par-1", "status": "parcel-created"}})
        if path == "/cancelAnnouncement":
            return httpx.Response(200, json={"data": {"status": "announcement-cancelled"}})
        if path == "/delivery/order/changeParcelResult":
            return httpx.Response(200, json={"data": {"status": "callback-accepted"}})
        if path == "/sandbox/changeParcels":
            return httpx.Response(200, json={"data": {"status": "parcels-updated"}})
        if path == "/delivery-sandbox/tasks/51":
            return httpx.Response(200, json={"data": {"taskId": 51, "status": "done"}})
        if path == "/stock-management/1/info":
            return httpx.Response(200, json={"stocks": [{"item_id": 123321, "quantity": 5, "is_multiple": True, "is_unlimited": False, "is_out_of_stock": False}]})
        if path == "/stock-management/1/stocks":
            return httpx.Response(200, json={"stocks": [{"item_id": 123321, "external_id": "AB123456", "success": True, "errors": []}]})
        return httpx.Response(200, json={"data": {"taskId": 51, "status": "done"}})

    transport = make_transport(httpx.MockTransport(handler))
    label = OrderLabel(transport, task_id="42")
    delivery = DeliveryOrder(transport)
    task = DeliveryTask(transport, task_id="51")
    stock = Stock(transport)

    assert label.create(order_ids=["ord-1"]).task_id == "42"
    assert label.download().binary.content == pdf_bytes
    assert delivery.create_announcement(order_id="ord-1").task_id == "11"
    assert delivery.create(order_id="ord-1", parcel_id="par-1").parcel_id == "par-1"
    assert delivery.delete(order_id="ord-1").status == "announcement-cancelled"
    assert delivery.create_change_parcel_result(parcel_id="par-1", result="ok").status == "callback-accepted"
    assert delivery.update_change_parcels(parcel_ids=["par-1"]).status == "parcels-updated"
    assert task.get().status == "done"
    assert stock.get(item_ids=[123321]).items[0].quantity == 5
    assert stock.update(stocks=[StockUpdateEntry(item_id=123321, quantity=7)]).items[0].success is True


def test_sandbox_delivery_rejects_invalid_event_dates_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    delivery = SandboxDelivery(make_transport(httpx.MockTransport(handler)))

    with pytest.raises(ValidationError, match="date"):
        delivery.tracking(
            order_id="ord-1",
            avito_status="CONFIRMED",
            avito_event_type="",
            provider_event_code="accepted",
            date="not-a-date",
            location="Москва",
        )


def test_order_apply_rejects_unknown_transition_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    order = Order(make_transport(httpx.MockTransport(handler)))

    with pytest.raises(ValidationError, match="transition"):
        order.apply(order_id="ord-1", transition="unknown")
