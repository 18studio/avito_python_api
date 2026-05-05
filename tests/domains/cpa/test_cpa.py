from __future__ import annotations

import json
import logging

import httpx
import pytest

from avito.core import ValidationError
from avito.cpa import CallTrackingCall, CpaArchive, CpaCall, CpaChat, CpaLead
from avito.cpa.models import CpaCallStatusId
from tests.helpers.transport import make_transport


def test_cpa_chat_and_phone_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/cpa/v1/chatByActionId/act-1":
            return httpx.Response(200, json={"chat": {"chat": {"id": "chat-1", "actionId": "act-1"}, "buyer": {"userId": 501, "name": "Иван"}, "item": {"id": 9001, "title": "Велосипед"}, "isArbitrageAvailable": True}})
        if path == "/cpa/v1/chatsByTime":
            assert payload == {"dateTimeFrom": "2026-04-18T00:00:00+03:00", "limit": 10, "offset": 0}
            return httpx.Response(200, json={"chats": [{"chat": {"id": "chat-v1", "actionId": "legacy-1"}, "buyer": {"userId": 502, "name": "Петр"}, "item": {"id": 9002, "title": "Самокат"}, "isArbitrageAvailable": False}]})
        if path == "/cpa/v2/chatsByTime":
            assert payload == {"dateTimeFrom": "2026-04-18T00:00:00+03:00", "limit": 10, "offset": 0}
            return httpx.Response(200, json={"chats": [{"chat": {"id": "chat-v2", "actionId": "act-2"}, "buyer": {"userId": 503, "name": "Мария"}, "item": {"id": 9003, "title": "Ноутбук"}, "isArbitrageAvailable": True}]})
        assert payload == {"dateTimeFrom": "2026-04-18T00:00:00+03:00", "limit": 10, "offset": 0}
        return httpx.Response(200, json={"total": 2, "results": [{"id": 101, "date": "2026-04-18T12:00:00+03:00", "phone_number": "+79990000001"}, {"id": 102, "date": "2026-04-18T12:05:00+03:00", "phone_number": "+79990000002"}]})

    chat = CpaChat(make_transport(httpx.MockTransport(handler)), action_id="act-1")
    assert chat.get().item_title == "Велосипед"
    with pytest.deprecated_call(match="cpa_chat\\(\\)\\.list\\(version=2\\)"):
        classic_chats = chat.list(
            created_at_from="2026-04-18T00:00:00+03:00",
            limit=10,
            offset=0,
            version=1,
        )
    assert classic_chats.items[0].buyer_name == "Петр"
    assert chat.list(
        created_at_from="2026-04-18T00:00:00+03:00",
        limit=10,
        offset=0,
    ).items[0].is_arbitrage_available is True
    assert chat.get_phones_info_from_chats(
        date_time_from="2026-04-18T00:00:00+03:00",
        limit=10,
        offset=0,
    ).items[1].phone_number == "+79990000002"


def test_cpa_calls_archive_and_balance_flows() -> None:
    audio_bytes = b"ID3 fake audio"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/cpa/v2/callsByTime":
            return httpx.Response(200, json={"calls": [{"id": 2001, "itemId": 3001, "buyerPhone": "+79990000010", "sellerPhone": "+79990000011", "virtualPhone": "+79990000012", "statusId": 2, "price": 171600, "duration": 119, "waitingDuration": 0.5, "createTime": "2026-04-18T11:00:00+03:00", "recordUrl": "https://example.com/record-2001.mp3"}]})
        if path == "/cpa/v1/createComplaint":
            return httpx.Response(200, json={"success": True})
        if path == "/cpa/v1/createComplaintByActionId":
            return httpx.Response(200, json={"success": True})
        if path == "/cpa/v3/balanceInfo":
            return httpx.Response(200, json={"balance": -5000})
        if path == "/cpa/v2/balanceInfo":
            return httpx.Response(200, json={"balance": -5000, "advance": 1000, "debt": 0})
        if path == "/cpa/v2/callById":
            return httpx.Response(200, json={"calls": {"id": 2001, "itemId": 3001, "buyerPhone": "+79990000010", "sellerPhone": "+79990000011", "virtualPhone": "+79990000012", "statusId": 2, "price": 171600, "duration": 119, "waitingDuration": 0.5, "createTime": "2026-04-18T11:00:00+03:00"}})
        return httpx.Response(200, content=audio_bytes, headers={"content-type": "audio/mpeg", "content-disposition": 'attachment; filename="call-2001.mp3"'})

    transport = make_transport(httpx.MockTransport(handler))
    cpa_call = CpaCall(transport)
    cpa_lead = CpaLead(transport)
    archive = CpaArchive(transport, call_id="2001")

    assert cpa_call.list(date_time_from="2026-04-18T00:00:00+03:00", limit=100).items[0].record_url == "https://example.com/record-2001.mp3"
    assert cpa_call.create_complaint(call_id=2001, reason="spam").success is True
    assert cpa_lead.create_complaint_by_action_id(action_id=101, reason="duplicate").success is True
    assert cpa_lead.get_balance_info().balance == -5000
    with pytest.deprecated_call(match="cpa_lead\\(\\)\\.get_balance_info"):
        archived_balance = archive.get_balance_info()
    with pytest.deprecated_call(match="call_tracking_call\\(\\)\\.get"):
        archived_call = archive.get_call_by_id(call_id=2001)
    with pytest.deprecated_call(match="call_tracking_call\\(\\)\\.download"):
        archived_audio = archive.get_call()
    assert archived_balance.advance == 1000
    assert archived_call.call_id == "2001"
    assert archived_audio.binary.content == audio_bytes


def test_cpa_complaint_idempotency_key_is_stable_across_retry() -> None:
    calls = {"count": 0}
    seen_keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        seen_keys.append(request.headers.get("Idempotency-Key"))
        if calls["count"] == 1:
            raise httpx.ConnectError("offline", request=request)
        assert request.url.path == "/cpa/v1/createComplaint"
        return httpx.Response(200, json={"success": True})

    cpa_call = CpaCall(make_transport(httpx.MockTransport(handler)))

    result = cpa_call.create_complaint(
        call_id=2001,
        reason="spam",
        idempotency_key="idem-cpa-complaint",
    )

    assert result.success is True
    assert calls["count"] == 2
    assert seen_keys == ["idem-cpa-complaint", "idem-cpa-complaint"]


def test_cpa_call_unknown_status_id_maps_to_unknown_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cpa/v2/callsByTime"
        return httpx.Response(
            200,
            json={
                "calls": [
                    {
                        "id": 2001,
                        "itemId": 3001,
                        "statusId": 999,
                    }
                ]
            },
        )

    caplog.set_level(logging.WARNING, logger="avito.core.enums")
    cpa_call = CpaCall(make_transport(httpx.MockTransport(handler)))

    first = cpa_call.list(
        date_time_from="2026-04-18T00:00:00+03:00",
        limit=100,
    ).items[0]
    second = cpa_call.list(
        date_time_from="2026-04-18T00:00:00+03:00",
        limit=100,
    ).items[0]

    assert first.status_id is CpaCallStatusId.UNKNOWN
    assert second.status_id is CpaCallStatusId.UNKNOWN
    records = [
        record
        for record in caplog.records
        if getattr(record, "enum", None) == "cpa.call_status_id"
        and getattr(record, "value", None) == 999
    ]
    assert len(records) == 1


def test_calltracking_flows() -> None:
    audio_bytes = b"RIFF fake wave"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/calltracking/v1/getCallById/":
            return httpx.Response(200, json={"call": {"callId": 7001, "itemId": 9901, "buyerPhone": "+79990000100", "sellerPhone": "+79990000101", "virtualPhone": "+79990000102", "callTime": "2026-04-18T09:00:00Z", "talkDuration": 67, "waitingDuration": 1.25}, "error": {"code": 0, "message": ""}})
        if request.url.path == "/calltracking/v1/getCalls/":
            return httpx.Response(200, json={"calls": [{"callId": 7001, "itemId": 9901, "buyerPhone": "+79990000100", "sellerPhone": "+79990000101", "virtualPhone": "+79990000102", "callTime": "2026-04-18T09:00:00Z", "talkDuration": 67, "waitingDuration": 1.25}], "error": {"code": 0, "message": ""}})
        return httpx.Response(200, content=audio_bytes, headers={"content-type": "audio/wav", "content-disposition": 'attachment; filename="record-7001.wav"'})

    call = CallTrackingCall(make_transport(httpx.MockTransport(handler)), call_id="7001")
    assert call.get().call.call_id == "7001"
    assert call.list(date_time_from="2026-04-01T00:00:00Z", date_time_to="2026-04-18T23:59:59Z", limit=100, offset=0).items[0].buyer_phone == "+79990000100"
    assert call.download().binary.content == audio_bytes


def test_cpa_rejects_invalid_datetime_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    chat = CpaChat(make_transport(httpx.MockTransport(handler)))
    call = CpaCall(make_transport(httpx.MockTransport(handler)))
    tracking = CallTrackingCall(make_transport(httpx.MockTransport(handler)))

    with pytest.raises(ValidationError, match="created_at_from"):
        chat.list(created_at_from="18.04.2026", limit=10, offset=0)
    with pytest.raises(ValidationError, match="date_time_from"):
        call.list(date_time_from="", limit=100)
    with pytest.raises(ValidationError, match="date_time_to"):
        tracking.list(date_time_from="2026-04-01T00:00:00Z", date_time_to="not-a-date")
