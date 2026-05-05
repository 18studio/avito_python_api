# Исключения

`AvitoError` — базовый тип ошибок SDK. Специализированные исключения отражают
класс сбоя: аутентификация, авторизация, validation, rate limit, transport и
ошибки upstream API. Вызовы после `AvitoClient.close()` поднимают
`ClientClosedError`.

## Диагностические поля

Каждое публичное исключение сохраняет безопасные диагностические данные:

| Поле | Назначение |
|---|---|
| `operation` | Имя SDK-операции, во время которой возникла ошибка |
| `status` / `status_code` | HTTP-статус upstream-ответа, если он был получен |
| `error_code` | Код ошибки из тела upstream-ответа, если API его вернул |
| `message` | Читаемое сообщение ошибки |
| `details` | Структурированные подробности из `details`, `fields`, `errors` или `violations` |
| `retry_after` | Количество секунд до повтора для `429`, если есть `Retry-After` |
| `request_id` | Идентификатор upstream-запроса, если API его вернул |
| `attempt` | Номер retry-попытки, если он доступен transport-слою |
| `method` | HTTP-метод запроса |
| `endpoint` | Путь endpoint без OAuth-секретов и приватных headers |

Секреты в `payload`, `headers` и `metadata` редактируются через
`sanitize_metadata()`.

Пример обработки rate limit:

```text
from avito.core.exceptions import RateLimitError

try:
    avito.ad_stats(user_id=7).get_item_stats(item_ids=[101])
except RateLimitError as exc:
    print(exc.operation)
    print(exc.status)
    print(exc.error_code)
    print(exc.retry_after)
    print(exc.request_id)
```

## Иерархия

::: avito.core.exceptions
