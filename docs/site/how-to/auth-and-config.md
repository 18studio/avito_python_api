# Авторизация и конфигурация

SDK поддерживает три публичных способа создать клиент. Для приложений и CLI обычно удобен `AvitoClient.from_env()`: секреты остаются вне кода, а конфигурация читается одинаково локально и в CI.

```bash
export AVITO_CLIENT_ID="client-id"
export AVITO_CLIENT_SECRET="client-secret"
```

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    profile = avito.account().get_self()

print(profile.user_id)
```

Для коротких скриптов можно передать ключи явно:

```python
from avito import AvitoClient

with AvitoClient(client_id="client-id", client_secret="client-secret") as avito:
    info = avito.debug_info()

print(info.base_url)
```

Для полного контроля используйте `AvitoSettings` и `AuthSettings`.

```python
from avito import AuthSettings, AvitoClient, AvitoSettings

settings = AvitoSettings(
    user_id=123,
    auth=AuthSettings(
        client_id="client-id",
        client_secret="client-secret",
    ),
)

with AvitoClient(settings) as avito:
    info = avito.debug_info()

print(info.user_id)
```

Значения из process environment имеют приоритет над `.env`. Если обязательные ключи отсутствуют, SDK поднимает `ConfigurationError` при создании клиента, до первого HTTP-запроса. Безопасный снимок `debug_info()` не содержит `client_secret`, access token или заголовок `Authorization`.

## Переменные окружения

### Обязательные

Оба значения выдаёт личный кабинет разработчика на [avito.ru/professionals/api](https://www.avito.ru/professionals/api).

**`AVITO_CLIENT_ID`** — идентификатор OAuth-приложения. Публичный, но не должен попадать в клиентский код.

**`AVITO_CLIENT_SECRET`** — секрет OAuth-приложения. Храните только в переменных окружения или в vault — не в репозитории. SDK автоматически скрывает это значение из логов и `debug_info()`.

### Опциональные — основные

**`AVITO_BASE_URL`** — базовый URL API, по умолчанию `https://api.avito.ru`. Переопределяется при работе с sandbox или внутренним proxy.

**`AVITO_USER_ID`** — ID пользователя по умолчанию. Если задан, не нужно передавать `user_id=` в каждый доменный вызов, где он обязателен. Полезно для приложений с одним фиксированным пользователем.

Если `AVITO_USER_ID` не задан, доменные методы, которым нужен пользователь, сначала смотрят явный `user_id`, а затем могут получить его через `account().get_self()`. Это работает для read-only операций вроде баланса, объявлений, статистики и продвижения объявлений. Если профиль текущего токена не содержит `user_id`, SDK поднимает `ValidationError` с подсказкой передать идентификатор явно.

**`AVITO_USER_AGENT_SUFFIX`** — суффикс, который добавляется к стандартному `User-Agent` заголовку. Используйте для идентификации вашего сервиса в логах и поддержке. Не должен содержать секреты, токены или слова `password`/`secret` — SDK проверяет это и поднимает `ConfigurationError`.

**`AVITO_SCOPE`** — OAuth scope через пробел. Задаётся, если приложению нужен нестандартный набор разрешений. Большинству приложений не нужен.

**`AVITO_REFRESH_TOKEN`** — refresh token для предварительного обмена на access token. Применяется, когда token уже получен внешней системой и передаётся в SDK для однократного использования.

### Опциональные — Автотека

[Автотека](autoteka-report.md) — отдельный сервис с собственной OAuth-авторизацией. Эти переменные нужны только при вызовах `avito.autoteka_*()`.

**`AVITO_AUTOTEKA_CLIENT_ID`** и **`AVITO_AUTOTEKA_CLIENT_SECRET`** — учётные данные для Автотека API. Выдаются отдельно от основных ключей Avito.

**`AVITO_AUTOTEKA_SCOPE`** — scope для Автотека API. Уточняйте в документации Автотеки.

**`AVITO_AUTOTEKA_TOKEN_URL`** — endpoint токена для Автотеки, по умолчанию `/autoteka/token`. Меняется только в нестандартных окружениях.

### Опциональные — URL-overrides

**`AVITO_TOKEN_URL`** и **`AVITO_ALTERNATE_TOKEN_URL`** — endpoint-ы получения access token. В продакшне менять не нужно. Используются при работе с proxy или staging-окружением.

### Опциональные — таймауты и retry

Управление таймаутами: `AVITO_TIMEOUT_CONNECT` (5 с), `AVITO_TIMEOUT_READ` (15 с), `AVITO_TIMEOUT_WRITE` (15 с), `AVITO_TIMEOUT_POOL` (5 с).

Управление retry: `AVITO_RETRY_MAX_ATTEMPTS` (3), `AVITO_RETRY_BACKOFF_FACTOR` (0.5), `AVITO_RETRY_MAX_DELAY` (30 с), `AVITO_RETRY_RETRY_ON_RATE_LIMIT` (true), `AVITO_RETRY_RETRY_ON_SERVER_ERROR` (true).

Полная таблица с типами и дефолтами — в [справочнике по конфигурации](../reference/config.md).
