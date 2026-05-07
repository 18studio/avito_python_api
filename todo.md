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
| Sequencing | M1 — фундамент с тестами; M2-PoC — proof-of-concept шаблона на `tariffs` (валидация фундамента, может вернуть feedback); M3…M12 — закрытие каждого домена отдельным PR на 100%; M-final — convenience-методы и релиз. До появления первого `AsyncX` класса strict-coverage по `variant="async"` пуст и не падает. |
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
`_safe_endpoint`, `_log_http_exchange`, `_log_retry`, `_elapsed_ms`. `Transport` и
`AsyncTransport` остаются тонкими обёртками с двумя различиями: формой sleep и формой
client.request.

**Контракт retry-петли в обоих режимах.** Catch-блок в `Transport.request()` /
`AsyncTransport.request()` ловит **только** `Exception`-наследников (явно: `httpx.RequestError`
и его подклассы). `BaseException` (включая `asyncio.CancelledError`,
`KeyboardInterrupt`, `SystemExit`) **никогда не уходит в retry** — пробрасывается
наружу немодифицированным. Это критично для async: иначе SDK будет ловить отмену
корутины и пытаться её ретраить, нарушая cancellation-семантику. Sync-режим тоже
получает это уточнение (поведенчески идентично — `KeyboardInterrupt` уже не
ретраится в `httpx.RequestError`-блоке). Закрепляется тестом
`tests/core/test_async_transport.py::test_cancelled_error_is_not_retried`.

**Важное уточнение по `_merge_headers`.** Текущая реализация
(`avito/core/transport.py:410-428`) внутри себя делает синхронный вызов
`self._auth_provider.get_access_token()` — то есть couples token retrieval с merge.
Чтобы helper стал IO-agnostic, рефакторим его контракт: shared `_merge_headers`
принимает уже резолвнутый `bearer_token: str | None`, а резолв (включая `await` в
async-варианте) выполняют сами `Transport`/`AsyncTransport` отдельно. Это первый шаг
Phase 1 (без поведенческих изменений sync), и он blocking для всего остального M1.

Аналогично: `avito/auth/_cache.py` содержит in-memory state (поля `_access_token`,
`_refresh_token`, `_autoteka_access_token`) и чистые helpers (`_is_token_fresh`).
Module-level функция `_map_token_response` (`avito/auth/provider.py:35`) переезжает
в `_cache.py` без изменения сигнатуры. `AuthProvider` и `AsyncAuthProvider`
делегируют кешу, сами добавляют только sync/async lock + IO.

### Порядок зависимостей в M1

```
  Phase 0   pre-flight (см. раздел "Pre-flight для PR M1")
            ↓
  Phase 1a  рефактор Transport._merge_headers → принимает резолвнутый bearer_token
            (sync без поведенческих изменений; baseline тестов pass/fail идентичен)
            ↓
  Phase 1b  _transport_shared.py  ◀── остальной IO-agnostic экстракт из Transport
            _cache.py             ◀── TokenCache + map_token_response, AuthProvider
                                      хранит TokenCache + property-shim'ы для
                                      _access_token/_refresh_token/_autoteka_access_token
                                      (ради существующих тестов)
            ↓
  Phase 2   AsyncTransport, AsyncOperationTransport, AsyncOperationExecutor
            AsyncAuthProvider (с asyncio.Lock на refresh + отдельным autoteka lock)
            AsyncTokenClient, AsyncAlternateTokenClient
            AsyncPaginatedList, AsyncPaginator
            ↓
  Phase 3   variant="async" в swagger декораторе/discovery/linter
            AsyncAvitoClient (без factory-методов; только lifecycle)
            avito/testing/async_fake_transport.py + tests/async_fake_transport.py
                                                    (re-export с DeprecationWarning)
            ↓
  Phase 4   тесты + docs (включая baseline-diff prove sync без изменений)
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
| `avito/auth/provider.py` | Извлекаем shared cache state в `_cache.py`. Сам `AuthProvider` остаётся sync. Сохраняем `_access_token`/`_refresh_token`/`_autoteka_access_token` как `@property` shim'ы поверх `TokenCache` (с сеттерами), потому что `tests/core/test_authentication.py:122-127` мутирует поле напрямую через `replace()`. |
| `avito/core/transport.py` (отдельно) | Phase 1a: `_merge_headers` рефакторится первым — принимает уже резолвнутый bearer-token, резолв вызывается отдельной строкой выше. Все остальные shared helpers — Phase 1b. |
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
                                         #   (_merge_headers принимает bearer_token: str | None)
avito/core/async_transport.py            # AsyncTransport (httpx.AsyncClient)
avito/core/async_pagination.py           # AsyncPaginatedList, AsyncPaginator, AsyncPageFetcher
avito/auth/_cache.py                     # TokenCache + map_token_response
avito/auth/async_provider.py             # AsyncAuthProvider (отдельные asyncio.Lock для
                                         #   основного и autoteka токенов)
avito/auth/async_token_client.py         # AsyncTokenClient, AsyncAlternateTokenClient
                                         #   (со @swagger_operation(..., variant="async"))
avito/async_client.py                    # AsyncAvitoClient (lifecycle + factory-методы пустые в M1)
avito/testing/async_fake_transport.py    # AsyncFakeTransport (httpx.MockTransport+AsyncClient)
tests/async_fake_transport.py            # тонкий re-export с DeprecationWarning (как у sync;
                                         #   шаблон скопирован 1:1 с tests/fake_transport.py)
tests/core/test_async_transport.py
tests/core/test_async_pagination.py
tests/core/test_async_executor.py
tests/core/test_async_client_lifecycle.py
tests/auth/test_async_provider.py
tests/contracts/test_async_parity.py     # инвариант "Async<X> ↔ X" для всех портированных доменов
```

### Новые файлы (M2-PoC + M3…M12, на каждый домен)

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

`AsyncTransport.request()` внутри:

1. вызывает `bearer_token = await self._auth_provider.get_access_token()` (если требуется);
2. передаёт `bearer_token` в shared `_merge_headers(...)` — строго pure-функция;
3. петля retry-decisions делегирует в shared `_decide_*_retry`;
4. при 401 — `self._auth_provider.invalidate_token()` (sync-операция clear cache),
   повторный `await self._auth_provider.get_access_token()`, один retry;
5. ловит **только** `Exception`-наследников (`httpx.RequestError` и т.п.).
   `asyncio.CancelledError` и любой `BaseException` пробрасываются наружу без retry —
   см. контракт shared retry-петли выше.

**Rate-limiter в async.** Один `RateLimiter` принадлежит одному `AsyncTransport`
(а не каждой корутине-вызову). Все корутины, делящие транспорт, должны
сериализоваться через `asyncio.Lock` внутри лимитера — иначе N параллельных запросов
независимо посчитают «надо ждать X секунд» и улетят пачкой после ожидания, нарушив
лимит. Sync `RateLimiter` (логика «ждать сколько») переезжает в `_transport_shared.py`
без поведенческих изменений; `AsyncRateLimiter`-обёртка — тонкая: `asyncio.Lock`
+ `await asyncio.sleep(delay)`. Lock создаётся лениво (как `_refresh_lock` в
`AsyncAuthProvider`) — биндится к event loop'у при первом `await`.

### `avito/core/operations.py` (расширение)

```python
class AsyncOperationTransport(Protocol):
    async def request(...) -> httpx.Response: ...           # async def, не Awaitable[T]
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

Замечание по типизации Protocol: для async-методов в `Protocol` используем `async def`, а
не `Awaitable[T]` в return-аннотации синхронной сигнатуры. Это даёт mypy strict корректный
runtime-protocol matching и избавляет от двойной оборачивания.

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


class AsyncPaginator[ItemT]:
    def __init__(self, fetch_page: AsyncPageFetcher[ItemT]) -> None: ...
    def iter_pages(self, *, start_page: int = 1) -> AsyncIterator[JsonPage[ItemT]]: ...
    async def collect(self, *, start_page: int = 1) -> list[ItemT]: ...
    def as_list(
        self,
        *,
        start_page: int = 1,
        first_page: JsonPage[ItemT] | None = None,
    ) -> AsyncPaginatedList[ItemT]: ...
```

`AsyncPaginatedList` **не** наследует `list[T]` — async-итерация и list-индексация
несовместимы. Документируем это явно в docstring и в `pagination` how-to. Семантика
страничного перехода идентична sync `PaginatedList._consume_page` (включая `next_cursor`,
`page+per_page`, `has_next_page`).

`AsyncPaginator` обязателен: sync-домены используют его в 4 местах
(`avito/ads/domain.py:266,1183`, `avito/accounts/domain.py:170,383`), включая один кейс
(`avito/ads/domain.py:266`), где возвращается `Paginator` напрямую (без `as_list()`) —
async-двойник такого метода вернёт `AsyncPaginator`. У него тот же контракт, что и у
sync `Paginator`, но `iter_pages()` — `AsyncIterator`, `collect()` — корутина. Внутри
`as_list()` создаёт `AsyncPaginatedList`, передавая `first_page` как и sync-аналог.

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

**Compat-shim для существующих тестов.** `tests/core/test_authentication.py:122-127`
напрямую читает и присваивает `provider._access_token` через `dataclasses.replace(...)`.
Чтобы не трогать тесты в M1 PR (риск scope-creep), `AuthProvider` сохраняет три
атрибут-shim'а через `@property`/setter:

```python
@property
def _access_token(self) -> AccessToken | None: return self._cache.access_token
@_access_token.setter
def _access_token(self, value: AccessToken | None) -> None:
    self._cache.access_token = value
# аналогично _refresh_token, _autoteka_access_token
```

Shim-ы помечены `# legacy private accessor — see PR M1` и удаляются позже отдельным PR
с миграцией тестов.

### `avito/auth/async_provider.py`

```python
class AsyncTokenFetcher(Protocol):
    """Async-зеркало sync `TokenFetcher` (avito/auth/provider.py:67-70)."""
    async def __call__(self, settings: AuthSettings) -> TokenResponse: ...


@dataclass(slots=True)
class AsyncAuthProvider:
    settings: AuthSettings
    token_client: AsyncTokenClient | None = None
    alternate_token_client: AsyncAlternateTokenClient | None = None
    autoteka_token_client: AsyncTokenClient | None = None
    token_fetcher: AsyncTokenFetcher | None = None
    _cache: TokenCache = field(default_factory=TokenCache, init=False, repr=False)
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _autoteka_refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def get_access_token(self) -> str: ...    # double-checked + _refresh_lock
    async def refresh_access_token(self) -> TokenResponse: ...
    def invalidate_token(self) -> None: ...         # sync clear cache, без await
    async def aclose(self) -> None: ...
    async def get_autoteka_access_token(self) -> str: ...   # double-checked + _autoteka_refresh_lock
```

**Lock lifecycle.** В Python 3.10+ `asyncio.Lock()`, созданный вне event loop,
лениво биндится к loop'у при первом `await`. Чтобы не получить cross-loop UB:
`AsyncAuthProvider` создаётся внутри `AsyncAvitoClient.__aenter__` (или `_from_transport`),
и не переиспользуется между разными event loop'ами. Документируем это в docstring
`AsyncAvitoClient` и в risk-секции.

Отдельный `_autoteka_refresh_lock` нужен потому, что concurrent first-touch
`get_autoteka_access_token()` вызывал бы дублирующиеся OAuth-запросы Автотеки. Sync-провайдер
этой защиты не имеет (GIL не помогает между потоками), но в async это уже явная гонка.

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

Внутри `AsyncTokenClient._request_token` создаётся **отдельный `AsyncTransport`** с
`auth_provider=None` (зеркало sync `TokenClient._build_transport()`, см.
`avito/auth/provider.py:345-350`). Использование основного `AsyncTransport` через
`AsyncAuthProvider` запрещено — это закольцует OAuth-запрос через сам же auth-провайдер.

`avito/core/swagger_discovery.py._NON_DOMAIN_BINDING_MODULES` дополняем строго
`"avito.auth.async_token_client"` (а не `async_provider`) — потому что классы со swagger
binding-ами (`AsyncTokenClient`, `AsyncAlternateTokenClient`) живут именно там. Иначе
async-bindings auth-домена не попадут в discovery.

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

    # M2-PoC: tariff() добавляется как валидация шаблона
    # M3+: на каждом этапе добавляются ВСЕ factory-методы домена сразу
    # def tariff(self) -> AsyncTariff: ...                # M2-PoC
    # def account(self, user_id=None) -> AsyncAccount: ...# M4
    # ...
```

**Ownership чужого `httpx.AsyncClient`.** Если `http_client` передан в `__init__`
извне — пользователь сам отвечает за его lifecycle: `aclose()` / `__aexit__` его
**не** закрывают (`AsyncTransport` хранит флаг `_owns_client = http_client is None`).
Это зеркало sync-политики (см. `avito/core/transport.py` — sync `Transport` уже
делает это для `httpx.Client`). Любое расхождение с sync = blocker.

**Rollback при partial failure в `__aenter__`.** Если `__aenter__` бросает в
середине (например, `httpx.AsyncClient` уже создан, но `AsyncAuthProvider.__post_init__`
или ленивая инициализация локов даёт исключение), весь уже-созданный state должен
быть закрыт до проброса наружу. Реализация:

```python
async def __aenter__(self) -> AsyncAvitoClient:
    try:
        # любая инициализация, которая может бросить
        await self._transport.__aenter__()
        return self
    except BaseException:
        await self.aclose()  # idempotent: безопасен на полу-инициализированном state
        raise
```

`aclose()` идемпотентен и устойчив к закрытию полу-инициализированного состояния
(каждый под-ресурс проверяет `is None` перед `await x.aclose()`). Закрепляется
тестом `tests/core/test_async_client_lifecycle.py::test_aenter_rollback_on_partial_failure`.

В M1 `AsyncAvitoClient` без factory-методов — только lifecycle и smoke-вызов через сырой
`transport.request_json(...)` в тесте. **Convenience методы `account_health`,
`business_summary`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`,
`promotion_summary`, `capabilities`** на `AsyncAvitoClient` — отдельный (последний)
этап M-final, потому что они комбинируют 5+ доменов и не нужны до того, как все домены
портированы. Реализация **не** должна буквально повторять sync последовательно: каждый
такой метод запускает независимые подзапросы параллельно — это и есть основной
user-value async-режима для агрегационных операций.

**Cancellation-safe паттерн (обязательный).** Используется `asyncio.TaskGroup`
(Python 3.11+, у нас floor 3.12+) с per-section try/except, конвертирующим `AvitoError
→ SummaryUnavailableSection` (как sync `_safe_summary`, `avito/client.py:91-98`).
`asyncio.gather(..., return_exceptions=True)` запрещён, потому что он возвращает
`CancelledError` как обычный результат — это глушит cancellation семантику. Шаблон:

```python
async def _safe_summary_async[T](
    section: str, factory: Callable[[], Awaitable[T]],
) -> tuple[T | None, list[SummaryUnavailableSection]]:
    try:
        return await factory(), []
    except asyncio.CancelledError:
        raise               # отмена пробрасывается, никогда не глушим
    except AvitoError as error:
        return None, [_summary_unavailable_section(section, error)]

async def business_summary(self, ...) -> BusinessSummary:
    async with asyncio.TaskGroup() as tg:
        t_acc = tg.create_task(_safe_summary_async("account", lambda: ...))
        t_chat = tg.create_task(_safe_summary_async("chat", lambda: ...))
        ...
    # После выхода из TaskGroup все таски завершены или отменены атомарно.
```

При отмене внешнего вызова `TaskGroup` отменит все child-таски и пробросит
`CancelledError` — без зависших корутин и без частичного state.

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

**Concurrency policy.** `_handle` мутирует `self.requests.append(...)` и `route.pop(0)`
для `route_sequence`-сценариев. Для тестов с `asyncio.gather(...)` (в первую очередь
M-final convenience-методы) `_handle` берёт `self._handle_lock = asyncio.Lock()` и
сериализует match-and-record под ним. Без этого две параллельные корутины могут
одновременно дёрнуть `route.pop(0)` и получить непредсказуемый порядок ответов.
Lock создаётся лениво при первом `_handle`-вызове (cross-loop safe). Документируется
в docstring класса: «AsyncFakeTransport безопасен для concurrent access внутри
одного event loop'а; не переиспользовать между разными loop'ами».

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
   - `_validate_operation_spec_coverage` — без изменений (sync OperationSpec — единый источник истины для обоих режимов; реюз спеки между sync и async-методами не запрещён). `used_specs` — `set[id(spec)]`, поэтому одна и та же `OperationSpec` от sync и async binding'ов не дублируется и не теряется.
   - `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`) — резолвит spec через `unwrapped_method.__globals__`. Async-методы должны импортировать spec явно (`from avito.<domain>.operations import LIST_SPEC`), иначе резолв вернёт `()` и spec будет считаться unbound. Pre-flight тест проверяет, что это работает; если нет — расширяем функцию в Phase 1b.
   - `_validate_json_body_model_coverage` — без изменений (контрактные схемы общие).

4. `tests/contracts/test_async_parity.py` — новый тест, проверяет для каждого Async-класса:
   - имя `Async<X>` ↔ существует sync `<X>` в том же пакете;
   - множество публичных async-методов (`async def` без префикса `_`) совпадает с sync-методами;
   - перебор методов фильтруется по `func.__qualname__.startswith(cls.__name__ + ".")`,
     чтобы не учитывать унаследованные от `AsyncDomainObject` (`_execute`, `_resolve_user_id`)
     или `object` методы;
   - для каждой пары `(sync_method, async_method)`:
     - `inspect.signature(sync).parameters` (без `self`) == `inspect.signature(async).parameters`;
     - аннотация возврата либо совпадает, либо `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`,
       либо `Paginator[T]` ↔ `AsyncPaginator[T]`;
     - оба декорированы `@swagger_operation` на ту же `(spec, method, path, operation_id)`, отличаясь только `variant`.

## Этапы

### Pre-flight для PR M1

До открытия PR M1 (всё это делается локально и валидируется до коммита):

- [ ] `grep -rn "\._access_token\|\._refresh_token\|\._autoteka_access_token" tests/` —
      зафиксировать все private probes; убедиться, что compat-shim в `AuthProvider`
      покроет каждый. Найденный сейчас кейс: `tests/core/test_authentication.py:122-127`.
- [ ] `grep -rn "\bPaginator\b" avito/` — зафиксировать все 4 usage-сайта
      (`avito/ads/domain.py:266,1183`, `avito/accounts/domain.py:170,383`); они
      определяют, нужен ли `AsyncPaginator.iter_pages()` и/или `as_list()` уже в M1
      или доставляется в первом домене с пагинацией (M4 `accounts`).
- [ ] `grep -rn "len(.*Paginated\|\\b[a-z_]*list\\[[0-9-]" avito/ tests/` — найти все
      потребители list-API на `PaginatedList[T]` (индексация, `len`, `bool`, slice).
      `AsyncPaginatedList` намеренно НЕ повторяет list-API: каждый такой кейс должен
      быть либо безопасен (только sync), либо явно заменён на `await materialize()` /
      `loaded_count` в async-двойнике. Список фиксируется в commit-message PoC.
- [ ] `grep -rn "^async def test_" tests/` — убедиться, что в существующих тестах нет
      async-функций без `@pytest.mark.asyncio`. После включения
      `asyncio_mode = "strict"` любой такой тест начнёт игнорироваться (warning,
      не падение). Если найдены — добавить маркер в pre-flight commit, отдельно от M1.
- [ ] Подтвердить минимальную поддерживаемую версию Python в `pyproject.toml`. SDK уже
      использует PEP 695 (`type PageFetcher[ItemT] = ...` в `avito/core/pagination.py:10`),
      значит требуется Python **3.12+**. Все async-контракты (`type AsyncPageFetcher`,
      `async def execute[ResponseT]`) сохраняют этот же floor; повышать не нужно, но
      явно зафиксировать в M1 PR description.
- [ ] Прогон `pytest -q` на чистом `main` — сохранить файл baseline-теста pass/fail
      статусов (`pytest --tb=no -q > /tmp/baseline_main.txt`). Используется в DoD M1.
- [ ] Проверить, что `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`)
      работает с `async_domain.py`: тест-стаб с `async def m(self): return self._execute(SOME_SPEC)`
      и `from ...operations import SOME_SPEC` — функция должна найти `SOME_SPEC` через
      `unwrapped_method.__globals__`. Если не работает — расширить функцию (Phase 1b),
      иначе оставить без изменений.

### M1 — Фундамент (1 PR)

DoD:
- [ ] `make check` зелёный: test, typecheck (mypy strict), lint (ruff), swagger-lint --strict, architecture-lint, docstring-lint, build.
- [ ] Покрытие тестами фундамента не ниже sync-аналогов (sample проверка по `coverage report`).
- [ ] Smoke-тест: `AsyncAvitoClient` через `AsyncFakeTransport` (без respx) делает один авторизованный запрос; токен рефрешится после 401; retry на 429 срабатывает; `Idempotency-Key` пробрасывается; `aclose()` корректно закрывает `httpx.AsyncClient` и `AsyncAuthProvider`.
- [ ] Документация `swagger-binding-subsystem.md` отражает variant и class-gated coverage.
- [ ] Публичная sync-поверхность не изменилась — formal: `pytest -q tests/core/ tests/auth/ tests/domains/ tests/contracts/ --tb=no` имеет идентичный список pass/fail с baseline-теста с `main` (см. pre-flight). Любое расхождение = blocker, до выяснения причины PR не мерджится.
- [ ] Phase 1a (`_merge_headers` рефакторинг) выделен отдельным коммитом внутри PR — для bisect-friendly history.

### M2-PoC — Proof-of-concept шаблона (отдельный PR, до переработки доменов)

**Цель этого шага — НЕ закрыть домен `tariffs`, а валидировать шаблон.** Это
осознанное исключение из правила «домен закрывается на 100%»: PoC может вернуть
feedback вида «контракт `AsyncPaginator` нужно расширить», «discovery не видит
spec»,  «mypy strict ругается на covariance возврата» — и это нормальный ожидаемый
выход. Все правки контракта вносятся в **этот же PR**, а если правки требуют
переработки M1-фундамента — PoC откатывается, фундамент дорабатывается отдельным
PR, после чего PoC переоткрывается.

PoC берёт `tariffs` (1 sync-операция с binding) — минимальная поверхность без
пагинации, без autoteka-flow, без write-методов. Этого достаточно, чтобы ткнуть
все слои фундамента в один сценарий end-to-end.

DoD M2-PoC:
- [ ] `avito/tariffs/async_domain.py` создан, `AsyncTariff` зеркалит `Tariff`
      ровно по 1 публичному методу.
- [ ] `AsyncAvitoClient.tariff()` factory-метод возвращает `AsyncTariff`.
- [ ] `tests/domains/tariffs/test_tariffs_async.py` зеркалит sync-тест 1:1
      (golden path + 401 + 429 + transport error). Все тесты зелёные.
- [ ] `make check` зелёный, включая `swagger-lint --strict` (для `tariffs` теперь
      требуется async-coverage 1:1).
- [ ] `tests/contracts/test_async_parity.py` зелёный.
- [ ] Документация `docs/site/reference/tariffs.md` дополнена async-секцией.
- [ ] **Lessons learned зафиксированы** в `docs/site/explanations/async-domain-template.md`
      (новый файл): шаблон файла `async_domain.py`, чек-лист переноса домена,
      найденные подводные камни. Этот документ становится нормативным для M3+.
- [ ] Если в ходе PoC понадобились изменения контракта (`AsyncPaginator`/`AsyncFakeTransport`/
      `swagger_linter`/`AsyncAuthProvider`), они **внесены в этот же PR** или вынесены
      в отдельный M1.5-PR, но **до** старта M3.

### M3…M12 + M-final — Закрытие доменов (по PR на домен)

Порядок (нарастающая сложность; самый простой шёл в PoC):

| # | Домен | Sync-методов с binding | Особенности |
|---|---|---|---|
| M3 | `ratings` | 4 | без пагинации |
| M4 | `accounts` | 8 | первая `AsyncPaginatedList` (`get_operations_history`, `list_items_by_employee`); async `_resolve_account_user_id` |
| M5 | `realty` | 7 | без пагинации |
| M6 | `cpa` | 14 | без пагинации |
| M7 | `messenger` | 18 | без пагинации |
| M8 | `jobs` | 25 | webhook-методы (REST) |
| M9 | `promotion` | 24 | без пагинации |
| M10 | `autoteka` | 26 | использует autoteka token flow → end-to-end проверка `AsyncAuthProvider.get_autoteka_access_token` + `_autoteka_refresh_lock` под нагрузкой (concurrent first-touch) |
| M11 | `ads` | 28 | вторая и третья `AsyncPaginatedList` (`Ad.list`, `AutoloadProfile`/`AutoloadReport.list`); прямой возврат `AsyncPaginator` (`avito/ads/domain.py:266`) |
| M12 | `orders` | 45 | самый большой; идемпотентность критична |
| M-final | — | — | convenience-методы `AsyncAvitoClient` (`account_health`, `business_summary`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`, `promotion_summary`, `capabilities`) — выполняют независимые подзапросы через `asyncio.TaskGroup` (cancellation-safe; `asyncio.gather(return_exceptions=True)` запрещён); per-section error handling — как в sync `_safe_summary`. Финальный hardening; `docs/site/how-to/async.md`; CHANGELOG → 2.1.0 |

Содержимое каждого M3…M12:

1. `avito/<domain>/async_domain.py` с `Async<X>(AsyncDomainObject)` для **каждого**
   sync-`<X>` в домене. Импортирует те же `OperationSpec` из
   `avito/<domain>/operations.py` **явно по именам**
   (`from avito.<domain>.operations import LIST_SPEC, GET_SPEC, ...`) — иначе
   `_operation_specs_for_sdk_method` не сможет резолвнуть spec через `__globals__`
   и swagger-lint выдаст `SWAGGER_OPERATION_SPEC_MISSING`.
2. **Каждый** публичный метод декорируется `@swagger_operation(..., variant="async")`
   теми же аргументами `(method, path, spec, operation_id, factory, factory_args,
   method_args, deprecated, legacy)`, что и sync.
3. Регистрация **всех** `Async<X>` домена в `AsyncAvitoClient` (factory-методы по
   именам, идентичным sync).
4. `tests/domains/<domain>/test_<domain>_async.py` — зеркало
   `tests/domains/<domain>/test_<domain>.py`, через `AsyncFakeTransport`. Тесты
   помечаем `@pytest.mark.asyncio`. **Каждый** sync-тест имеет async-двойник
   с тем же сценарием.
5. Если в домене есть пагинация — соответствующие методы возвращают
   `AsyncPaginatedList[T]` или `AsyncPaginator[T]` (зеркально sync). M4 `accounts` —
   первый домен с `AsyncPaginatedList`; M11 `ads` — первый домен с прямым
   `AsyncPaginator` (см. `avito/ads/domain.py:266`).
6. `docs/site/reference/<domain>.md` дополняется async-секцией (или второй колонкой).
7. Если в домене есть write-методы с `dry_run` — async-двойник реализует тот же
   контракт: при `dry_run=True` транспорт **не вызывается** (тест проверяет
   `count(method=..., path=...) == 0`).
8. Если в домене есть idempotency-key поведение — async-тесты явно проверяют
   проброс заголовка `Idempotency-Key`.

### Definition of done каждого M3…M12 — закрыть домен на 100%, без работы на потом

«100%» определяется проверяемо. Все пункты ниже — **обязательные**, не «nice to have»:

- [ ] **Покрытие методов 1:1**: для каждого публичного sync-метода домена есть
      async-двойник; `tests/contracts/test_async_parity.py` зелёный для домена.
      Локальная проверка: `python -c "from avito.<domain>.domain import *; from
      avito.<domain>.async_domain import *"` + parity-test без skip-маркеров.
- [ ] **Покрытие тестов 1:1**: каждый сценарий из `tests/domains/<domain>/test_*.py`
      имеет async-двойник; счётчики тестов сверены: `pytest --collect-only -q
      tests/domains/<domain>/ | grep -c "test_.*async\|test_.*[^c]$"` показывает
      идентичное количество sync- и async-тестов. Покрываются: golden path, 401,
      403, 422, 429, transport error/timeout, пагинация (если есть), idempotency
      (для write), `dry_run` (если есть в sync).
- [ ] **Swagger-lint coverage 1:1 для домена**: `swagger-lint --strict` после этапа
      требует async binding для **каждой** swagger-операции этого домена; class-gated
      coverage гейт включён, и domain больше не «пуст по async». Никаких
      исключений/skip'ов для отдельных методов.
- [ ] **Документация**: `docs/site/reference/<domain>.md` содержит async-секцию для
      **всех** портированных классов; `make docs-strict` зелёный; ссылки и примеры
      кода скомпилированы.
- [ ] **Никаких TODO/FIXME/`pytest.skip`/`xfail` в добавленных файлах**:
      `git diff main..HEAD -- avito/<domain>/ tests/domains/<domain>/ | grep -E
      "TODO|FIXME|@pytest.mark.skip|xfail"` пуст. Любая отсрочка работы = blocker.
- [ ] **`make check` локально и в CI зелёный**.
- [ ] **AsyncAvitoClient полностью настроен для домена**: factory-методы возвращают
      готовые объекты, lifecycle (`aclose`/`__aexit__`) корректно закрывает все
      ресурсы домена.
- [ ] **Регрессия sync = 0**: список pass/fail sync-тестов идентичен предыдущему
      этапу (sanity-проверка через сравнение `pytest -q --tb=no` до и после).
- [ ] **Cumulative parity invariant**: после merge'а `tests/contracts/test_async_parity.py`
      зелёный для **всех** уже портированных доменов (включая текущий). Этап не
      может ослабить инвариант для предыдущих доменов.
- [ ] **Нет работы «потом»**: переоткрытие PR с фразой «допилю в следующем PR»
      запрещено. Если scope не закрывается — PR разделяется или раздвигается, но
      не оставляется частичный домен в main.

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

Ручной smoke (M1, в тесте — не на проде; через `AsyncFakeTransport`, без `respx`):
```python
import asyncio
from avito.testing.async_fake_transport import AsyncFakeTransport
from avito.core.types import RequestContext

async def main():
    async with (
        AsyncFakeTransport()
        .add_json("POST", "/token", {"access_token": "t", "expires_in": 3600})
        .add_json("GET", "/core/v1/accounts/self", {"id": 1})
        .as_client()
    ) as client:
        payload = await client.transport.request_json(
            "GET", "/core/v1/accounts/self",
            context=RequestContext("smoke"),
        )
        assert payload == {"id": 1}

asyncio.run(main())
```

`AsyncFakeTransport` строится на `httpx.MockTransport(self._handle)` поверх
`httpx.AsyncClient` — это уже самодостаточный механизм перехвата; `respx` поверх него
избыточен. Использовать `respx` стоит только если в smoke нужен уникальный матчер,
которого `add_json`/`add` не покрывает (на текущем этапе таких нет).

### M2-PoC (proof-of-concept)
```bash
poetry run pytest tests/domains/tariffs/                  # sync + async для tariffs
poetry run pytest tests/contracts/test_async_parity.py    # parity для tariffs
make swagger-lint                                         # async-coverage 1:1 для tariffs
make check
# Артефакт: docs/site/explanations/async-domain-template.md создан
```

### Каждый M3…M12 (закрытие домена на 100%)
```bash
# Sync regression baseline (sanity)
poetry run pytest -q --tb=no tests/domains/<domain>/test_<domain>.py > /tmp/sync_before.txt

# После применения изменений:
poetry run pytest tests/domains/<domain>/                 # sync + async
poetry run pytest -q --tb=no tests/domains/<domain>/test_<domain>.py > /tmp/sync_after.txt
diff /tmp/sync_before.txt /tmp/sync_after.txt             # должен быть пустой

poetry run pytest tests/contracts/test_async_parity.py    # parity для всех закрытых доменов
make swagger-lint                                         # async-coverage 1:1 для этого домена

# Грязные следы — пустой выхлоп
git diff main..HEAD -- avito/<domain>/ tests/domains/<domain>/ \
  | grep -E "TODO|FIXME|@pytest.mark.skip|xfail" || echo "OK: no leftover work"

# Cumulative счётчики (sync-тестов = async-тестов в домене)
sync_count=$(poetry run pytest --collect-only -q tests/domains/<domain>/test_<domain>.py | grep -c "::test_")
async_count=$(poetry run pytest --collect-only -q tests/domains/<domain>/test_<domain>_async.py | grep -c "::test_")
test "$sync_count" -eq "$async_count" && echo "OK: $sync_count == $async_count"

make check
make docs-strict
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
| `_merge_headers` срытно делает sync IO (`get_access_token()`) | Phase 1a первым шагом рефакторит контракт: helper принимает уже резолвнутый `bearer_token: str | None`. Без этого shared слой не IO-agnostic, и vary-логика расползётся. |
| `AsyncPaginatedList` не наследует `list` → ломаются ожидания сервисов | Документируем в docstring; parity-test допускает `PaginatedList[T]` ↔ `AsyncPaginatedList[T]` и `Paginator[T]` ↔ `AsyncPaginator[T]`. List-API не реплицируется намеренно. |
| `AsyncPaginator` не покрывает кейс прямого возврата `Paginator` без `as_list()` | Контракт `AsyncPaginator` симметричен sync (`iter_pages`/`collect`/`as_list`); все 5 текущих usage-сайтов покрыты. |
| Auth-bindings не попадают в async-coverage | `_NON_DOMAIN_BINDING_MODULES` дополнен строго `"avito.auth.async_token_client"`; class-gated coverage гейтится по присутствию `AsyncTokenClient`/`AsyncAlternateTokenClient`. |
| Двойной декор одной функции | Текущая защита `__swagger_binding__` остаётся; sync и async — разные функции. |
| Гонка на основном refresh-токене в async | `asyncio.Lock` (`_refresh_lock`) в `AsyncAuthProvider` + double-checked pattern (как sync, но через `await`). |
| Гонка на autoteka-токене в async | Отдельный `_autoteka_refresh_lock` + double-checked в `get_autoteka_access_token()`. Sync аналога не имел, потому что в sync GIL предотвращает деление instruction stream между потоками; в async это явная race-condition. |
| `asyncio.Lock` создан вне event loop'а → cross-loop UB | `AsyncAuthProvider` создаётся внутри `AsyncAvitoClient` (через `__aenter__` или `_from_transport`); в docstring явное предупреждение «не переиспользовать между event loop'ами». Python 3.10+ лениво биндит lock к loop'у при первом `await`. |
| Миграция `_access_token` в `TokenCache` ломает `tests/core/test_authentication.py:122-127` | `AuthProvider` сохраняет `@property`/setter shim'ы для всех трёх частных полей; шим помечен legacy-комментом и удаляется в отдельном PR. |
| `_operation_specs_for_sdk_method` не находит spec из `async_domain.py` | Pre-flight smoke-тест с async-методом + явным импортом spec; текущая реализация через `unwrapped_method.__globals__` (`swagger_linter.py:578-601`) обязана работать, потому что `from ...operations import SOME_SPEC` ставит spec в `__globals__` модуля. Если не работает — фикс в Phase 1b. |
| Convenience-методы (`account_health`, …) теряют main user-value async (параллелизм) | M-final требует `asyncio.TaskGroup` для независимых подзапросов + per-секция try/except `AvitoError → SummaryUnavailableSection` (зеркало sync `_safe_summary`). Запрещено реализовывать «sync, обмазанный await». |
| `asyncio.gather(return_exceptions=True)` глушит `CancelledError` в convenience-методах | Запрещён; используется `asyncio.TaskGroup` (Python 3.11+, у нас floor 3.12+). При отмене внешнего вызова TaskGroup атомарно отменяет все child-таски без потери cancellation. |
| Retry-петля ловит `asyncio.CancelledError` и зацикливает отмену | Shared `_decide_*_retry` и обёртки `Transport`/`AsyncTransport` ловят **только** `Exception`, не `BaseException`. Закреплено тестом `test_cancelled_error_is_not_retried`. |
| `AsyncAvitoClient.__aenter__` оставляет полу-инициализированный state при ошибке | `__aenter__` обёрнут `try/except BaseException`: при любом исключении вызывает идемпотентный `aclose()` и пробрасывает наружу. Закреплено тестом `test_aenter_rollback_on_partial_failure`. |
| Ownership чужого `httpx.AsyncClient` не определён — потенциальный resource-leak или double-close | `AsyncTransport` хранит `_owns_client = http_client is None`; внешне переданный клиент `aclose()`/`__aexit__` не закрывают. Зеркало sync-политики; расхождение = blocker. |
| `AsyncFakeTransport` рассинхронизирован при `asyncio.gather` | `_handle_lock = asyncio.Lock()` сериализует match-and-record; create lazily. Закреплено тестом `test_async_fake_transport_concurrent_handle`. |
| Существующие `async def test_*` в репозитории молча скипаются после `asyncio_mode = "strict"` | Pre-flight `grep -rn "^async def test_" tests/` фиксирует все такие тесты до M1; маркер `@pytest.mark.asyncio` добавляется отдельным pre-flight commit'ом. |
| `len(PaginatedList)` / `paginated[0]` в коде ломаются при попытке мигрировать на `AsyncPaginatedList` | Pre-flight `grep` фиксирует все list-API usage. `AsyncPaginatedList` не повторяет list-API намеренно; каждый кейс заменяется на `await materialize()` / `loaded_count` в async-двойнике или остаётся sync-only. |
| Скрытая работа «на потом» в доменных PR (TODO/FIXME/skip) | DoD M3…M12 явно требует пустой выхлоп `grep -E "TODO|FIXME|@pytest.mark.skip|xfail"` по diff'у; счётчики sync- и async-тестов сравниваются равенством; PR не мерджится при частичном покрытии домена. |
| PoC обнаруживает, что фундамент (M1) недостаточен | Это и есть назначение PoC: feedback от M2-PoC → правки фундамента в этом же PR или M1.5-PR; `tariffs`-домен после доработок закрыт на 100%, как и остальные. M3 не стартует, пока M2-PoC не зелёный. |
| `AsyncTokenClient._request_token` закольцован через основной auth-провайдер | Внутри создаётся независимый `AsyncTransport` с `auth_provider=None` (зеркало sync `TokenClient._build_transport()`). |
| Sync поведение незаметно изменилось в Phase 1 | DoD M1 включает baseline-diff: `pytest --tb=no -q` до и после M1 даёт идентичный список pass/fail. Любое расхождение блокирует merge. Phase 1a — отдельный коммит для bisect. |
