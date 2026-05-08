# Двухрежимный SDK (sync + async)

## Контекст

SDK сейчас полностью синхронный: `AvitoClient` → `Transport` (`httpx.Client` + `time.sleep`) →
`AuthProvider` (`TokenClient` поверх sync-transport) → `DomainObject` подклассы
(11 API-пакетов + auth-bindings, 204 swagger-операции) → `PaginatedList[T]`
(наследник `list`). Цель — добавить вторую,
асинхронную, поверхность по образцу `httpx.Client`/`httpx.AsyncClient`, без слома sync-API,
с переиспользованием `OperationSpec`, моделей, request/query DTO, swagger-инвариантов и
ошибок.

## Принятые решения

| Вопрос | Решение |
|---|---|
| Стиль | Параллельные классы вручную: рядом с каждым sync-слоем кладём `Async*` класс. Codegen не используем. |
| Размещение | `avito/<domain>/async_domain.py` рядом с `domain.py`. |
| Swagger-binding | `@swagger_operation(..., variant="sync"\|"async")`. Уникальный ключ линтера — `(operation_key, variant)`. |
| Нормативные документы | M1 обновляет `STYLEGUIDE.md`, потому что сейчас он описывает SDK как sync-only и разрешает только `domain.py`. Без этого M1 конфликтует с главным style gate. |
| Sequencing | M1 — фундамент с тестами и async auth-bindings; M2-PoC — proof-of-concept шаблона на `tariffs` (валидация фундамента, может вернуть feedback); M3…M12 — закрытие каждого домена отдельным PR на 100%; M-final — convenience-методы и релиз. До появления первого доменного `Async<X>` класса strict-coverage по `variant="async"` для API-доменов пуст и не падает; auth gated отдельно по `AsyncTokenClient` / `AsyncAlternateTokenClient`. |
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
`_safe_endpoint`, `_log_http_exchange`, `_log_retry`, `_elapsed_ms`,
`RateLimitState` (pure token-bucket state с `compute_delay()`/`observe_response()`,
без `Lock` и без `sleep` — см. блок «Контракт shared-частей RateLimiter» ниже).
`Transport` и `AsyncTransport` остаются тонкими обёртками с тремя различиями:
формой sleep, формой client.request, и типом lock'а вокруг `RateLimitState`
(`threading.Lock` vs `asyncio.Lock`).

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
| `avito/core/operations.py` | + `AsyncOperationTransport` (Protocol, async зеркало `OperationTransport`), + `AsyncOperationExecutor` (async зеркало `OperationExecutor.execute`) с теми же ветками `json` / `empty` / `binary`, что и sync. Helpers `render_path`, `_serialize_query`, `_serialize_request`, `_merge_content_type`, `_extract_filename` уже module-level — переиспользуем без копий. |
| `avito/core/swagger.py` | + поле `variant: Literal["sync","async"] = "sync"` в `SwaggerOperationBinding`. + параметр `variant` в `swagger_operation(...)`. Ошибка `ConfigurationError` при двойном декоре одной функции — без изменений. |
| `avito/core/swagger_discovery.py` | `_iter_domain_modules` дополнительно ищет `<domain>.async_domain` (рядом с `<domain>.domain`). `DiscoveredSwaggerBinding` получает `variant`. `canonical_map` остаётся sync-only compatibility API для существующих sync contract tests; новый `canonical_map_by_variant` / `binding_for(operation_key, variant)` использует ключ `(operation_key, variant)`. |
| `avito/core/swagger_linter.py` | `_validate_duplicate_bindings` группирует по `(operation_key, variant)`. `_validate_complete_bindings` запускается per-variant; для `variant="async"` ожидаемое множество ограничено доменами, у которых уже найден `Async*` класс (class-gated coverage). `_validate_no_unbound_operation_specs` остаётся по `OperationSpec` (sync OperationSpec реюзается обоими режимами — счётчик использований единый). |
| `avito/core/swagger_report.py` | JSON report становится variant-aware: summary хранит `sync` и `async` coverage отдельно, `operations[].bindings` содержит mapping по variant. Старые поля `bound`/`unbound` остаются sync-only compatibility до отдельного report API bump. |
| `avito/auth/provider.py` | Извлекаем shared cache state в `_cache.py`. Сам `AuthProvider` остаётся sync. Сохраняем `_access_token`/`_refresh_token`/`_autoteka_access_token` как `@property` shim'ы поверх `TokenCache` (с сеттерами), потому что `tests/core/test_authentication.py:122-127` мутирует поле напрямую через `replace()`. |
| `avito/core/deprecation.py` | `deprecated_method(...)` становится async-aware: если исходный метод coroutine function, wrapper тоже `async def` и делает `return await method(...)`, сохраняя `__sdk_deprecation__`. Это нужно для deprecated async-двойников в `cpa` и `ads`. |
| `avito/core/transport.py` (отдельно) | Phase 1a: `_merge_headers` рефакторится первым — принимает уже резолвнутый bearer-token, резолв вызывается отдельной строкой выше. Все остальные shared helpers — Phase 1b. |
| `avito/__init__.py` | + экспорт `AsyncAvitoClient`, `AsyncPaginatedList`. `AsyncPaginator` не выносим на root level, потому что sync-root экспортирует `PaginatedList`, но не `Paginator`; `AsyncPaginator` остаётся доступен из `avito.core`. |
| `avito/core/__init__.py` | + экспорт `AsyncTransport`, `AsyncOperationExecutor`, `AsyncOperationTransport`, `AsyncPaginatedList`, `AsyncPaginator`. |
| `avito/auth/__init__.py` | + экспорт `AsyncAuthProvider`, `AsyncTokenClient`, `AsyncAlternateTokenClient`, если эти классы объявлены публичными для consumer-side тестов и type-hint'ов. |
| `avito/testing/__init__.py` | + экспорт `AsyncFakeTransport`, `AsyncSwaggerFakeTransport` и общих helpers, чтобы async test utilities были таким же публичным контрактом, как sync `FakeTransport`. |
| `avito/<domain>/__init__.py` | На каждом M2/M3…M12 добавляется export соответствующих `Async<X>` классов; без этого `_gen_reference.py`, mkdocstrings и IDE-discovery не увидят async-поверхность. |
| `docs/site/assets/_gen_reference.py` | + расширение `public_domain_packages()` / `public_domain_classes()` / `public_domain_methods()` для подхвата `async_domain.py` и `Async<X>`-классов рядом с sync-аналогами. Builder не должен зависеть только от `avito.<package>.__all__`: он обязан импортировать `avito.<package>.domain` и `avito.<package>.async_domain` напрямую, затем сохранять порядок sync-класс → async-класс. Без этого `make docs-strict` после M2-PoC не докажет полноту reference. |
| `avito/core/domain.py` | + `AsyncDomainObject` с async `_execute` и async `_resolve_user_id`. Sync `DomainObject` — без изменений. |
| `pyproject.toml` | + `pytest-asyncio = "^0.24"` в dev-deps. + `[tool.pytest.ini_options] asyncio_mode = "strict"`. |
| `Makefile` | + цель `async-parity-lint`, включённая в `quality`; `make check` после M1 должен оставаться зелёным. |
| `scripts/lint_architecture.py` | `LEGACY_FILENAMES` не трогаем, но public-method checks применяются к `domain.py` и `async_domain.py`; AST-парсер должен учитывать `ast.AsyncFunctionDef` наравне с `ast.FunctionDef`. |
| `scripts/lint_docstrings.py` | Проверяет `avito/*/domain.py` и `avito/*/async_domain.py`, чтобы async public methods не получили generic/reference-плохие docstring-и. |
| `scripts/lint_async_parity.py` | Новый static linter, не pytest: проверяет `Async<X> ↔ X`, сигнатуры, return annotations (`PaginatedList[T] ↔ AsyncPaginatedList[T]`), `async def`, binding equality и отсутствие лишних/пропущенных public methods. |
| `scripts/lint_swagger_bindings.py` | Без изменений в CLI (логика вынесена в `swagger_linter.py`). |
| `tests/contracts/test_swagger_contracts.py` | Фильтруется на `variant="sync"` и продолжает проверять sync `SwaggerFakeTransport` без изменения behavioral coverage. |
| `STYLEGUIDE.md` | M1 нормативно разрешает двухрежимный SDK: `async_domain.py`, `AsyncDomainObject`, `AsyncTransport`/`httpx.AsyncClient`, async lifecycle и variant-aware Swagger bindings. Sync-only рекомендация заменяется на описание двух поверхностей. |
| `docs/site/explanations/swagger-binding-subsystem.md` | Раздел про `variant` и class-gated coverage. |
| `docs/site/explanations/domain-architecture-v2.md` | Параграф про `async_domain.py` как разрешённый файл, парный к `domain.py`. |
| `README.md`, `mkdocs.yml`, `docs/site/index.md`, `docs/site/reference/client.md`, `docs/site/reference/pagination.md`, `docs/site/reference/testing.md`, `docs/site/how-to/index.md` | В M-final обновляются с «синхронный SDK» на двухрежимный SDK и получают ссылки на async lifecycle/testing/pagination. |

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
avito/testing/async_swagger_fake_transport.py
                                         # AsyncSwaggerFakeTransport: async contract runner
                                         #   для discovered bindings с variant="async"
tests/async_fake_transport.py            # тонкий re-export с DeprecationWarning (как у sync;
                                         #   шаблон скопирован 1:1 с tests/fake_transport.py)
tests/core/test_async_transport.py
tests/core/test_async_pagination.py
tests/core/test_async_executor.py
tests/core/test_async_client_lifecycle.py
tests/auth/test_async_provider.py
tests/contracts/test_async_swagger_contracts.py
                                         # Swagger-spec compliance для async bindings
scripts/lint_async_parity.py             # static linter, не pytest
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
    async def download_binary(...) -> BinaryResponse: ...   # full-buffer, см. ниже
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

**Rate-limiter в async.** Один rate-limiter принадлежит одному `AsyncTransport`
(а не каждой корутине-вызову). Все корутины, делящие транспорт, должны
сериализоваться через `asyncio.Lock` внутри лимитера — иначе N параллельных запросов
независимо посчитают «надо ждать X секунд» и улетят пачкой после ожидания, нарушив
лимит.

**Контракт shared-частей RateLimiter.** Текущий `avito/core/rate_limit.py` содержит
*и* состояние token-bucket'а (`_tokens`, `_blocked_until`, `_updated_at`), *и*
`while True: self._sleep(delay)` внутри `acquire()` — sleep запечён в метод. Sync
`RateLimiter` нельзя «обернуть» в async без переделки, потому что внутри стоит
`threading.Lock`, который удерживать через `await` запрещено. Поэтому декомпозиция
строгая, в три части:

1. **`RateLimitState`** (pure dataclass в `avito/core/_transport_shared.py`):
   `_tokens: float`, `_updated_at: float`, `_blocked_until: float`, политика
   (`rate`, `capacity`, `enabled`). Методы:
   - `compute_delay(now: float) -> float` — pure-функция, **не** sleep'ает,
     возвращает 0 если можно сразу, иначе нужную задержку. Резервирует токен,
     если возвращает 0 (мутирует state).
   - `observe_response(now: float, headers: Mapping[str, str]) -> None` — pure
     обновление `_blocked_until` по rate-limit headers (без IO).

2. **`RateLimiter`** (sync, остаётся в `avito/core/rate_limit.py`): хранит
   `RateLimitState` + `threading.Lock` + `_sleep` + `_clock`. Чтобы не менять
   sync-поведение, wrapper сохраняет текущий порядок: lock держится только на
   вычислении/мутации state, sleep выполняется вне `threading.Lock`. Любое изменение
   sync-concurrency semantics — отдельный сознательный PR, не часть M1.

3. **`AsyncRateLimiter`** (новый, в `avito/core/async_transport.py` или отдельно
   в `avito/core/_async_rate_limit.py` — выбор фиксируется в M1 PR): хранит
   **отдельный `RateLimitState`** (не shared с sync — состояние не делится между
   режимами; sync- и async-транспорты — независимые сущности с независимыми
   bucket'ами) + `asyncio.Lock` + `_clock` + `_sleep: Callable[[float],
   Awaitable[None]] = asyncio.sleep`. `async def acquire()` — это
   `async with self._lock: while (delay := state.compute_delay(now())) > 0:
   await self._sleep(delay)`.

Async wrapper намеренно держит `asyncio.Lock` во время ожидания, чтобы несколько
корутин с одним transport-ом не просыпались одной пачкой после одинакового delay.
`asyncio.Lock` создаётся при создании `AsyncRateLimiter` внутри async lifecycle
(`AsyncAvitoClient.__aenter__`, `AsyncFakeTransport.as_client()` внутри тестового loop'а
или явное создание пользователем внутри loop'а) и биндится к event loop'у при первом
`await`. Запрещено переиспользовать один `AsyncRateLimiter` между event loop'ами.

**Закрепляется тестами**: `tests/core/test_rate_limit_state.py` (pure compute);
`tests/core/test_async_transport.py::test_async_rate_limiter_serializes_concurrent_acquires`
(пять параллельных корутин не уходят пачкой после ожидания, а сериализуются под
`asyncio.Lock`).

**Семантика `AsyncTransport.download_binary`.** В M1 — **full-buffer**, как sync:
внутри `await response.aread()` и возвращается `BinaryResponse` с полным `bytes`-
контентом. Streaming-вариант (`async for chunk in response.aiter_bytes()`) —
**out of scope для M1…M-final**: ни один публичный sync-метод не возвращает
chunked stream, `scripts/lint_async_parity.py` и async contract suite это бы поломали,
и пользователи Async API не получат
расхождения с sync. Если в будущем понадобится stream — это отдельный API
(`download_binary_stream` или итератор), вводимый отдельным минорным релизом
после 2.1.0 с симметричным sync-аналогом. Закрепляется тестом
`tests/core/test_async_transport.py::test_download_binary_full_buffer_matches_sync`.

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
`AsyncOperationExecutor.execute()` повторяет все три ветки sync-executor'а:

- `response_kind == "json"`: `payload = await transport.request_json(...)`, затем
  `response_model.from_payload(payload)`;
- `response_kind == "empty"`: `response = await transport.request(...)`, затем
  `EmptyResponse(status_code=response.status_code, headers=dict(response.headers))`;
- `response_kind == "binary"`: executor вызывает `await transport.request(...)`
  с method/path из `OperationSpec`, затем строит `BinaryResponse` тем же helper-кодом,
  что sync `_request_binary()` использует для `OrderLabel.download()`. `download_binary()`
  остаётся низкоуровневым convenience-методом `AsyncTransport`, но **не** входит в
  `AsyncOperationTransport` Protocol, иначе binary-ветка начнёт отличаться от sync
  executor и потеряет method/path из `OperationSpec`.

Binary-ветка закрепляется M1 unit-тестом на executor и M12 domain-тестом
`OrderLabel.download()` через `AsyncSwaggerFakeTransport`/`AsyncFakeTransport`.

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

Async-двойник sync-`DomainObject._resolve_user_id`: тот же fallback-порядок, что и
текущий sync-код в `avito/core/domain.py`: сначала аргумент, затем `settings.user_id`,
затем internal raw request на `/core/v1/accounts/self` через transport. Это
осознанный exception для базового helper-а: `core` не импортирует
`avito.accounts.operations.GET_SELF`, чтобы не создавать зависимость core → domain.
Swagger-binding для `/core/v1/accounts/self` покрывается публичным
`Account.get_self()` / `AsyncAccount.get_self()`, а `_resolve_user_id` остаётся
internal helper без отдельного binding-а. Если в будущем sync `_resolve_user_id`
переводится на executor, async меняется в том же PR.

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

**Concurrency contract.** `AsyncPaginatedList` не поддерживает concurrent iteration
одного instance из нескольких корутин. Но это не должно превращаться в silent data
corruption: класс хранит флаг активной итерации (`_active_iterator`) и fail-fast
бросает `RuntimeError("AsyncPaginatedList уже итерируется; используйте materialize() или создайте отдельный список.")`,
если второй `__aiter__` стартует до завершения первого. Если нужен fan-out —
вызывайте `await materialize()` один раз и итерируйтесь по полученному `list[T]`,
либо создавайте отдельный `AsyncPaginatedList` per consumer. Документируется
в docstring класса и в `docs/site/explanations/pagination-semantics.md`
(дополнение в M-final). Закрепляется поведением
`tests/core/test_async_pagination.py::test_concurrent_aiter_raises_runtime_error`.

`AsyncPaginator` обязателен как implementation helper: sync-домены используют
`Paginator(...).as_list(...)` в 4 местах (`avito/ads/domain.py:266,1183`,
`avito/accounts/domain.py:170,383`). Текущая публичная поверхность не возвращает
`Paginator` напрямую, поэтому async public methods возвращают `AsyncPaginatedList[T]`,
а не `AsyncPaginator[T]`. Сам `AsyncPaginator` остаётся доступен из `avito.core` для
симметрии core API: `iter_pages()` — `AsyncIterator`, `collect()` — корутина,
`as_list()` создаёт `AsyncPaginatedList`, передавая `first_page` как sync-аналог.

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
    def token_flow(self) -> AsyncTokenClient: ...
    def alternate_token_flow(self) -> AsyncAlternateTokenClient: ...
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

    def auth(self) -> AsyncAuthProvider: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> AsyncAvitoClient: ...
    async def __aexit__(self, *exc) -> None: ...

    # M2-PoC: tariff() добавляется как валидация шаблона
    # M3+: на каждом этапе добавляются ВСЕ factory-методы домена сразу
    # def tariff(self) -> AsyncTariff: ...                # M2-PoC
    # def account(self, user_id=None) -> AsyncAccount: ...# M4
    # ...
```

**Lifecycle `from_env` и `__init__`.** `from_env` — **синхронная** фабрика
(зеркало sync `AvitoClient.from_env`): читает `.env`/окружение, конструирует
`AvitoSettings` и возвращает не-инициализированный `AsyncAvitoClient`. SDK-managed
сетевых ресурсов (`httpx.AsyncClient`, `asyncio.Lock`) на этом этапе ещё нет —
они создаются лениво в `__aenter__` под текущий event loop. Исключение: если
пользователь явно передал внешний `http_client`, он уже существует, но transport
и auth-provider всё равно связываются с ним только в `__aenter__`. Это критично потому,
что:
- `httpx.AsyncClient`, созданный в одном loop'е и использованный в другом, даёт
  неопределённое поведение;
- `asyncio.Lock` биндится к loop'у при первом `await` и не переносится между
  loop'ами;
- `from_env` сам не `async` — пользователь не должен подключать SDK через
  `await AsyncAvitoClient.from_env()`.

**Контракт использования — обязательные паттерны:**

```python
# (1) Рекомендованный: контекст-менеджер
async with AsyncAvitoClient.from_env() as client:
    ...

# (2) Допустимый: явный aclose
client = AsyncAvitoClient.from_env()
async with client:           # инициализация в __aenter__
    ...
# или
client = AsyncAvitoClient.from_env()
await client.__aenter__()    # эквивалент async with
try:
    ...
finally:
    await client.aclose()
```

**Запрещено:**
```python
client = AsyncAvitoClient.from_env()
await client.transport.request_json(...)   # transport ещё None — RuntimeError
```

`transport`/`auth_provider` — `@property`, возвращают `RuntimeError("AsyncAvitoClient
не инициализирован: используйте 'async with' или дождитесь '__aenter__'")` до
первого `__aenter__`. Закрепляется тестом
`tests/core/test_async_client_lifecycle.py::test_access_before_aenter_raises`.

**Ownership внешнего `httpx.AsyncClient`.** В M1 нельзя незаметно менять текущую
sync-семантику. Сейчас sync `Transport.close()` закрывает `httpx.Client` даже если
он был передан извне. Поэтому `AsyncTransport.aclose()` в 2.1.0 зеркалит это
поведение: закрывает внутренний `httpx.AsyncClient` независимо от того, создан он
SDK или передан пользователем. Это фиксируется тестом, чтобы план не опирался на
неверное предположение про `_owns_client`. Если нужна политика "external client is
owned by caller", она вводится отдельным PR одновременно для sync и async с явным
CHANGELOG/deprecation-дизайном. Если `http_client` передан, его loop должен совпадать
с loop'ом, в котором будет вызван `__aenter__`; cross-loop ownership — UB,
проверяется только документацией.

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
этап M-final, потому что часть из них комбинирует несколько доменов и не нужна до
того, как все домены портированы.

**Классификация методов M-final (важно для имплементации).** Не все 8 методов —
агрегаторы; путать паттерн нельзя.

| Метод | Тип | Sync поведение | Async поведение |
|---|---|---|---|
| `account_health` | агрегатор с зависимостями | сначала `_resolve_user_id`; затем независимые ветки `balance`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`; `promotion_summary` зависит от `item_ids` из `listing_health` (`avito/client.py:206-263`) | **`asyncio.TaskGroup`** только для независимых веток после `user_id`; `promotion_summary` запускается после `listing_health`. Ошибки `balance`/`listing_health` пробрасываются как sync; chat/order/review/promotion остаются safe-секциями через `_safe_summary_async`. |
| `listing_health` | агрегатор с first-list dependency | сначала `ad.list(...)`, потом при наличии `item_ids` вызывает item stats, calls stats и spendings (`avito/client.py:265-368`) | список объявлений загружается первым; после получения `item_ids` **`asyncio.TaskGroup`** на независимые stats/calls/spendings. Spendings остаётся optional safe-секцией; stats/calls ошибки пробрасываются как sync. |
| `business_summary` | **алиас** для `account_health` | `return self.account_health(...)` (`avito/client.py:184-204`) | `return await self.account_health(...)` — **никакого `TaskGroup`**, делегирование 1:1 |
| `chat_summary` | leaf/sequential | `_resolve_user_id`, затем один вызов `messenger`-домена | последовательный `async def`; `TaskGroup` не нужен |
| `order_summary` | leaf | один вызов `orders`-домена | один `await`; `TaskGroup` запрещён |
| `review_summary` | small aggregator | `review().list()` optional-safe, `rating_profile().get()` required (`avito/client.py:396-429`) | допускается **`asyncio.TaskGroup`**: reviews через `_safe_summary_async`, rating как required task. `rating` error пробрасывается; reviews error превращается в unavailable section. |
| `promotion_summary` | conditional aggregator | `list_orders`; если `item_ids` переданы — дополнительно `list_services` (`avito/client.py:431-465`) | без `item_ids` один `await`; с `item_ids` допускается **`asyncio.TaskGroup`** на `list_orders` и `list_services`. |
| `capabilities` | статическая справка | не делает сетевых probe-запросов, только строит `CapabilityDiscoveryResult` из текущей конфигурации (`avito/client.py:467-531`) | остаётся sync-shaped CPU-only методом без `TaskGroup` и без сетевых вызовов. Если позже capabilities станет probe-методом, это отдельное API/behavior изменение с тестами. |

Правило: параллелим только фактически независимые сетевые ветки и сохраняем sync
error semantics. Алиасы (`business_summary`), CPU-only методы (`capabilities`) и
leaf'ы (`order_summary`) не получают `TaskGroup`. Это записано в DoD M-final ниже
как явная проверка через code review checklist.

**Cancellation-safe паттерн для агрегаторов (обязательный).** Используется
`asyncio.TaskGroup` (Python 3.11+, у нас floor 3.12+) с per-section try/except,
конвертирующим `AvitoError → SummaryUnavailableSection` (как sync `_safe_summary`,
`avito/client.py:91-98`). `asyncio.gather(..., return_exceptions=True)` запрещён,
потому что он возвращает `CancelledError` как обычный результат — это глушит
cancellation семантику. Шаблон:

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

async def account_health(self, ...) -> AccountHealthSummary:
    async with asyncio.TaskGroup() as tg:
        t_balance = tg.create_task(self.account(resolved_user_id).get_balance())
        t_listings = tg.create_task(self.listing_health(...))
        t_chat = tg.create_task(_safe_summary_async("chat", lambda: ...))
        ...
    # После выхода из TaskGroup все таски завершены или отменены атомарно.
    # Зависимая promotion ветка запускается после получения item_ids из listings.
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

**Инициализация lock'а в `__init__` (а не лениво).** Лениво создавать `asyncio.Lock`
из `_handle` нельзя: две корутины, одновременно прошедшие `if self._handle_lock is
None`, создадут разные lock-объекты — и сериализация сломается до первого `await`.
Поэтому `self._handle_lock = asyncio.Lock()` создаётся в `__init__`; экземпляр
`AsyncFakeTransport` создаётся внутри async-теста/loop'а, а lock биндится к loop'у
при первом `await`. Цена: `AsyncFakeTransport` нельзя переиспользовать между event
loop'ами (под `pytest-asyncio strict` это и так не происходит — каждый тест получает
свой loop). Документируется в docstring: «AsyncFakeTransport безопасен для concurrent
access внутри одного event loop'а; создавать новый instance в каждом тесте; не
переиспользовать между loop'ами».

## Swagger binding — детали изменений

1. `SwaggerOperationBinding` (`avito/core/swagger.py`):
   - `variant: Literal["sync","async"] = "sync"` (frozen field).
   - Декоратор `swagger_operation(..., variant: Literal["sync","async"] = "sync")`.
   - `__post_init__` валидирует runtime-значение: любое значение кроме `"sync"` /
     `"async"` даёт `ConfigurationError`, потому что `Literal` не защищает вызов
     из runtime-кода.
   - Двойной декор одной функции остаётся `ConfigurationError`.

2. `DiscoveredSwaggerBinding` (`avito/core/swagger_discovery.py`):
   - `variant: Literal["sync","async"]` копируется из `SwaggerOperationBinding`.
   - `_iter_domain_modules` ищет в каждом пакете оба модуля: `<pkg>.domain` и `<pkg>.async_domain`. Если `async_domain` нет — игнорируем (это нормальная стадия миграции).
   - `canonical_map` остаётся sync-only compatibility property, чтобы текущие
     `tests/contracts/test_swagger_contracts.py` и report builder не получили
     silent semantic break. Реализация явно фильтрует `variant == "sync"`, а не
     "последний binding wins".
   - новый API: `canonical_map_by_variant: Mapping[Literal["sync","async"],
     Mapping[str, DiscoveredSwaggerBinding]]` и/или `binding_for(operation_key,
     variant)`. Внутренний уникальный ключ — `(operation_key, variant)`.

3. `swagger_linter.py`:
   - `_validate_single_binding_per_sdk_method` — без изменений: ключ `binding.sdk_method` уникален даже в async (т.к. `module.class.method` отличается).
   - `_validate_duplicate_bindings` — ключ `(operation_key, variant)` вместо `operation_key`. Допустимо иметь две независимые цепочки (sync + async) на одну swagger-операцию.
   - `_validate_factory` становится variant-aware: sync binding проверяет factory на
     `AvitoClient`, async binding — на `AsyncAvitoClient`. Иначе можно получить
     зелёный swagger-lint при отсутствии async factory-метода.
   - `_validate_complete_bindings(operations, bindings)` → `_validate_complete_bindings(operations, bindings, variant)`. Запускается дважды:
     - для `variant="sync"`: ожидаемое множество = все `operations` (как сейчас).
     - для `variant="async"`: ожидаемое множество = **per-class**, не per-domain.
       Для каждого sync-класса в домене (`<X>`) проверяем: существует ли
       `Async<X>` (по имени, `cls.__name__.startswith("Async") and
       cls.__name__.removeprefix("Async") == sync_cls.__name__`, в том же пакете).
       Если да — все swagger-операции, привязанные к sync-методам этого класса,
       обязаны иметь async-двойник в `Async<X>`. Если нет — класс считается
       «ещё не портированным», и его операции не входят в expected для
       `variant="async"` на этом этапе.

       Помимо `_API_DOMAINS`, для `domain == "auth"` берём операции из
       `Авторизация.json` и `Автотека.json`, если найден `AsyncTokenClient` /
       `AsyncAlternateTokenClient` соответственно (та же per-class логика).

       Это даёт два важных свойства:
      1. M1 фундамент мерджится: для API-доменов ни одного `Async<X>` нет →
         domain expected = ∅; для auth expected включает только
         `AsyncTokenClient` / `AsyncAlternateTokenClient` bindings. Линтер зелёный.
       2. Большой домен (например, M11 `ads` с 3 классами `Ad`/`AutoloadProfile`/
          `AutoloadReport`) теоретически можно разбить на под-PR'ы по классу;
          DoD M3…M12 всё равно требует закрытия домена на 100%, но per-class
          гранулярность даёт безопасную точку выхода, если PR раздувается.
          (Дробление допустимо только при явном решении, а не «сделаю остальное
          потом» — см. DoD M3…M12.)
   - `_validate_operation_spec_coverage` — без изменений (sync OperationSpec — единый источник истины для обоих режимов; реюз спеки между sync и async-методами не запрещён). `used_specs` — `set[id(spec)]`, поэтому одна и та же `OperationSpec` от sync и async binding'ов не дублируется и не теряется.
   - `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`) — резолвит spec через `unwrapped_method.__globals__`. Async-методы должны импортировать spec явно (`from avito.<domain>.operations import LIST_SPEC`), иначе резолв вернёт `()` и spec будет считаться unbound. Pre-flight тест проверяет, что это работает; если нет — расширяем функцию в Phase 1b.
   - `_validate_json_body_model_coverage` — запускается по sync bindings; async
     bindings проверяются через `AsyncSwaggerFakeTransport` contract suite, чтобы
     не дублировать schema-lint ошибки на общих `OperationSpec`.

4. `swagger_report.py` и docs report:
   - `operations[].binding` остаётся sync-only compatibility field.
   - добавляется `operations[].bindings_by_variant = {"sync": ..., "async": ...}`.
   - `summary.bound/unbound/duplicate/ambiguous` остаются sync-only до отдельного
     report API bump.
   - добавляется `summary.variants.sync` и `summary.variants.async` с теми же
     счётчиками. Для M1 async domain summary может быть `bound=0, expected=0`,
     а async auth summary уже должен покрывать свои bindings; после M-final общий
     async expected/bound = 204.
   - `docs/site/assets/_gen_reference.py` и `reference/operations.md` показывают обе
     SDK-ссылки, когда async binding уже существует, но не ломают текущую sync-карту.

5. Contract tests:
   - `tests/contracts/test_swagger_contracts.py` фильтрует bindings по
     `variant="sync"` и сохраняет текущий exhaustive sync behavior.
   - новый `tests/contracts/test_async_swagger_contracts.py` — Swagger-spec
     compliance test, а не architecture/introspection test: для каждого discovered
     binding с `variant="async"` `AsyncSwaggerFakeTransport` строит
     `AsyncAvitoClient`, вызывает async SDK method через `await`, валидирует
     фактический request против Swagger и проверяет success/error payload mapping.
     В M1 он покрывает async auth-bindings; в M2+ автоматически расширяется на
     портированные домены.

6. `scripts/lint_async_parity.py` — static linter, проверяет для каждого Async-класса:
   - имя `Async<X>` ↔ существует sync `<X>` в том же пакете;
   - множество публичных async-методов (`async def` без префикса `_`) совпадает с sync-методами;
   - перебор методов фильтруется по `func.__qualname__.startswith(cls.__name__ + ".")`,
     чтобы не учитывать унаследованные от `AsyncDomainObject` (`_execute`, `_resolve_user_id`)
     или `object` методы;
   - для каждой пары `(sync_method, async_method)`:
     - `inspect.signature(sync).parameters` (без `self`) == `inspect.signature(async).parameters`;
     - аннотация возврата либо совпадает, либо `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`,
       либо `BinaryResponse`/wrapper-модель совпадает напрямую; `Paginator[T] ↔
       AsyncPaginator[T]` допускается только если в будущем появится публичный
       sync-метод, который реально возвращает `Paginator[T]`;
     - оба декорированы `@swagger_operation` на ту же `(spec, method, path, operation_id)`, отличаясь только `variant`.
   - для каждой async class-level `__sdk_factory__` проверяет, что такой factory
     существует на `AsyncAvitoClient`, имеет сигнатуру, совместимую с sync factory
     на `AvitoClient`, и возвращает соответствующий `Async<X>`.
   Этот linter вызывается из `make quality`; pytest не содержит parity/introspection
   тестов, потому что STYLEGUIDE разрешает в pytest только functional tests и
   Swagger-spec compliance tests.

## Этапы

### Pre-flight для PR M1

До открытия PR M1 (всё это делается локально и валидируется до коммита):

- [ ] `grep -rn "\._access_token\|\._refresh_token\|\._autoteka_access_token" tests/` —
      зафиксировать все private probes; убедиться, что compat-shim в `AuthProvider`
      покроет каждый. Найденный сейчас кейс: `tests/core/test_authentication.py:122-127`.
- [ ] `grep -rn "\bPaginator\b" avito/` — зафиксировать все 4 usage-сайта
      (`avito/ads/domain.py:266,1183`, `avito/accounts/domain.py:170,383`).
      Все текущие usage-сайты завершаются `.as_list(...)`; прямого публичного
      возврата `Paginator` нет. `AsyncPaginator.as_list()` нужен уже к M4
      (`accounts`), но root-level export `AsyncPaginator` не нужен.
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
- [ ] Прогон baseline на чистом `main` — сохранить **nodeid существующих тестов** и
      их pass/fail статусы:
      `poetry run pytest --collect-only -q tests/core tests/auth tests/domains tests/contracts | grep '::' > /tmp/baseline_nodeids.txt`
      и затем `poetry run pytest -q --tb=no $(cat /tmp/baseline_nodeids.txt) >
      /tmp/baseline_main.txt`. Используется в DoD M1; новые async tests после M1
      не входят в baseline-сравнение.
- [ ] Проверить, что `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`)
      работает с `async_domain.py`: тест-стаб с `async def m(self): return self._execute(SOME_SPEC)`
      и `from ...operations import SOME_SPEC` — функция должна найти `SOME_SPEC` через
      `unwrapped_method.__globals__`. Если не работает — расширить функцию (Phase 1b),
      иначе оставить без изменений.
- [ ] Прочитать `docs/site/assets/_gen_reference.py` целиком и зафиксировать
      существующие точки фильтрации: `PACKAGE_ROOT.glob("*/domain.py")`,
      `EXCLUDED_PACKAGES`, `public_domain_classes()` (фильтр по `DomainObject`-наследованию
      и `value.__module__.startswith(f"avito.{package}.")`), `public_domain_methods()`
      (фильтр по `value.__qualname__.startswith(f"{domain_class.__name__}.")`).
      Расширение builder'а в M1 обязано переиспользовать ровно эту логику для
      `async_domain.py` + `AsyncDomainObject`-наследников и не полагаться только
      на `avito.<package>.__all__`. Без этого reference будет несимметричным.
- [ ] Прочитать `scripts/lint_architecture.py` и `scripts/lint_docstrings.py`:
      текущие проверки смотрят только `domain.py` и `ast.FunctionDef`. M1 обязан
      расширить их на `async_domain.py` и `ast.AsyncFunctionDef`.
- [ ] Прочитать `avito/core/deprecation.py`: текущий `deprecated_method` возвращает
      sync-wrapper. M1 обязан добавить async-aware wrapper до портирования
      deprecated методов `cpa`/`ads`.

### M1 — Фундамент (1 PR)

DoD:
- [ ] `make check` зелёный: test, typecheck (mypy strict), lint (ruff),
      swagger-lint --strict, architecture-lint, async-parity-lint,
      docstring-lint, build.
- [ ] `make docs-strict` зелёный: M1 правит `STYLEGUIDE.md`,
      `swagger-binding-subsystem.md` и `domain-architecture-v2.md` + расширяет
      `_gen_reference.py` (см. таблицу «Существующие, изменяются в M1»). Без правки
      `STYLEGUIDE.md` план формально противоречит нормативному sync-only тексту.
      Без зелёного docs-strict нельзя гарантировать, что reference-builder в M2-PoC
      увидит первый `Async<X>`. Если на M1 ещё ни одного `Async<X>` нет — builder
      проверяется на нейтральность (sync reference генерится идентично baseline'у).
- [ ] Покрытие тестами фундамента не ниже sync-аналогов (sample проверка по `coverage report`).
- [ ] Smoke-тест: `AsyncAvitoClient` через `AsyncFakeTransport` (без respx) делает один авторизованный запрос; токен рефрешится после 401; retry на 429 срабатывает; `Idempotency-Key` пробрасывается; `aclose()` корректно закрывает `httpx.AsyncClient` и `AsyncAuthProvider`.
- [ ] Ownership test: `AsyncTransport.aclose()` закрывает переданный
      `httpx.AsyncClient`, потому что это выбранная mirror-политика текущего sync
      `Transport.close()`. Тест отдельно покрывает idempotent double-close.
- [ ] Async auth public surface зеркалит sync: `AsyncAvitoClient.auth()` возвращает
      `AsyncAuthProvider`, а `token_flow()` / `alternate_token_flow()` возвращают
      async token clients с `variant="async"` bindings.
- [ ] Документация `swagger-binding-subsystem.md` отражает variant и class-gated coverage.
- [ ] `AsyncSwaggerFakeTransport` добавлен и экспортирован из `avito.testing`; async
      contract suite зелёный для discovered async bindings (`auth` в M1, домены
      появляются позже).
- [ ] Публичная sync-поверхность не изменилась — formal: pass/fail статусы
      **только baseline nodeids из `/tmp/baseline_nodeids.txt`** идентичны
      baseline-тесту с `main` (см. pre-flight). Новые async tests не участвуют
      в сравнении. Любое расхождение по старым nodeid = blocker.
- [ ] Phase 1a (`_merge_headers` рефакторинг) выделен отдельным коммитом внутри PR — для bisect-friendly history.
- [ ] CHANGELOG `## [Unreleased]` в корневом `CHANGELOG.md` дополнен:
      `- Фундамент Async API: AsyncTransport,
      AsyncAuthProvider, AsyncOperationExecutor, AsyncPaginatedList,
      AsyncAvitoClient (без factory-методов доменов); RateLimitState вынесен в shared`.

### M2-PoC — Proof-of-concept шаблона (отдельный PR, до переработки доменов)

**Цель этого шага — валидировать шаблон на минимальном домене и при этом закрыть
`tariffs` полностью.** Это не "частичный доменный PR": к merge `tariffs` должен
иметь async-поверхность, тесты, swagger coverage и reference 1:1. PoC может вернуть
feedback вида «контракт `AsyncPaginator` нужно расширить», «discovery не видит
spec», «mypy strict ругается на covariance возврата» — и это нормальный ожидаемый
выход. Все правки контракта вносятся в **этот же PR**, а если правки требуют
переработки M1-фундамента — PoC откатывается, фундамент дорабатывается отдельным
PR, после чего PoC переоткрывается. M3 не начинается, пока M2-PoC не зелёный и
`tariffs` не закрыт на 100%.

PoC берёт `tariffs` (1 sync-операция с binding) — минимальная поверхность без
пагинации, без autoteka-flow, без write-методов. Этого достаточно, чтобы ткнуть
все слои фундамента в один сценарий end-to-end.

DoD M2-PoC:
- [ ] `avito/tariffs/async_domain.py` создан, `AsyncTariff` зеркалит `Tariff`
      ровно по 1 публичному методу.
- [ ] `avito/tariffs/__init__.py` экспортирует `AsyncTariff` рядом с `Tariff`.
- [ ] `AsyncAvitoClient.tariff()` factory-метод возвращает `AsyncTariff`.
- [ ] `tests/domains/tariffs/test_tariffs_async.py` зеркалит sync-тест 1:1
      (golden path + 401 + 429 + transport error). Все тесты зелёные.
- [ ] `make check` зелёный, включая `swagger-lint --strict` (для `tariffs` теперь
      требуется async-coverage 1:1).
- [ ] `scripts/lint_async_parity.py` зелёный.
- [ ] `tests/contracts/test_async_swagger_contracts.py` зелёный для async auth +
      `tariffs`.
- [ ] Документация generated reference для `docs/site/reference/domains/tariffs.md`
      содержит async-секцию.
- [ ] **`_gen_reference.py` валидируется на реальном домене**: после расширения builder'а в M1 на M2-PoC он впервые видит `AsyncTariff` и должен сгенерировать reference-страницу с обоими классами (`Tariff` + `AsyncTariff`). `make docs-strict` зелёный, в `docs/site/reference/domains/tariffs.md` в выхлопе билда присутствуют обе секции. Если builder требует доработки — она входит в этот же PR (это и есть смысл PoC). Конкретно в `_gen_reference.py`: `public_domain_packages()` дополнительно возвращает пакет, если есть `*/async_domain.py`; `public_domain_classes()` импортирует `avito.<package>.domain` и `avito.<package>.async_domain` напрямую, а не только `avito.<package>.__all__`; `Async<X>` фильтруется через `cls.__name__.startswith("Async")` + `issubclass(AsyncDomainObject)`; `EXCLUDED_PACKAGES` остаётся прежним; для `auth` (исключён) async-классы reference не получают.
- [ ] **Lessons learned зафиксированы** в `docs/site/explanations/async-domain-template.md`
      (новый файл): шаблон файла `async_domain.py`, чек-лист переноса домена,
      найденные подводные камни. Этот документ становится нормативным для M3+.
- [ ] Если в ходе PoC понадобились изменения контракта (`AsyncPaginator`/`AsyncFakeTransport`/
      `swagger_linter`/`AsyncAuthProvider`), они **внесены в этот же PR** или вынесены
      в отдельный M1.5-PR, но **до** старта M3.
- [ ] Корневой `CHANGELOG.md` (`## [Unreleased]`) дополнен:
      `- Async-поддержка домена tariffs: AsyncTariff (PoC шаблона)`.

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
| M11 | `ads` | 28 | вторая и третья `AsyncPaginatedList` (`Ad.list`, `AutoloadReport.list`); сложный offset/limit first-page reuse в `Ad.list` (`avito/ads/domain.py:266`) |
| M12 | `orders` | 45 | самый большой; идемпотентность критична |
| M-final | — | — | convenience-методы `AsyncAvitoClient`: `account_health`, `listing_health`, `review_summary` и `promotion_summary` используют `asyncio.TaskGroup` только там, где есть фактически независимые сетевые ветки; `business_summary` делегирует в `account_health`; `chat_summary`/`order_summary` остаются sequential leaf; `capabilities` остаётся CPU-only без сетевых probe-запросов. `asyncio.gather(return_exceptions=True)` запрещён. Финальный hardening; `docs/site/how-to/async.md`; CHANGELOG `## [Unreleased]` → `## [2.1.0]` (свод накопленных пунктов из M1…M12 + запись про convenience-методы). |

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
3. `avito/<domain>/__init__.py` экспортирует **все** `Async<X>` класса домена рядом
   с sync-классами, чтобы mkdocstrings, IDE и generated reference видели публичную
   async-поверхность.
4. Регистрация **всех** `Async<X>` домена в `AsyncAvitoClient` (factory-методы по
   именам, идентичным sync).
5. `tests/domains/<domain>/test_<domain>_async.py` — зеркало
   `tests/domains/<domain>/test_<domain>.py`, через `AsyncFakeTransport`. Тесты
   помечаем `@pytest.mark.asyncio`. **Каждый** sync-тест имеет async-двойник
   с тем же сценарием.
6. Если в домене есть пагинация — соответствующие методы возвращают
   `AsyncPaginatedList[T]` (зеркально sync `PaginatedList[T]`). M4 `accounts` —
   первый домен с `AsyncPaginatedList`; M11 `ads` проверяет сложный first-page
   reuse в `Ad.list`.
7. Generated reference `docs/site/reference/domains/<domain>.md` дополняется
   async-секцией (или второй колонкой).
8. Если в домене есть write-методы с `dry_run` — async-двойник реализует тот же
   контракт: при `dry_run=True` транспорт **не вызывается** (тест проверяет
   `count(method=..., path=...) == 0`).
9. Если в домене есть idempotency-key поведение — async-тесты явно проверяют
   проброс заголовка `Idempotency-Key`.

### Definition of done каждого M3…M12 — закрыть домен на 100%, без работы на потом

«100%» определяется проверяемо. Все пункты ниже — **обязательные**, не «nice to have»:

- [ ] **Покрытие методов 1:1**: для каждого публичного sync-метода домена есть
      async-двойник; `scripts/lint_async_parity.py` зелёный для домена.
      Локальная проверка: `python -c "from avito.<domain>.domain import *; from
      avito.<domain>.async_domain import *"` + `scripts/lint_async_parity.py`
      без allowlist/skip для текущего домена.
- [ ] **Покрытие тестов 1:1**: каждый сценарий из `tests/domains/<domain>/test_*.py`
      имеет async-двойник; счётчики тестов сверены отдельными командами:
      `pytest --collect-only -q tests/domains/<domain>/test_<domain>.py | grep -c "::test_"`
      и `pytest --collect-only -q tests/domains/<domain>/test_<domain>_async.py | grep -c "::test_"`
      показывают одинаковое число. Покрываются: golden path, 401,
      403, 422, 429, transport error/timeout, пагинация (если есть), idempotency
      (для write), `dry_run` (если есть в sync).
- [ ] **Swagger-lint coverage 1:1 для домена**: `swagger-lint --strict` после этапа
      требует async binding для **каждой** swagger-операции этого домена; class-gated
      coverage гейт включён, и domain больше не «пуст по async». Никаких
      исключений/skip'ов для отдельных методов.
- [ ] **Async Swagger contract coverage**: `tests/contracts/test_async_swagger_contracts.py`
      вызывает **каждый** async binding домена через `AsyncSwaggerFakeTransport` и
      валидирует request/response/error contract. Это обязательный Swagger-spec
      compliance test, поэтому он разрешён STYLEGUIDE.
- [ ] **Документация**: generated `docs/site/reference/domains/<domain>.md` содержит async-секцию для
      **всех** портированных классов; `make docs-strict` зелёный; ссылки и примеры
      кода скомпилированы.
- [ ] **Никаких TODO/FIXME/`pytest.skip`/`xfail` в добавленных файлах**:
      `git diff main..HEAD -- avito/<domain>/ tests/domains/<domain>/ | grep -E
      "TODO|FIXME|@pytest.mark.skip|xfail"` пуст. Любая отсрочка работы = blocker.
- [ ] **Сообщения ошибок только на русском** (STYLEGUIDE.md, секция «Errors»):
      все новые `raise <AvitoError>("...")` в `async_domain.py` пишутся по-русски,
      без английских вкраплений. Code review checklist; `make lint` напрямую этого
      не ловит, но смешанные языки — формальный blocker. Если sync-аналог уже
      использует английский (legacy) — оставляем как есть в sync, а в async
      пишем по-русски и заводим отдельный issue на миграцию sync.
- [ ] **`make check` локально и в CI зелёный**.
- [ ] **AsyncAvitoClient полностью настроен для домена**: factory-методы возвращают
      готовые объекты, lifecycle (`aclose`/`__aexit__`) корректно закрывает все
      ресурсы домена.
- [ ] **Регрессия sync = 0**: список pass/fail sync-тестов идентичен предыдущему
      этапу (sanity-проверка через сравнение `pytest -q --tb=no` до и после).
- [ ] **Cumulative parity invariant**: после merge'а `scripts/lint_async_parity.py`
      и `tests/contracts/test_async_swagger_contracts.py` зелёные для **всех** уже
      портированных доменов (включая текущий). Этап не может ослабить инвариант
      для предыдущих доменов.
- [ ] **Нет работы «потом»**: переоткрытие PR с фразой «допилю в следующем PR»
      запрещено. Если scope не закрывается — PR разделяется или раздвигается, но
      не оставляется частичный домен в main.
- [ ] **CHANGELOG обновлён**: в корневом `CHANGELOG.md` (раздел `## [Unreleased]`)
      добавлена строка вида `- Async-поддержка домена <domain>: Async<X>, Async<Y>
      (#<PR-номер>)`. M-final сводит накопленные `Unreleased`-строки в релиз 2.1.0,
      добавляя только запись про convenience-методы и `AsyncAvitoClient`-агрегаторы.
      Без этого history-readers не увидят, в каком PR домен стал async, и release
      notes 2.1.0 не получится собрать механически.

### Definition of done M-final — релиз 2.1.0

«Финальный hardening» определяется проверяемо:

- [ ] **Convenience-методы реализованы по таблице классификации** (агрегатор / алиас / leaf / CPU-only). Code review проверяет: `asyncio.TaskGroup` стоит только в ветках с фактически независимыми сетевыми вызовами (`account_health`, `listing_health`, `review_summary`, `promotion_summary` при наличии `item_ids`); в `business_summary` — `return await self.account_health(...)` без `TaskGroup`; `chat_summary` и `order_summary` sequential; `capabilities` не делает сетевых probe-запросов и не использует `TaskGroup`. Любое нарушение = blocker.
- [ ] **`_safe_summary_async` живёт в одном модуле с sync `_safe_summary`** — `avito/client.py` (вынесение в общий `avito/summary/_helpers.py` допускается, но требует одновременного переноса sync `_safe_summary`; частичное вынесение запрещено, чтобы не разделять симметричные хелперы по разным файлам). Импорт в `avito/async_client.py` явный.
- [ ] **Версия пакета поднята до 2.1.0**: `poetry version 2.1.0`, изменение в `pyproject.toml` зафиксировано в M-final PR. CHANGELOG `## [Unreleased]` → `## [2.1.0] - YYYY-MM-DD`, накопленные строки M1…M12 + запись про convenience-методы и `AsyncAvitoClient`-агрегаторы сведены в один раздел. `git tag v2.1.0` ставится после merge M-final.
- [ ] **`AsyncSwaggerFakeTransport` contract suite полный**: `tests/contracts/test_async_swagger_contracts.py`
      вызывает все async bindings (204 Swagger operations, включая auth-bindings)
      и проверяет success/error/request-body schema, как sync contract suite.
- [ ] **`docs/site/how-to/async.md` написан**: контракт lifecycle (`async with` обязателен), пример с `AsyncFakeTransport`, миграционный гайд «как переписать sync-вызов на async», ограничения (`AsyncPaginatedList` не list-API, full-buffer download, нет streaming). Ссылки из `docs/site/index.md` и `docs/site/how-to/index.md`.
- [ ] **README/site wording обновлены**: `README.md`, `mkdocs.yml`, `docs/site/index.md`,
      `docs/site/reference/client.md`, `docs/site/reference/pagination.md`,
      `docs/site/reference/testing.md` больше не называют SDK только синхронным.
- [ ] **`make check` + `make docs-strict` зелёные**; `scripts/lint_async_parity.py`
      и `tests/contracts/test_async_swagger_contracts.py` зелёные для всех 11 API-доменов
      + auth-bindings.
- [ ] **Cumulative coverage**: после M-final swagger-lint --strict требует обоюдное 1:1 (sync + async) для всех 204 операций. Любой пропуск = blocker; никаких «допилим в 2.1.1».
- [ ] **CHANGELOG release-ready**: запись 2.1.0 содержит: фундамент Async API, по строке на каждый портированный домен (агрегируется из `## [Unreleased]`-записей M1…M12), convenience-методы `AsyncAvitoClient`. Release notes 2.1.0 собираются механически — это и есть проверка дисциплины M3…M12.

## Верификация (как проверить, что план сработал)

### M1
```bash
poetry install
make test                                 # sync + новые async unit-тесты
make typecheck                            # mypy strict — все Awaitable[T], AsyncPaginatedList[T] корректны
make lint                                 # ruff
make swagger-lint                         # sync 1:1; async auth 1:1, domain expected пуст
make async-parity-lint                    # static Async<X> ↔ X checks, не pytest
make check                                # финальный гейт
poetry run pytest tests/core/test_async_transport.py tests/core/test_async_pagination.py \
  tests/core/test_async_executor.py tests/core/test_async_client_lifecycle.py \
  tests/auth/test_async_provider.py tests/contracts/test_async_swagger_contracts.py
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
make async-parity-lint                                    # parity для tariffs как static lint
poetry run pytest tests/contracts/test_async_swagger_contracts.py
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

make async-parity-lint                                    # parity для всех закрытых доменов
poetry run pytest tests/contracts/test_async_swagger_contracts.py
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

# Версия и release notes
poetry version 2.1.0                                       # бамп до 2.1.0
grep -E "^## \[2\.1\.0\]" CHANGELOG.md                     # секция 2.1.0 существует
grep -E "^## \[Unreleased\]" CHANGELOG.md                  # Unreleased пуст или содержит только заголовок

# Reference после билда содержит обе поверхности на каждом домене
poetry run mkdocs build --strict 2>&1 | tee /tmp/mkdocs.log
for cls in AsyncTariff AsyncReview AsyncReviewAnswer AsyncRatingProfile AsyncAccount \
  AsyncAccountHierarchy AsyncRealtyListing AsyncRealtyBooking AsyncRealtyPricing \
  AsyncRealtyAnalyticsReport AsyncCpaLead AsyncCpaChat AsyncCpaCall AsyncCpaArchive \
  AsyncCallTrackingCall AsyncChat AsyncChatMessage AsyncChatWebhook AsyncChatMedia \
  AsyncSpecialOfferCampaign AsyncVacancy AsyncApplication AsyncResume AsyncJobWebhook \
  AsyncJobDictionary AsyncPromotionOrder AsyncBbipPromotion AsyncTrxPromotion \
  AsyncCpaAuction AsyncTargetActionPricing AsyncAutostrategyCampaign AsyncAutotekaVehicle \
  AsyncAutotekaReport AsyncAutotekaMonitoring AsyncAutotekaScoring AsyncAutotekaValuation \
  AsyncAd AsyncAdStats AsyncAdPromotion AsyncAutoloadProfile AsyncAutoloadReport \
  AsyncAutoloadArchive AsyncOrder AsyncOrderLabel AsyncDeliveryOrder AsyncSandboxDelivery \
  AsyncDeliveryTask AsyncStock; do
  grep -R -q "$cls" site/reference/domains || echo "MISSING async section: $cls"
done

# После merge
git tag v2.1.0
git push --tags
```

После M-final:
- swagger-lint --strict требует обоюдное 1:1 покрытие (sync + async) для всех 11 API-доменов и
  auth-bindings;
- `scripts/lint_async_parity.py` и `tests/contracts/test_async_swagger_contracts.py`
  зелёные для всех доменов;
- `pyproject.toml` версия = 2.1.0; корневой `CHANGELOG.md` содержит `## [2.1.0]` с агрегированной
  историей M1…M12 + convenience-методы;
- `docs/site/reference/domains/<domain>/` для каждого домена показывает обе классовые
  поверхности (sync + async);
- релиз 2.1.0 с CHANGELOG: «двухрежимный SDK, AsyncAvitoClient».

## Риски и mitigations

| Риск | Mitigation |
|---|---|
| Расхождение retry/auth-логики sync vs async | Вся не-IO логика — в `_transport_shared.py` и `_cache.py`, обе обёртки делегируют. |
| `RateLimiter` неприменим к async (sleep + `threading.Lock` запечены в `acquire()`) | Декомпозиция в три части: pure `RateLimitState.compute_delay()` в shared (без sleep, без lock), sync `RateLimiter` поверх (`threading.Lock` + `time.sleep`), отдельный `AsyncRateLimiter` (`asyncio.Lock` + `await asyncio.sleep`). State **не** делится между режимами — sync и async транспорты независимы. |
| `_resolve_user_id` в async расходится с sync fallback-порядком | Async-двойник повторяет текущий sync helper: argument → `settings.user_id` → raw `/core/v1/accounts/self` через transport. Публичный Swagger binding `/core/v1/accounts/self` покрывается `AsyncAccount.get_self()`, не internal helper-ом. |
| `download_binary` в async может неявно стать streaming, расходясь с sync | M1 фиксирует full-buffer-семантику (`await response.aread()`), как sync. Streaming — отдельный API после 2.1.0 с симметричным sync-аналогом. Закреплено тестом `test_download_binary_full_buffer_matches_sync`. |
| Convenience-метод М-final реализован как «sync с обмазанным await» (потеря параллелизма) ИЛИ leaf/CPU-only метод обёрнут в ненужный `TaskGroup` | DoD M-final проверяет классификацию по фактическому sync-коду: `TaskGroup` только для независимых сетевых веток (`account_health`, `listing_health`, `review_summary`, `promotion_summary` при `item_ids`); `business_summary` — алиас; `chat_summary`/`order_summary` — sequential; `capabilities` — CPU-only без network probes. |
| Class-gated swagger-coverage применён per-domain → большой домен (`ads`) нельзя разбить, либо мини-домен с двумя классами требует доделки до merge'а | Class-gated применяется **per-class**: `Async<X>` существует ↔ все операции класса `<X>` обязаны иметь async-binding. Отсутствие `Async<Y>` в том же домене не блокирует мердж класса `Async<X>`. DoD M3…M12 всё равно требует домен закрыть на 100%. |
| `from_env` инициализирует loop-зависимые ресурсы вне loop'а → cross-loop UB | `from_env` синхронен, SDK-managed ресурсы (`httpx.AsyncClient`, `asyncio.Lock`) создаются в `__aenter__`. Если внешний `http_client` передан пользователем, transport связывается с ним только в `__aenter__`. Доступ к `transport`/`auth_provider` до `__aenter__` бросает `RuntimeError` с понятным сообщением. Закреплено тестом `test_access_before_aenter_raises`. |
| Release notes 2.1.0 невозможно собрать механически, потому что в PR M3…M12 нет CHANGELOG-записей | DoD M3…M12 требует `## [Unreleased]` строку в корневом `CHANGELOG.md` на каждый PR. M-final сводит накопленное в `## [2.1.0]`. |
| `_merge_headers` срытно делает sync IO (`get_access_token()`) | Phase 1a первым шагом рефакторит контракт: helper принимает уже резолвнутый `bearer_token: str | None`. Без этого shared слой не IO-agnostic, и vary-логика расползётся. |
| `AsyncPaginatedList` не наследует `list` → ломаются ожидания сервисов | Документируем в docstring; `scripts/lint_async_parity.py` допускает `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`. List-API не реплицируется намеренно. |
| `AsyncPaginator` не покрывает helper usage `Paginator(...).as_list(...)` | Контракт `AsyncPaginator` симметричен sync (`iter_pages`/`collect`/`as_list`); все 4 текущих usage-сайта покрыты через методы, возвращающие `AsyncPaginatedList[T]`. |
| Auth-bindings не попадают в async-coverage | `_NON_DOMAIN_BINDING_MODULES` дополнен строго `"avito.auth.async_token_client"`; class-gated coverage гейтится по присутствию `AsyncTokenClient`/`AsyncAlternateTokenClient`. |
| Двойной декор одной функции | Текущая защита `__swagger_binding__` остаётся; sync и async — разные функции. |
| Гонка на основном refresh-токене в async | `asyncio.Lock` (`_refresh_lock`) в `AsyncAuthProvider` + double-checked pattern (как sync, но через `await`). |
| Гонка на autoteka-токене в async | Отдельный `_autoteka_refresh_lock` + double-checked в `get_autoteka_access_token()`. Sync-провайдер остаётся без нового thread-safety контракта в M1, чтобы не менять sync semantics; async получает явную защиту, потому что concurrent first-touch через один event loop — штатный сценарий. |
| `asyncio.Lock` создан вне event loop'а → cross-loop UB | `AsyncAuthProvider` создаётся внутри `AsyncAvitoClient` (через `__aenter__` или `_from_transport`); в docstring явное предупреждение «не переиспользовать между event loop'ами». Python 3.10+ лениво биндит lock к loop'у при первом `await`. |
| Миграция `_access_token` в `TokenCache` ломает `tests/core/test_authentication.py:122-127` | `AuthProvider` сохраняет `@property`/setter shim'ы для всех трёх частных полей; шим помечен legacy-комментом и удаляется в отдельном PR. |
| `_operation_specs_for_sdk_method` не находит spec из `async_domain.py` | Pre-flight smoke-тест с async-методом + явным импортом spec; текущая реализация через `unwrapped_method.__globals__` (`swagger_linter.py:578-601`) обязана работать, потому что `from ...operations import SOME_SPEC` ставит spec в `__globals__` модуля. Если не работает — фикс в Phase 1b. |
| Convenience-методы (`account_health`, …) теряют main user-value async (параллелизм) или меняют error semantics | M-final требует `asyncio.TaskGroup` только для независимых подзапросов и сохраняет sync error semantics: required ветки пробрасывают `AvitoError`, optional ветки идут через `_safe_summary_async`. Запрещено реализовывать «sync, обмазанный await» и запрещено превращать required ошибку в unavailable section. |
| `asyncio.gather(return_exceptions=True)` глушит `CancelledError` в convenience-методах | Запрещён; используется `asyncio.TaskGroup` (Python 3.11+, у нас floor 3.12+). При отмене внешнего вызова TaskGroup атомарно отменяет все child-таски без потери cancellation. |
| Retry-петля ловит `asyncio.CancelledError` и зацикливает отмену | Shared `_decide_*_retry` и обёртки `Transport`/`AsyncTransport` ловят **только** `Exception`, не `BaseException`. Закреплено тестом `test_cancelled_error_is_not_retried`. |
| `AsyncAvitoClient.__aenter__` оставляет полу-инициализированный state при ошибке | `__aenter__` обёрнут `try/except BaseException`: при любом исключении вызывает идемпотентный `aclose()` и пробрасывает наружу. Закреплено тестом `test_aenter_rollback_on_partial_failure`. |
| Ownership внешнего `httpx.AsyncClient` не определён — потенциальный resource-leak или double-close | M1 явно выбирает mirror текущего sync-поведения: `AsyncTransport.aclose()` закрывает переданный `httpx.AsyncClient`. Это закреплено тестом. Альтернативная политика `_owns_client` возможна только отдельным PR одновременно для sync и async. |
| `AsyncFakeTransport` рассинхронизирован при `asyncio.gather` | `_handle_lock = asyncio.Lock()` сериализует match-and-record; **создаётся в `__init__`**, не лениво (лениво — гонка на самой инициализации lock'а). Закреплено тестом `test_async_fake_transport_concurrent_handle`. |
| Существующие `async def test_*` в репозитории молча скипаются после `asyncio_mode = "strict"` | Pre-flight `grep -rn "^async def test_" tests/` фиксирует все такие тесты до M1; маркер `@pytest.mark.asyncio` добавляется отдельным pre-flight commit'ом. |
| `len(PaginatedList)` / `paginated[0]` в коде ломаются при попытке мигрировать на `AsyncPaginatedList` | Pre-flight `grep` фиксирует все list-API usage. `AsyncPaginatedList` не повторяет list-API намеренно; каждый кейс заменяется на `await materialize()` / `loaded_count` в async-двойнике или остаётся sync-only. |
| Скрытая работа «на потом» в доменных PR (TODO/FIXME/skip) | DoD M3…M12 явно требует пустой выхлоп `grep -E "TODO|FIXME|@pytest.mark.skip|xfail"` по diff'у; счётчики sync- и async-тестов сравниваются равенством; PR не мерджится при частичном покрытии домена. |
| PoC обнаруживает, что фундамент (M1) недостаточен | Это и есть назначение PoC: feedback от M2-PoC → правки фундамента в этом же PR или M1.5-PR; `tariffs`-домен после доработок закрыт на 100%, как и остальные. M3 не стартует, пока M2-PoC не зелёный. |
| `AsyncTokenClient._request_token` закольцован через основной auth-провайдер | Внутри создаётся независимый `AsyncTransport` с `auth_provider=None` (зеркало sync `TokenClient._build_transport()`). |
| Sync поведение незаметно изменилось в Phase 1 | DoD M1 включает baseline-diff только по nodeid существующих тестов с main; новые async tests не участвуют в сравнении. Любое расхождение по старым nodeid блокирует merge. Phase 1a — отдельный коммит для bisect. |
| `_gen_reference.py` строит reference только из sync `*/domain.py` → `Async<X>` молча отсутствуют в reference, `make docs-strict` остаётся зелёным, но публикация неполна | M1 обязан расширить builder (`public_domain_packages` подхватывает `async_domain.py`, `public_domain_classes` фильтрует `Async<X>` через `AsyncDomainObject`-наследование, `public_domain_methods` — через `value.__qualname__.startswith(f"{cls.__name__}.")`). Pre-flight фиксирует текущие точки фильтрации. M2-PoC валидирует на `tariffs`. |
| Версия пакета не поднята в M-final → релиз 2.1.0 опубликован под старой версией | DoD M-final требует `poetry version 2.1.0` + `## [2.1.0] - YYYY-MM-DD` в CHANGELOG в одном PR. `git tag v2.1.0` после merge. |
| `_safe_summary_async` вынесен в отдельный модуль, sync `_safe_summary` остался в `client.py` → симметричные хелперы в разных файлах | DoD M-final требует: либо оба в `avito/client.py`, либо оба в `avito/summary/_helpers.py`. Частичное вынесение запрещено. |
| Concurrent iteration одного `AsyncPaginatedList` мутит общий `_cursor` → пользователь получает silent data corruption | Fail-fast контракт: второй `__aiter__` на активном instance бросает `RuntimeError`; fan-out делается через `await materialize()` или отдельный `AsyncPaginatedList` per consumer. |
| Английский в новых сообщениях ошибок `async_domain.py` (STYLEGUIDE.md violation) | DoD M3…M12 включает явный пункт «сообщения ошибок только на русском»; code review проверяет каждый `raise <AvitoError>("...")`. |
| `AsyncSwaggerFakeTransport` не синхронизирован со sync `SwaggerFakeTransport` | Добавляется в M1 как thin async mirror поверх общих schema/argument helpers. `tests/contracts/test_async_swagger_contracts.py` проходит по discovered `variant="async"` bindings на каждом этапе и в M-final покрывает все 204 operations. |
