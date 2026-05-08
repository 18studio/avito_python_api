from __future__ import annotations

import httpx
import pytest

from avito.core import ValidationError
from avito.orders import (
    AsyncDeliveryOrder,
    AsyncDeliveryTask,
    AsyncOrder,
    AsyncOrderLabel,
    AsyncSandboxDelivery,
    AsyncStock,
    OrderTransition,
)
from avito.orders.models import StockUpdateEntry
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_order_management_flows() -> None:
    def update_markings(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"markings": [{"orderId": "ord-1", "markings": ["abc"]}]}
        assert request.headers["idempotency-key"] == "markings-key"
        return httpx.Response(
            200,
            json={"result": {"success": True, "orderId": "ord-1", "status": "marked"}},
        )

    fake = (
        AsyncFakeTransport()
        .add_json(
            "GET",
            "/order-management/1/orders",
            {
                "orders": [
                    {"id": "ord-1", "status": "new", "buyerInfo": {"fullName": "Иван"}}
                ],
                "total": 1,
            },
        )
        .add("POST", "/order-management/1/markings", update_markings)
        .add_json(
            "POST",
            "/order-management/1/order/applyTransition",
            {"result": {"success": True, "orderId": "ord-1", "status": "confirmed"}},
        )
        .add_json(
            "POST",
            "/order-management/1/order/checkConfirmationCode",
            {"result": {"success": True, "orderId": "ord-1", "status": "code-valid"}},
        )
        .add_json(
            "GET",
            "/order-management/1/order/getCourierDeliveryRange",
            {
                "result": {
                    "address": "Москва",
                    "timeIntervals": [
                        {
                            "id": "int-1",
                            "date": "2026-04-18",
                            "startAt": "10:00",
                            "endAt": "12:00",
                        }
                    ],
                }
            },
        )
        .add_json(
            "POST",
            "/order-management/1/order/setCourierDeliveryRange",
            {"result": {"success": True, "status": "range-set"}},
        )
        .add_json(
            "POST",
            "/order-management/1/order/setTrackingNumber",
            {"result": {"success": True, "status": "tracking-set"}},
        )
        .add_json(
            "POST",
            "/order-management/1/order/acceptReturnOrder",
            {"result": {"success": True, "status": "return-accepted"}},
        )
    )
    transport = fake.build()
    order = AsyncOrder(transport)

    assert (await order.list()).items[0].buyer_name == "Иван"
    assert (
        await order.update_markings(
            order_id="ord-1",
            codes=["abc"],
            idempotency_key="markings-key",
        )
    ).status == "marked"
    assert (await order.apply(order_id="ord-1", transition=OrderTransition.CONFIRM)).status == "confirmed"
    assert (await order.check_confirmation_code(order_id="ord-1", code="1234")).status == "code-valid"
    assert (await order.get_courier_delivery_range()).items[0].interval_id == "int-1"
    assert (await order.set_courier_delivery_range(order_id="ord-1", interval_id="int-1")).status == "range-set"
    assert (await order.update_tracking_number(order_id="ord-1", tracking_number="TRK-1")).status == "tracking-set"
    assert (await order.accept_return_order(order_id="ord-1", postal_office_id="ops-1")).status == "return-accepted"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_labels_delivery_and_stock_flows() -> None:
    pdf_bytes = b"%PDF-1.4 fake"

    def create_announcement(request: RecordedRequest) -> httpx.Response:
        assert request.json_body is not None
        assert request.json_body["announcementID"] == "ord-1"
        assert "packages" in request.json_body
        return httpx.Response(200, json={"data": {"taskId": 11, "status": "announcement-created"}})

    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/order-management/1/orders/labels",
            {"result": {"taskId": 42, "status": "created"}},
        )
        .add(
            "GET",
            "/order-management/1/orders/labels/42/download",
            httpx.Response(
                200,
                content=pdf_bytes,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="label-42.pdf"',
                },
            ),
        )
        .add("POST", "/createAnnouncement", create_announcement)
        .add_json("POST", "/createParcel", {"data": {"parcelId": "par-1", "status": "parcel-created"}})
        .add_json("POST", "/cancelAnnouncement", {"data": {"status": "announcement-cancelled"}})
        .add_json(
            "POST",
            "/delivery/order/changeParcelResult",
            {"data": {"status": "callback-accepted"}},
        )
        .add_json("POST", "/sandbox/changeParcels", {"data": {"status": "parcels-updated"}})
        .add_json("GET", "/delivery-sandbox/tasks/51", {"data": {"taskId": 51, "status": "done"}})
        .add_json(
            "POST",
            "/stock-management/1/info",
            {
                "stocks": [
                    {
                        "item_id": 123321,
                        "quantity": 5,
                        "is_multiple": True,
                        "is_unlimited": False,
                        "is_out_of_stock": False,
                    }
                ]
            },
        )
        .add_json(
            "PUT",
            "/stock-management/1/stocks",
            {"stocks": [{"item_id": 123321, "external_id": "AB123456", "success": True, "errors": []}]},
        )
    )
    transport = fake.build()
    label = AsyncOrderLabel(transport, task_id="42")
    delivery = AsyncDeliveryOrder(transport)
    task = AsyncDeliveryTask(transport, task_id="51")
    stock = AsyncStock(transport)

    assert (await label.create(order_ids=["ord-1"])).task_id == "42"
    assert (await label.download()).binary.content == pdf_bytes
    assert (await delivery.create_announcement(order_id="ord-1")).task_id == "11"
    assert (await delivery.create(order_id="ord-1", parcel_id="par-1")).parcel_id == "par-1"
    assert (await delivery.delete(order_id="ord-1")).status == "announcement-cancelled"
    assert (await delivery.create_change_parcel_result(parcel_id="par-1", result="ok")).status == "callback-accepted"
    assert (await delivery.update_change_parcels(parcel_ids=["par-1"])).status == "parcels-updated"
    assert (await task.get()).status == "done"
    assert (await stock.get(item_ids=[123321])).items[0].quantity == 5
    assert (await stock.update(stocks=[StockUpdateEntry(item_id=123321, quantity=7)])).items[0].success is True
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_sandbox_delivery_rejects_invalid_event_dates_before_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    delivery = AsyncSandboxDelivery(transport)

    with pytest.raises(ValidationError, match="date"):
        await delivery.tracking(
            order_id="ord-1",
            avito_status="CONFIRMED",
            avito_event_type="",
            provider_event_code="accepted",
            date="not-a-date",
            location="Москва",
        )

    assert fake.count() == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_order_apply_rejects_unknown_transition_before_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    order = AsyncOrder(transport)

    with pytest.raises(ValidationError, match="transition"):
        await order.apply(order_id="ord-1", transition="unknown")

    assert fake.count() == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_orders_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.order(), AsyncOrder)
    assert isinstance(client.order_label(task_id="42"), AsyncOrderLabel)
    assert isinstance(client.delivery_order(), AsyncDeliveryOrder)
    assert isinstance(client.sandbox_delivery(), AsyncSandboxDelivery)
    assert isinstance(client.delivery_task(task_id="51"), AsyncDeliveryTask)
    assert isinstance(client.stock(), AsyncStock)
    await client.aclose()
