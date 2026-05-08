from __future__ import annotations

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import ValidationError
from avito.messenger import (
    AsyncChat,
    AsyncChatMedia,
    AsyncChatMessage,
    AsyncChatWebhook,
    AsyncSpecialOfferCampaign,
)
from avito.messenger.models import UploadImageFile
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_messenger_chat_message_and_media_flows() -> None:
    def blacklist(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"users": [{"user_id": 42}]}
        assert request.headers["idempotency-key"] == "idem-blacklist"
        return httpx.Response(200, json={"success": True})

    def send_message(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "message": {"text": "Здравствуйте"},
            "type": "text",
        }
        return httpx.Response(200, json={"success": True, "message_id": "msg-1", "status": "sent"})

    def send_image(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"image_id": "img-1", "caption": "Фото"}
        return httpx.Response(
            200, json={"success": True, "message_id": "msg-img-1", "status": "sent"}
        )

    fake = (
        AsyncFakeTransport()
        .add_json(
            "GET",
            "/messenger/v2/accounts/7/chats",
            {"chats": [{"id": "chat-1", "user_id": 7, "title": "Покупатель"}]},
        )
        .add_json(
            "GET",
            "/messenger/v2/accounts/7/chats/chat-1",
            {"id": "chat-1", "user_id": 7, "title": "Покупатель"},
        )
        .add("POST", "/messenger/v2/accounts/7/blacklist", blacklist)
        .add_json("POST", "/messenger/v1/accounts/7/chats/chat-1/read", {"success": True})
        .add_json(
            "GET",
            "/messenger/v3/accounts/7/chats/chat-1/messages/",
            {"messages": [{"id": "msg-1", "chat_id": "chat-1", "text": "Здравствуйте"}]},
        )
        .add("POST", "/messenger/v1/accounts/7/chats/chat-1/messages", send_message)
        .add("POST", "/messenger/v1/accounts/7/chats/chat-1/messages/image", send_image)
        .add_json(
            "POST",
            "/messenger/v1/accounts/7/chats/chat-1/messages/msg-1",
            {"success": True, "status": "confirmed"},
        )
        .add_json(
            "GET",
            "/messenger/v1/accounts/7/getVoiceFiles",
            {"voice_files": [{"id": "voice-1", "url": "https://cdn/voice-1.ogg", "duration": 3}]},
        )
        .add_json(
            "POST",
            "/messenger/v1/accounts/7/uploadImages",
            {"images": [{"image_id": "img-1", "url": "https://cdn/img-1.jpg"}]},
        )
    )
    transport = fake.build()
    chat = AsyncChat(transport, chat_id="chat-1", user_id=7)
    message = AsyncChatMessage(transport, chat_id="chat-1", message_id="msg-1", user_id=7)
    media = AsyncChatMedia(transport, user_id=7)

    chats = await chat.list()
    info = await chat.get()
    blocked = await chat.blacklist(blacklisted_user_id=42, idempotency_key="idem-blacklist")
    read = await chat.mark_read()
    messages = await message.list()
    sent = await message.send_message(message="Здравствуйте")
    image_sent = await message.send_image(image_id="img-1", caption="Фото")
    deleted = await message.delete()
    voices = await media.get_voice_files(voice_ids=["voice-1"])
    uploaded = await media.upload_images(
        files=[
            UploadImageFile(
                field_name="image",
                filename="photo.jpg",
                content=b"binary",
                content_type="image/jpeg",
            )
        ]
    )

    assert chats.items[0].chat_id == "chat-1"
    assert info.title == "Покупатель"
    assert blocked.success is True
    assert read.success is True
    assert messages.items[0].message_id == "msg-1"
    assert sent.message_id == "msg-1"
    assert image_sent.message_id == "msg-img-1"
    assert deleted.success is True
    assert voices.items[0].id == "voice-1"
    assert uploaded.items[0].image_id == "img-1"
    assert fake.last(method="GET", path="/messenger/v1/accounts/7/getVoiceFiles").params == {
        "voice_ids": "voice-1"
    }
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_messenger_webhook_and_special_offer_flows() -> None:
    def subscribe(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"url": "https://example.com/hook", "secret": "top-secret"}
        return httpx.Response(200, json={"success": True, "status": "subscribed"})

    def unsubscribe(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"url": "https://example.com/hook"}
        return httpx.Response(200, json={"success": True, "status": "confirmed"})

    def available(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"itemIds": [1, 2]}
        return httpx.Response(
            200,
            json={"items": [{"itemId": 1, "title": "Объявление", "available": True}]},
        )

    def create_multi(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"itemIds": [1]}
        return httpx.Response(200, json={"campaign_id": "camp-1", "status": "draft"})

    def confirm_multi(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dispatches": [
                {
                    "dispatchId": 1,
                    "recipientsCount": 20,
                    "offerSlug": "discount",
                    "discountValue": 10,
                }
            ],
            "expiresAt": 1767225600,
        }
        return httpx.Response(200, json={"success": True, "status": "confirmed"})

    def stats(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {
            "dateTimeFrom": "2026-05-01T00:00:00+03:00",
            "dateTimeTo": "2026-05-02T00:00:00+03:00",
        }
        return httpx.Response(
            200,
            json={
                "campaign_id": "camp-1",
                "sent_count": 20,
                "delivered_count": 18,
                "read_count": 10,
            },
        )

    fake = (
        AsyncFakeTransport()
        .add_json(
            "POST",
            "/messenger/v1/subscriptions",
            {
                "subscriptions": [
                    {"url": "https://example.com/hook", "version": "v3", "status": "active"}
                ]
            },
        )
        .add("POST", "/messenger/v3/webhook", subscribe)
        .add("POST", "/messenger/v1/webhook/unsubscribe", unsubscribe)
        .add("POST", "/special-offers/v1/available", available)
        .add("POST", "/special-offers/v1/multiCreate", create_multi)
        .add("POST", "/special-offers/v1/multiConfirm", confirm_multi)
        .add("POST", "/special-offers/v1/stats", stats)
        .add_json(
            "POST", "/special-offers/v1/tariffInfo", {"price": 5.5, "currency": "RUB", "limit": 100}
        )
    )
    transport = fake.build()
    webhook = AsyncChatWebhook(transport)
    campaign = AsyncSpecialOfferCampaign(transport, campaign_id="camp-1")

    subscriptions = await webhook.list()
    subscribed = await webhook.subscribe(url="https://example.com/hook", secret="top-secret")
    unsubscribed = await webhook.unsubscribe(url="https://example.com/hook")
    available_result = await campaign.get_available(item_ids=[1, 2])
    created = await campaign.create_multi(item_ids=[1])
    confirmed = await campaign.confirm_multi(
        dispatch_id=1,
        recipients_count=20,
        offer_slug="discount",
        discount_value=10,
        expires_at=1767225600,
    )
    stats_result = await campaign.get_stats(
        date_time_from="2026-05-01T00:00:00+03:00",
        date_time_to="2026-05-02T00:00:00+03:00",
    )
    tariff = await campaign.get_tariff_info()

    assert subscriptions.items[0].status == "active"
    assert subscribed.status == "subscribed"
    assert unsubscribed.status == "confirmed"
    assert available_result.items[0].item_id == 1
    assert created.status == "draft"
    assert confirmed.status == "confirmed"
    assert stats_result.delivered_count == 18
    assert tariff.daily_limit == 100
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_messenger_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.chat("chat-1", user_id=7), AsyncChat)
    assert isinstance(client.chat_message("msg-1", chat_id="chat-1", user_id=7), AsyncChatMessage)
    assert isinstance(client.chat_webhook(), AsyncChatWebhook)
    assert isinstance(client.chat_media(user_id=7), AsyncChatMedia)
    assert isinstance(client.special_offer_campaign("camp-1"), AsyncSpecialOfferCampaign)
    await client.aclose()


def test_async_client_messenger_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.chat()
    with pytest.raises(RuntimeError):
        client.chat_message()
    with pytest.raises(RuntimeError):
        client.chat_webhook()
    with pytest.raises(RuntimeError):
        client.chat_media()
    with pytest.raises(RuntimeError):
        client.special_offer_campaign()


@pytest.mark.asyncio
async def test_async_special_offer_stats_reject_invalid_datetime_before_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    campaign = AsyncSpecialOfferCampaign(transport, campaign_id="camp-1")

    with pytest.raises(ValidationError, match="date_time_from"):
        await campaign.get_stats(date_time_from="not-a-date", date_time_to="2026-05-02T00:00:00Z")

    assert fake.count() == 0
    await transport.aclose()
