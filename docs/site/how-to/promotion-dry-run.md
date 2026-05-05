# Продвижение с dry-run

Этот рецепт показывает безопасный цикл для продвижения: сначала прочитать доступные цены, затем проверить write-payload через `dry_run=True` и только после этого выполнять реальный вызов с `idempotency_key`.

## Цены услуг

`ad_promotion().get_vas_prices()` читает доступные услуги продвижения по объявлениям. Для чтения нужен `user_id`, а список объявлений передаётся явно.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    prices = avito.ad_promotion(item_id=101, user_id=7).get_vas_prices(item_ids=[101])

print(prices.items[0].code)
print(prices.items[0].price)
```

## Проверка payload без transport

При `dry_run=True` SDK строит тот же payload, что и для реального write-вызова, но transport не вызывается. Это удобно для UI-preview, ревью операций и тестов.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    preview = avito.ad_promotion(item_id=101, user_id=7).apply_vas(
        vas_id="xl",
        dry_run=True,
    )

print(preview.action)
print(preview.applied)
print(preview.request_payload)
```

## Пакет услуг

Пакетная операция поддерживает тот же dry-run контракт.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    preview = avito.ad_promotion(item_id=101, user_id=7).apply_vas_package(
        package_code="package-xl",
        dry_run=True,
    )

print(preview.status)
print(preview.target["item_id"])
```

## Реальный write-вызов

Когда preview подтверждён пользователем, выполните реальный вызов с идемпотентным ключом. В этом примере блок не помечен как `python`, потому что он намеренно показывает сетевую write-операцию.

```text
with AvitoClient.from_env() as avito:
    result = avito.ad_promotion(item_id=101, user_id=7).apply_vas(
        vas_id="xl",
        idempotency_key="promotion-apply-vas-2026-04-23-101",
    )
```

Полный контракт смотрите в [reference по ads](../reference/domains/ads.md) и [reference по promotion](../reference/domains/promotion.md). Общие правила идемпотентности и dry-run описаны в [конфигурации](../reference/config.md).
