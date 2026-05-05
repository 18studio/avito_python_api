"""Operation specs for messenger domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.messenger.models import (
    BlacklistRequest,
    ChatInfo,
    ChatsResult,
    MessageActionResult,
    MessagesResult,
    MultiConfirmSpecialOfferRequest,
    MultiCreateSpecialOfferRequest,
    MultiCreateSpecialOfferResult,
    SendImageMessageRequest,
    SendMessageRequest,
    SpecialOfferAvailableRequest,
    SpecialOfferAvailableResult,
    SpecialOfferStatsRequest,
    SpecialOfferStatsResult,
    SubscriptionsResult,
    TariffInfo,
    UnsubscribeWebhookRequest,
    UpdateWebhookRequest,
    UploadImagesResult,
    VoiceFilesResult,
    WebhookActionResult,
)

LIST_CHATS = OperationSpec(
    name="messenger.list_chats",
    method="GET",
    path="/messenger/v2/accounts/{user_id}/chats",
    response_model=ChatsResult,
)
GET_CHAT = OperationSpec(
    name="messenger.get_chat",
    method="GET",
    path="/messenger/v2/accounts/{user_id}/chats/{chat_id}",
    response_model=ChatInfo,
)
READ_CHAT = OperationSpec(
    name="messenger.read_chat",
    method="POST",
    path="/messenger/v1/accounts/{user_id}/chats/{chat_id}/read",
    response_model=MessageActionResult,
    retry_mode="enabled",
)
ADD_TO_BLACKLIST = OperationSpec(
    name="messenger.add_to_blacklist",
    method="POST",
    path="/messenger/v2/accounts/{user_id}/blacklist",
    request_model=BlacklistRequest,
    response_model=MessageActionResult,
    retry_mode="enabled",
)
LIST_MESSAGES = OperationSpec(
    name="messenger.list_messages",
    method="GET",
    path="/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/",
    response_model=MessagesResult,
)
SEND_MESSAGE = OperationSpec(
    name="messenger.send_message",
    method="POST",
    path="/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages",
    request_model=SendMessageRequest,
    response_model=MessageActionResult,
    retry_mode="enabled",
)
SEND_IMAGE_MESSAGE = OperationSpec(
    name="messenger.send_image_message",
    method="POST",
    path="/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/image",
    request_model=SendImageMessageRequest,
    response_model=MessageActionResult,
    retry_mode="enabled",
)
DELETE_MESSAGE = OperationSpec(
    name="messenger.delete_message",
    method="POST",
    path="/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/{message_id}",
    response_model=MessageActionResult,
    retry_mode="enabled",
)
GET_SUBSCRIPTIONS = OperationSpec(
    name="messenger.webhook.get_subscriptions",
    method="POST",
    path="/messenger/v1/subscriptions",
    response_model=SubscriptionsResult,
    retry_mode="enabled",
)
UNSUBSCRIBE_WEBHOOK = OperationSpec(
    name="messenger.webhook.unsubscribe",
    method="POST",
    path="/messenger/v1/webhook/unsubscribe",
    request_model=UnsubscribeWebhookRequest,
    response_model=WebhookActionResult,
    retry_mode="enabled",
)
UPDATE_WEBHOOK_V3 = OperationSpec(
    name="messenger.webhook.update_v3",
    method="POST",
    path="/messenger/v3/webhook",
    request_model=UpdateWebhookRequest,
    response_model=WebhookActionResult,
    retry_mode="enabled",
)
GET_VOICE_FILES = OperationSpec(
    name="messenger.media.get_voice_files",
    method="GET",
    path="/messenger/v1/accounts/{user_id}/getVoiceFiles",
    response_model=VoiceFilesResult,
)
UPLOAD_IMAGES = OperationSpec(
    name="messenger.media.upload_images",
    method="POST",
    path="/messenger/v1/accounts/{user_id}/uploadImages",
    response_model=UploadImagesResult,
    retry_mode="enabled",
)
GET_AVAILABLE_SPECIAL_OFFERS = OperationSpec(
    name="messenger.special_offers.get_available",
    method="POST",
    path="/special-offers/v1/available",
    request_model=SpecialOfferAvailableRequest,
    response_model=SpecialOfferAvailableResult,
    retry_mode="enabled",
)
CREATE_MULTI_SPECIAL_OFFER = OperationSpec(
    name="messenger.special_offers.create_multi",
    method="POST",
    path="/special-offers/v1/multiCreate",
    request_model=MultiCreateSpecialOfferRequest,
    response_model=MultiCreateSpecialOfferResult,
    retry_mode="enabled",
)
CONFIRM_MULTI_SPECIAL_OFFER = OperationSpec(
    name="messenger.special_offers.confirm_multi",
    method="POST",
    path="/special-offers/v1/multiConfirm",
    request_model=MultiConfirmSpecialOfferRequest,
    response_model=WebhookActionResult,
    retry_mode="enabled",
)
GET_SPECIAL_OFFER_STATS = OperationSpec(
    name="messenger.special_offers.get_stats",
    method="POST",
    path="/special-offers/v1/stats",
    request_model=SpecialOfferStatsRequest,
    response_model=SpecialOfferStatsResult,
    retry_mode="enabled",
)
GET_SPECIAL_OFFER_TARIFF_INFO = OperationSpec(
    name="messenger.special_offers.get_tariff_info",
    method="POST",
    path="/special-offers/v1/tariffInfo",
    response_model=TariffInfo,
    retry_mode="enabled",
)

__all__ = (
    "ADD_TO_BLACKLIST",
    "CONFIRM_MULTI_SPECIAL_OFFER",
    "CREATE_MULTI_SPECIAL_OFFER",
    "DELETE_MESSAGE",
    "GET_AVAILABLE_SPECIAL_OFFERS",
    "GET_CHAT",
    "GET_SPECIAL_OFFER_STATS",
    "GET_SPECIAL_OFFER_TARIFF_INFO",
    "GET_SUBSCRIPTIONS",
    "GET_VOICE_FILES",
    "LIST_CHATS",
    "LIST_MESSAGES",
    "READ_CHAT",
    "SEND_IMAGE_MESSAGE",
    "SEND_MESSAGE",
    "UNSUBSCRIBE_WEBHOOK",
    "UPDATE_WEBHOOK_V3",
    "UPLOAD_IMAGES",
)
