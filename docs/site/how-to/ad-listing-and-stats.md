# Объявления, статистика и продвижение

Этот рецепт покрывает повседневный сценарий домена `ads`: найти объявления, открыть карточку, посмотреть статистику и подготовить безопасное действие продвижения.

## Список объявлений

`ad().list()` возвращает `PaginatedList[Listing]`. Первую страницу SDK загружает сразу, остальные страницы дочитываются при обращении по индексу, итерации или `materialize()`.

`user_id` можно передать явно или задать через `AVITO_USER_ID`. Если идентификатор не задан, SDK попробует получить его через `account().get_self()` и затем выполнит запрос объявлений.

`limit` задаёт общий максимум элементов в результате, а `page_size` — размер страницы upstream API. Например, `limit=3, page_size=2` вернёт не больше трёх объявлений и сделает второй запрос только за одним оставшимся элементом.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    listings = avito.ad(user_id=7).list(status="active", limit=3, page_size=2)
    items = listings.materialize()

print(items[0].item_id)
print(items[0].title)
```

## Карточка объявления

Для чтения одного объявления нужен `item_id`; `user_id` определяется тем же порядком, что и для списка: явный аргумент, настройки SDK, затем `get_self()`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    item = avito.ad(item_id=101).get()

print(item.status)
print(item.price)
print(item.category)
print(item.city)
```

Модель `Listing` нормализует ключевые поля карточки: `title`, `price`, `status`, `description`, `url`, `category`, `city`, `published_at`, `updated_at`, `is_moderated` и `is_visible`. Вложенные upstream-ответы вроде `{"status": {"value": "active"}}` и `{"price": {"value": 1000}}` маппятся в обычные typed-поля SDK.

## Статистика объявлений

`ad_stats()` группирует статистику, аналитику, звонки и расходы. Если `item_id` передан в фабрику, методы используют его по умолчанию.

```python
from datetime import date

from avito import AvitoClient

with AvitoClient.from_env() as avito:
    stats = avito.ad_stats(item_id=101, user_id=7)
    item_stats = stats.get_item_stats(
        date_from=date(2026, 4, 1),
        date_to="2026-04-23",
    )
    calls = stats.get_calls_stats(
        date_from=date(2026, 4, 1),
        date_to="2026-04-23",
    )
    spendings = stats.get_account_spendings(
        date_from=date(2026, 4, 1),
        date_to="2026-04-23",
        spending_types=["promotion"],
        grouping="day",
    )

print(item_stats.items[0].views)
print(calls.items[0].answered_calls)
print(spendings.total)
```

Поля дат статистики принимают `date`, `datetime` и ISO-строки. Перед запросом SDK приводит их к формату `YYYY-MM-DD`, потому что статистические endpoints Avito ожидают дату без времени.

## Аналитика по списку объявлений

Когда нужно сравнить несколько объявлений, передайте `item_ids` явно.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    analytics = avito.ad_stats(user_id=7).get_item_analytics(
        date_from="2026-04-01",
        date_to="2026-04-23",
        metrics=["views", "contacts", "favorites"],
        grouping="day",
        limit=100,
        offset=0,
    )

print(analytics.items[0].contacts)
```

## Цены продвижения и dry-run

Перед включением услуг продвижения проверьте доступные цены. Для write-операций используйте `dry_run=True`, чтобы получить preview результата без вызова transport.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    promotion = avito.ad_promotion(item_id=101, user_id=7)
    prices = promotion.get_vas_prices(item_ids=[101])
    preview = promotion.apply_vas(vas_id="xl", dry_run=True)

print(prices.items[0].price)
print(preview.applied)
print(preview.request_payload)
```

## Обновление цены

`update_price()` меняет цену конкретного объявления. Для повторяемых запусков передавайте `idempotency_key`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    result = avito.ad(item_id=101, user_id=7).update_price(
        price=10900,
        idempotency_key="ad-price-example-1",
    )

print(result.status)
print(result.price)
```

Полный список методов домена смотрите в [reference по ads](../reference/domains/ads.md), а общие правила `PaginatedList` — в [reference по пагинации](../reference/pagination.md).
