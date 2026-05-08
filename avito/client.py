"""Высокоуровневый единый клиент SDK Avito."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from types import TracebackType

from avito.accounts import Account, AccountHierarchy
from avito.ads import Ad, AdPromotion, AdStats, AutoloadArchive, AutoloadProfile, AutoloadReport
from avito.ads.models import CallStats, ListingStats, ListingStatus, SpendingRecord
from avito.auth import AlternateTokenClient, AuthProvider, TokenClient
from avito.autoteka import (
    AutotekaMonitoring,
    AutotekaReport,
    AutotekaScoring,
    AutotekaValuation,
    AutotekaVehicle,
)
from avito.config import AvitoSettings
from avito.core import Transport, TransportDebugInfo
from avito.core.exceptions import AvitoError, ClientClosedError
from avito.cpa import CallTrackingCall, CpaArchive, CpaCall, CpaChat, CpaLead
from avito.jobs import Application, JobDictionary, JobWebhook, Resume, Vacancy
from avito.messenger import Chat, ChatMedia, ChatMessage, ChatWebhook, SpecialOfferCampaign
from avito.orders import DeliveryOrder, DeliveryTask, Order, OrderLabel, SandboxDelivery, Stock
from avito.orders.models import OrderStatus
from avito.promotion import (
    AutostrategyCampaign,
    BbipPromotion,
    CpaAuction,
    PromotionOrder,
    TargetActionPricing,
    TrxPromotion,
)
from avito.promotion.models import PromotionOrderServiceStatus, PromotionOrderStatus
from avito.ratings import RatingProfile, Review, ReviewAnswer
from avito.realty import RealtyAnalyticsReport, RealtyBooking, RealtyListing, RealtyPricing
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
from avito.tariffs import Tariff

SummaryDate = date | datetime | str


def _default_summary_date_range(
    date_from: SummaryDate | None,
    date_to: SummaryDate | None,
) -> tuple[SummaryDate, SummaryDate]:
    if date_from is not None and date_to is not None:
        return date_from, date_to
    today = date.today().isoformat()
    return date_from or today, date_to or today


def _sum_optional_int(values: Iterable[int | None]) -> int | None:
    resolved = [value for value in values if value is not None]
    if not resolved:
        return None
    return sum(resolved)


def _sum_optional_float(values: Iterable[float | None]) -> float | None:
    resolved = [value for value in values if value is not None]
    if not resolved:
        return None
    return sum(resolved)


def _summary_unavailable_section(section: str, error: AvitoError) -> SummaryUnavailableSection:
    return SummaryUnavailableSection(
        section=section,
        operation=error.operation,
        status_code=error.status_code,
        retry_after=error.retry_after,
        message=error.message,
    )


def _safe_summary[SummaryT](
    section: str,
    factory: Callable[[], SummaryT],
) -> tuple[SummaryT | None, list[SummaryUnavailableSection]]:
    try:
        return factory(), []
    except AvitoError as error:
        return None, [_summary_unavailable_section(section, error)]


async def _safe_summary_async[SummaryT](
    section: str,
    factory: Callable[[], Awaitable[SummaryT]],
) -> tuple[SummaryT | None, list[SummaryUnavailableSection]]:
    try:
        return await factory(), []
    except AvitoError as error:
        return None, [_summary_unavailable_section(section, error)]


class AvitoClient:
    """Единственная публичная точка входа SDK с фабриками доменных объектов.

    Пример:
        ```python
        from avito import AvitoClient

        with AvitoClient() as avito:
            profile = avito.account().get_self()
            ad = avito.ad(42).get()
        ```
    """

    def __init__(
        self,
        settings: AvitoSettings | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        if client_id is not None or client_secret is not None:
            from avito.auth.settings import AuthSettings

            auth = AuthSettings(client_id=client_id, client_secret=client_secret)
            settings = AvitoSettings(auth=auth)
        self._closed = False
        self._settings = (settings or AvitoSettings.from_env()).validate_required()
        self._auth_provider = self._build_auth_provider()
        self._transport = Transport(self.settings, auth_provider=self.auth_provider)

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> AvitoClient:
        """Создает клиент из переменных окружения и optional `.env` файла."""

        return cls(AvitoSettings.from_env(env_file=env_file))

    @classmethod
    def _from_transport(
        cls,
        settings: AvitoSettings,
        *,
        transport: Transport,
        auth_provider: AuthProvider,
    ) -> AvitoClient:
        client = cls.__new__(cls)
        client._closed = False
        client._settings = settings
        client._auth_provider = auth_provider
        client._transport = transport
        return client

    @property
    def settings(self) -> AvitoSettings:
        """Возвращает read-only настройки клиента."""

        return self._settings

    @property
    def auth_provider(self) -> AuthProvider:
        """Возвращает read-only auth provider клиента."""

        return self._auth_provider

    @property
    def transport(self) -> Transport:
        """Возвращает read-only transport клиента."""

        return self._transport

    def auth(self) -> AuthProvider:
        """Возвращает объект аутентификации и token-flow операций.

        Raises: AvitoError с полями operation, status, request_id, attempt, method и endpoint.
        """

        self._ensure_open()
        return self.auth_provider

    def debug_info(self) -> TransportDebugInfo:
        """Возвращает безопасный снимок transport-настроек для диагностики."""

        return self._require_transport().debug_info()

    def business_summary(
        self,
        *,
        user_id: int | str | None = None,
        listing_limit: int = 50,
        listing_page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> AccountHealthSummary:
        """Возвращает итоговую read-only сводку бизнеса.

        Метод является совместимым именем для `account_health()` и не содержит отдельной логики.
        """

        return self.account_health(
            user_id=user_id,
            listing_limit=listing_limit,
            listing_page_size=listing_page_size,
            date_from=date_from,
            date_to=date_to,
        )

    def account_health(
        self,
        *,
        user_id: int | str | None = None,
        listing_limit: int = 50,
        listing_page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> AccountHealthSummary:
        """Возвращает итоговую read-only health-сводку аккаунта."""

        resolved_user_id = self._resolve_user_id(user_id)
        balance = self.account(resolved_user_id).get_balance()
        listings = self.listing_health(
            user_id=resolved_user_id,
            limit=listing_limit,
            page_size=listing_page_size,
            date_from=date_from,
            date_to=date_to,
        )
        item_ids = [item.item_id for item in listings.items if item.item_id is not None]
        chats, chats_unavailable = _safe_summary(
            "chats",
            lambda: self.chat_summary(user_id=resolved_user_id),
        )
        orders, orders_unavailable = _safe_summary("orders", self.order_summary)
        reviews, reviews_unavailable = _safe_summary("reviews", self.review_summary)
        promotion, promotion_unavailable = _safe_summary(
            "promotion",
            lambda: self.promotion_summary(item_ids=item_ids),
        )
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

    def listing_health(
        self,
        *,
        user_id: int | str | None = None,
        limit: int = 50,
        page_size: int = 50,
        date_from: SummaryDate | None = None,
        date_to: SummaryDate | None = None,
    ) -> ListingHealthSummary:
        """Возвращает health-сводку объявлений без ручного сопоставления статистики."""

        resolved_user_id = self._resolve_user_id(user_id)
        listing_collection = self.ad(user_id=resolved_user_id).list(
            limit=limit,
            page_size=page_size,
        )
        listings = listing_collection.materialize()
        item_ids = [item.item_id for item in listings if item.item_id is not None]
        stats_by_item_id: dict[int, ListingStats] = {}
        calls_by_item_id: dict[int, CallStats] = {}
        spendings_by_item_id: dict[int, SpendingRecord] = {}
        unavailable_sections: list[SummaryUnavailableSection] = []
        if item_ids:
            stats_date_from, stats_date_to = _default_summary_date_range(date_from, date_to)
            item_stats = self.ad_stats(user_id=resolved_user_id).get_item_stats(
                item_ids=item_ids,
                date_from=stats_date_from,
                date_to=stats_date_to,
            )
            calls_stats = self.ad_stats(user_id=resolved_user_id).get_calls_stats(
                item_ids=item_ids,
                date_from=stats_date_from,
                date_to=stats_date_to,
            )
            stats_by_item_id = {
                stats.item_id: stats for stats in item_stats.items if stats.item_id is not None
            }
            calls_by_item_id = {
                stats.item_id: stats for stats in calls_stats.items if stats.item_id is not None
            }
            try:
                spendings = self.ad_stats(user_id=resolved_user_id).get_account_spendings(
                    item_ids=item_ids,
                    date_from=stats_date_from,
                    date_to=stats_date_to,
                    spending_types=["promotion", "presence", "commission", "rest"],
                    grouping="day",
                )
            except AvitoError as error:
                unavailable_sections.append(_summary_unavailable_section("spendings", error))
            else:
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

    def chat_summary(self, *, user_id: int | str | None = None) -> ChatSummary:
        """Возвращает итоговую read-only сводку по чатам."""

        resolved_user_id = self._resolve_user_id(user_id)
        result = self.chat(user_id=resolved_user_id).list()
        unread_counts = [item.unread_count or 0 for item in result.items]
        return ChatSummary(
            user_id=resolved_user_id,
            total_chats=result.total if result.total is not None else len(result.items),
            unread_chats=sum(1 for count in unread_counts if count > 0),
            unread_messages=sum(unread_counts),
        )

    def order_summary(self) -> OrderSummary:
        """Возвращает итоговую read-only сводку по заказам."""

        result = self.order().list()
        return OrderSummary(
            total_orders=result.total if result.total is not None else len(result.items),
            active_orders=sum(
                1
                for item in result.items
                if item.status is not None and item.status is not OrderStatus.UNKNOWN
            ),
        )

    def review_summary(self) -> ReviewSummary:
        """Возвращает итоговую read-only сводку по отзывам."""

        reviews_error: AvitoError | None = None
        try:
            reviews = self.review().list()
        except AvitoError as error:
            reviews = None
            reviews_error = error
        rating = self.rating_profile().get()
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

    def promotion_summary(self, *, item_ids: list[int] | None = None) -> PromotionSummary:
        """Возвращает итоговую read-only сводку по продвижению."""

        orders = self.promotion_order().list_orders(item_ids=item_ids)
        services = self.promotion_order().list_services(item_ids=item_ids) if item_ids else None
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
        """Возвращает справочник возможностей SDK и типовых причин отказов API."""

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

    def close(self) -> None:
        """Закрывает внутренние HTTP-клиенты SDK."""

        if self._closed:
            return
        self.transport.close()
        self.auth_provider.close()
        self._closed = True

    def __enter__(self) -> AvitoClient:
        """Открывает клиент как контекстный менеджер."""

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Закрывает клиент при выходе из контекстного менеджера."""

        self.close()

    def _build_auth_provider(self) -> AuthProvider:
        return AuthProvider(
            self.settings.auth,
            token_client=TokenClient(self.settings.auth, sdk_settings=self.settings),
            alternate_token_client=AlternateTokenClient(
                self.settings.auth,
                sdk_settings=self.settings,
            ),
            autoteka_token_client=TokenClient(
                self.settings.auth,
                token_url=self.settings.auth.autoteka_token_url,
                sdk_settings=self.settings,
            ),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClientClosedError("Клиент закрыт; создайте новый AvitoClient.")

    def _require_transport(self) -> Transport:
        self._ensure_open()
        return self.transport

    def _resolve_user_id(self, user_id: int | str | None = None) -> int:
        return Account(self._require_transport(), user_id=user_id)._resolve_user_id(user_id)

    def account(self, user_id: int | str | None = None) -> Account:
        """Создает доменный объект аккаунта."""

        return Account(self._require_transport(), user_id=user_id)

    def account_hierarchy(self, user_id: int | str | None = None) -> AccountHierarchy:
        """Создает доменный объект иерархии аккаунта."""

        return AccountHierarchy(self._require_transport(), user_id=user_id)

    def ad(self, item_id: int | str | None = None, user_id: int | str | None = None) -> Ad:
        """Создает доменный объект объявления."""

        return Ad(self._require_transport(), item_id=item_id, user_id=user_id)

    def ad_stats(
        self, item_id: int | str | None = None, user_id: int | str | None = None
    ) -> AdStats:
        """Создает доменный объект статистики объявления."""

        return AdStats(self._require_transport(), item_id=item_id, user_id=user_id)

    def ad_promotion(
        self, item_id: int | str | None = None, user_id: int | str | None = None
    ) -> AdPromotion:
        """Создает доменный объект продвижения объявления."""

        return AdPromotion(self._require_transport(), item_id=item_id, user_id=user_id)

    def autoload_profile(self, user_id: int | str | None = None) -> AutoloadProfile:
        """Создает доменный объект профиля автозагрузки."""

        return AutoloadProfile(self._require_transport(), user_id=user_id)

    def autoload_report(self, report_id: int | str | None = None) -> AutoloadReport:
        """Создает доменный объект отчета автозагрузки."""

        return AutoloadReport(self._require_transport(), report_id=report_id)

    def autoload_archive(self, report_id: int | str | None = None) -> AutoloadArchive:
        """Создает доменный объект архивных операций автозагрузки."""

        return AutoloadArchive(self._require_transport(), report_id=report_id)

    def chat(self, chat_id: int | str | None = None, *, user_id: int | str | None = None) -> Chat:
        """Создает доменный объект чата."""

        return Chat(self._require_transport(), chat_id=chat_id, user_id=user_id)

    def chat_message(
        self,
        message_id: int | str | None = None,
        *,
        chat_id: int | str | None = None,
        user_id: int | str | None = None,
    ) -> ChatMessage:
        """Создает доменный объект сообщения чата."""

        return ChatMessage(
            self._require_transport(),
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
        )

    def chat_webhook(self) -> ChatWebhook:
        """Создает доменный объект webhook мессенджера."""

        return ChatWebhook(self._require_transport())

    def chat_media(self, *, user_id: int | str | None = None) -> ChatMedia:
        """Создает доменный объект медиа мессенджера."""

        return ChatMedia(self._require_transport(), user_id=user_id)

    def special_offer_campaign(self, campaign_id: int | str | None = None) -> SpecialOfferCampaign:
        """Создает доменный объект рассылки спецпредложений."""

        return SpecialOfferCampaign(self._require_transport(), campaign_id=campaign_id)

    def promotion_order(self, order_id: int | str | None = None) -> PromotionOrder:
        """Создает доменный объект заявки на продвижение."""

        return PromotionOrder(self._require_transport(), order_id=order_id)

    def bbip_promotion(self, item_id: int | str | None = None) -> BbipPromotion:
        """Создает доменный объект BBIP-продвижения."""

        return BbipPromotion(self._require_transport(), item_id=item_id)

    def trx_promotion(self, item_id: int | str | None = None) -> TrxPromotion:
        """Создает доменный объект TrxPromo."""

        return TrxPromotion(self._require_transport(), item_id=item_id)

    def cpa_auction(self, item_id: int | str | None = None) -> CpaAuction:
        """Создает доменный объект CPA-аукциона."""

        return CpaAuction(self._require_transport(), item_id=item_id)

    def target_action_pricing(self, item_id: int | str | None = None) -> TargetActionPricing:
        """Создает доменный объект цены целевого действия."""

        return TargetActionPricing(self._require_transport(), item_id=item_id)

    def autostrategy_campaign(self, campaign_id: int | str | None = None) -> AutostrategyCampaign:
        """Создает доменный объект автостратегии."""

        return AutostrategyCampaign(self._require_transport(), campaign_id=campaign_id)

    def order(self) -> Order:
        """Создает доменный объект заказа."""

        return Order(self._require_transport())

    def order_label(self, task_id: int | str | None = None) -> OrderLabel:
        """Создает доменный объект этикетки заказа."""

        return OrderLabel(self._require_transport(), task_id=task_id)

    def delivery_order(self) -> DeliveryOrder:
        """Создает доменный объект доставки."""

        return DeliveryOrder(self._require_transport())

    def sandbox_delivery(self) -> SandboxDelivery:
        """Создает доменный объект песочницы доставки."""

        return SandboxDelivery(self._require_transport())

    def delivery_task(self, task_id: int | str | None = None) -> DeliveryTask:
        """Создает доменный объект задачи доставки."""

        return DeliveryTask(self._require_transport(), task_id=task_id)

    def stock(self) -> Stock:
        """Создает доменный объект остатков."""

        return Stock(self._require_transport())

    def vacancy(self, vacancy_id: int | str | None = None) -> Vacancy:
        """Создает доменный объект вакансии."""

        return Vacancy(self._require_transport(), vacancy_id=vacancy_id)

    def application(self) -> Application:
        """Создает доменный объект отклика."""

        return Application(self._require_transport())

    def resume(self, resume_id: int | str | None = None) -> Resume:
        """Создает доменный объект резюме."""

        return Resume(self._require_transport(), resume_id=resume_id)

    def job_webhook(self) -> JobWebhook:
        """Создает доменный объект webhook раздела Работа."""

        return JobWebhook(self._require_transport())

    def job_dictionary(self, dictionary_id: int | str | None = None) -> JobDictionary:
        """Создает доменный объект словаря Работа."""

        return JobDictionary(self._require_transport(), dictionary_id=dictionary_id)

    def cpa_lead(self) -> CpaLead:
        """Создает доменный объект CPA-лида."""

        return CpaLead(self._require_transport())

    def cpa_chat(self, chat_id: int | str | None = None) -> CpaChat:
        """Создает доменный объект CPA-чата."""

        return CpaChat(self._require_transport(), action_id=chat_id)

    def cpa_call(self) -> CpaCall:
        """Создает доменный объект CPA-звонка."""

        return CpaCall(self._require_transport())

    def cpa_archive(self, call_id: int | str | None = None) -> CpaArchive:
        """Создает доменный объект архивных операций CPA."""

        return CpaArchive(self._require_transport(), call_id=call_id)

    def call_tracking_call(self, call_id: int | str | None = None) -> CallTrackingCall:
        """Создает доменный объект CallTracking."""

        return CallTrackingCall(self._require_transport(), call_id=call_id)

    def autoteka_vehicle(self, vehicle_id: int | str | None = None) -> AutotekaVehicle:
        """Создает доменный объект транспортного средства Автотеки."""

        return AutotekaVehicle(self._require_transport(), vehicle_id=vehicle_id)

    def autoteka_report(self, report_id: int | str | None = None) -> AutotekaReport:
        """Создает доменный объект отчета Автотеки."""

        return AutotekaReport(self._require_transport(), report_id=report_id)

    def autoteka_monitoring(self) -> AutotekaMonitoring:
        """Создает доменный объект мониторинга Автотеки."""

        return AutotekaMonitoring(self._require_transport())

    def autoteka_scoring(self, scoring_id: int | str | None = None) -> AutotekaScoring:
        """Создает доменный объект скоринга Автотеки."""

        return AutotekaScoring(self._require_transport(), scoring_id=scoring_id)

    def autoteka_valuation(self) -> AutotekaValuation:
        """Создает доменный объект оценки Автотеки."""

        return AutotekaValuation(self._require_transport())

    def realty_listing(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> RealtyListing:
        """Создает доменный объект объявления недвижимости."""

        return RealtyListing(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_booking(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> RealtyBooking:
        """Создает доменный объект бронирования недвижимости."""

        return RealtyBooking(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_pricing(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> RealtyPricing:
        """Создает доменный объект цен недвижимости."""

        return RealtyPricing(self._require_transport(), item_id=item_id, user_id=user_id)

    def realty_analytics_report(
        self,
        item_id: int | str | None = None,
        *,
        user_id: int | str | None = None,
    ) -> RealtyAnalyticsReport:
        """Создает доменный объект аналитического отчета недвижимости."""

        return RealtyAnalyticsReport(self._require_transport(), item_id=item_id, user_id=user_id)

    def review(self) -> Review:
        """Создает доменный объект отзыва."""

        return Review(self._require_transport())

    def review_answer(self, answer_id: int | str | None = None) -> ReviewAnswer:
        """Создает доменный объект ответа на отзыв."""

        return ReviewAnswer(self._require_transport(), answer_id=answer_id)

    def rating_profile(self) -> RatingProfile:
        """Создает доменный объект рейтингового профиля."""

        return RatingProfile(self._require_transport())

    def tariff(self, tariff_id: int | str | None = None) -> Tariff:
        """Создает доменный объект тарифа."""

        return Tariff(self._require_transport(), tariff_id=tariff_id)


__all__ = ("AvitoClient",)
