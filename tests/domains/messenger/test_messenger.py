from __future__ import annotations

import json

import httpx
import pytest

from avito.core import ValidationError
from avito.messenger import Chat, ChatMedia, ChatMessage, ChatWebhook, SpecialOfferCampaign
from avito.messenger.models import UploadImageFile
from tests.helpers.transport import make_transport


def test_messenger_chat_message_and_media_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/messenger/v2/accounts/7/chats":
            return httpx.Response(200, json={"chats": [{"id": "chat-1", "user_id": 7, "title": "Покупатель"}]})
        if path == "/messenger/v2/accounts/7/chats/chat-1":
            return httpx.Response(200, json={"id": "chat-1", "user_id": 7, "title": "Покупатель"})
        if path == "/messenger/v2/accounts/7/blacklist":
            assert json.loads(request.content.decode()) == {"users": [{"user_id": 42}]}
            return httpx.Response(200, json={"success": True})
        if path == "/messenger/v1/accounts/7/chats/chat-1/messages":
            assert json.loads(request.content.decode()) == {
                "message": {"text": "Здравствуйте"},
                "type": "text",
            }
            return httpx.Response(200, json={"success": True, "message_id": "msg-1", "status": "sent"})
        if path == "/messenger/v1/accounts/7/uploadImages":
            return httpx.Response(200, json={"images": [{"image_id": "img-1", "url": "https://cdn/img-1.jpg"}]})
        assert path == "/messenger/v1/accounts/7/chats/chat-1/messages/image"
        assert json.loads(request.content.decode()) == {"image_id": "img-1"}
        return httpx.Response(200, json={"success": True, "message_id": "msg-img-1", "status": "sent"})

    transport = make_transport(httpx.MockTransport(handler))
    chat = Chat(transport, chat_id="chat-1", user_id=7)
    message = ChatMessage(transport, user_id=7)
    media = ChatMedia(transport, user_id=7)

    chats = chat.list()
    info = chat.get()
    blocked = chat.blacklist(blacklisted_user_id=42)
    sent = message.send_message(chat_id="chat-1", message="Здравствуйте")
    uploaded = media.upload_images(
        files=[UploadImageFile(field_name="image", filename="photo.jpg", content=b"binary", content_type="image/jpeg")]
    )
    image_sent = message.send_image(chat_id="chat-1", image_id=uploaded.items[0].image_id or "")

    assert chats.items[0].chat_id == "chat-1"
    assert info.title == "Покупатель"
    assert blocked.success is True
    assert sent.message_id == "msg-1"
    assert uploaded.items[0].image_id == "img-1"
    assert image_sent.message_id == "msg-img-1"


def test_messenger_webhook_and_special_offer_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = json.loads(request.content.decode()) if request.content else None
        if path == "/messenger/v1/subscriptions":
            return httpx.Response(200, json={"subscriptions": [{"url": "https://example.com/hook", "version": "v2", "status": "active"}]})
        if path == "/messenger/v3/webhook":
            assert payload == {"url": "https://example.com/hook", "secret": "top-secret"}
            return httpx.Response(200, json={"success": True, "status": "subscribed"})
        if path == "/special-offers/v1/multiCreate":
            assert payload == {"itemIds": [1]}
            return httpx.Response(200, json={"campaign_id": "camp-1", "status": "draft"})
        if path == "/special-offers/v1/multiConfirm":
            assert payload == {
                "dispatches": [
                    {"dispatchId": 1, "recipientsCount": 20, "offerSlug": "discount"}
                ]
            }
            return httpx.Response(200, json={"success": True, "status": "confirmed"})
        assert path == "/special-offers/v1/stats"
        assert payload == {
            "dateTimeFrom": "2026-05-01T00:00:00+03:00",
            "dateTimeTo": "2026-05-02T00:00:00+03:00",
        }
        return httpx.Response(200, json={"campaign_id": "camp-1", "sent_count": 20, "delivered_count": 18, "read_count": 10})

    transport = make_transport(httpx.MockTransport(handler))
    webhook = ChatWebhook(transport)
    campaign = SpecialOfferCampaign(transport, campaign_id="camp-1")

    subscriptions = webhook.list()
    subscribed = webhook.subscribe(url="https://example.com/hook", secret="top-secret")
    created = campaign.create_multi(item_ids=[1])
    confirmed = campaign.confirm_multi(
        dispatch_id=1,
        recipients_count=20,
        offer_slug="discount",
    )
    stats = campaign.get_stats(
        date_time_from="2026-05-01T00:00:00+03:00",
        date_time_to="2026-05-02T00:00:00+03:00",
    )

    assert subscriptions.items[0].status == "active"
    assert subscribed.status == "subscribed"
    assert created.status == "draft"
    assert confirmed.status == "confirmed"
    assert stats.delivered_count == 18


def test_special_offer_stats_reject_invalid_datetime_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    campaign = SpecialOfferCampaign(
        make_transport(httpx.MockTransport(handler)),
        campaign_id="camp-1",
    )

    with pytest.raises(ValidationError, match="date_time_from"):
        campaign.get_stats(date_time_from="not-a-date", date_time_to="2026-05-02T00:00:00Z")
