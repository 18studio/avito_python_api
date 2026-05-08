"""Асинхронный высокоуровневый клиент SDK Avito."""

from __future__ import annotations

from pathlib import Path

import httpx

from avito.accounts import AsyncAccount, AsyncAccountHierarchy
from avito.auth.async_provider import AsyncAuthProvider
from avito.auth.async_token_client import AsyncAlternateTokenClient, AsyncTokenClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.async_transport import AsyncTransport
from avito.core.exceptions import ClientClosedError
from avito.core.types import TransportDebugInfo
from avito.cpa import (
    AsyncCallTrackingCall,
    AsyncCpaArchive,
    AsyncCpaCall,
    AsyncCpaChat,
    AsyncCpaLead,
)
from avito.jobs import (
    AsyncApplication,
    AsyncJobDictionary,
    AsyncJobWebhook,
    AsyncResume,
    AsyncVacancy,
)
from avito.messenger import (
    AsyncChat,
    AsyncChatMedia,
    AsyncChatMessage,
    AsyncChatWebhook,
    AsyncSpecialOfferCampaign,
)
from avito.promotion import (
    AsyncAutostrategyCampaign,
    AsyncBbipPromotion,
    AsyncCpaAuction,
    AsyncPromotionOrder,
    AsyncTargetActionPricing,
    AsyncTrxPromotion,
)
from avito.ratings import AsyncRatingProfile, AsyncReview, AsyncReviewAnswer
from avito.realty import (
    AsyncRealtyAnalyticsReport,
    AsyncRealtyBooking,
    AsyncRealtyListing,
    AsyncRealtyPricing,
)
from avito.tariffs import AsyncTariff


class AsyncAvitoClient:
    """Асинхронная публичная точка входа SDK с factory-методами портированных доменов."""

    def __init__(
        self,
        settings: AvitoSettings | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if client_id is not None or client_secret is not None:
            auth = AuthSettings(client_id=client_id, client_secret=client_secret)
            settings = AvitoSettings(auth=auth)
        self._closed = False
        self._entered = False
        self._settings = (settings or AvitoSettings.from_env()).validate_required()
        self._external_http_client = http_client
        self._auth_provider: AsyncAuthProvider | None = None
        self._transport: AsyncTransport | None = None

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> AsyncAvitoClient:
        """Создает async-клиент из переменных окружения и optional `.env` файла."""

        return cls(AvitoSettings.from_env(env_file=env_file))

    @classmethod
    def _from_transport(
        cls,
        settings: AvitoSettings,
        *,
        transport: AsyncTransport,
        auth_provider: AsyncAuthProvider,
    ) -> AsyncAvitoClient:
        client = cls.__new__(cls)
        client._closed = False
        client._entered = True
        client._settings = settings
        client._external_http_client = None
        client._auth_provider = auth_provider
        client._transport = transport
        return client

    async def __aenter__(self) -> AsyncAvitoClient:
        self._ensure_open()
        if self._entered:
            return self
        try:
            self._auth_provider = self._build_auth_provider()
            self._transport = AsyncTransport(
                self.settings,
                auth_provider=self._auth_provider,
                client=self._external_http_client,
            )
            self._entered = True
            return self
        except BaseException:
            await self.aclose()
            raise

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    @property
    def settings(self) -> AvitoSettings:
        """Возвращает read-only настройки клиента."""

        return self._settings

    @property
    def auth_provider(self) -> AsyncAuthProvider:
        """Возвращает read-only auth provider клиента."""

        self._ensure_ready()
        if self._auth_provider is None:
            raise RuntimeError("AsyncAvitoClient не инициализирован: используйте 'async with'.")
        return self._auth_provider

    @property
    def transport(self) -> AsyncTransport:
        """Возвращает read-only async transport клиента."""

        return self._require_transport()

    def auth(self) -> AsyncAuthProvider:
        """Возвращает объект аутентификации и async token-flow операций."""

        self._ensure_open()
        return self.auth_provider

    def debug_info(self) -> TransportDebugInfo:
        """Возвращает безопасный снимок transport-настроек для диагностики."""

        return self._require_transport().debug_info()

    def account(self, user_id: int | str | None = None) -> AsyncAccount:
        """Создает async-доменный объект аккаунта."""

        return AsyncAccount(self._require_transport(), user_id=user_id)

    def account_hierarchy(self, user_id: int | str | None = None) -> AsyncAccountHierarchy:
        """Создает async-доменный объект иерархии аккаунта."""

        return AsyncAccountHierarchy(self._require_transport(), user_id=user_id)

    def cpa_lead(self) -> AsyncCpaLead:
        """Создает async-доменный объект CPA-лида."""

        return AsyncCpaLead(self._require_transport())

    def cpa_chat(self, chat_id: int | str | None = None) -> AsyncCpaChat:
        """Создает async-доменный объект CPA-чата."""

        return AsyncCpaChat(self._require_transport(), action_id=chat_id)

    def cpa_call(self) -> AsyncCpaCall:
        """Создает async-доменный объект CPA-звонка."""

        return AsyncCpaCall(self._require_transport())

    def cpa_archive(self, call_id: int | str | None = None) -> AsyncCpaArchive:
        """Создает async-доменный объект архивных операций CPA."""

        return AsyncCpaArchive(self._require_transport(), call_id=call_id)

    def call_tracking_call(self, call_id: int | str | None = None) -> AsyncCallTrackingCall:
        """Создает async-доменный объект CallTracking."""

        return AsyncCallTrackingCall(self._require_transport(), call_id=call_id)

    def tariff(self, tariff_id: int | str | None = None) -> AsyncTariff:
        """Создает async-доменный объект тарифа."""

        return AsyncTariff(self._require_transport(), tariff_id=tariff_id)

    def review(self) -> AsyncReview:
        """Создает async-доменный объект отзыва."""

        return AsyncReview(self._require_transport())

    def review_answer(self, answer_id: int | str | None = None) -> AsyncReviewAnswer:
        """Создает async-доменный объект ответа на отзыв."""

        return AsyncReviewAnswer(self._require_transport(), answer_id=answer_id)

    def rating_profile(self) -> AsyncRatingProfile:
        """Создает async-доменный объект рейтингового профиля."""

        return AsyncRatingProfile(self._require_transport())

    def realty_listing(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> AsyncRealtyListing:
        """Создает async-доменный объект объявления недвижимости."""

        return AsyncRealtyListing(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_booking(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> AsyncRealtyBooking:
        """Создает async-доменный объект бронирования недвижимости."""

        return AsyncRealtyBooking(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_pricing(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> AsyncRealtyPricing:
        """Создает async-доменный объект цен недвижимости."""

        return AsyncRealtyPricing(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_analytics_report(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> AsyncRealtyAnalyticsReport:
        """Создает async-доменный объект аналитического отчета недвижимости."""

        return AsyncRealtyAnalyticsReport(
            self._require_transport(),
            item_id=item_id,
            user_id=user_id,
        )

    def chat(
        self, chat_id: int | str | None = None, *, user_id: int | str | None = None
    ) -> AsyncChat:
        """Создает async-доменный объект чата."""

        return AsyncChat(self._require_transport(), chat_id=chat_id, user_id=user_id)

    def chat_message(
        self,
        message_id: int | str | None = None,
        *,
        chat_id: int | str | None = None,
        user_id: int | str | None = None,
    ) -> AsyncChatMessage:
        """Создает async-доменный объект сообщения чата."""

        return AsyncChatMessage(
            self._require_transport(),
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
        )

    def chat_webhook(self) -> AsyncChatWebhook:
        """Создает async-доменный объект webhook мессенджера."""

        return AsyncChatWebhook(self._require_transport())

    def chat_media(self, *, user_id: int | str | None = None) -> AsyncChatMedia:
        """Создает async-доменный объект медиа мессенджера."""

        return AsyncChatMedia(self._require_transport(), user_id=user_id)

    def special_offer_campaign(
        self, campaign_id: int | str | None = None
    ) -> AsyncSpecialOfferCampaign:
        """Создает async-доменный объект рассылки спецпредложений."""

        return AsyncSpecialOfferCampaign(self._require_transport(), campaign_id=campaign_id)

    def vacancy(self, vacancy_id: int | str | None = None) -> AsyncVacancy:
        """Создает async-доменный объект вакансии."""

        return AsyncVacancy(self._require_transport(), vacancy_id=vacancy_id)

    def application(self) -> AsyncApplication:
        """Создает async-доменный объект откликов."""

        return AsyncApplication(self._require_transport())

    def resume(self, resume_id: int | str | None = None) -> AsyncResume:
        """Создает async-доменный объект резюме."""

        return AsyncResume(self._require_transport(), resume_id=resume_id)

    def job_webhook(self) -> AsyncJobWebhook:
        """Создает async-доменный объект webhook Авито Работы."""

        return AsyncJobWebhook(self._require_transport())

    def job_dictionary(self, dictionary_id: int | str | None = None) -> AsyncJobDictionary:
        """Создает async-доменный объект справочника Авито Работы."""

        return AsyncJobDictionary(self._require_transport(), dictionary_id=dictionary_id)

    def promotion_order(self, order_id: int | str | None = None) -> AsyncPromotionOrder:
        """Создает async-доменный объект заявок promotion."""

        return AsyncPromotionOrder(self._require_transport(), order_id=order_id)

    def bbip_promotion(self, item_id: int | str | None = None) -> AsyncBbipPromotion:
        """Создает async-доменный объект BBIP-продвижения."""

        return AsyncBbipPromotion(self._require_transport(), item_id=item_id)

    def trx_promotion(self, item_id: int | str | None = None) -> AsyncTrxPromotion:
        """Создает async-доменный объект TrxPromo."""

        return AsyncTrxPromotion(self._require_transport(), item_id=item_id)

    def cpa_auction(self, item_id: int | str | None = None) -> AsyncCpaAuction:
        """Создает async-доменный объект CPA-аукциона."""

        return AsyncCpaAuction(self._require_transport(), item_id=item_id)

    def target_action_pricing(self, item_id: int | str | None = None) -> AsyncTargetActionPricing:
        """Создает async-доменный объект цены целевого действия."""

        return AsyncTargetActionPricing(self._require_transport(), item_id=item_id)

    def autostrategy_campaign(
        self, campaign_id: int | str | None = None
    ) -> AsyncAutostrategyCampaign:
        """Создает async-доменный объект кампании автостратегии."""

        return AsyncAutostrategyCampaign(self._require_transport(), campaign_id=campaign_id)

    async def aclose(self) -> None:
        """Закрывает transport и auth-provider; повторный вызов безопасен."""

        transport = self._transport
        auth_provider = self._auth_provider
        self._closed = True
        self._entered = False
        self._transport = None
        self._auth_provider = None
        if transport is not None:
            await transport.aclose()
        if auth_provider is not None:
            await auth_provider.aclose()

    def _build_auth_provider(self) -> AsyncAuthProvider:
        token_client = AsyncTokenClient(
            self.settings.auth,
            client=self._external_http_client,
            sdk_settings=self.settings,
        )
        alternate_token_client = AsyncAlternateTokenClient(
            self.settings.auth,
            client=self._external_http_client,
            sdk_settings=self.settings,
        )
        autoteka_token_client = AsyncTokenClient(
            self.settings.auth,
            token_url=self.settings.auth.autoteka_token_url,
            client=self._external_http_client,
            sdk_settings=self.settings,
        )
        return AsyncAuthProvider(
            self.settings.auth,
            token_client=token_client,
            alternate_token_client=alternate_token_client,
            autoteka_token_client=autoteka_token_client,
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClientClosedError("Клиент закрыт; создайте новый AsyncAvitoClient.")

    def _ensure_ready(self) -> None:
        self._ensure_open()
        if not self._entered:
            raise RuntimeError(
                "AsyncAvitoClient не инициализирован: используйте 'async with' "
                "или дождитесь '__aenter__'."
            )

    def _require_transport(self) -> AsyncTransport:
        self._ensure_ready()
        if self._transport is None:
            raise RuntimeError("AsyncAvitoClient не инициализирован: используйте 'async with'.")
        return self._transport


__all__ = ("AsyncAvitoClient",)
