"""Асинхронный высокоуровневый клиент SDK Avito."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

import httpx

from avito.accounts import AsyncAccount, AsyncAccountHierarchy
from avito.ads import (
    AsyncAd,
    AsyncAdPromotion,
    AsyncAdStats,
    AsyncAutoloadArchive,
    AsyncAutoloadProfile,
    AsyncAutoloadReport,
)
from avito.ads.models import CallStats, ListingStats, ListingStatus, SpendingRecord
from avito.auth.async_provider import AsyncAuthProvider
from avito.auth.async_token_client import AsyncAlternateTokenClient, AsyncTokenClient
from avito.auth.settings import AuthSettings
from avito.autoteka import (
    AsyncAutotekaMonitoring,
    AsyncAutotekaReport,
    AsyncAutotekaScoring,
    AsyncAutotekaValuation,
    AsyncAutotekaVehicle,
)
from avito.client import (
    _default_summary_date_range,
    _safe_summary_async,
    _sum_optional_float,
    _sum_optional_int,
    _summary_unavailable_section,
)
from avito.config import AvitoSettings
from avito.core.async_transport import AsyncTransport
from avito.core.exceptions import AvitoError, ClientClosedError
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
from avito.orders import (
    AsyncDeliveryOrder,
    AsyncDeliveryTask,
    AsyncOrder,
    AsyncOrderLabel,
    AsyncSandboxDelivery,
    AsyncStock,
)
from avito.orders.models import OrderStatus
from avito.promotion import (
    AsyncAutostrategyCampaign,
    AsyncBbipPromotion,
    AsyncCpaAuction,
    AsyncPromotionOrder,
    AsyncTargetActionPricing,
    AsyncTrxPromotion,
)
from avito.promotion.models import PromotionOrderServiceStatus, PromotionOrderStatus
from avito.ratings import AsyncRatingProfile, AsyncReview, AsyncReviewAnswer
from avito.realty import (
    AsyncRealtyAnalyticsReport,
    AsyncRealtyBooking,
    AsyncRealtyListing,
    AsyncRealtyPricing,
)
from avito.summary import (
    AccountHealthSummary,
    CapabilityDiscoveryResult,
    CapabilityInfo,
    ChatSummary,
    ListingHealthItem,
    ListingHealthSummary,
    OrderSummary,
    PromotionSummary,
    ReviewSummary,
    SummaryUnavailableSection,
)
from avito.tariffs import AsyncTariff

SummaryDate = date | datetime | str


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
        """Initialize AsyncAvitoClient."""
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
        """Run the from transport helper."""
        client = cls.__new__(cls)
        client._closed = False
        client._entered = True
        client._settings = settings
        client._external_http_client = None
        client._auth_provider = auth_provider
        client._transport = transport
        return client

    async def __aenter__(self) -> AsyncAvitoClient:
        """Enter the async context manager."""
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
        """Exit the async context manager."""
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

    async def business_summary(
        self,
        *,
        user_id: int | str | None = None,
        listing_limit: int = 50,
        listing_page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> AccountHealthSummary:
        """Возвращает итоговую async read-only сводку бизнеса."""

        return await self.account_health(
            user_id=user_id,
            listing_limit=listing_limit,
            listing_page_size=listing_page_size,
            date_from=date_from,
            date_to=date_to,
        )

    async def account_health(
        self,
        *,
        user_id: int | str | None = None,
        listing_limit: int = 50,
        listing_page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> AccountHealthSummary:
        """Возвращает итоговую async read-only health-сводку аккаунта."""

        resolved_user_id = await self._resolve_user_id(user_id)
        async with asyncio.TaskGroup() as task_group:
            balance_task = task_group.create_task(self.account(resolved_user_id).get_balance())
            listings_task = task_group.create_task(
                self.listing_health(
                    user_id=resolved_user_id,
                    limit=listing_limit,
                    page_size=listing_page_size,
                    date_from=date_from,
                    date_to=date_to,
                )
            )
            chats_task = task_group.create_task(
                _safe_summary_async(
                    "chats",
                    lambda: self.chat_summary(user_id=resolved_user_id),
                )
            )
            orders_task = task_group.create_task(
                _safe_summary_async("orders", self.order_summary)
            )
            reviews_task = task_group.create_task(
                _safe_summary_async("reviews", self.review_summary)
            )
        balance = balance_task.result()
        listings = listings_task.result()
        item_ids = [item.item_id for item in listings.items if item.item_id is not None]
        promotion, promotion_unavailable = await _safe_summary_async(
            "promotion",
            lambda: self.promotion_summary(item_ids=item_ids),
        )
        chats, chats_unavailable = chats_task.result()
        orders, orders_unavailable = orders_task.result()
        reviews, reviews_unavailable = reviews_task.result()
        unavailable_sections = [
            *listings.unavailable_sections,
            *chats_unavailable,
            *orders_unavailable,
            *reviews_unavailable,
            *promotion_unavailable,
        ]
        if chats is not None:
            unavailable_sections.extend(chats.unavailable_sections)
        if orders is not None:
            unavailable_sections.extend(orders.unavailable_sections)
        if reviews is not None:
            unavailable_sections.extend(reviews.unavailable_sections)
        if promotion is not None:
            unavailable_sections.extend(promotion.unavailable_sections)
        return AccountHealthSummary(
            user_id=resolved_user_id,
            balance_total=balance.total,
            balance_real=balance.real,
            balance_bonus=balance.bonus,
            listings=listings,
            chats=chats,
            orders=orders,
            reviews=reviews,
            promotion=promotion,
            unavailable_sections=unavailable_sections,
        )

    async def listing_health(
        self,
        *,
        user_id: int | str | None = None,
        limit: int = 50,
        page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> ListingHealthSummary:
        """Возвращает async health-сводку объявлений."""

        resolved_user_id = await self._resolve_user_id(user_id)
        listing_collection = await self.ad(user_id=resolved_user_id).list(
            limit=limit,
            page_size=page_size,
        )
        listings = await listing_collection.materialize()
        item_ids = [item.item_id for item in listings if item.item_id is not None]
        stats_by_item_id: dict[int, ListingStats] = {}
        calls_by_item_id: dict[int, CallStats] = {}
        spendings_by_item_id: dict[int, SpendingRecord] = {}
        unavailable_sections: list[SummaryUnavailableSection] = []
        if item_ids:
            stats_date_from, stats_date_to = _default_summary_date_range(date_from, date_to)
            async with asyncio.TaskGroup() as task_group:
                item_stats_task = task_group.create_task(
                    self.ad_stats(user_id=resolved_user_id).get_item_stats(
                        item_ids=item_ids,
                        date_from=stats_date_from,
                        date_to=stats_date_to,
                    )
                )
                calls_stats_task = task_group.create_task(
                    self.ad_stats(user_id=resolved_user_id).get_calls_stats(
                        item_ids=item_ids,
                        date_from=stats_date_from,
                        date_to=stats_date_to,
                    )
                )
                spendings_task = task_group.create_task(
                    _safe_summary_async(
                        "spendings",
                        lambda: self.ad_stats(user_id=resolved_user_id).get_account_spendings(
                            item_ids=item_ids,
                            date_from=stats_date_from,
                            date_to=stats_date_to,
                            spending_types=["promotion", "presence", "commission", "rest"],
                            grouping="day",
                        ),
                    )
                )
            item_stats = item_stats_task.result()
            calls_stats = calls_stats_task.result()
            spendings, spendings_unavailable = spendings_task.result()
            stats_by_item_id = {
                stats.item_id: stats for stats in item_stats.items if stats.item_id is not None
            }
            calls_by_item_id = {
                stats.item_id: stats for stats in calls_stats.items if stats.item_id is not None
            }
            unavailable_sections.extend(spendings_unavailable)
            if spendings is not None:
                spendings_by_item_id = {
                    item.item_id: item for item in spendings.items if item.item_id is not None
                }
        health_items = [
            ListingHealthItem(
                item_id=listing.item_id,
                title=listing.title,
                status=listing.status,
                price=listing.price,
                url=listing.url,
                is_visible=listing.is_visible,
                views=stats_by_item_id[listing.item_id].views
                if listing.item_id in stats_by_item_id
                else None,
                contacts=stats_by_item_id[listing.item_id].contacts
                if listing.item_id in stats_by_item_id
                else None,
                favorites=stats_by_item_id[listing.item_id].favorites
                if listing.item_id in stats_by_item_id
                else None,
                calls=calls_by_item_id[listing.item_id].calls
                if listing.item_id in calls_by_item_id
                else None,
                spendings=spendings_by_item_id[listing.item_id].amount
                if listing.item_id in spendings_by_item_id
                else None,
            )
            for listing in listings
        ]
        loaded_listings = len(health_items)
        total_listings = listing_collection.source_total
        listing_limit = limit if limit >= 0 else None
        expected_loaded = (
            min(total_listings, listing_limit)
            if total_listings is not None and listing_limit is not None
            else total_listings
        )
        return ListingHealthSummary(
            user_id=resolved_user_id,
            items=health_items,
            loaded_listings=loaded_listings,
            total_listings=total_listings,
            listing_limit=listing_limit,
            is_complete=expected_loaded is not None and loaded_listings >= expected_loaded,
            visible_listings=sum(1 for item in health_items if item.is_visible is True),
            active_listings=sum(1 for item in health_items if item.status is ListingStatus.ACTIVE),
            total_views=_sum_optional_int(item.views for item in health_items),
            total_contacts=_sum_optional_int(item.contacts for item in health_items),
            total_favorites=_sum_optional_int(item.favorites for item in health_items),
            total_calls=_sum_optional_int(item.calls for item in health_items),
            total_spendings=_sum_optional_float(item.spendings for item in health_items),
            unavailable_sections=unavailable_sections,
        )

    async def chat_summary(self, *, user_id: int | str | None = None) -> ChatSummary:
        """Возвращает итоговую async read-only сводку по чатам."""

        resolved_user_id = await self._resolve_user_id(user_id)
        result = await self.chat(user_id=resolved_user_id).list()
        unread_counts = [item.unread_count or 0 for item in result.items]
        return ChatSummary(
            user_id=resolved_user_id,
            total_chats=result.total if result.total is not None else len(result.items),
            unread_chats=sum(1 for count in unread_counts if count > 0),
            unread_messages=sum(unread_counts),
        )

    async def order_summary(self) -> OrderSummary:
        """Возвращает итоговую async read-only сводку по заказам."""

        result = await self.order().list()
        return OrderSummary(
            total_orders=result.total if result.total is not None else len(result.items),
            active_orders=sum(
                1
                for item in result.items
                if item.status is not None and item.status is not OrderStatus.UNKNOWN
            ),
        )

    async def review_summary(self) -> ReviewSummary:
        """Возвращает итоговую async read-only сводку по отзывам."""

        reviews_error: AvitoError | None = None
        try:
            reviews = await self.review().list()
        except AvitoError as error:
            reviews = None
            reviews_error = error
        rating = await self.rating_profile().get()
        scores = [item.score for item in reviews.items if item.score is not None] if reviews else []
        average_score = sum(scores) / len(scores) if scores else None
        unavailable_sections = (
            [_summary_unavailable_section("reviews", reviews_error)]
            if reviews_error is not None
            else []
        )
        return ReviewSummary(
            total_reviews=(
                reviews.total
                if reviews is not None and reviews.total is not None
                else rating.reviews_count
                if reviews is None
                else len(reviews.items)
            ),
            average_score=average_score if reviews is not None else rating.score,
            unanswered_reviews=(
                sum(1 for item in reviews.items if item.can_answer is True)
                if reviews is not None
                else None
            ),
            rating_score=rating.score,
            unavailable_sections=unavailable_sections,
        )

    async def promotion_summary(self, *, item_ids: list[int] | None = None) -> PromotionSummary:
        """Возвращает итоговую async read-only сводку по продвижению."""

        if item_ids:
            async with asyncio.TaskGroup() as task_group:
                orders_task = task_group.create_task(
                    self.promotion_order().list_orders(item_ids=item_ids)
                )
                services_task = task_group.create_task(
                    self.promotion_order().list_services(item_ids=item_ids)
                )
            orders = orders_task.result()
            services = services_task.result()
        else:
            orders = await self.promotion_order().list_orders(item_ids=item_ids)
            services = None
        service_items = services.items if services is not None else []
        return PromotionSummary(
            total_orders=len(orders.items),
            active_orders=sum(
                1
                for item in orders.items
                if item.status
                in {
                    PromotionOrderStatus.INITIALIZED,
                    PromotionOrderStatus.WAITING,
                    PromotionOrderStatus.IN_PROCESS,
                    PromotionOrderStatus.PROCESSED,
                    PromotionOrderStatus.APPLIED,
                    PromotionOrderStatus.AUTO,
                    PromotionOrderStatus.CREATED,
                    PromotionOrderStatus.MANUAL,
                    PromotionOrderStatus.PARTIAL,
                }
            ),
            total_services=len(service_items),
            available_services=sum(
                1
                for item in service_items
                if item.status
                in {
                    PromotionOrderServiceStatus.ACTIVE,
                    PromotionOrderServiceStatus.AVAILABLE,
                }
            ),
        )

    def capabilities(self) -> CapabilityDiscoveryResult:
        """Возвращает справочник возможностей SDK без сетевых probe-запросов."""

        has_user_id = self.debug_info().user_id is not None
        configured_reasons = ["Настроены OAuth client_id и client_secret."]
        user_id_reasons = (
            ["Настроен user_id или его можно получить через профиль."]
            if has_user_id
            else [
                "Для части операций SDK получит user_id через профиль или потребует явный аргумент."
            ]
        )
        return CapabilityDiscoveryResult(
            items=[
                CapabilityInfo(
                    operation="account_health",
                    factory_method="account_health",
                    is_available=True,
                    reasons=configured_reasons + user_id_reasons,
                    possible_error_codes=[400, 401, 403, 429],
                ),
                CapabilityInfo(
                    operation="listing_health",
                    factory_method="listing_health",
                    is_available=True,
                    reasons=user_id_reasons
                    + [
                        "400 возможен при неверном фильтре, 403 при недоступном аккаунте, 429 при лимите."
                    ],
                    possible_error_codes=[400, 403, 429],
                ),
                CapabilityInfo(
                    operation="chat_summary",
                    factory_method="chat_summary",
                    is_available=True,
                    reasons=user_id_reasons
                    + ["403 возможен без доступа к мессенджеру, 429 при лимите запросов."],
                    possible_error_codes=[400, 403, 429],
                ),
                CapabilityInfo(
                    operation="order_summary",
                    factory_method="order_summary",
                    is_available=True,
                    reasons=["Операция использует read-only список заказов."],
                    possible_error_codes=[400, 403, 429],
                ),
                CapabilityInfo(
                    operation="review_summary",
                    factory_method="review_summary",
                    is_available=True,
                    reasons=["Операция использует список отзывов и рейтинг профиля."],
                    possible_error_codes=[400, 403, 429],
                ),
                CapabilityInfo(
                    operation="promotion_summary",
                    factory_method="promotion_summary",
                    is_available=True,
                    reasons=[
                        "Сводка заявок доступна без item_ids; сводка услуг требует item_ids.",
                        "403 возможен без доступа к продвижению, 429 при лимите запросов.",
                    ],
                    possible_error_codes=[400, 403, 429],
                ),
            ]
        )

    def account(self, user_id: int | str | None = None) -> AsyncAccount:
        """Создает async-доменный объект аккаунта."""

        return AsyncAccount(self._require_transport(), user_id=user_id)

    def account_hierarchy(self, user_id: int | str | None = None) -> AsyncAccountHierarchy:
        """Создает async-доменный объект иерархии аккаунта."""

        return AsyncAccountHierarchy(self._require_transport(), user_id=user_id)

    def ad(self, item_id: int | str | None = None, user_id: int | str | None = None) -> AsyncAd:
        """Создает async-доменный объект объявления."""

        return AsyncAd(self._require_transport(), item_id=item_id, user_id=user_id)

    def ad_stats(
        self, item_id: int | str | None = None, user_id: int | str | None = None
    ) -> AsyncAdStats:
        """Создает async-доменный объект статистики объявления."""

        return AsyncAdStats(self._require_transport(), item_id=item_id, user_id=user_id)

    def ad_promotion(
        self, item_id: int | str | None = None, user_id: int | str | None = None
    ) -> AsyncAdPromotion:
        """Создает async-доменный объект продвижения объявления."""

        return AsyncAdPromotion(self._require_transport(), item_id=item_id, user_id=user_id)

    def autoload_profile(self, user_id: int | str | None = None) -> AsyncAutoloadProfile:
        """Создает async-доменный объект профиля автозагрузки."""

        return AsyncAutoloadProfile(self._require_transport(), user_id=user_id)

    def autoload_report(
        self, report_id: int | str | None = None
    ) -> AsyncAutoloadReport:
        """Создает async-доменный объект отчета автозагрузки."""

        return AsyncAutoloadReport(self._require_transport(), report_id=report_id)

    def autoload_archive(
        self, report_id: int | str | None = None
    ) -> AsyncAutoloadArchive:
        """Создает async-доменный объект архивных операций автозагрузки."""

        return AsyncAutoloadArchive(self._require_transport(), report_id=report_id)

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

    def order(self) -> AsyncOrder:
        """Создает async-доменный объект заказа."""

        return AsyncOrder(self._require_transport())

    def order_label(self, task_id: int | str | None = None) -> AsyncOrderLabel:
        """Создает async-доменный объект этикетки заказа."""

        return AsyncOrderLabel(self._require_transport(), task_id=task_id)

    def delivery_order(self) -> AsyncDeliveryOrder:
        """Создает async-доменный объект доставки."""

        return AsyncDeliveryOrder(self._require_transport())

    def sandbox_delivery(self) -> AsyncSandboxDelivery:
        """Создает async-доменный объект песочницы доставки."""

        return AsyncSandboxDelivery(self._require_transport())

    def delivery_task(self, task_id: int | str | None = None) -> AsyncDeliveryTask:
        """Создает async-доменный объект задачи доставки."""

        return AsyncDeliveryTask(self._require_transport(), task_id=task_id)

    def stock(self) -> AsyncStock:
        """Создает async-доменный объект остатков."""

        return AsyncStock(self._require_transport())

    def autoteka_vehicle(
        self,
        vehicle_id: int | str | None = None,
    ) -> AsyncAutotekaVehicle:
        """Создает async-доменный объект автомобиля Автотеки."""

        return AsyncAutotekaVehicle(self._require_transport(), vehicle_id=vehicle_id)

    def autoteka_report(
        self,
        report_id: int | str | None = None,
    ) -> AsyncAutotekaReport:
        """Создает async-доменный объект отчетов Автотеки."""

        return AsyncAutotekaReport(self._require_transport(), report_id=report_id)

    def autoteka_monitoring(self) -> AsyncAutotekaMonitoring:
        """Создает async-доменный объект мониторинга Автотеки."""

        return AsyncAutotekaMonitoring(self._require_transport())

    def autoteka_scoring(
        self,
        scoring_id: int | str | None = None,
    ) -> AsyncAutotekaScoring:
        """Создает async-доменный объект скоринга Автотеки."""

        return AsyncAutotekaScoring(self._require_transport(), scoring_id=scoring_id)

    def autoteka_valuation(self) -> AsyncAutotekaValuation:
        """Создает async-доменный объект оценки автомобиля Автотеки."""

        return AsyncAutotekaValuation(self._require_transport())

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
        """Build auth provider."""
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
        """Ensure open."""
        if self._closed:
            raise ClientClosedError("Клиент закрыт; создайте новый AsyncAvitoClient.")

    def _ensure_ready(self) -> None:
        """Ensure ready."""
        self._ensure_open()
        if not self._entered:
            raise RuntimeError(
                "AsyncAvitoClient не инициализирован: используйте 'async with' "
                "или дождитесь '__aenter__'."
            )

    def _require_transport(self) -> AsyncTransport:
        """Validate required transport."""
        self._ensure_ready()
        if self._transport is None:
            raise RuntimeError("AsyncAvitoClient не инициализирован: используйте 'async with'.")
        return self._transport

    async def _resolve_user_id(self, user_id: int | str | None = None) -> int:
        """Resolve user id."""
        return await AsyncAccount(self._require_transport(), user_id=user_id)._resolve_user_id(
            user_id
        )


__all__ = ("AsyncAvitoClient",)
