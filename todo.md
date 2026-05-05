# Двухрежимный SDK (sync + async)

## Контекст

SDK сейчас полностью синхронный: `AvitoClient` → `Transport` (`httpx.Client` + `time.sleep`) →
`AuthProvider` (`TokenClient` поверх sync-transport) → `DomainObject` подклассы (12 пакетов,
~204 swagger-операций) → `PaginatedList[T]` (наследник `list`). Цель — добавить вторую,
асинхронную, поверхность по образцу `httpx.Client`/`httpx.AsyncClient`, без слома sync-API,
с переиспользованием `OperationSpec`, моделей, request/query DTO, swagger-инвариантов и
ошибок.

## Принятые решения

| Вопрос | Решение |
|---|---|
| Стиль | Параллельные классы вручную: рядом с каждым sync-слоем кладём `Async*` класс. Codegen не используем. |
| Размещение | `avito/<domain>/async_domain.py` рядом с `domain.py`. |
| Swagger-binding | `@swagger_operation(..., variant="sync"\|"async")`. Уникальный ключ линтера — `(operation_key, variant)`. |
| Sequencing | M1 — фундамент с тестами; M2…M13 — порт каждого домена отдельным PR. До появления первого `AsyncX` класса strict-coverage по `variant="async"` пуст и не падает. |
| Pagination | `AsyncPaginatedList[ItemT]` — отдельный класс (не наследник `list`), без list-API parity (только `__aiter__` / `materialize` / `loaded_count` / `is_materialized` / `known_total` / `source_total`). |

## Архитектура: что общее, что дублируем

```
        ┌────────── shared (без изменений по семантике) ─────────────┐
        │                                                            │
        │  OperationSpec, models, request/query DTO, ApiTimeouts,    │
        │  RequestContext, JsonPage, exceptions, RetryPolicy,        │
        │  RateLimiter (логика "ждать сколько"), retries.RetryDecision│
        │                                                            │
        └─────────────────────┬──────────────────────────────────────┘
                              │ используется обоими
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌──────── SYNC (как есть) ───┐   ┌──────── ASYNC (новое) ─────┐
    │ Transport                  │   │ AsyncTransport             │
    │  ↓ httpx.Client            │   │  ↓ httpx.AsyncClient       │
    │  ↓ time.sleep              │   │  ↓ asyncio.sleep           │
    │ OperationExecutor          │   │ AsyncOperationExecutor     │
    │ AuthProvider/TokenClient   │   │ AsyncAuthProvider/         │
    │                            │   │   AsyncTokenClient/        │
    │                            │   │   AsyncAlternateTokenClient│
    │ PaginatedList[T] (list-sub)│   │ AsyncPaginatedList[T]      │
    │ DomainObject               │   │ AsyncDomainObject          │
    │  ├─ Account                │   │  ├─ AsyncAccount           │
    │  ├─ Ad …                   │   │  ├─ AsyncAd …              │
    │ AvitoClient                │   │ AsyncAvitoClient           │
    └────────────────────────────┘   └────────────────────────────┘

           Swagger binding: variant="sync"          variant="async"
              ↓                                         ↓
                  swagger_discovery + linter
                       (per-variant ключи)
```

Чтобы не разойтись retry-логике и маппингу ошибок, выносим в `avito/core/_transport_shared.py`
IO-agnostic вычисления (без httpx-вызова и sleep): `_decide_transport_retry`,
`_decide_http_retry`, `_is_retryable_request`, `_get_retry_after_seconds`, `_map_http_error`,
`_safe_payload`, `_extract_message`, `_extract_error_code`, `_extract_error_details`,
`_extract_request_id`, `_normalize_path`, `_normalize_params`, `_normalize_files`,
`_merge_headers`, `_build_user_agent`, `_extract_filename`, `build_httpx_timeout`,
`_safe_endpoint`. `Transport` и `AsyncTransport` остаются тонкими обёртками с двумя различиями:
формой sleep и формой client.request.

Аналогично: `avito/auth/_cache.py` содержит in-memory state (поля `_access_token`,
`_refresh_token`, `_autoteka_access_token`) и чистые helpers (`_is_token_fresh`,
`_map_token_response` уже в provider.py — переедет туда). `AuthProvider` и `AsyncAuthProvider`
делегируют кешу, сами добавляют только sync/async lock + IO.

### Порядок зависимостей в M1

```
  Phase 1   _transport_shared.py  ◀── рефактор Transport (без поведенческих изменений)
            _cache.py             ◀── рефактор AuthProvider (без поведенческих изменений)
            ↓
  Phase 2   AsyncTransport, AsyncOperationTransport, AsyncOperationExecutor
            AsyncAuthProvider, AsyncTokenClient, AsyncAlternateTokenClient
            AsyncPaginatedList
            ↓
  Phase 3   variant="async" в swagger декораторе/discovery/linter
            AsyncAvitoClient (без factory-методов; только lifecycle)
            tests/async_fake_transport.py
            ↓
  Phase 4   тесты + docs
```

## Ключевые файлы и точки соединения

### Существующие, изменяются в M1

| Файл | Что меняем |
|---|---|
| `avito/core/transport.py` | Извлекаем IO-agnostic helpers в `_transport_shared.py` и переиспользуем. Поведение sync — без изменений. |
| `avito/core/operations.py` | + `AsyncOperationTransport` (Protocol, async зеркало `OperationTransport`), + `AsyncOperationExecutor` (async зеркало `OperationExecutor.execute`). Helpers `render_path`, `_serialize_query`, `_serialize_request`, `_merge_content_type`, `_extract_filename` уже module-level — переиспользуем без копий. |
| `avito/core/swagger.py` | + поле `variant: Literal["sync","async"] = "sync"` в `SwaggerOperationBinding`. + параметр `variant` в `swagger_operation(...)`. Ошибка `ConfigurationError` при двойном декоре одной функции — без изменений. |
| `avito/core/swagger_discovery.py` | `_iter_domain_modules` дополнительно ищет `<domain>.async_domain` (рядом с `<domain>.domain`). `DiscoveredSwaggerBinding` получает `variant`. `canonical_map` — ключ `(operation_key, variant)`. |
| `avito/core/swagger_linter.py` | `_validate_duplicate_bindings` группирует по `(operation_key, variant)`. `_validate_complete_bindings` запускается per-variant; для `variant="async"` ожидаемое множество ограничено доменами, у которых уже найден `Async*` класс (class-gated coverage). `_validate_no_unbound_operation_specs` остаётся по `OperationSpec` (sync OperationSpec реюзается обоими режимами — счётчик использований единый). |
| `avito/auth/provider.py` | Извлекаем shared cache state в `_cache.py`. Сам `AuthProvider` остаётся sync. |
| `avito/__init__.py` | + экспорт `AsyncAvitoClient`. |
| `avito/core/__init__.py` | + экспорт `AsyncTransport`, `AsyncOperationExecutor`, `AsyncOperationTransport`, `AsyncPaginatedList`. |
| `avito/core/domain.py` | + `AsyncDomainObject` с async `_execute` и async `_resolve_user_id`. Sync `DomainObject` — без изменений. |
| `pyproject.toml` | + `pytest-asyncio = "^0.24"` в dev-deps. + `[tool.pytest.ini_options] asyncio_mode = "strict"`. |
| `Makefile` | Без новых целей; `make check` после M1 должен оставаться зелёным. |
| `scripts/lint_architecture.py` | `LEGACY_FILENAMES` не трогаем (там `client.py`, `mappers.py`, `enums.py` — `async_domain.py` не пересекается). |
| `scripts/lint_swagger_bindings.py` | Без изменений в CLI (логика вынесена в `swagger_linter.py`). |
| `docs/site/explanations/swagger-binding-subsystem.md` | Раздел про `variant` и class-gated coverage. |
| `docs/site/explanations/domain-architecture-v2.md` | Параграф про `async_domain.py` как разрешённый файл, парный к `domain.py`. |

### Новые файлы (M1)

```
avito/core/_transport_shared.py          # IO-agnostic helpers, retry/error mapping/headers
avito/core/async_transport.py            # AsyncTransport (httpx.AsyncClient)
avito/core/async_pagination.py           # AsyncPaginatedList, AsyncPaginator, AsyncPageFetcher
avito/auth/_cache.py                     # TokenCache + _map_token_response
avito/auth/async_provider.py             # AsyncAuthProvider (asyncio.Lock на refresh)
avito/auth/async_token_client.py         # AsyncTokenClient, AsyncAlternateTokenClient
                                         #   (со @swagger_operation(..., variant="async"))
avito/async_client.py                    # AsyncAvitoClient (lifecycle + factory-методы пустые в M1)
avito/testing/async_fake_transport.py    # AsyncFakeTransport (httpx.MockTransport+AsyncClient)
tests/async_fake_transport.py            # тонкий re-export с DeprecationWarning (как у sync)
tests/core/test_async_transport.py
tests/core/test_async_pagination.py
tests/core/test_async_executor.py
tests/core/test_async_client_lifecycle.py
tests/auth/test_async_provider.py
tests/contracts/test_async_parity.py     # инвариант "Async<X> ↔ X" для всех портированных доменов
```

### Новые файлы (M2…M13, на каждый домен)

```
avito/<domain>/async_domain.py
tests/domains/<domain>/test_<domain>_async.py
```

## Контракты новых классов

### `avito/core/async_transport.py`

```python
class AsyncTransport:
    def __init__(
        self,
        settings: AvitoSettings,
        *,
        auth_provider: AsyncAuthProvider | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None: ...

    async def request(self, method, path, *, context, params=None, json_body=None,
                      data=None, files=None, headers=None, content=None,
                      idempotency_key=None) -> httpx.Response: ...
    async def request_json(...) -> object: ...
    async def download_binary(...) -> BinaryResponse: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> AsyncTransport: ...
    async def __aexit__(self, *exc) -> None: ...
    @property
    def auth_provider(self) -> AsyncAuthProvider | None: ...
    def debug_info(self) -> TransportDebugInfo: ...
```

Реализует `AsyncOperationTransport` (Protocol, async-зеркало `OperationTransport` из
`avito/core/operations.py`).

### `avito/core/operations.py` (расширение)

```python
class AsyncOperationTransport(Protocol):
    async def request(...) -> httpx.Response: ...
    async def request_json(...) -> object: ...

class AsyncOperationExecutor:
    def __init__(self, transport: AsyncOperationTransport) -> None: ...
    async def execute[ResponseT](self, spec: OperationSpec[ResponseT], *,
                                 path_params=None, query=None, request=None,
                                 headers=None, idempotency_key=None,
                                 data=None, files=None, timeout=None,
                                 retry=None) -> ResponseT: ...
```

`render_path`, `_serialize_query`, `_serialize_request`, `_merge_content_type`,
`_extract_filename` — общие, переиспользуются обоими executor'ами без копирования.

### `avito/core/domain.py` (расширение)

```python
@dataclass(slots=True, frozen=True)
class AsyncDomainObject:
    transport: AsyncTransport

    async def _execute[ResponseT](self, spec: OperationSpec[ResponseT], *,
                                  path_params=..., query=..., request=...,
                                  headers=..., idempotency_key=..., data=...,
                                  files=..., timeout=..., retry=...) -> ResponseT: ...
    async def _resolve_user_id(self, user_id: int | str | None = None) -> int: ...
```

Async-двойник sync-`DomainObject._resolve_user_id`: тот же fallback-порядок (аргумент →
`AvitoSettings.user_id` → `await self.transport.request_json("GET", "/core/v1/accounts/self")`).

### `avito/core/async_pagination.py`

```python
class AsyncPaginatedList[ItemT]:
    def __init__(self, fetch_page: AsyncPageFetcher[ItemT], *,
                 start_page: int = 1,
                 first_page: JsonPage[ItemT] | None = None) -> None: ...
    def __aiter__(self) -> AsyncIterator[ItemT]: ...
    async def materialize(self) -> list[ItemT]: ...
    async def aload_until(self, index: int) -> None: ...
    @property
    def loaded_count(self) -> int: ...
    @property
    def known_total(self) -> int | None: ...
    @property
    def source_total(self) -> int | None: ...
    @property
    def is_materialized(self) -> bool: ...

type AsyncPageFetcher[ItemT] = Callable[[int | None, str | None],
                                        Awaitable[JsonPage[ItemT]]]
```

`AsyncPaginatedList` **не** наследует `list[T]` — async-итерация и list-индексация
несовместимы. Документируем это явно в docstring и в `pagination` how-to. Семантика
страничного перехода идентична sync `PaginatedList._consume_page` (включая `next_cursor`,
`page+per_page`, `has_next_page`).

### `avito/auth/_cache.py`

```python
@dataclass(slots=True)
class TokenCache:
    access_token: AccessToken | None = None
    refresh_token: str | None = None
    autoteka_access_token: AccessToken | None = None
    def access_is_fresh(self, now: datetime) -> bool: ...
    def autoteka_is_fresh(self, now: datetime) -> bool: ...
    def reset_access(self) -> None: ...
    def reset_autoteka(self) -> None: ...

def map_token_response(payload: object, *, now: datetime | None = None) -> TokenResponse: ...
```

`AuthProvider` и `AsyncAuthProvider` хранят `TokenCache` и используют общий `map_token_response`.

### `avito/auth/async_provider.py`

```python
@dataclass(slots=True)
class AsyncAuthProvider:
    settings: AuthSettings
    token_client: AsyncTokenClient | None = None
    alternate_token_client: AsyncAlternateTokenClient | None = None
    autoteka_token_client: AsyncTokenClient | None = None
    token_fetcher: AsyncTokenFetcher | None = None
    _cache: TokenCache = field(default_factory=TokenCache, init=False, repr=False)
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def get_access_token(self) -> str: ...    # double-checked + asyncio.Lock
    async def refresh_access_token(self) -> TokenResponse: ...
    def invalidate_token(self) -> None: ...         # неблокирующая операция
    async def aclose(self) -> None: ...
    async def get_autoteka_access_token(self) -> str: ...
```

### `avito/auth/async_token_client.py`

```python
@dataclass(slots=True, frozen=True)
class AsyncTokenClient:
    __swagger_domain__ = "auth"
    settings: AuthSettings
    token_url: str | None = None
    client: httpx.AsyncClient | None = None
    sdk_settings: AvitoSettings | None = None

    async def aclose(self) -> None: ...

    @swagger_operation("POST", "/token", spec="Авторизация.json",
                       operation_id="getAccessToken",
                       method_args={"request": "body"},
                       variant="async")
    async def request_client_credentials_token(self, request) -> TokenResponse: ...

    @swagger_operation("POST", "/token", spec="Автотека.json",
                       operation_id="getAccessToken",
                       method_args={"request": "query.grant_type"},
                       variant="async")
    async def request_autoteka_client_credentials_token(self, request) -> TokenResponse: ...

    async def request_refresh_token(self, request) -> TokenResponse: ...   # без binding (sync тоже без)
```

`AsyncAlternateTokenClient` — зеркало sync-аналога с `variant="async"` на двух методах
(`getAccessTokenAuthorizationCode`, `refreshAccessTokenAuthorizationCode`).

`avito/core/swagger_discovery.py._NON_DOMAIN_BINDING_MODULES` дополняем
`"avito.auth.async_provider"` (или `async_token_client`, в зависимости от того, где живут
классы) — иначе async-bindings auth-домена не попадут в discovery.

### `avito/async_client.py`

```python
class AsyncAvitoClient:
    def __init__(self, settings: AvitoSettings | None = None, *,
                 client_id: str | None = None,
                 client_secret: str | None = None,
                 http_client: httpx.AsyncClient | None = None) -> None: ...

    @classmethod
    def from_env(cls, *, env_file=...) -> AsyncAvitoClient: ...
    @classmethod
    def _from_transport(cls, settings, *, transport, auth_provider) -> AsyncAvitoClient: ...

    @property
    def settings(self) -> AvitoSettings: ...
    @property
    def auth_provider(self) -> AsyncAuthProvider: ...
    @property
    def transport(self) -> AsyncTransport: ...

    async def aclose(self) -> None: ...
    async def __aenter__(self) -> AsyncAvitoClient: ...
    async def __aexit__(self, *exc) -> None: ...

    # M2+ постепенно добавляются (один factory на этап):
    # def account(self, user_id=None) -> AsyncAccount: ...
    # ...
```

В M1 `AsyncAvitoClient` без factory-методов — только lifecycle и smoke-вызов через сырой
`transport.request_json(...)` в тесте. **Convenience методы `account_health`,
`business_summary`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`,
`promotion_summary`, `capabilities`** на `AsyncAvitoClient` — отдельный (последний)
этап M-final, потому что они комбинируют 5+ доменов и не нужны до того, как все домены
портированы.

### `avito/testing/async_fake_transport.py`

```python
class AsyncFakeTransport:
    def __init__(self, *, base_url: str = "https://api.avito.ru") -> None: ...
    def add(self, method, path, *responses) -> AsyncFakeTransport: ...
    def add_json(self, method, path, payload, *, status_code=200, headers=None) -> AsyncFakeTransport: ...
    def build(self, *, retry_policy=None, user_id=None) -> AsyncTransport: ...
    def as_client(self, *, user_id=None, retry_policy=None) -> AsyncAvitoClient: ...
    def count(self, *, method=None, path=None) -> int: ...
    def last(self, *, method=None, path=None) -> RecordedRequest: ...
    requests: list[RecordedRequest]
```

Зеркало sync `FakeTransport` (`avito/testing/fake_transport.py`). Использует
`httpx.MockTransport(self._handle)` поверх `httpx.AsyncClient`. `RecordedRequest`,
`JsonValue`, `json_response`, `route_sequence` — переиспользуем без копий из sync.
`sleep` — `lambda _: asyncio.sleep(0)`.

## Swagger binding — детали изменений

1. `SwaggerOperationBinding` (`avito/core/swagger.py`):
   - `variant: Literal["sync","async"] = "sync"` (frozen field, нормализация в `__post_init__` не нужна).
   - Декоратор `swagger_operation(..., variant: Literal["sync","async"] = "sync")`.
   - Двойной декор одной функции остаётся `ConfigurationError`.

2. `DiscoveredSwaggerBinding` (`avito/core/swagger_discovery.py`):
   - `variant: Literal["sync","async"]` копируется из `SwaggerOperationBinding`.
   - `_iter_domain_modules` ищет в каждом пакете оба модуля: `<pkg>.domain` и `<pkg>.async_domain`. Если `async_domain` нет — игнорируем (это нормальная стадия миграции).
   - `canonical_map` — ключ `f"{operation_key}\t{variant}"` (или вложенный mapping).

3. `swagger_linter.py`:
   - `_validate_single_binding_per_sdk_method` — без изменений: ключ `binding.sdk_method` уникален даже в async (т.к. `module.class.method` отличается).
   - `_validate_duplicate_bindings` — ключ `(operation_key, variant)` вместо `operation_key`. Допустимо иметь две независимые цепочки (sync + async) на одну swagger-операцию.
   - `_validate_complete_bindings(operations, bindings)` → `_validate_complete_bindings(operations, bindings, variant)`. Запускается дважды:
     - для `variant="sync"`: ожидаемое множество = все `operations` (как сейчас).
     - для `variant="async"`: ожидаемое множество = только операции из доменов, у которых найден хотя бы один `Async*` discovery binding (class-gated). Помимо `_API_DOMAINS`, для `domain == "auth"` берём операции из `Авторизация.json` и `Автотека.json`, если найден `AsyncTokenClient` / `AsyncAlternateTokenClient`.
   - `_validate_operation_spec_coverage` — без изменений (sync OperationSpec — единый источник истины для обоих режимов; реюз спеки между sync и async-методами не запрещён).
   - `_validate_json_body_model_coverage` — без изменений (контрактные схемы общие).

4. `tests/contracts/test_async_parity.py` — новый тест, проверяет для каждого Async-класса:
   - имя `Async<X>` ↔ существует sync `<X>` в том же пакете;
   - множество публичных async-методов (`async def` без префикса `_`) совпадает с sync-методами;
   - для каждой пары `(sync_method, async_method)`:
     - `inspect.signature(sync).parameters` (без `self`) == `inspect.signature(async).parameters`;
     - аннотация возврата либо совпадает, либо `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`;
     - оба декорированы `@swagger_operation` на ту же `(spec, method, path, operation_id)`, отличаясь только `variant`.

## Этапы

### M1 — Фундамент (1 PR)

DoD:
- [ ] `make check` зелёный: test, typecheck (mypy strict), lint (ruff), swagger-lint --strict, architecture-lint, docstring-lint, build.
- [ ] Покрытие тестами фундамента не ниже sync-аналогов (sample проверка по `coverage report`).
- [ ] Smoke-тест: `AsyncAvitoClient` через `AsyncFakeTransport` + respx делает один авторизованный запрос; токен рефрешится после 401; retry на 429 срабатывает; `Idempotency-Key` пробрасывается.
- [ ] Документация `swagger-binding-subsystem.md` отражает variant и class-gated coverage.
- [ ] Публичная sync-поверхность не изменилась (тесты sync без правок проходят).

### M2…M13 — Этапы по доменам (по PR на домен)

Порядок (нарастающая сложность; пилот на самом простом):

| # | Домен | Sync-методов с binding | Особенности |
|---|---|---|---|
| M2 | `tariffs` | 1 | пилот — обкатка шаблона |
| M3 | `ratings` | 4 | без пагинации |
| M4 | `accounts` | 8 | первая `AsyncPaginatedList` (`get_operations_history`, `list_items_by_employee`); async `_resolve_account_user_id` |
| M5 | `realty` | 7 | без пагинации |
| M6 | `cpa` | 14 | без пагинации |
| M7 | `messenger` | 18 | без пагинации |
| M8 | `jobs` | 25 | webhook-методы (REST) |
| M9 | `promotion` | 24 | без пагинации |
| M10 | `autoteka` | 26 | использует autoteka token flow → проверить `AsyncAuthProvider.get_autoteka_access_token` |
| M11 | `ads` | 28 | вторая и третья `AsyncPaginatedList` (`Ad.list`, `AutoloadProfile`/`AutoloadReport.list`) |
| M12 | `orders` | 45 | самый большой |
| M13 | M-final | — | convenience-методы `AsyncAvitoClient` (`account_health`, `business_summary`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`, `promotion_summary`, `capabilities`); финальный hardening; `docs/site/how-to/async.md`; CHANGELOG → 2.1.0 |

Содержимое каждого M2…M12:

1. `avito/<domain>/async_domain.py` с `Async<X>(AsyncDomainObject)` для каждого sync-`<X>`.
   Импортирует те же `OperationSpec` из `avito/<domain>/operations.py`.
2. Каждый публичный метод декорируется `@swagger_operation(..., variant="async")` теми же
   аргументами `(method, path, spec, operation_id, factory, factory_args, method_args,
   deprecated, legacy)`, что и sync.
3. Регистрация `Async<X>` в `AsyncAvitoClient` (factory-метод по имени, идентичному sync).
4. `tests/domains/<domain>/test_<domain>_async.py` — зеркало
   `tests/domains/<domain>/test_<domain>.py`, через `AsyncFakeTransport`. Тесты помечаем
   `@pytest.mark.asyncio`.
5. Если в домене есть пагинация — соответствующие методы возвращают `AsyncPaginatedList[T]`.
6. `docs/site/reference/<domain>.md` дополняется async-секцией (или второй колонкой).
7. `make check` после этапа: swagger-lint --strict теперь требует async-coverage 1:1 для
   этого домена (class-gated rule увидит свежий `Async<X>` класс).
8. `tests/contracts/test_async_parity.py` зелёный для всех уже портированных доменов.

### Definition of done на каждом этапе

- [ ] Все sync-методы домена имеют async-двойников (parity-тест зелёный).
- [ ] Все async-методы покрыты тестами с теми же сценариями, что sync (golden path,
      ошибки 401/403/422/429, пагинация если есть, idempotency для write-методов,
      `dry_run` если есть).
- [ ] `make check` зелёный.
- [ ] Документация и `make docs-strict` зелёные.

## Верификация (как проверить, что план сработал)

### M1
```bash
poetry install
make test                                 # sync + новые async unit-тесты
make typecheck                            # mypy strict — все Awaitable[T], AsyncPaginatedList[T] корректны
make lint                                 # ruff
make swagger-lint                         # 1) sync coverage 1:1 как сейчас; 2) async coverage пуст и не падает
make check                                # финальный гейт
poetry run pytest tests/core/test_async_transport.py tests/core/test_async_pagination.py \
  tests/core/test_async_executor.py tests/core/test_async_client_lifecycle.py \
  tests/auth/test_async_provider.py tests/contracts/test_async_parity.py
```

Ручной smoke (M1, в тесте — не на проде):
```python
import asyncio, httpx, respx
from avito.async_client import AsyncAvitoClient
from avito.config import AvitoSettings
from avito.auth.settings import AuthSettings

async def main():
    async with AsyncAvitoClient(AvitoSettings(
        base_url="https://api.avito.ru",
        auth=AuthSettings(client_id="x", client_secret="y"),
    )) as client:
        with respx.mock(base_url="https://api.avito.ru") as mock:
            mock.post("/token").respond(json={"access_token":"t","expires_in":3600})
            mock.get("/core/v1/accounts/self").respond(json={"id": 1})
            payload = await client.transport.request_json(
                "GET", "/core/v1/accounts/self",
                context=RequestContext("smoke"),
            )
            assert payload == {"id": 1}

asyncio.run(main())
```

### Каждый M2…M12
```bash
poetry run pytest tests/domains/<domain>/                 # sync + async
poetry run pytest tests/contracts/test_async_parity.py    # инвариант parity
make swagger-lint                                         # async-coverage 1:1 для этого домена
make check
```

### M-final
```bash
make check
make docs-strict
poetry run pytest                                          # полный набор
```

После M-final:
- swagger-lint --strict требует обоюдное 1:1 покрытие (sync + async) для всех 12 доменов и
  auth-bindings;
- `tests/contracts/test_async_parity.py` зелёный для всех доменов;
- релиз 2.1.0 с CHANGELOG: «двухрежимный SDK, AsyncAvitoClient».

## Риски и mitigations

| Риск | Mitigation |
|---|---|
| Расхождение retry/auth-логики sync vs async | Вся не-IO логика — в `_transport_shared.py` и `_cache.py`, обе обёртки делегируют. |
| `AsyncPaginatedList` не наследует `list` → ломаются ожидания сервисов | Документируем в docstring; parity-test допускает `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`. List-API не реплицируется намеренно. |
| Auth-bindings не попадают в async-coverage | `_NON_DOMAIN_BINDING_MODULES` дополнен async-модулем; class-gated coverage гейтится по присутствию `AsyncTokenClient`/`AsyncAlternateTokenClient`. |
| Двойной декор одной функции | Текущая защита `__swagger_binding__` остаётся; sync и async — разные функции. |
| Гонка на refresh-токене в async | `asyncio.Lock` в `AsyncAuthProvider` + double-checked pattern (как sync, но через `await`). |
| Convenience-методы (`account_health`, …) расходятся между sync/async | Делаем их в M-final, когда все домены уже портированы; реализация буквально awaits то же, что sync вызывает напрямую. |
