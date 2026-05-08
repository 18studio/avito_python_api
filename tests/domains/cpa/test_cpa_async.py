from __future__ import annotations

import logging

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import ValidationError
from avito.core.retries import RetryPolicy
from avito.cpa import (
    AsyncCallTrackingCall,
    AsyncCpaArchive,
    AsyncCpaCall,
    AsyncCpaChat,
    AsyncCpaLead,
)
from avito.cpa.models import CpaCallStatusId
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_cpa_chat_and_phone_flows() -> None:
    def chats_v1(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dateTimeFrom": "2026-04-18T00:00:00+03:00",
            "limit": 10,
            "offset": 0,
        }
        return httpx.Response(
            200,
            json={
                "chats": [
                    {
                        "chat": {"id": "chat-v1", "actionId": "legacy-1"},
                        "buyer": {"userId": 502, "name": "Петр"},
                        "item": {"id": 9002, "title": "Самокат"},
                        "isArbitrageAvailable": False,
                    }
                ]
            },
        )

    def chats_v2(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dateTimeFrom": "2026-04-18T00:00:00+03:00",
            "limit": 10,
            "offset": 0,
        }
        return httpx.Response(
            200,
            json={
                "chats": [
                    {
                        "chat": {"id": "chat-v2", "actionId": "act-2"},
                        "buyer": {"userId": 503, "name": "Мария"},
                        "item": {"id": 9003, "title": "Ноутбук"},
                        "isArbitrageAvailable": True,
                    }
                ]
            },
        )

    def phones(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dateTimeFrom": "2026-04-18T00:00:00+03:00",
            "limit": 10,
            "offset": 0,
        }
        return httpx.Response(
            200,
            json={
                "total": 2,
                "results": [
                    {
                        "id": 101,
                        "date": "2026-04-18T12:00:00+03:00",
                        "phone_number": "+79990000001",
                    },
                    {
                        "id": 102,
                        "date": "2026-04-18T12:05:00+03:00",
                        "phone_number": "+79990000002",
                    },
                ],
            },
        )

    fake = (
        AsyncFakeTransport()
        .add_json(
            "GET",
            "/cpa/v1/chatByActionId/act-1",
            {
                "chat": {
                    "chat": {"id": "chat-1", "actionId": "act-1"},
                    "buyer": {"userId": 501, "name": "Иван"},
                    "item": {"id": 9001, "title": "Велосипед"},
                    "isArbitrageAvailable": True,
                }
            },
        )
        .add("POST", "/cpa/v1/chatsByTime", chats_v1)
        .add("POST", "/cpa/v2/chatsByTime", chats_v2)
        .add("POST", "/cpa/v1/phonesInfoFromChats", phones)
    )
    transport = fake.build()
    chat = AsyncCpaChat(transport, action_id="act-1")

    assert (await chat.get()).item_title == "Велосипед"
    with pytest.deprecated_call(match="cpa_chat\\(\\)\\.list\\(version=2\\)"):
        classic_chats = await chat.list(
            created_at_from="2026-04-18T00:00:00+03:00",
            limit=10,
            offset=0,
            version=1,
        )
    assert classic_chats.items[0].buyer_name == "Петр"
    assert (
        await chat.list(
            created_at_from="2026-04-18T00:00:00+03:00",
            limit=10,
            offset=0,
        )
    ).items[0].is_arbitrage_available is True
    assert (
        await chat.get_phones_info_from_chats(
            date_time_from="2026-04-18T00:00:00+03:00",
            limit=10,
            offset=0,
        )
    ).items[1].phone_number == "+79990000002"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_cpa_calls_archive_and_balance_flows() -> None:
    audio_bytes = b"ID3 fake audio"
    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/cpa/v2/callsByTime",
            {
                "calls": [
                    {
                        "id": 2001,
                        "itemId": 3001,
                        "buyerPhone": "+79990000010",
                        "sellerPhone": "+79990000011",
                        "virtualPhone": "+79990000012",
                        "statusId": 2,
                        "price": 171600,
                        "duration": 119,
                        "waitingDuration": 0.5,
                        "createTime": "2026-04-18T11:00:00+03:00",
                        "recordUrl": "https://example.com/record-2001.mp3",
                    }
                ]
            },
        )
        .add_json("POST", "/cpa/v1/createComplaint", {"success": True})
        .add_json("POST", "/cpa/v1/createComplaintByActionId", {"success": True})
        .add_json("POST", "/cpa/v3/balanceInfo", {"balance": -5000})
        .add_json("POST", "/cpa/v2/balanceInfo", {"balance": -5000, "advance": 1000, "debt": 0})
        .add_json(
            "POST",
            "/cpa/v2/callById",
            {
                "calls": {
                    "id": 2001,
                    "itemId": 3001,
                    "buyerPhone": "+79990000010",
                    "sellerPhone": "+79990000011",
                    "virtualPhone": "+79990000012",
                    "statusId": 2,
                    "price": 171600,
                    "duration": 119,
                    "waitingDuration": 0.5,
                    "createTime": "2026-04-18T11:00:00+03:00",
                }
            },
        )
        .add(
            "GET",
            "/cpa/v1/call/2001",
            httpx.Response(
                200,
                content=audio_bytes,
                headers={
                    "content-type": "audio/mpeg",
                    "content-disposition": 'attachment; filename="call-2001.mp3"',
                },
            ),
        )
    )
    transport = fake.build()
    cpa_call = AsyncCpaCall(transport)
    cpa_lead = AsyncCpaLead(transport)
    archive = AsyncCpaArchive(transport, call_id="2001")

    assert (
        await cpa_call.list(date_time_from="2026-04-18T00:00:00+03:00", limit=100)
    ).items[0].record_url == "https://example.com/record-2001.mp3"
    assert (await cpa_call.create_complaint(call_id=2001, reason="spam")).success is True
    assert (
        await cpa_lead.create_complaint_by_action_id(action_id=101, reason="duplicate")
    ).success is True
    assert (await cpa_lead.get_balance_info()).balance == -5000
    with pytest.deprecated_call(match="cpa_lead\\(\\)\\.get_balance_info"):
        archived_balance = await archive.get_balance_info()
    with pytest.deprecated_call(match="call_tracking_call\\(\\)\\.get"):
        archived_call = await archive.get_call_by_id(call_id=2001)
    with pytest.deprecated_call(match="call_tracking_call\\(\\)\\.download"):
        archived_audio = await archive.get_call()
    assert archived_balance.advance == 1000
    assert archived_call.call_id == "2001"
    assert archived_audio.binary.content == audio_bytes
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_cpa_complaint_idempotency_key_is_stable_across_retry() -> None:
    calls = {"count": 0}
    seen_keys: list[str | None] = []

    def create_complaint(request: RecordedRequest) -> httpx.Response:
        calls["count"] += 1
        seen_keys.append(request.headers.get("idempotency-key"))
        if calls["count"] == 1:
            raise httpx.ConnectError("offline")
        assert request.path == "/cpa/v1/createComplaint"
        return httpx.Response(200, json={"success": True})

    fake = AsyncFakeTransport().add("POST", "/cpa/v1/createComplaint", create_complaint)
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=2))
    cpa_call = AsyncCpaCall(transport)

    result = await cpa_call.create_complaint(
        call_id=2001,
        reason="spam",
        idempotency_key="idem-cpa-complaint",
    )

    assert result.success is True
    assert calls["count"] == 2
    assert seen_keys == ["idem-cpa-complaint", "idem-cpa-complaint"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_cpa_call_unknown_status_id_maps_to_unknown_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = AsyncFakeTransport().add_json(
        "POST",
        "/cpa/v2/callsByTime",
        {"calls": [{"id": 2001, "itemId": 3001, "statusId": 998}]},
    )
    transport = fake.build()
    caplog.set_level(logging.WARNING, logger="avito.core.enums")
    cpa_call = AsyncCpaCall(transport)

    first = (
        await cpa_call.list(
            date_time_from="2026-04-18T00:00:00+03:00",
            limit=100,
        )
    ).items[0]
    second = (
        await cpa_call.list(
            date_time_from="2026-04-18T00:00:00+03:00",
            limit=100,
        )
    ).items[0]

    assert first.status_id is CpaCallStatusId.UNKNOWN
    assert second.status_id is CpaCallStatusId.UNKNOWN
    records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "cpa.call_status_id"
        and getattr(record, "value", None) == 998
    ]
    assert len(records) == 1
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_calltracking_flows() -> None:
    audio_bytes = b"RIFF fake wave"
    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/calltracking/v1/getCallById/",
            {
                "call": {
                    "callId": 7001,
                    "itemId": 9901,
                    "buyerPhone": "+79990000100",
                    "sellerPhone": "+79990000101",
                    "virtualPhone": "+79990000102",
                    "callTime": "2026-04-18T09:00:00Z",
                    "talkDuration": 67,
                    "waitingDuration": 1.25,
                },
                "error": {"code": 0, "message": ""},
            },
        )
        .add_json(
            "POST",
            "/calltracking/v1/getCalls/",
            {
                "calls": [
                    {
                        "callId": 7001,
                        "itemId": 9901,
                        "buyerPhone": "+79990000100",
                        "sellerPhone": "+79990000101",
                        "virtualPhone": "+79990000102",
                        "callTime": "2026-04-18T09:00:00Z",
                        "talkDuration": 67,
                        "waitingDuration": 1.25,
                    }
                ],
                "error": {"code": 0, "message": ""},
            },
        )
        .add(
            "GET",
            "/calltracking/v1/getRecordByCallId/",
            httpx.Response(
                200,
                content=audio_bytes,
                headers={
                    "content-type": "audio/wav",
                    "content-disposition": 'attachment; filename="record-7001.wav"',
                },
            ),
        )
    )
    transport = fake.build()
    call = AsyncCallTrackingCall(transport, call_id="7001")

    assert (await call.get()).call.call_id == "7001"
    assert (
        await call.list(
            date_time_from="2026-04-01T00:00:00Z",
            date_time_to="2026-04-18T23:59:59Z",
            limit=100,
            offset=0,
        )
    ).items[0].buyer_phone == "+79990000100"
    assert (await call.download()).binary.content == audio_bytes
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_cpa_rejects_invalid_datetime_before_transport() -> None:
    transport = AsyncFakeTransport().build()
    chat = AsyncCpaChat(transport)
    call = AsyncCpaCall(transport)
    tracking = AsyncCallTrackingCall(transport)

    with pytest.raises(ValidationError, match="created_at_from"):
        await chat.list(created_at_from="18.04.2026", limit=10, offset=0)
    with pytest.raises(ValidationError, match="date_time_from"):
        await call.list(date_time_from="", limit=100)
    with pytest.raises(ValidationError, match="date_time_to"):
        await tracking.list(date_time_from="2026-04-01T00:00:00Z", date_time_to="not-a-date")
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_cpa_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.cpa_lead(), AsyncCpaLead)
    assert isinstance(client.cpa_chat(chat_id="act-1"), AsyncCpaChat)
    assert isinstance(client.cpa_call(), AsyncCpaCall)
    assert isinstance(client.cpa_archive(call_id=2001), AsyncCpaArchive)
    assert isinstance(client.call_tracking_call(call_id=7001), AsyncCallTrackingCall)
    await client.aclose()


def test_async_client_cpa_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.cpa_lead()
    with pytest.raises(RuntimeError):
        client.cpa_chat()
    with pytest.raises(RuntimeError):
        client.cpa_call()
    with pytest.raises(RuntimeError):
        client.cpa_archive()
    with pytest.raises(RuntimeError):
        client.call_tracking_call()
