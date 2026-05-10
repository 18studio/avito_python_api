# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

### Added
- Добавлена базовая CLI-оболочка: `avito --help`, `avito --version`, `avito version`,
  `avito help` и единый вход через `python -m avito`.
- Задокументирован первый CLI-контракт: глобальные флаги, режимы вывода,
  разделение stdout/stderr, безопасный JSON/human-рендеринг ошибок и стабильные
  exit codes.
- Добавлены локальные CLI-команды учетных записей: `avito account add`,
  `avito account list`, `avito account use`, `avito account current`,
  `avito account delete` и alias `avito account remove`.
- CLI хранит учетные записи в локальных JSON-файлах с правами доступа к файлам и
  маскирует секреты во всех режимах вывода; первая версия использует plaintext
  storage без OS keychain.
- Для безопасного ввода `client_secret` добавлены скрытый интерактивный prompt и
  `--client-secret-stdin`; `--client-secret` и совместимый `--api-key` оставлены
  для явной автоматизации с учетом риска попадания значения в историю shell.
- Добавлена registry-backed справка `avito help <resource>` и
  `avito help <resource> <action>` для локальных команд, helper workflows,
  aliases и API command candidates без создания `AvitoClient`.
- Добавлена основа сериализации результатов CLI: SDK-модели выводятся через
  публичный `model_dump()` / `to_dict()`, секреты маскируются после
  сериализации, а `PaginatedList` по умолчанию выгружает только ограниченный
  набор страниц.

## [2.1.0] - 2026-05-08

### Added
- Фундамент Async API: `AsyncTransport`, `AsyncAuthProvider`,
  `AsyncOperationExecutor`, `AsyncPaginatedList`, `AsyncAvitoClient` без
  доменных factory-методов; `RateLimitState` вынесен в shared.
- Async-поддержка домена tariffs: `AsyncTariff` (PoC шаблона).
- Async-поддержка домена accounts: AsyncAccount, AsyncAccountHierarchy.
- Async-поддержка домена ads: AsyncAd, AsyncAdStats, AsyncAdPromotion, AsyncAutoloadProfile, AsyncAutoloadReport, AsyncAutoloadArchive.
- Async-поддержка домена autoteka: AsyncAutotekaVehicle, AsyncAutotekaReport, AsyncAutotekaMonitoring, AsyncAutotekaScoring, AsyncAutotekaValuation.
- Async-поддержка домена cpa: AsyncCallTrackingCall, AsyncCpaArchive, AsyncCpaCall, AsyncCpaChat, AsyncCpaLead.
- Async-поддержка домена jobs: AsyncApplication, AsyncJobDictionary, AsyncJobWebhook, AsyncResume, AsyncVacancy.
- Async-поддержка домена messenger: AsyncChat, AsyncChatMedia, AsyncChatMessage, AsyncChatWebhook, AsyncSpecialOfferCampaign.
- Async-поддержка домена orders: AsyncOrder, AsyncOrderLabel, AsyncDeliveryOrder, AsyncSandboxDelivery, AsyncDeliveryTask, AsyncStock.
- Async-поддержка домена promotion: AsyncPromotionOrder, AsyncBbipPromotion, AsyncTrxPromotion, AsyncCpaAuction, AsyncTargetActionPricing, AsyncAutostrategyCampaign.
- Async-поддержка домена ratings: AsyncRatingProfile, AsyncReview, AsyncReviewAnswer.
- Async-поддержка домена realty: AsyncRealtyAnalyticsReport, AsyncRealtyBooking, AsyncRealtyListing, AsyncRealtyPricing.
- Async convenience methods для `AsyncAvitoClient`: `business_summary`, `account_health`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`, `promotion_summary`, `capabilities`.
- Добавлен `ClientClosedError` для вызовов после `AvitoClient.close()`.

### Deprecated
- Env alias `AVITO_SECRET` для `AVITO_CLIENT_SECRET` устарел и теперь эмитирует `DeprecationWarning`; используйте `AVITO_CLIENT_SECRET`.
- Архивные CPA-методы `CpaArchive.get_call`, `CpaArchive.get_balance_info`, `CpaArchive.get_call_by_id` и режим `CpaChat.list(version=1)` теперь эмитируют `DeprecationWarning` при первом вызове; используйте `call_tracking_call().download`, `cpa_lead().get_balance_info`, `call_tracking_call().get` и `cpa_chat().list(version=2)`.
- Архивные методы автозагрузки `AutoloadArchive.get_profile`, `AutoloadArchive.save_profile`, `AutoloadArchive.get_last_completed_report`, `AutoloadArchive.get_report` теперь эмитируют `DeprecationWarning` при первом вызове; используйте `autoload_profile().get`, `autoload_profile().save`, `autoload_report().get_last_completed` и `autoload_report().get`.

### Changed
- Централизовано выполнение схемы `request + map` через `Transport.request_public_model`.
- Убраны прямые обращения доменных клиентов к `request_json` и приватному `Transport._auth_provider`.
- Секционные клиенты переведены на `@dataclass(slots=True, frozen=True)`.
- Иерархия исключений упрощена до frozen dataclass без кастомного `__setattr__`.
- `AvitoClient.settings`, `AvitoClient.auth_provider` и `AvitoClient.transport` стали read-only свойствами; для тестов используйте `AvitoClient._from_transport(...)`.
- OAuth token flow переведен на общий `Transport` без прямого `httpx.Client().post(...)`; ошибки OAuth продолжают приходить как `AuthenticationError`.
- Публичные сигнатуры `accounts`, `ads`, `autoteka`, `cpa`, `jobs`, `messenger`, `orders`, `promotion`, `ratings` и `realty` переведены с `request`-DTO на keyword-only примитивы и коллекции.
- Swagger-bound public methods теперь принимают per-operation overrides `timeout` и `retry`; `retry="enabled"` форсирует retry, `retry="disabled"` запрещает retry для конкретного вызова.
- `Review.list`, `AutotekaMonitoring.get_monitoring_reg_actions`, `Vacancy.list`, `Vacancy.get`, `Application.get_ids` и `Resume.list` больше не принимают internal query DTO в публичных сигнатурах; передавайте `page`, `offset`, `limit`, `query`, `vacancy_id` и `updated_at_from` напрямую.
- Promotion input модели `BbipItem`, `TrxItem` и `CpaAuctionBidInput`, а также jobs-модель `ApplicationViewedItem` оформлены как публичные frozen dataclass-модели без наследования от internal `RequestModel`.
- Transport получил поддержку `Idempotency-Key`; публичные write-методы во всех доменах принимают `idempotency_key`, а dry-run/write-контракт promotion покрыт тестами.
- Во всех доменных пакетах добавлены `enums.py`; `accounts`, `ads`, `autoteka`, `jobs`, `messenger`, `orders`, `promotion`, `ratings`, `realty` и `tariffs` переведены на typed enums с fallback на `UNKNOWN` и warning-логом ровно один раз на неизвестное upstream-значение.
- `CpaCallStatusId` получил `UNKNOWN`; неизвестный upstream `statusId` больше не превращается в `None` и логирует warning один раз на процесс.
- **BREAKING:** `AccountHierarchy.list_items_by_employee(...)` теперь требует `category_id` и отправляет Swagger body `employeeId/categoryId/lastItemId`; старые `limit`/`offset` не входят в контракт `/listItemsByEmployeeIdV1`.
- **BREAKING:** статистические методы `AdStats.get_item_stats(...)`, `get_calls_stats(...)`, `get_item_analytics(...)` и `get_account_spendings(...)` теперь требуют обязательные поля периода и параметры, описанные в Swagger requestBody.
- **BREAKING:** `AdPromotion.apply_vas(...)` принимает `vas_id` для legacy v1 endpoint, а `apply_vas_direct(...)` принимает `slugs`; payload больше не использует внутренний ключ `codes`.
- **BREAKING:** CPA methods now match Swagger request bodies: complaints send `message`, balanceInfo sends JSON string `"{}"`, chats/phones/calls list methods require `limit`/`offset` or `limit` fields declared by Swagger.
- **BREAKING:** Autoteka request bodies now match Swagger: `get_leads(...)` requires `subscription_id`, catalog resolve sends `fieldsValueIds`, monitoring bucket methods send `data`, and vehicle/request identifiers use Swagger JSON types.
- **BREAKING:** Autoload profile saves now require Swagger fields (`report_email`, schedule and feed/upload URL), stock info sends `item_ids`, TrxPromo cancel sends `itemIDs`, and Autostrategy update/stop generated calls include `campaignId` and `version`.
- **BREAKING:** Jobs vacancy write methods now require Swagger billing fields, classic v1 vacancy create requires the documented required fields, `JobWebhook.update(...)` requires `secret`, and vacancy statuses send UUID string ids.
- **BREAKING:** Messenger request bodies now match Swagger for blacklist, text messages and image messages; malformed Swagger required fields absent from schema properties are ignored by the normalized schema tree.
- **BREAKING:** Special-offers request bodies now match Swagger: `create_multi(...)` sends only `itemIds`, `confirm_multi(...)` sends `dispatches`/`expiresAt`, and `get_stats(...)` requires `date_time_from`/`date_time_to`.
- Вызовы после `AvitoClient.close()` теперь поднимают `ClientClosedError` вместо `ConfigurationError`.

### Removed
- **BREAKING:** удалены классы исключений `NotFoundError`, `ClientError`, `ServerError` из `avito.core.exceptions`. HTTP 404 и 5xx теперь маппятся на `UpstreamApiError`. Пользователям, ловившим эти типы, перейти на `UpstreamApiError` или `AvitoError` и проверять `status_code`.
- **BREAKING:** удален публичный wrapper `Application.list(...)`; используйте `application().get_ids(updated_at_from=...)` для синхронизации id и `application().get_by_ids(ids=...)` для получения данных откликов.
- **BREAKING:** internal query DTO `ApplicationIdsQuery`, `ResumeSearchQuery`, `VacanciesQuery` и `MonitoringEventsQuery` больше не re-export-ятся из доменных пакетов; публичные методы принимают primitive keyword-only параметры.
- **BREAKING:** удалены старые public input aliases `BbipItemInput`, `TrxItemInput` и `BidItemInput`; используйте `BbipItem`, `TrxItem` и `CpaAuctionBidInput`.
- Удалены legacy-модули `avito/auth/mappers.py` и `avito/auth/enums.py` (внутренние, без публичных импортов).
- Удалены инфраструктурные мета-тесты (`tests/docs/`, `tests/test_inventory_architecture.py`, `tests/test_download_avito_api_specs.py`, `tests/core/test_architecture_lint.py`, `tests/core/test_swagger_{linter,discovery,factory_map,report}.py`); архитектурные инварианты остаются под `make swagger-lint` и `make architecture-lint`.
- Удалены архитектурные тесты `tests/contracts/test_public_surface.py` и `tests/core/test_swagger.py` — публичная поверхность и метаданные `@swagger_operation` верифицируются `mypy strict` + `make swagger-lint` + `tests/contracts/test_swagger_contracts.py`.

### Fixed
- Нет изменений.

## [1.0.2] - 2026-04-21

### Added
- Первый публичный релиз changelog для `avito-py`.

### Changed
- Зафиксирована базовая структура истории изменений для следующих фаз исправления STYLEGUIDE.
