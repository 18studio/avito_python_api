# Конфигурация

SDK поддерживает три уровня инициализации: переменные окружения, короткие
OAuth-credentials и полный объект настроек. Приоритет при загрузке из окружения:
значения процесса, затем `.env`, затем значения по умолчанию.

## AvitoSettings

::: avito.AvitoSettings

## AuthSettings

::: avito.AuthSettings

## Env-переменные

### Обязательные

Без этих двух переменных SDK поднимает `ConfigurationError` при создании клиента,
до первого HTTP-запроса.

| Переменная | Поле | Описание |
|---|---|---|
| `AVITO_CLIENT_ID` | `auth.client_id` | Client ID OAuth-приложения. Получить на [avito.ru/professionals/api](https://www.avito.ru/professionals/api). |
| `AVITO_CLIENT_SECRET` | `auth.client_secret` | Client Secret OAuth-приложения. Хранить только в защищённом месте — в логах и `debug_info()` не отображается. |

### Опциональные — основные

| Переменная | Поле | По умолчанию | Описание |
|---|---|---|---|
| `AVITO_BASE_URL` | `base_url` | `https://api.avito.ru` | Базовый URL API. Переопределяется для тестирования на sandbox-окружении. |
| `AVITO_USER_ID` | `user_id` | — | ID пользователя по умолчанию. Если задан, передаётся в методы, где `user_id` обязателен, без явного указания в каждом вызове. |
| `AVITO_USER_AGENT_SUFFIX` | `user_agent_suffix` | — | Суффикс к заголовку `User-Agent`. Полезен для идентификации вашего сервиса в логах Avito. Не должен содержать секретов. |
| `AVITO_SCOPE` | `auth.scope` | — | OAuth-scope через пробел. Задаётся, если приложению нужен нестандартный набор прав. |
| `AVITO_REFRESH_TOKEN` | `auth.refresh_token` | — | Refresh token для предварительного обмена на access token. Используется в сценариях, когда токен получен заранее вне SDK. |

### Опциональные — URL-overrides

Нужны только при работе с нестандартными окружениями (staging, proxy, internal mirror).
В продакшне менять не требуется.

| Переменная | Поле | По умолчанию | Описание |
|---|---|---|---|
| `AVITO_TOKEN_URL` | `auth.token_url` | `/token` | Endpoint для получения access token. |
| `AVITO_ALTERNATE_TOKEN_URL` | `auth.alternate_token_url` | `/token` | Альтернативный endpoint токена — используется при недоступности основного. |

### Опциональные — Автотека

Нужны только при использовании [методов Автотеки](../how-to/autoteka-report.md).
Автотека — отдельный сервис с собственными OAuth-ключами.

| Переменная | Поле | Описание |
|---|---|---|
| `AVITO_AUTOTEKA_CLIENT_ID` | `auth.autoteka_client_id` | Client ID для Автотека API. |
| `AVITO_AUTOTEKA_CLIENT_SECRET` | `auth.autoteka_client_secret` | Client Secret для Автотека API. |
| `AVITO_AUTOTEKA_SCOPE` | `auth.autoteka_scope` | OAuth-scope для Автотека API. |
| `AVITO_AUTOTEKA_TOKEN_URL` | `auth.autoteka_token_url` | Endpoint токена для Автотеки. По умолчанию `/autoteka/token`. |

### Опциональные — таймауты

По умолчанию все таймауты указаны в секундах и рассчитаны под типичные продакшн-условия.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `AVITO_TIMEOUT_CONNECT` | `5.0` | Время ожидания установки TCP-соединения. |
| `AVITO_TIMEOUT_READ` | `15.0` | Время ожидания ответа сервера после отправки запроса. |
| `AVITO_TIMEOUT_WRITE` | `15.0` | Время ожидания записи тела запроса. |
| `AVITO_TIMEOUT_POOL` | `5.0` | Время ожидания свободного соединения из пула. |

### Опциональные — retry-политика

| Переменная | По умолчанию | Описание |
|---|---|---|
| `AVITO_RETRY_MAX_ATTEMPTS` | `3` | Максимальное число попыток одного запроса. |
| `AVITO_RETRY_BACKOFF_FACTOR` | `0.5` | Базовый множитель задержки между попытками (экспоненциальный backoff). |
| `AVITO_RETRY_MAX_DELAY` | `30.0` | Максимальная задержка между попытками в секундах. |
| `AVITO_RETRY_RETRYABLE_METHODS` | `GET,HEAD,OPTIONS,PUT,DELETE` | HTTP-методы, для которых разрешён retry. Через запятую или JSON-массив. |
| `AVITO_RETRY_RETRY_ON_RATE_LIMIT` | `true` | Повторять запрос при ответе `429 Too Many Requests`. |
| `AVITO_RETRY_RETRY_ON_SERVER_ERROR` | `true` | Повторять запрос при ответах `5xx`. |
| `AVITO_RETRY_RETRY_ON_TRANSPORT_ERROR` | `true` | Повторять запрос при сетевых ошибках (обрыв соединения, DNS). |
| `AVITO_RETRY_MAX_RATE_LIMIT_WAIT_SECONDS` | `30.0` | Максимальное время ожидания при `429`, если сервер вернул `Retry-After`. |
| `AVITO_RATE_LIMIT_ENABLED` | `false` | Включить локальное превентивное ограничение частоты запросов перед отправкой в API. |
| `AVITO_RATE_LIMIT_REQUESTS_PER_SECOND` | `8.0` | Целевая частота запросов для локального token bucket. |
| `AVITO_RATE_LIMIT_BURST` | `8` | Максимальный краткий burst перед принудительной паузой. |

## Per-operation overrides

| Тип операции | Разрешённые overrides |
|---|---|
| read / list / probe | `timeout`, `retries` |
| write при `dry_run=False` | `timeout`, `retries`, `idempotency_key` |
| write при `dry_run=True` | `timeout` |
| pagination-чтение | `timeout`, `retries`, `page_size` |

`dry_run=True` обязан строить тот же payload, что и реальный write-вызов, но не
должен выполнять transport-вызов.
