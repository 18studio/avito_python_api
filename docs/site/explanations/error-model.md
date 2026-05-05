# Модель ошибок

SDK переводит HTTP-статусы, transport failures и ошибки маппинга в typed exceptions. Пользовательскому коду не нужно разбирать `httpx.Response` или сырой JSON ошибки.

## Классы ошибок

| Ситуация | Исключение |
|---|---|
| Некорректный пользовательский ввод | `ValidationError` |
| Не хватает настроек клиента | `ConfigurationError` |
| Вызов после `AvitoClient.close()` | `ClientClosedError` |
| `401` | `AuthenticationError` |
| `403` | `AuthorizationError` |
| `409` | `ConflictError` |
| `429` | `RateLimitError` |
| Transport failure | `TransportError` |
| Upstream вернул неподдержанный ответ | `UpstreamApiError` |
| JSON не соответствует SDK-модели | `ResponseMappingError` |

`AuthenticationError` и `AuthorizationError` — разные ветки. Это позволяет consumer-коду отдельно обрабатывать истёкший токен и недостаток прав.

## Диагностические поля

Каждая публичная ошибка несёт безопасный диагностический набор: `operation`, `status` / `status_code`, `error_code`, `message`, `details`, `retry_after`, `request_id`, `metadata`, `payload` и `headers`. Эти поля нужны для логов, алертов и обращений в поддержку upstream API.

`details` заполняется из структурированных полей тела ответа (`details`, `fields`, `errors`, `violations`). Для `429` SDK также сохраняет `retry_after`, если upstream вернул заголовок `Retry-After`.

Секреты не должны попадать в сообщения ошибок. Перед сохранением metadata SDK санитайзит OAuth-токены, `client_secret` и `Authorization`.

## Где ловить ошибки

Пользовательский код обычно ловит `AvitoError` на границе integration job, CLI-команды или web-handler. Более точные типы нужны, когда поведение реально различается: например, `RateLimitError` можно отправить в delayed retry, а `ValidationError` надо вернуть как ошибку конфигурации задачи.

Полный список public exceptions и полей metadata смотрите в [reference по исключениям](../reference/exceptions.md).
