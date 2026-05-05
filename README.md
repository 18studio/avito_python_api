# SDK для Avito

[![CI](https://github.com/p141592/avito_python_api/actions/workflows/ci.yml/badge.svg)](https://github.com/p141592/avito_python_api/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/p141592/avito_python_api/badge.svg?branch=main)](https://coveralls.io/github/p141592/avito_python_api?branch=main)
[![PyPI Downloads](https://img.shields.io/pypi/dm/avito-py.svg)](https://pypi.org/project/avito-py/)
[![Docs](https://img.shields.io/badge/docs-latest-blue)](https://p141592.github.io/avito_python_api/)

Отчёт покрытия Avito API: [покрытие API](https://p141592.github.io/avito_python_api/reference/api-report/).

## Быстрый старт

Получение ключей — https://www.avito.ru/professionals/api

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    profile = avito.account().get_self()
    ad = avito.ad(item_id=42, user_id=123).get()

print(profile.name)
print(ad.title)
```

По умолчанию настройки читаются из переменных окружения с префиксом `AVITO_`.

`avito-py` — синхронный Python SDK для работы с Avito API через единый объектный фасад `AvitoClient`.

## Установка

```bash
poetry add avito-py
```

или

```bash
pip install avito-py
```

Требование к интерпретатору: Python `3.14` и выше в рамках ветки `3.x`. Репозиторий и релизный контур валидируются именно на Python `3.14`.

## Инициализация клиента

SDK предоставляет три нормативных способа создания клиента — от самого простого к самому явному.

### 1. Из переменных окружения

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    ...
```

### 2. Напрямую через `client_id` / `client_secret`

Короткий путь без промежуточных объектов:

```python
from avito import AvitoClient

with AvitoClient(client_id="client-id", client_secret="client-secret") as avito:
    ...
```

### 3. Полная конфигурация через `AvitoSettings`

```python
from avito import AuthSettings, AvitoClient, AvitoSettings

settings = AvitoSettings(
    base_url="https://api.avito.ru",
    user_id=123,
    auth=AuthSettings(
        client_id="client-id",
        client_secret="client-secret",
    ),
)

with AvitoClient(settings) as avito:
    ...
```

Все опциональные параметры конструктора — keyword-only. `AvitoClient` иммутабелен: `base_url`, таймауты, retry-политика и `auth` не меняются у живого клиента — вместо этого создаётся новый клиент.

### Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `AVITO_CLIENT_ID` | **да** | Client ID OAuth-приложения |
| `AVITO_CLIENT_SECRET` | **да** | Client Secret OAuth-приложения |
| `AVITO_BASE_URL` | нет | Базовый URL API (по умолчанию `https://api.avito.ru`) |
| `AVITO_USER_ID` | нет | ID пользователя по умолчанию |
| `AVITO_USER_AGENT_SUFFIX` | нет | Суффикс к заголовку `User-Agent` |
| `AVITO_SCOPE` | нет | OAuth scope |
| `AVITO_REFRESH_TOKEN` | нет | Refresh token для предварительного обмена |
| `AVITO_AUTOTEKA_CLIENT_ID` | нет | Client ID для Автотека API |
| `AVITO_AUTOTEKA_CLIENT_SECRET` | нет | Client Secret для Автотека API |
| `AVITO_AUTOTEKA_SCOPE` | нет | OAuth scope для Автотека API |

Полный список переменных, включая URL-overrides, таймауты и retry-политику, — в [справочнике по конфигурации](https://p141592.github.io/avito_python_api/reference/config/).

Правила resolution:

- значения из process environment имеют приоритет над `.env`;
- `AvitoSettings.from_env()` и `AvitoClient.from_env()` детерминированно читают `.env` из текущей рабочей директории или из переданного `env_file`;
- при отсутствии `AVITO_CLIENT_ID` или `AVITO_CLIENT_SECRET` SDK поднимает `ConfigurationError` при создании клиента, до первого HTTP-запроса.

## Примеры по доменам

### Аккаунт и объявления

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    account = avito.account(user_id=123)
    balance = account.get_balance()
    ad = avito.ad(item_id=42, user_id=123).get()
    stats = avito.ad_stats(item_id=42, user_id=123).get_item_stats(
        date_from="2026-04-01",
        date_to="2026-04-23",
    )
```

`user_id` можно передать явно, задать через `AVITO_USER_ID` или оставить пустым для read-only вызовов, где SDK может определить пользователя через `account().get_self()`. Если идентификатор не удалось определить, SDK поднимает `ValidationError` с подсказкой, как вызвать метод правильно. Для OAuth secret используйте `AVITO_CLIENT_SECRET`.

Статистические методы принимают `date`, `datetime` и ISO-строки, а в Avito API отправляют дату в формате `YYYY-MM-DD`. Модель `Listing` нормализует основные поля объявления: `title`, `price`, `status`, `description`, `url`, `category`, `city`, `published_at`, `updated_at`, `is_moderated`, `is_visible`.

### Автозагрузка

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    profile = avito.autoload_profile(user_id=123).get()
    report = avito.autoload_report(report_id=777).get()
```

### Мессенджер

```python
from avito import AvitoClient
from avito.messenger import UploadImageFile

with AvitoClient.from_env() as avito:
    chats = avito.chat(user_id=123).list()
    message = avito.chat_message(chat_id="chat-1", user_id=123).send_message(
        message="Здравствуйте"
    )
    uploaded = avito.chat_media(user_id=123).upload_images(
        files=[
            UploadImageFile(
                field_name="image",
                filename="photo.jpg",
                content=b"...",
                content_type="image/jpeg",
            )
        ]
    )
    subscriptions = avito.chat_webhook().list()
```

### Продвижение

```python
from avito import AvitoClient
from datetime import datetime

with AvitoClient.from_env() as avito:
    services = avito.promotion_order().list_orders()
    forecast = avito.bbip_promotion(item_id=42).get_forecasts(items=[])
    budget = avito.autostrategy_campaign().create_budget(
        campaign_type="AS",
        start_time=datetime(2026, 4, 20),
        finish_time=datetime(2026, 4, 27),
        items=[42, 43],
    )
    campaign = avito.autostrategy_campaign(campaign_id=15).get()
    campaigns = avito.autostrategy_campaign().list(
        limit=50,
        status_id=[1, 2],
        order_by=[("startTime", "asc")],
        updated_from=datetime(2026, 4, 1),
        updated_to=datetime(2026, 4, 30),
    )

print(budget.calc_id)
print(campaign.campaign.title if campaign.campaign else None)
print(campaigns.total_count)
```

Write-операции продвижения, поддерживающие сухой прогон, принимают `dry_run: bool = False`. При `dry_run=True` SDK валидирует параметры, строит тот же payload, что и в реальном вызове, но не выполняет сетевой запрос и возвращает `PromotionActionResult` со статусом `preview`/`validated`.

### Заказы и доставка

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    orders = avito.order().list()
    label_task = avito.order_label().create(order_ids=["100500"])
    label_pdf = avito.order_label(task_id=label_task.task_id).download()
    stock_info = avito.stock().get(item_ids=[100500])
```

### Работа

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    vacancies = avito.vacancy().list(query="python")
    application_ids = avito.application().get_ids(updated_at_from="2026-04-18")
    applications = avito.application().get_by_ids(ids=[application_ids.items[0].id])
    resumes = avito.resume().list(query="оператор")
    webhooks = avito.job_webhook().list()
```

### CPA и CallTracking

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    calls = avito.cpa_call().list(
        date_time_from="2026-04-18T00:00:00Z",
        limit=100,
    )
    calltracking = avito.call_tracking_call(10).get()
    records = avito.call_tracking_call(10).download()
```

### Автотека

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    catalog = avito.autoteka_vehicle().resolve_catalog(brand_id=1)
    preview = avito.autoteka_vehicle().create_preview_by_vin(vin="XTA00000000000000")
    report = avito.autoteka_report().create_report(preview_id=int(preview.preview_id or 0))
    reports = avito.autoteka_report().list_reports()
```

### Недвижимость, отзывы и тарифы

```python
from avito import AvitoClient
from avito.realty import RealtyPricePeriod

with AvitoClient.from_env() as avito:
    booking = avito.realty_booking(20, user_id=10)
    booking.update_bookings_info(blocked_dates=["2026-05-01"])
    bookings = booking.list_realty_bookings(date_start="2026-05-01", date_end="2026-05-05")
    avito.realty_pricing(20, user_id=10).update_realty_prices(
        periods=[RealtyPricePeriod(date_from="2026-05-01", price=5000)]
    )
    reviews = avito.review().list()
    tariff = avito.tariff().get_tariff_info()
```

`review().list()` по умолчанию запрашивает первую страницу отзывов (`page=1`, `limit=50`). Для явной пагинации передайте `page`, `offset` или `limit` напрямую.

## Пагинация

Публичные list-операции, которые поддерживают lazy pagination, возвращают обычные SDK-результаты, а поле `items` в них типизировано как `PaginatedList[T]` и ведёт себя как list-like коллекция.

Стабильный публичный контракт:

- первая страница загружается сразу, остальные подгружаются только при чтении элементов за её пределами;
- доступ к уже загруженным элементам не делает повторных запросов;
- частичная итерация и slicing загружают только необходимые страницы;
- пустая коллекция не приводит к дополнительным запросам;
- ошибка на последующей странице поднимается в момент её чтения;
- явная полная материализация выполняется через `items.materialize()` и загружает всё ровно один раз.

Пример:

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    items = avito.ad(user_id=123).list(status="active", limit=50, page_size=25)

    first = items[0]
    preview = items[:10]
    all_items = items.materialize()
```

В `ad().list()` параметр `limit` ограничивает общий максимум элементов результата, а `page_size` задаёт размер страницы upstream API.

## Ошибки

Все исключения SDK наследуются от `AvitoError` и импортируются из `avito.core.exceptions`. HTTP-коды отображаются в конкретные типы:

- `400`, `422` → `ValidationError`
- `401` → `AuthenticationError`
- `403` → `AuthorizationError`
- `409` → `ConflictError`
- `429` → `RateLimitError`
- прочие `5xx` и нераспознанные ответы → `UpstreamApiError`
- транспортные сбои → `TransportError`
- ошибки маппинга ответа → `ResponseMappingError`

`AuthenticationError` (401) и `AuthorizationError` (403) — семантически разные ошибки и **не** состоят в отношении наследования. Тексты сообщений написаны на русском языке. Секреты (access token, `client_secret`, `Authorization`) автоматически санитайзятся из сообщений и metadata.

Для диагностики доступны структурированные поля `operation`, `status` / `status_code`, `error_code`, `message`, `details`, `retry_after`, `request_id`, `metadata`, `payload` и `headers`. Например, у `RateLimitError` можно прочитать `retry_after`, а у ошибок валидации — `details`, если upstream вернул подробности по параметрам.

## Отладка интеграции

SDK не раскрывает сырой transport в основном API, но даёт безопасный debug snapshot без секретов:

```python
from avito import AvitoClient

client = AvitoClient.from_env()
info = client.debug_info()

print(info.base_url)
print(info.user_id)
print(info.retry_max_attempts)
client.close()
```

`debug_info()` подходит для smoke-проверок окружения и диагностики конфигурации. Стабильный контракт включает `base_url`, `user_id`, флаг `requires_auth`, таймауты и retry-настройки. Access token, `client_secret` и `Authorization` header в этот снимок не попадают.

## Проверки качества

Минимальный релизный набор:

```bash
make check
```

Для локальной разработки команды разделены:

```bash
make fmt
make lint
make typecheck
make test
make quality
make build
```

## GitHub Actions

Для репозитория настроены два workflow:

- `CI` запускается на каждый `push` в `main`/`master` и на каждый `pull_request`, выполняет `make quality`, docs-gates и один полный pytest-прогон через coverage.
- `Release` запускается при пуше тега вида `v*`, выставляет версию пакета из тега, повторно выполняет `make check`, публикует пакет на PyPI и создаёт GitHub Release.

Для публикации релиза нужно добавить secret:

- `PYPI_API_TOKEN` — токен публикации в PyPI для `poetry publish`.

Порядок релиза:

```bash
git tag v1.0.2
git push origin v1.0.2
```

## Документация репозитория

- [STYLEGUIDE.md](STYLEGUIDE.md) — нормативные архитектурные правила
- [docs/site/reference](docs/site/reference) — справочник публичного API SDK
