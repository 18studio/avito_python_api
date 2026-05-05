# Идемпотентность

Write-операции в SDK могут завершиться успешно на стороне API, но не вернуть ответ из-за сетевой ошибки. Параметр `idempotency_key` позволяет безопасно повторить такой вызов: API обработает повторный запрос с тем же ключом как no-op и вернёт оригинальный результат.

## Когда нужен idempotency_key

Используйте ключ для любой write-операции, которую вы можете повторить при сбое. Методы, принимающие `idempotency_key`, явно документируют его в docstring. Без ключа повтор может создать дублирующую операцию.

## Обновление цены

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    result = avito.ad(item_id=101, user_id=7).update_price(
        price=10900,
        idempotency_key="price-update-user7-item101-v1",
    )

print(result.item_id)
print(result.price)
```

При сетевом сбое передайте тот же `idempotency_key` повторно. Ключ должен однозначно идентифицировать логическую операцию: включайте идентификаторы ресурса и версию намерения.

## Пометка чата как прочитанного

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    result = avito.chat(chat_id="chat-1", user_id=7).mark_read(
        idempotency_key="mark-read-user7-chat1-2026-04-24",
    )

print(result.status)
```

## Правила формирования ключа

Хороший ключ идемпотентности:

- уникален для каждой логической операции (разные ресурсы → разные ключи);
- воспроизводим при повторе (тот же ключ при той же попытке);
- не переиспользуется для разных намерений (изменение цены с 9900 → 10900 и с 10900 → 12000 должны иметь разные ключи).

```text
price-update-{user_id}-{item_id}-{target_price}
mark-read-{user_id}-{chat_id}-{date}
```

## Dry-run и idempotency_key

При `dry_run=True` `idempotency_key` не принимается, потому что transport-вызов не выполняется. При переходе от dry-run к реальному вызову добавляйте ключ явно.

```text
# dry-run — проверяем payload, ключ не нужен
preview = avito.ad_promotion(item_id=101, user_id=7).apply_vas(
    vas_id="xl",
    dry_run=True,
)

# реальный вызов — добавляем ключ
result = avito.ad_promotion(item_id=101, user_id=7).apply_vas(
    vas_id="xl",
    idempotency_key="apply-vas-user7-item101-xl-2026-04-24",
)
```

Полный контракт overrides описан в [reference по конфигурации](../reference/config.md). Сценарий с dry-run разобран в [рецепте по продвижению](promotion-dry-run.md).
