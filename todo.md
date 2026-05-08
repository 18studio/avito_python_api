# Dual-mode SDK (sync + async)

## Context

The SDK is currently fully synchronous: `AvitoClient` → `Transport` (`httpx.Client` + `time.sleep`) →
`AuthProvider` (`TokenClient` on top of sync-transport) → `DomainObject` subclasses
(11 API packages + auth-bindings, 204 swagger operations) → `PaginatedList[T]`
(subclass of `list`). The goal is to add a second,
asynchronous, surface modeled after `httpx.Client`/`httpx.AsyncClient`, without breaking the sync API,
reusing `OperationSpec`, models, request/query DTOs, swagger invariants, and
errors.

## Decisions made

| Question | Decision |
|---|---|
| Style | Parallel classes by hand: next to each sync layer we place an `Async*` class. We do not use codegen. |
| Placement | `avito/<domain>/async_domain.py` next to `domain.py`. |
| Swagger binding | `@swagger_operation(..., variant="sync"\|"async")`. The linter's unique key is `(operation_key, variant)`. |
| Normative documents | M1 updates `STYLEGUIDE.md`, because right now it describes the SDK as sync-only and only allows `domain.py`. Without this, M1 conflicts with the main style gate. |
| Sequencing | M1 — foundation with tests and async auth-bindings; M2-PoC — proof-of-concept of the template on `tariffs` (foundation validation, may return feedback); M3…M12 — closing each domain in a separate PR to 100%; M-final — convenience methods and release. Until the first domain `Async<X>` class appears, strict-coverage by `variant="async"` for API domains is empty and does not fail; auth is gated separately by `AsyncTokenClient` / `AsyncAlternateTokenClient`. |
| Pagination | `AsyncPaginatedList[ItemT]` — a separate class (not a subclass of `list`), without list-API parity (only `__aiter__` / `materialize` / `loaded_count` / `is_materialized` / `known_total` / `source_total`). |

## Architecture: what is shared, what is duplicated

```
        ┌────────── shared (semantics unchanged) ────────────────────┐
        │                                                            │
        │  OperationSpec, models, request/query DTO, ApiTimeouts,    │
        │  RequestContext, JsonPage, exceptions, RetryPolicy,        │
        │  RateLimiter ("how long to wait" logic), retries.RetryDecision│
        │                                                            │
        └─────────────────────┬──────────────────────────────────────┘
                              │ used by both
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌──────── SYNC (as is) ──────┐   ┌──────── ASYNC (new) ───────┐
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
                       (per-variant keys)
```

To keep retry logic and error mapping from drifting, we extract IO-agnostic
computations into `avito/core/_transport_shared.py` (no httpx call and no sleep):
`_decide_transport_retry`,
`_decide_http_retry`, `_is_retryable_request`, `_get_retry_after_seconds`, `_map_http_error`,
`_safe_payload`, `_extract_message`, `_extract_error_code`, `_extract_error_details`,
`_extract_request_id`, `_normalize_path`, `_normalize_params`, `_normalize_files`,
`_merge_headers`, `_build_user_agent`, `_extract_filename`, `build_httpx_timeout`,
`_safe_endpoint`, `_log_http_exchange`, `_log_retry`, `_elapsed_ms`,
`RateLimitState` (pure token-bucket state with `compute_delay()`/`observe_response()`,
without `Lock` and without `sleep` — see the "Contract for shared parts of RateLimiter" block below).
`Transport` and `AsyncTransport` remain thin wrappers with three differences:
the form of sleep, the form of client.request, and the type of lock around `RateLimitState`
(`threading.Lock` vs `asyncio.Lock`).

**Retry-loop contract in both modes.** The catch block in `Transport.request()` /
`AsyncTransport.request()` catches only explicitly retryable transport exceptions.
For M1 this mirrors the current sync behavior: `httpx.TimeoutException` and
`httpx.NetworkError`. Expanding catch to all of `httpx.RequestError` cannot be done
silently: it changes sync semantics and is only possible as a separate deliberate
behavior PR with tests. `BaseException` (including `asyncio.CancelledError`,
`KeyboardInterrupt`, `SystemExit`) **never goes into retry** — it is propagated
outwards unmodified. This is critical for async: otherwise the SDK would catch
coroutine cancellation and try to retry it, breaking cancellation semantics. Locked in
by the test `tests/core/test_async_transport.py::test_cancelled_error_is_not_retried` and
a sync baseline-diff in M1.

**Important clarification about `_merge_headers`.** The current implementation
(`avito/core/transport.py:410-428`) internally makes a synchronous call
`self._auth_provider.get_access_token()` — i.e. it couples token retrieval with merge.
To make the helper IO-agnostic, we refactor its contract: the shared `_merge_headers`
takes an already-resolved `bearer_token: str | None`, while resolution (including `await` in
the async variant) is performed by `Transport`/`AsyncTransport` themselves separately. This is the first step
of Phase 1 (without behavioral changes to sync), and it is blocking for everything else in M1.

Similarly: `avito/auth/_cache.py` contains in-memory state (fields `_access_token`,
`_refresh_token`, `_autoteka_access_token`) and pure helpers (`_is_token_fresh`).
The module-level function `_map_token_response` (`avito/auth/provider.py:35`) moves
to `_cache.py` without changing its signature. `AuthProvider` and `AsyncAuthProvider`
delegate to the cache and only add the sync/async lock + IO themselves.

### Dependency order in M1

```
  Phase 0   pre-flight (see "Pre-flight for PR M1" section)
            ↓
  Phase 1a  refactor Transport._merge_headers → accepts a resolved bearer_token
            (sync without behavioral changes; baseline pass/fail of tests is identical)
            ↓
  Phase 1b  _transport_shared.py  ◀── the rest of the IO-agnostic extract from Transport
            _cache.py             ◀── TokenCache + map_token_response, AuthProvider
                                      stores TokenCache + property-shims for
                                      _access_token/_refresh_token/_autoteka_access_token
                                      (for the sake of existing tests)
            ↓
  Phase 2   AsyncTransport, AsyncOperationTransport, AsyncOperationExecutor
            AsyncAuthProvider (with asyncio.Lock on refresh + a separate autoteka lock)
            AsyncTokenClient, AsyncAlternateTokenClient
            AsyncPaginatedList, AsyncPaginator
            ↓
  Phase 3   variant="async" in the swagger decorator/discovery/linter
            AsyncAvitoClient (no factory methods; lifecycle only)
            avito/testing/async_fake_transport.py + tests/async_fake_transport.py
                                                    (re-export with DeprecationWarning)
            ↓
  Phase 4   tests + docs (including baseline-diff proving sync is unchanged)
```

## Key files and join points

### Existing, modified in M1

| File | What we change |
|---|---|
| `avito/core/transport.py` | Extract IO-agnostic helpers into `_transport_shared.py` and reuse them. Sync behavior is unchanged. |
| `avito/core/operations.py` | + `AsyncOperationTransport` (Protocol, async mirror of `OperationTransport`), + `AsyncOperationExecutor` (async mirror of `OperationExecutor.execute`) with the same `json` / `empty` / `binary` branches as sync. Helpers `render_path`, `_serialize_query`, `_serialize_request`, `_merge_content_type`, `_extract_filename` are already module-level — reused without copies. |
| `avito/core/swagger.py` | + a `variant: Literal["sync","async"] = "sync"` field on `SwaggerOperationBinding`. + a `variant` parameter on `swagger_operation(...)`. The `ConfigurationError` on double-decorating one function — unchanged. |
| `avito/core/swagger_discovery.py` | `_iter_domain_modules` additionally looks for `<domain>.async_domain` (next to `<domain>.domain`). `DiscoveredSwaggerBinding` gets `variant`. `canonical_map` remains a sync-only compatibility API for existing sync contract tests; the new `canonical_map_by_variant` / `binding_for(operation_key, variant)` uses the key `(operation_key, variant)`. |
| `avito/core/swagger_linter.py` | `_validate_duplicate_bindings` groups by `(operation_key, variant)`. `_validate_complete_bindings` runs per-variant; for `variant="async"` the expected set is limited to domains where an `Async*` class has already been found (class-gated coverage). `_validate_no_unbound_operation_specs` stays per `OperationSpec` (the sync OperationSpec is reused by both modes — the usage counter is unified). |
| `avito/core/swagger_report.py` | The JSON report becomes variant-aware: the summary stores `sync` and `async` coverage separately, `operations[].bindings` contains a mapping by variant. The old `bound`/`unbound` fields remain sync-only compatibility until a separate report API bump. |
| `avito/auth/provider.py` | Extract shared cache state into `_cache.py`. `AuthProvider` itself stays sync. We keep `_access_token`/`_refresh_token`/`_autoteka_access_token` as `@property` shims over `TokenCache` (with setters), because `tests/core/test_authentication.py:122-127` mutates the field directly via `replace()`. |
| `avito/core/deprecation.py` | `deprecated_method(...)` becomes async-aware: if the original method is a coroutine function, the wrapper is also `async def` and does `return await method(...)`, preserving `__sdk_deprecation__`. This is needed for deprecated async doubles in `cpa` and `ads`. |
| `avito/core/transport.py` (separately) | Phase 1a: `_merge_headers` is refactored first — it takes an already-resolved bearer token, and resolution is called as a separate line above. All other shared helpers are Phase 1b. |
| `avito/__init__.py` | + export `AsyncAvitoClient`, `AsyncPaginatedList`. `AsyncPaginator` is not raised to root level, because the sync-root exports `PaginatedList` but not `Paginator`; `AsyncPaginator` remains accessible from `avito.core`. |
| `avito/core/__init__.py` | + export `AsyncTransport`, `AsyncOperationExecutor`, `AsyncOperationTransport`, `AsyncPaginatedList`, `AsyncPaginator`. |
| `avito/auth/__init__.py` | + export `AsyncAuthProvider`, `AsyncTokenClient`, `AsyncAlternateTokenClient`, if these classes are declared public for consumer-side tests and type hints. |
| `avito/testing/__init__.py` | + export `AsyncFakeTransport`, `AsyncSwaggerFakeTransport` and shared helpers, so that async test utilities are the same public contract as sync `FakeTransport`. |
| `avito/<domain>/__init__.py` | At every M2/M3…M12 we add the export of the corresponding `Async<X>` classes; without this, `_gen_reference.py`, mkdocstrings and IDE-discovery will not see the async surface. |
| `docs/site/assets/_gen_reference.py` | + extension of `public_domain_packages()` / `public_domain_classes()` / `public_domain_methods()` to pick up `async_domain.py` and `Async<X>` classes alongside their sync counterparts. The builder must not depend solely on `avito.<package>.__all__`: it must import `avito.<package>.domain` and `avito.<package>.async_domain` directly, then preserve the order sync-class → async-class. Important: the current `write_domain_pages()` writes only `::: avito.<package>` and does not use the class/method helper functions; M1 must move domain page generation to explicit class directives (`::: avito.<package>.ClassName`) in the order sync-class → async-class. `ensure_debug_info_exists()` is extended to `AsyncAvitoClient.debug_info()`. Without this, `make docs-strict` after M2-PoC will not prove reference completeness. |
| `avito/core/domain.py` | + `AsyncDomainObject` with async `_execute` and async `_resolve_user_id`. Sync `DomainObject` — unchanged. |
| `pyproject.toml` | + `pytest-asyncio = "^0.24"` in dev-deps. + `[tool.pytest.ini_options] asyncio_mode = "strict"` and `asyncio_default_fixture_loop_scope = "function"`. Without an explicit `asyncio_default_fixture_loop_scope`, `pytest-asyncio` 0.23+ emits a `PytestDeprecationWarning` on every test — at the time of M1 there is no `filterwarnings = error` in `pyproject.toml` (verified by grep), so this won't break pytest immediately, but it will accumulate noise in output and block enabling `filterwarnings = error` in the future. Locked in M1 PR preventively. |
| `Makefile` | + an `async-parity-lint` target, included in `quality`; `make check` after M1 must remain green. |
| `scripts/lint_architecture.py` | We do not touch `LEGACY_FILENAMES`, but public-method checks apply to `domain.py` and `async_domain.py`; the AST parser must consider `ast.AsyncFunctionDef` on equal footing with `ast.FunctionDef`. |
| `scripts/lint_docstrings.py` | Checks `avito/*/domain.py` and `avito/*/async_domain.py`, so async public methods do not get generic / reference-poor docstrings. |
| `scripts/lint_async_parity.py` | A new static linter, not pytest: checks `Async<X> ↔ X`, signatures, return annotations (`PaginatedList[T] ↔ AsyncPaginatedList[T]`), `async def`, binding equality, and the absence of extra/missing public methods. |
| `scripts/lint_swagger_bindings.py` | No CLI changes (the logic is moved into `swagger_linter.py`). |
| `tests/contracts/test_swagger_contracts.py` | Filtered to `variant="sync"` and continues to check sync `SwaggerFakeTransport` without changing behavioral coverage. |
| `STYLEGUIDE.md` | M1 normatively allows a dual-mode SDK: `async_domain.py`, `AsyncDomainObject`, `AsyncTransport`/`httpx.AsyncClient`, async lifecycle, and variant-aware Swagger bindings. The sync-only recommendation is replaced with a description of two surfaces. |
| `docs/site/explanations/swagger-binding-subsystem.md` | A section on `variant` and class-gated coverage. |
| `docs/site/explanations/domain-architecture-v2.md` | A paragraph on `async_domain.py` as an allowed file paired with `domain.py`. |
| `README.md`, `mkdocs.yml`, `docs/site/index.md`, `docs/site/reference/client.md`, `docs/site/reference/pagination.md`, `docs/site/reference/testing.md`, `docs/site/how-to/index.md` | In M-final updated from "synchronous SDK" to dual-mode SDK and given links to async lifecycle/testing/pagination. |

### New files (M1)

```
avito/core/_transport_shared.py          # IO-agnostic helpers, retry/error mapping/headers
                                         #   (_merge_headers takes bearer_token: str | None;
                                         #   _request_binary_async mirrors sync _request_binary)
avito/core/_async_rate_limit.py          # AsyncRateLimiter (asyncio.Lock + asyncio.sleep
                                         #   over shared RateLimitState)
avito/core/async_transport.py            # AsyncTransport (httpx.AsyncClient)
avito/core/async_pagination.py           # AsyncPaginatedList, AsyncPaginator, AsyncPageFetcher
avito/auth/_cache.py                     # TokenCache + map_token_response
avito/auth/async_provider.py             # AsyncAuthProvider (separate asyncio.Lock for
                                         #   the main and autoteka tokens)
avito/auth/async_token_client.py         # AsyncTokenClient, AsyncAlternateTokenClient
                                         #   (with @swagger_operation(..., variant="async"))
avito/async_client.py                    # AsyncAvitoClient (lifecycle + auth/debug_info/closed-state;
                                         #   domain factory methods empty in M1)
avito/testing/async_fake_transport.py    # AsyncFakeTransport (httpx.MockTransport+AsyncClient)
avito/testing/async_swagger_fake_transport.py
                                         # AsyncSwaggerFakeTransport: async contract runner
                                         #   for discovered bindings with variant="async"
tests/async_fake_transport.py            # thin re-export with DeprecationWarning (as in sync;
                                         #   template copied 1:1 from tests/fake_transport.py)
tests/core/test_async_transport.py
tests/core/test_async_pagination.py
tests/core/test_async_executor.py
tests/core/test_async_client_lifecycle.py
tests/auth/test_async_provider.py
tests/contracts/test_async_swagger_contracts.py
                                         # Swagger-spec compliance for async bindings
scripts/lint_async_parity.py             # static linter, not pytest
```

### New files (M2-PoC + M3…M12, per domain)

```
avito/<domain>/async_domain.py
tests/domains/<domain>/test_<domain>_async.py
```

## Contracts of new classes

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
    async def download_binary(...) -> BinaryResponse: ...   # full-buffer, see below
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> AsyncTransport: ...
    async def __aexit__(self, *exc) -> None: ...
    @property
    def auth_provider(self) -> AsyncAuthProvider | None: ...
    def debug_info(self) -> TransportDebugInfo: ...
```

Implements `AsyncOperationTransport` (Protocol, async mirror of `OperationTransport` from
`avito/core/operations.py`).

`AsyncTransport.request()` internally (an exact mirror of sync `Transport.request()`,
`avito/core/transport.py:146-185`):

1. calls `bearer_token = await self._auth_provider.get_access_token()` (if required);
2. passes `bearer_token` to the shared `_merge_headers(...)` — strictly a pure function;
3. **on every retry-loop attempt** (including the first): `delay = await
   self._rate_limiter.acquire()` **before** `await self._client.request(...)` — mirrors
   sync `Transport.request()` line 148. If `delay > 0` — the same info log
   `transport rate limit delay` with `reason="client_rate_limit"` is written, as in sync;
4. **after a successful response**: `self._rate_limiter.observe_response(headers=
   response.headers)` — mirrors sync line 183. `observe_response` remains a sync
   method on `AsyncRateLimiter` (only state mutation under `asyncio.Lock` inside,
   no sleep, no IO; await is not needed);
5. the loop of retry decisions delegates to the shared `_decide_*_retry`;
6. on 401 — `self._auth_provider.invalidate_token()` (sync clear-cache operation),
   a repeated `await self._auth_provider.get_access_token()`, one retry;
7. catches only `httpx.TimeoutException` and `httpx.NetworkError`, like sync
   `Transport` at the time of M1. `asyncio.CancelledError` and any `BaseException`
   propagate outwards without retry — see the shared retry-loop contract above.

**Forbidden** to call `self._client.request(...)` without first awaiting `await
self._rate_limiter.acquire()`: otherwise rate-limit headers (Retry-After, X-RateLimit-*)
will update the state, but the actual serialization of requests through the limiter will not work, and
parallel coroutines will go out in a batch. Locked in by the test
`tests/core/test_async_transport.py::test_request_acquires_rate_limiter_before_httpx_call`,
which via `AsyncFakeTransport` runs 5 parallel coroutines on one transport
and verifies that `RateLimitState._tokens` is updated exactly one at a time before each
httpx call (and not in a batch), and the second test
`test_request_calls_observe_response_after_success` verifies that
`observe_response` was called with the same headers the mock returned.

**Rate limiter in async.** One rate limiter belongs to one `AsyncTransport`
(not to each call coroutine). All coroutines sharing the transport must
serialize through `asyncio.Lock` inside the limiter — otherwise N parallel requests
will independently compute "must wait X seconds" and will go out in a batch after waiting, breaking
the limit.

**Contract of shared parts of RateLimiter.** The current `avito/core/rate_limit.py` contains
*both* the token-bucket state (`_tokens`, `_blocked_until`, `_updated_at`), *and*
`while True: self._sleep(delay)` inside `acquire()` — sleep is baked into the method. The sync
`RateLimiter` cannot be "wrapped" in async without rework, because internally there is
a `threading.Lock` that is forbidden to hold across `await`. Therefore the decomposition
is strict, in three parts:

1. **`RateLimitState`** (pure dataclass in `avito/core/_transport_shared.py`):
   `_tokens: float`, `_updated_at: float`, `_blocked_until: float`, policy
   (`rate`, `capacity`, `enabled`). Methods:
   - `compute_delay(now: float) -> float` — a pure function that **does not** sleep,
     returns 0 if it can go immediately, otherwise the required delay. Reserves a token
     if it returns 0 (mutates state).
   - `observe_response(now: float, headers: Mapping[str, str]) -> None` — a pure
     update of `_blocked_until` from rate-limit headers (no IO).

2. **`RateLimiter`** (sync, stays in `avito/core/rate_limit.py`): stores
   `RateLimitState` + `threading.Lock` + `_sleep` + `_clock`. To avoid changing
   sync behavior, the wrapper preserves the current order: the lock is held only on
   computing/mutating state, and sleep is performed outside the `threading.Lock`. Any change
   to sync-concurrency semantics — a separate deliberate PR, not part of M1.

3. **`AsyncRateLimiter`** (new, **in `avito/core/_async_rate_limit.py`** —
   symmetrically with sync `avito/core/rate_limit.py`, so that grep `RateLimit` finds both
   modules side by side and the async infrastructure does not bleed into `async_transport.py`).
   Stores
   **a separate `RateLimitState`** (not shared with sync — state is not shared between
   modes; sync and async transports are independent entities with independent
   buckets) + `asyncio.Lock` + `_clock` + `_sleep: Callable[[float],
   Awaitable[None]] = asyncio.sleep`. `async def acquire()` is
   `async with self._lock: while (delay := state.compute_delay(now())) > 0:
   await self._sleep(delay)`.

The async wrapper deliberately holds `asyncio.Lock` during the wait, so that several
coroutines sharing one transport do not wake up in a single batch after the same delay.
`asyncio.Lock` is created when `AsyncRateLimiter` is created inside the async lifecycle
(`AsyncAvitoClient.__aenter__`, `AsyncFakeTransport.as_client()` inside the test loop,
or explicit creation by the user inside the loop) and is bound to the event loop on first
`await`. It is forbidden to reuse one `AsyncRateLimiter` across event loops.

**Locked in by tests**: `tests/core/test_rate_limit_state.py` (pure compute);
`tests/core/test_async_transport.py::test_async_rate_limiter_serializes_concurrent_acquires`
(five parallel coroutines do not go out in a batch after waiting, but serialize under
`asyncio.Lock`).

**Connection pool and fan-out limits.** `AsyncTransport` creates `httpx.AsyncClient`
with **default** `httpx.Limits` (max_connections=100, max_keepalive_connections=20),
without overriding. This is a deliberate decision: explicit tuning of limits in M1 is a separate
behavioral axis that should not be introduced together with the async foundation. At the same time
**the convenience methods of M-final limit fan-out**: no aggregator
(`account_health`, `listing_health`, `review_summary`, `promotion_summary`) should
spawn > 6 simultaneously in-flight tasks via `asyncio.TaskGroup` (current sync
code has at most 5–6 independent branches in `account_health`). If a domain in the future
requires parallel fan-out > 6, this is introduced in a separate PR with an explicit
semaphore policy (`asyncio.Semaphore`) — but not in 2.1.0. Locked in by the M-final DoD code review
checklist and risk table. If an external `httpx.AsyncClient` is passed by the user,
its limits are the user's responsibility; the SDK does not override them and documents
this fact in the `AsyncAvitoClient.__init__` docstring.

**Semantics of `AsyncTransport.download_binary`.** In M1 — **full-buffer**, like sync:
internally `await response.aread()` and a `BinaryResponse` is returned with the full `bytes`
content. The streaming variant (`async for chunk in response.aiter_bytes()`) is
**out of scope for M1…M-final**: no public sync method returns a chunked stream,
`scripts/lint_async_parity.py` and the async contract suite would break it,
and Async API users would not see a divergence
from sync. If a stream is needed in the future — that is a separate API
(`download_binary_stream` or an iterator), introduced in a separate minor release
after 2.1.0 with a symmetric sync analog. Locked in by the test
`tests/core/test_async_transport.py::test_download_binary_full_buffer_matches_sync`.

### `avito/core/operations.py` (extension)

```python
class AsyncOperationTransport(Protocol):
    async def request(...) -> httpx.Response: ...           # async def, not Awaitable[T]
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
`_extract_filename` are common, reused by both executors without copying.
`AsyncOperationExecutor.execute()` repeats all three branches of the sync executor:

- `response_kind == "json"`: `payload = await transport.request_json(...)`, then
  `response_model.from_payload(payload)`;
- `response_kind == "empty"`: `response = await transport.request(...)`, then
  `EmptyResponse(status_code=response.status_code, headers=dict(response.headers))`;
- `response_kind == "binary"`: the executor calls a module-level helper
  `_request_binary_async(transport, *, spec, path, context, params, headers,
  idempotency_key)` — async mirror of sync `_request_binary` (`avito/core/operations.py:254-278`).
  The helper is module-level and accepts an `AsyncOperationTransport` Protocol (not a concrete
  `AsyncTransport`), as sync accepts `OperationTransport`. Inside,
  `await transport.request(...)` with method/path from `OperationSpec`, then it builds
  `BinaryResponse(content=response.content, content_type=...,
  filename=_extract_filename(...), status_code=..., headers=dict(response.headers))`.
  The helper lives in **`avito/core/operations.py`** next to sync `_request_binary` (not
  in `_transport_shared.py`), because the sync version is already there and works with
  the `OperationTransport` Protocol — these are two symmetric twins on the same level
  of abstraction, and splitting them across different modules only multiplies navigation.
  `_extract_filename` is already module-level in the same file — reused without copies.
  `download_binary()` remains a low-level convenience method of `AsyncTransport`,
  but is **not** part of the `AsyncOperationTransport` Protocol, otherwise the binary branch will
  diverge from sync executor and lose method/path from `OperationSpec`.

The binary branch is locked in by an M1 unit test on the executor
(`tests/core/test_async_executor.py::test_binary_branch_uses_request_binary_async_helper`,
verifies that `_request_binary_async` is actually called and `BinaryResponse`
is built from the same fields as sync) and an M12 domain test for `OrderLabel.download()` via
`AsyncSwaggerFakeTransport`/`AsyncFakeTransport`.

**Executor retry policy — exact mirror of sync.** `AsyncOperationExecutor.execute()`
chooses retry in the same order as sync `OperationExecutor`: `retry or spec.retry`,
with the same defaulting, and propagates it to `AsyncTransport.request()` with an identical argument.
Forbidden: (1) take `retry` only from the argument and ignore `spec.retry`, (2) take
`spec.retry` always and ignore the override. Locked in by the unit test
`tests/core/test_async_executor.py::test_executor_retry_resolution_matches_sync`,
parameterized with three cases `(retry=None, spec.retry=A) → A`,
`(retry=B, spec.retry=A) → B`, `(retry=B, spec.retry=None) → B` and comparing the result with
sync `OperationExecutor` on the same `OperationSpec`. Without this test, divergence in
retry semantics between sync and async could go unnoticed.

A note on Protocol typing: for async methods in `Protocol` we use `async def`, not
`Awaitable[T]` in the return annotation of a sync signature. This gives mypy strict correct
runtime-protocol matching and avoids double wrapping.

### `avito/core/domain.py` (extension)

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

Async double of sync `DomainObject._resolve_user_id`: the same fallback order as the
current sync code in `avito/core/domain.py`: first the argument, then `settings.user_id`,
then an internal raw request to `/core/v1/accounts/self` via transport. This is
a deliberate exception for a base helper: `core` does not import
`avito.accounts.operations.GET_SELF`, to avoid creating a core → domain dependency.
The Swagger binding for `/core/v1/accounts/self` is covered by the public
`Account.get_self()` / `AsyncAccount.get_self()`, while `_resolve_user_id` remains an
internal helper without a separate binding. If sync `_resolve_user_id` is moved
to the executor in the future, async changes in the same PR.

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

`AsyncPaginatedList` does **not** inherit `list[T]` — async iteration and list indexing
are incompatible. We document this explicitly in the docstring and in the `pagination` how-to. The
page transition semantics are identical to sync `PaginatedList._consume_page` (including `next_cursor`,
`page+per_page`, `has_next_page`).

**Concurrency contract.** `AsyncPaginatedList` does not support concurrent iteration
of one instance from multiple coroutines. But this should not turn into silent data
corruption: the class stores an active-iteration flag (`_active_iterator`) and fail-fast
raises `RuntimeError("AsyncPaginatedList уже итерируется; используйте materialize() или создайте отдельный список.")`,
if a second `__aiter__` starts before the first finishes. If fan-out is needed —
call `await materialize()` once and iterate over the resulting `list[T]`,
or create a separate `AsyncPaginatedList` per consumer. Documented
in the class docstring and in `docs/site/explanations/pagination-semantics.md`
(addition in M-final). Locked in by the behavior of
`tests/core/test_async_pagination.py::test_concurrent_aiter_raises_runtime_error`.

**Lifecycle contract — behavior after transport `aclose()`.** `AsyncPaginatedList`
captures the `fetch_page` callable at creation time, which holds a reference to
`AsyncTransport`. If the user calls `await client.aclose()` while an
`AsyncPaginatedList` is mid-iteration (i.e. the first page is loaded but
subsequent pages are not), the next `__anext__` / next `aload_until` /
`materialize()` must raise `ClientClosedError("Клиент закрыт во время итерации
AsyncPaginatedList; пагинация прервана.")` rather than silently returning the
partial buffer or hanging on a closed `httpx.AsyncClient`. Implementation: the
`fetch_page` wrapper checks `transport._closed` (or the client's `_closed` flag,
propagated via an internal hook) before each network call; if closed, raises
`ClientClosedError`. Already-buffered items from previous pages are **not**
flushed — the iterator simply stops on the next page boundary. The same rule
applies to `AsyncPaginator.iter_pages()` and `collect()`. Locked in by
`tests/core/test_async_pagination.py::test_aiter_raises_after_client_aclose` and
`::test_materialize_raises_after_client_aclose`.

`AsyncPaginator` is mandatory as an implementation helper: sync domains use
`Paginator(...).as_list(...)` in 4 places (`avito/ads/domain.py:266,1183`,
`avito/accounts/domain.py:170,383`). The current public surface does not return
`Paginator` directly, so async public methods return `AsyncPaginatedList[T]`,
not `AsyncPaginator[T]`. `AsyncPaginator` itself remains accessible from `avito.core` for
core API symmetry: `iter_pages()` — `AsyncIterator`, `collect()` — coroutine,
`as_list()` creates an `AsyncPaginatedList`, passing `first_page` like its sync analog.

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

`AuthProvider` and `AsyncAuthProvider` store `TokenCache` and use the shared `map_token_response`.

**Compat-shim for existing tests.** `tests/core/test_authentication.py:122-127`
directly reads and assigns `provider._access_token` via `dataclasses.replace(...)`.
To avoid touching tests in the M1 PR (scope-creep risk), `AuthProvider` keeps three
attribute shims via `@property`/setter:

```python
@property
def _access_token(self) -> AccessToken | None: return self._cache.access_token
@_access_token.setter
def _access_token(self, value: AccessToken | None) -> None:
    self._cache.access_token = value
# similarly for _refresh_token, _autoteka_access_token
```

The shims are marked `# legacy private accessor — see PR M1` and are removed later in a separate PR
along with test migration.

### `avito/auth/async_provider.py`

```python
class AsyncTokenFetcher(Protocol):
    """Async mirror of sync `TokenFetcher` (avito/auth/provider.py:67-70)."""
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
    def invalidate_token(self) -> None: ...         # sync clear cache, no await
    async def aclose(self) -> None: ...
    async def get_autoteka_access_token(self) -> str: ...   # double-checked + _autoteka_refresh_lock
    def token_flow(self) -> AsyncTokenClient: ...
    def alternate_token_flow(self) -> AsyncAlternateTokenClient: ...
```

**Contract of `invalidate_token()` — sync, no await.** The method performs one operation
`self._cache.access_token = None` (atomic assignment of a dataclass field). This
is safe outside `_refresh_lock`, because in asyncio there is no true parallelism between
coroutines of the same loop: between two `await` points control is not transferred, and
a parallel coroutine cannot "catch" half-updated state. **Forbidden** to make
`invalidate_token` a coroutine with `async with self._refresh_lock` — this introduces a false
appearance of protection, increases latency of 401-handling in `AsyncTransport.request()`, and
contradicts the sync contract, where `AuthProvider.invalidate_token()` is also sync. Locked in
by the test `tests/auth/test_async_provider.py::test_invalidate_token_is_sync_and_idempotent`,
which verifies that the method can be called outside a coroutine (e.g. from a `__del__` wrapper),
that a repeated call is a no-op, and that after it `get_access_token()` triggers a refresh.

**Lock lifecycle.** In Python 3.10+ `asyncio.Lock()` created outside the event loop
lazily binds to the loop on first `await`. To avoid cross-loop UB:
`AsyncAuthProvider` is created inside `AsyncAvitoClient.__aenter__` (or `_from_transport`),
and is not reused across different event loops. We document this in the docstring of
`AsyncAvitoClient` and in the risk section.

A separate `_autoteka_refresh_lock` is needed because concurrent first-touch
`get_autoteka_access_token()` would cause duplicate Autoteka OAuth requests. The sync provider
does not have this protection (the GIL doesn't help between threads), but in async this is already an explicit race.

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

    async def request_refresh_token(self, request) -> TokenResponse: ...   # no binding (sync also has none)
```

`AsyncAlternateTokenClient` is a mirror of the sync analog with `variant="async"` on two methods
(`getAccessTokenAuthorizationCode`, `refreshAccessTokenAuthorizationCode`).

Inside `AsyncTokenClient._request_token` a **separate `AsyncTransport`** is created with
`auth_provider=None` (mirror of sync `TokenClient._build_transport()`, see
`avito/auth/provider.py:345-350`). Use of the main `AsyncTransport` through
`AsyncAuthProvider` is forbidden — that would loop the OAuth request through the auth provider itself.

`avito/core/swagger_discovery.py._NON_DOMAIN_BINDING_MODULES` is augmented strictly with
`"avito.auth.async_token_client"` (not `async_provider`) — because the classes with swagger
bindings (`AsyncTokenClient`, `AsyncAlternateTokenClient`) live there. Otherwise
async bindings of the auth domain will not enter discovery.

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
    def debug_info(self) -> TransportDebugInfo: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> AsyncAvitoClient: ...
    async def __aexit__(self, *exc) -> None: ...

    # M2-PoC: tariff() is added as template validation
    # M3+: at each step ALL domain factory methods are added at once
    # def tariff(self) -> AsyncTariff: ...                # M2-PoC
    # def account(self, user_id=None) -> AsyncAccount: ...# M4
    # ...
```

**Lifecycle of `from_env` and `__init__`.** `from_env` is a **synchronous** factory
(mirror of sync `AvitoClient.from_env`): it reads `.env`/environment, constructs
`AvitoSettings`, and returns an uninitialized `AsyncAvitoClient`. SDK-managed
network resources (`httpx.AsyncClient`, `asyncio.Lock`) do not yet exist at this stage —
they are created lazily in `__aenter__` for the current event loop. Exception: if
the user explicitly passes an external `http_client`, it already exists, but transport
and auth-provider are still bound to it only in `__aenter__`. This is critical because:
- `httpx.AsyncClient` created in one loop and used in another gives
  undefined behavior;
- `asyncio.Lock` binds to the loop on first `await` and does not transfer between
  loops;
- `from_env` itself is not `async` — the user should not connect the SDK via
  `await AsyncAvitoClient.from_env()`.

**Usage contract — required patterns:**

```python
# (1) Recommended: context manager
async with AsyncAvitoClient.from_env() as client:
    ...

# (2) Allowed: explicit aclose
client = AsyncAvitoClient.from_env()
async with client:           # initialization in __aenter__
    ...
# or
client = AsyncAvitoClient.from_env()
await client.__aenter__()    # equivalent of async with
try:
    ...
finally:
    await client.aclose()
```

**Forbidden:**
```python
client = AsyncAvitoClient.from_env()
await client.transport.request_json(...)   # transport is still None — RuntimeError
```

`transport`/`auth_provider` are `@property`, return `RuntimeError("AsyncAvitoClient
не инициализирован: используйте 'async with' или дождитесь '__aenter__'")` until
the first `__aenter__`. Locked in by the test
`tests/core/test_async_client_lifecycle.py::test_access_before_aenter_raises`.

**Public client-contract parity.** `AsyncAvitoClient` mirrors the public contract of
`AvitoClient` that does not depend on a specific domain:

- `debug_info()` is available after `__aenter__`, returns the same `TransportDebugInfo`
  as sync `AvitoClient.debug_info()`, and works through `_require_transport()`;
- `auth()` checks `_ensure_open()` and returns `AsyncAuthProvider`;
- `aclose()` is idempotent, sets `_closed=True`, and closes `AsyncTransport`
  + `AsyncAuthProvider`;
- after `aclose()` public methods (`auth()`, `debug_info()`, factory methods,
  convenience methods after M-final) raise `ClientClosedError("Клиент закрыт; создайте новый AsyncAvitoClient.")`;
- access to `transport`/`auth_provider` before `__aenter__` remains an initialization
  error, and after `aclose()` — a closed-client error. If both states are
  possible, `_closed` has priority.

This is not optional sugar: `debug_info()` is part of the public diagnostic contract of the sync SDK
and must appear in M1, before the first domain.

**Ownership of an external `httpx.AsyncClient`.** In M1 we cannot quietly change the current
sync semantics. Currently, sync `Transport.close()` closes the `httpx.Client` even if
it was passed externally. Therefore `AsyncTransport.aclose()` in 2.1.0 mirrors this
behavior: it closes the internal `httpx.AsyncClient` regardless of whether it was created by
the SDK or passed by the user. This is locked in by a test, so the plan does not rely on a
wrong assumption about `_owns_client`. If an "external client is
owned by caller" policy is needed, it is introduced in a separate PR simultaneously for sync and async with an explicit
CHANGELOG/deprecation design. If `http_client` is passed, its loop must match
the loop in which `__aenter__` will be called; cross-loop ownership is UB,
verified only by documentation.

**Rollback on partial failure in `__aenter__`.** If `__aenter__` raises in
the middle (for example, `httpx.AsyncClient` is already created, but `AsyncAuthProvider.__post_init__`
or lazy lock initialization throws an exception), all already-created state must
be closed before re-raising. Implementation:

```python
async def __aenter__(self) -> AsyncAvitoClient:
    try:
        # any initialization that may raise
        await self._transport.__aenter__()
        return self
    except BaseException:
        await self.aclose()  # idempotent: safe on partially-initialized state
        raise
```

`aclose()` is idempotent and resilient to closing partially-initialized state
(each sub-resource checks `is None` before `await x.aclose()`). Locked in by
the test `tests/core/test_async_client_lifecycle.py::test_aenter_rollback_on_partial_failure`.

In M1 `AsyncAvitoClient` has no domain factory methods — only lifecycle, `auth()`,
`debug_info()`, closed-state, and a smoke-call via raw `transport.request_json(...)`
in a test. **Convenience methods `account_health`,
`business_summary`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`,
`promotion_summary`, `capabilities`** on `AsyncAvitoClient` are a separate (last)
stage, M-final, because some of them combine multiple domains and are not needed before
all domains are ported.

**Classification of M-final methods (important for implementation).** Not all 8 methods are
aggregators; the pattern must not be conflated.

| Method | Type | Sync behavior | Async behavior |
|---|---|---|---|
| `account_health` | aggregator with dependencies | first `_resolve_user_id`; then independent branches `balance`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`; `promotion_summary` depends on `item_ids` from `listing_health` (`avito/client.py:206-263`) | **`asyncio.TaskGroup`** only for independent branches after `user_id`; `promotion_summary` runs after `listing_health`. Errors of `balance`/`listing_health` propagate as in sync; chat/order/review/promotion remain safe sections via `_safe_summary_async`. |
| `listing_health` | aggregator with first-list dependency | first `ad.list(...)`, then if `item_ids` are present, calls item stats, calls stats and spendings (`avito/client.py:265-368`) | the list of ads is loaded first; after obtaining `item_ids`, **`asyncio.TaskGroup`** for independent stats/calls/spendings. Spendings remains an optional safe section; stats/calls errors propagate as in sync. |
| `business_summary` | **alias** for `account_health` | `return self.account_health(...)` (`avito/client.py:184-204`) | `return await self.account_health(...)` — **no `TaskGroup`**, 1:1 delegation |
| `chat_summary` | leaf/sequential | `_resolve_user_id`, then a single call to the `messenger` domain | sequential `async def`; no `TaskGroup` needed |
| `order_summary` | leaf | a single call to the `orders` domain | one `await`; `TaskGroup` forbidden |
| `review_summary` | mixed required+optional | `review().list()` is optional-safe, `rating_profile().get()` is required (`avito/client.py:396-429`) | **sequentially**, without `TaskGroup`: first `reviews` via `_safe_summary_async` (optional, error → unavailable section), then `await rating_profile().get()` (required, error propagates). TaskGroup forbidden, see "Important TaskGroup subtlety" block below. |
| `promotion_summary` | conditional aggregator | `list_orders`; if `item_ids` are passed — additionally `list_services` (`avito/client.py:431-465`) | without `item_ids` one `await`; with `item_ids` **`asyncio.TaskGroup`** is allowed for `list_orders` and `list_services`. |
| `capabilities` | static reference | does not make network probe requests, only builds `CapabilityDiscoveryResult` from current configuration (`avito/client.py:467-531`) | remains a sync-shaped CPU-only method without `TaskGroup` and without network calls. If capabilities later becomes a probe method, that is a separate API/behavior change with tests. |

The rule: we parallelize only actually independent network branches and preserve sync
error semantics. Aliases (`business_summary`), CPU-only methods (`capabilities`), and
leaves (`order_summary`) do not get `TaskGroup`. This is recorded in the M-final DoD below
as an explicit code review checklist check.

**Important TaskGroup subtlety for mixed required+optional branches.** In sync code,
`review_summary` first does `review().list()` via `_safe_summary` (optional, error
turns into an unavailable section), then `rating_profile().get()` (required, error
propagates). If in async we put both tasks into **one** `TaskGroup` and the required
`rating` raises — TaskGroup will cancel the not-yet-finished optional `reviews` task via
`CancelledError`. This **changes sync semantics**: in sync, `reviews` could already have
completed successfully by the time of the `rating` error. So the correct async pattern for
mixed branches is **sequential within branch, parallel across required-only**:

```python
async def review_summary(self, ...) -> ReviewSummary:
    # reviews — optional, always wrapped in _safe_summary_async
    reviews_result, reviews_unavailable = await _safe_summary_async(
        "reviews", lambda: self.review(...).list(...).materialize()
    )
    # rating — required, propagates AvitoError
    rating = await self.rating_profile().get()
    return ReviewSummary(reviews=reviews_result, rating=rating,
                         unavailable_sections=reviews_unavailable)
```

`asyncio.TaskGroup` in `review_summary` is allowed **only** if both branches go through
`_safe_summary_async` (i.e. both are optional) — that changes the public contract and is **forbidden**
in M-final. Allowed parallelism: if both were required and independent. The current
optional+required mix excludes TaskGroup parallelism for `review_summary`.
The M-final DoD checks: `review_summary` async does not use TaskGroup, runs
sequentially reviews-then-rating. The same rule applies to any future
aggregator with a mixed required/optional set of branches.

**Cancellation-safe pattern for aggregators (mandatory).** Used:
`asyncio.TaskGroup` (Python 3.11+, our floor is 3.12+) with per-section try/except
converting `AvitoError → SummaryUnavailableSection` (like sync `_safe_summary`,
`avito/client.py:91-98`). `asyncio.gather(..., return_exceptions=True)` is forbidden,
because it returns `CancelledError` as an ordinary result — that swallows
cancellation semantics. Template:

```python
async def _safe_summary_async[T](
    section: str, factory: Callable[[], Awaitable[T]],
) -> tuple[T | None, list[SummaryUnavailableSection]]:
    try:
        return await factory(), []
    except asyncio.CancelledError:
        raise               # cancellation propagates, never swallowed
    except AvitoError as error:
        return None, [_summary_unavailable_section(section, error)]

async def account_health(self, ...) -> AccountHealthSummary:
    async with asyncio.TaskGroup() as tg:
        t_balance = tg.create_task(self.account(resolved_user_id).get_balance())
        t_listings = tg.create_task(self.listing_health(...))
        t_chat = tg.create_task(_safe_summary_async("chat", lambda: ...))
        ...
    # After exiting TaskGroup all tasks are completed or cancelled atomically.
    # The dependent promotion branch starts after item_ids from listings are obtained.
```

On cancellation of the outer call, `TaskGroup` will cancel all child tasks and raise
`CancelledError` — without hanging coroutines and without partial state.

### `avito/testing/async_fake_transport.py`

```python
class AsyncFakeTransport:
    def __init__(self, *, base_url: str = "https://api.avito.ru") -> None: ...
    def add(self, method, path, *responses) -> AsyncFakeTransport: ...
    def add_json(self, method, path, payload, *, status_code=200, headers=None) -> AsyncFakeTransport: ...
    def build(self, *, retry_policy=None, user_id=None,
              authenticated: bool = False,
              auth_settings: AuthSettings | None = None) -> AsyncTransport: ...
    def as_client(self, *, user_id=None, retry_policy=None,
                  authenticated: bool = False,
                  auth_settings: AuthSettings | None = None) -> AsyncAvitoClient: ...
    def count(self, *, method=None, path=None) -> int: ...
    def last(self, *, method=None, path=None) -> RecordedRequest: ...
    requests: list[RecordedRequest]
```

Mirror of sync `FakeTransport` (`avito/testing/fake_transport.py`). Uses
`httpx.MockTransport(self._handle)` over `httpx.AsyncClient`. `RecordedRequest`,
`JsonValue`, `json_response`, `route_sequence` — reused without copies from sync.
`sleep` is `lambda _: asyncio.sleep(0)`.

**Auth mode for fake transport.** By default `authenticated=False`, so simple
domain tests, like sync `FakeTransport.as_client()`, do not require a `/token` route.
For M1 auth/retry smoke and contract tests, where it is needed to verify a real
`Authorization`, 401 invalidate, and token refresh, `authenticated=True` is used:

- `as_client(authenticated=True)` creates `AsyncAuthProvider` with `AsyncTokenClient` /
  `AsyncAlternateTokenClient` built on the same `httpx.MockTransport(self._handle)`;
- the main `AsyncTransport` receives this `auth_provider`, so the first
  authorized request triggers `/token`, and a 401 clears the cache and triggers a second
  `/token`;
- the test must explicitly register token routes via `add_json("POST", "/token", ...)`;
- `build(authenticated=True)` returns a low-level `AsyncTransport` with the same
  auth provider, so core tests do not bypass the auth pipeline.

Without this, the M1 smoke could look "authenticated" but actually go through
a transport with `auth_provider=None` and not verify refresh semantics.

**Semantics of `user_id` separately from `authenticated`.** `as_client(user_id=N,
authenticated=False)` is the correct pattern for domain tests that call
methods with `_resolve_user_id` (for example, `AsyncAccount.get_balance()`). In this
mode:

- `AsyncAvitoClient.settings.user_id == N` — `_resolve_user_id` takes it as a
  fallback and **does not** make a raw request to `/core/v1/accounts/self`;
- `AsyncTransport` is created with `auth_provider=None` — the request-level header
  `Authorization` is not set; `RequestContext.requires_auth=True` without an auth
  provider does not fail (mirror of sync `Transport._merge_headers`: `if
  context.requires_auth and self._auth_provider is not None: ...`);
- if a domain test requires both `user_id` and a check of the auth pipeline (refresh, 401
  invalidate) — combine `as_client(user_id=N, authenticated=True)`, but in this case
  any request to `/core/v1/accounts/self` is still not made, because
  `user_id` is already resolved.

This is a mirror of the sync `FakeTransport.as_client(user_id=N)` contract (without
`authenticated`). Locked in by the test
`tests/core/test_async_fake_transport.py::test_as_client_user_id_skips_self_lookup`.

**Concurrency policy.** `_handle` mutates `self.requests.append(...)` and `route.pop(0)`
for `route_sequence` scenarios. For tests with `asyncio.gather(...)` (primarily
M-final convenience methods) `_handle` takes `self._handle_lock = asyncio.Lock()` and
serializes match-and-record under it. Without this, two parallel coroutines may
simultaneously call `route.pop(0)` and get an unpredictable order of responses.

**Lock initialization in `__init__` (not lazy).** It is not allowed to lazily create `asyncio.Lock`
from `_handle`: two coroutines simultaneously passing `if self._handle_lock is
None` would create different lock objects — and serialization will break before the first `await`.
Therefore `self._handle_lock = asyncio.Lock()` is created in `__init__`; the
`AsyncFakeTransport` instance is created inside an async test/loop, and the lock is bound to the loop
on the first `await`. The cost: `AsyncFakeTransport` cannot be reused across event
loops (under `pytest-asyncio strict` this does not happen anyway — each test gets
its own loop). Documented in the docstring: "AsyncFakeTransport is safe for concurrent
access within a single event loop; create a new instance in each test; do not
reuse across loops."

## Swagger binding — change details

1. `SwaggerOperationBinding` (`avito/core/swagger.py`):
   - `variant: Literal["sync","async"] = "sync"` (frozen field).
   - The decorator `swagger_operation(..., variant: Literal["sync","async"] = "sync")`.
   - `__post_init__` validates the runtime value: any value other than `"sync"` /
     `"async"` gives `ConfigurationError`, because `Literal` does not protect a call
     from runtime code.
   - Double-decorating one function remains `ConfigurationError`.

2. `DiscoveredSwaggerBinding` (`avito/core/swagger_discovery.py`):
   - `variant: Literal["sync","async"]` is copied from `SwaggerOperationBinding`.
   - `_iter_domain_modules` looks for both modules in each package: `<pkg>.domain` and `<pkg>.async_domain`. If `async_domain` is not there — we ignore (this is a normal stage of migration).
   - `canonical_map` remains a sync-only compatibility property, so that current
     `tests/contracts/test_swagger_contracts.py` and the report builder do not get a
     silent semantic break. The implementation explicitly filters `variant == "sync"`, not
     "last binding wins".
   - new API: `canonical_map_by_variant: Mapping[Literal["sync","async"],
     Mapping[str, DiscoveredSwaggerBinding]]` and/or `binding_for(operation_key,
     variant)`. The internal unique key is `(operation_key, variant)`.

3. `swagger_linter.py`:
   - `_validate_single_binding_per_sdk_method` — unchanged: the key `binding.sdk_method` is unique even in async (because `module.class.method` differs).
   - `_validate_duplicate_bindings` — key `(operation_key, variant)` instead of `operation_key`. It is allowed to have two independent chains (sync + async) for one swagger operation.
   - `_validate_factory` becomes variant-aware with **class-gated coverage**, symmetrically to
     `_validate_complete_bindings`:
     - sync binding with a given `factory` checks the factory on `AvitoClient`.
     - async binding with a given `factory` is checked on `AsyncAvitoClient` **only if**
       the corresponding `Async<X>` already exists in the domain (the same class-gated predicate
       as in `_validate_complete_bindings`). If `Async<X>` has not yet appeared — async
       bindings for its class must not exist at all (per-class invariant), and if there are
       exceptions — it is not checked.
     - an async binding **without** a `factory` in the decorator (primarily auth bindings
       `AsyncTokenClient.request_client_credentials_token`,
       `AsyncAlternateTokenClient.*`) is skipped exactly as sync without `factory`.
       So in M1 (when there are no domain factories on `AsyncAvitoClient` yet), async auth
       bindings do not fail on `_validate_factory`, and starting from M2-PoC `tariff()` the factory must
       appear.
     Without this class-gated approach, either M1 is red (false fail on auth), or the invariant
     is weakened (green swagger-lint with a missing async factory in M3+). The M1 DoD explicitly
     includes a check that `_validate_factory(variant="async")` is green for async auth
     bindings and does not require any domain factory on `AsyncAvitoClient`.
   - `_validate_complete_bindings(operations, bindings)` → `_validate_complete_bindings(operations, bindings, variant)`. Runs twice:
     - for `variant="sync"`: expected set = all `operations` (as it is now).
     - for `variant="async"`: expected set = **per-class**, not per-domain.
       For each sync class in the domain (`<X>`) we check: does
       `Async<X>` exist (by name, `cls.__name__.startswith("Async") and
       cls.__name__.removeprefix("Async") == sync_cls.__name__`, in the same package).
       If yes — all swagger operations bound to sync methods of this class
       must have an async double in `Async<X>`. If not — the class is considered
       "not yet ported", and its operations do not enter expected for
       `variant="async"` at this stage.

       In addition to `_API_DOMAINS`, for `domain == "auth"` we take operations from
       `Авторизация.json` and `Автотека.json` if `AsyncTokenClient` /
       `AsyncAlternateTokenClient` is found respectively (the same per-class logic).

       This gives two important properties:
      1. The M1 foundation is mergeable: for API domains there is no `Async<X>` →
         domain expected = ∅; for auth, expected only includes
         `AsyncTokenClient` / `AsyncAlternateTokenClient` bindings. Linter is green.
       2. A large domain (e.g. M11 `ads` with 3 classes `Ad`/`AutoloadProfile`/
          `AutoloadReport`) can theoretically be split into sub-PRs by class;
          the M3…M12 DoD still requires closing the domain to 100%, but per-class
          granularity provides a safe exit point if the PR balloons.
          (Splitting is allowed only on an explicit decision, not as "I'll do the rest
          later" — see DoD M3…M12.)
   - `_validate_operation_spec_coverage` — unchanged (sync OperationSpec is the single source of truth for both modes; reusing the spec between sync and async methods is not forbidden). `used_specs` is `set[id(spec)]`, so the same `OperationSpec` from sync and async bindings is not duplicated and not lost.
   - `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`) resolves the spec via `unwrapped_method.__globals__`. Async methods must import the spec explicitly (`from avito.<domain>.operations import LIST_SPEC`), otherwise the resolution will return `()` and the spec will be considered unbound. A pre-flight test verifies this works; if it does not — a fallback plan for Phase 1b is laid out **before** the start of M1, not "as we go":
     1. **Primary fallback** (minimum changes): extend `_operation_specs_for_sdk_method`
        so that in addition to `__globals__` it also goes through `inspect.getsourcefile(method)` →
        `ast.parse` → looks in the source for **local** references to `OperationSpec` objects
        and resolves them via AST + module `getattr`. This covers the case where a spec
        is invoked through `self._execute(LIST_SPEC, ...)` without `from ... import LIST_SPEC`
        at module level.
     2. **Secondary fallback** (structural): introduce a class-level attribute
        `__operation_specs__: Mapping[str, OperationSpec]` on each domain class,
        listing `(method_name, spec)` pairs. `_operation_specs_for_sdk_method`
        reads the attribute first, before `__globals__`. This option requires writing
        sync classes the same way (for symmetry), but provides deterministic resolution without AST.
     The decision between primary and secondary is taken **by pre-flight result**, no later,
     with a scope estimate in hours. If neither works — this is a blocker for M1, and the plan
     is rolled back for review (a foundation without a working swagger-coverage gate
     is not fit for purpose).
   - `_validate_json_body_model_coverage` runs against sync bindings; async
     bindings are checked through the `AsyncSwaggerFakeTransport` contract suite, so as
     not to duplicate schema-lint errors on shared `OperationSpec`s.

4. `swagger_report.py` and the docs report:
   - `operations[].binding` remains a sync-only compatibility field.
   - `operations[].bindings_by_variant = {"sync": ..., "async": ...}` is added.
   - `summary.bound/unbound/duplicate/ambiguous` remain sync-only until a separate
     report API bump.
   - `summary.variants.sync` and `summary.variants.async` are added with the same
     counters. For M1 the async domain summary may be `bound=0, expected=0`,
     while the async auth summary must already cover its bindings; after M-final, total
     async expected/bound = 204.
   - `docs/site/assets/_gen_reference.py` and `reference/operations.md` show both
     SDK links when an async binding already exists, but do not break the current sync map.

5. Contract tests:
   - `tests/contracts/test_swagger_contracts.py` filters bindings by
     `variant="sync"` and preserves the current exhaustive sync behavior.
   - new `tests/contracts/test_async_swagger_contracts.py` — a Swagger-spec
     compliance test, not an architecture/introspection test: for each discovered
     binding with `variant="async"`, `AsyncSwaggerFakeTransport` builds
     `AsyncAvitoClient`, calls the async SDK method via `await`, validates
     the actual request against Swagger, and checks success/error payload mapping.
     In M1 it covers async auth bindings; in M2+ it automatically extends to
     ported domains.

6. `scripts/lint_async_parity.py` — a static linter, checks for each Async class:
   - the name `Async<X>` ↔ a sync `<X>` exists in the same package;
   - class-level metadata mirrors the sync class: `__swagger_domain__`,
     `__sdk_factory__`, `__sdk_factory_args__` must match by value
     (except for deliberately documented legacy wrappers, if such appear in a separate PR);
   - the set of public async methods (`async def` without `_` prefix) matches sync methods;
   - method enumeration is filtered by `func.__qualname__.startswith(cls.__name__ + ".")`,
     so as not to count methods inherited from `AsyncDomainObject` (`_execute`, `_resolve_user_id`)
     or `object`;
   - for each pair `(sync_method, async_method)`:
     - `inspect.signature(sync).parameters` (without `self`) == `inspect.signature(async).parameters`;
     - the return annotation either matches, or `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`,
       or `BinaryResponse`/wrapper-model matches directly; `Paginator[T] ↔
       AsyncPaginator[T]` is allowed only if a public sync method that actually returns
       `Paginator[T]` appears in the future;
     - both are decorated with `@swagger_operation` for the same `(spec, method, path, operation_id)`, differing only by `variant`.
   - for each async class-level `__sdk_factory__` it checks that such a factory
     exists on `AsyncAvitoClient`, has a signature compatible with the sync factory
     on `AvitoClient`, and returns the corresponding `Async<X>`.
     If metadata is missing, it is a blocker even if decorators are present:
     swagger discovery, the reference builder, and IDE-discovery must see the async class
     the same way as the sync class.
   This linter is invoked from `make quality`; pytest does not contain parity/introspection
   tests, because the STYLEGUIDE only allows functional tests and
   Swagger-spec compliance tests in pytest.

   The linter additionally exports `iter_async_classes() -> Iterator[type[AsyncDomainObject]]`
   as a public module API (without `_` prefix). This is the **single source of truth**
   for the list of `Async<X>` classes: the M-final verification script takes it from there instead of
   hardcoding names, so adding a new class does not require editing the M-final check.
   Contract of `iter_async_classes()`:
   - returns all `Async<X>` classes from all `avito/<domain>/async_domain.py`
     (excluding `EXCLUDED_PACKAGES = {"auth", "core", "testing"}` — auth bindings
     do not get a reference);
   - order: stable sort by `(package_name, class_name)`;
   - does not depend on prior state (can be called before and after any M stage).

## Stages

### Pre-flight for PR M1

Before opening PR M1 (all of this is done locally and validated before commit):

- [x] `grep -rn "\._access_token\|\._refresh_token\|\._autoteka_access_token" tests/` —
      record all private probes; ensure that the compat-shim in `AuthProvider`
      covers each. Currently found case: `tests/core/test_authentication.py:122-127`.
- [x] `grep -rn "\bPaginator\b" avito/` — record all 4 usage sites
      (`avito/ads/domain.py:266,1183`, `avito/accounts/domain.py:170,383`).
      All current usage sites end with `.as_list(...)`; there is no direct public
      return of `Paginator`. `AsyncPaginator.as_list()` is needed by M4
      (`accounts`), but a root-level export of `AsyncPaginator` is not needed.
- [x] `grep -rn "len(.*Paginated\|\\b[a-z_]*list\\[[0-9-]" avito/ tests/` — find all
      consumers of the list API on `PaginatedList[T]` (indexing, `len`, `bool`, slice).
      `AsyncPaginatedList` deliberately does NOT replicate the list API: each such case must
      either be safe (sync-only), or explicitly replaced with `await materialize()` /
      `loaded_count` in the async double. The list is recorded in the PoC commit message.
- [x] `grep -rn "^async def test_" tests/` — ensure that existing tests have no
      async functions without `@pytest.mark.asyncio`. After enabling
      `asyncio_mode = "strict"`, any such test will start being ignored (warning,
      not failure). If found — add the marker in a pre-flight commit, separately from M1.
- [x] Confirm the minimum supported Python version in `pyproject.toml`. The SDK already
      uses PEP 695 (`type PageFetcher[ItemT] = ...` in `avito/core/pagination.py:10`),
      which means Python **3.12+** is required. All async contracts (`type AsyncPageFetcher`,
      `async def execute[ResponseT]`) keep this same floor; raising it is unnecessary, but
      explicitly recorded in the M1 PR description.
- [x] Baseline run on a clean `main` — save **nodeids of existing tests** and
      their pass/fail statuses:
      `poetry run pytest --collect-only -q tests/core tests/auth tests/domains tests/contracts | grep '::' > /tmp/baseline_nodeids.txt`
      and then `poetry run pytest -q --tb=no $(cat /tmp/baseline_nodeids.txt) >
      /tmp/baseline_main.txt`. Used in the M1 DoD; new async tests after M1
      do not enter the baseline comparison.
- [x] Verify that `_operation_specs_for_sdk_method` (`avito/core/swagger_linter.py:578`)
      works with `async_domain.py`: a test stub with `async def m(self): return self._execute(SOME_SPEC)`
      and `from ...operations import SOME_SPEC` — the function must find `SOME_SPEC` via
      `unwrapped_method.__globals__`. If it does not work — extend the function (Phase 1b),
      otherwise leave unchanged.
- [x] Read `docs/site/assets/_gen_reference.py` in full and record
      existing filter points: `PACKAGE_ROOT.glob("*/domain.py")`,
      `EXCLUDED_PACKAGES`, `public_domain_classes()` (filter by `DomainObject` inheritance
      and `value.__module__.startswith(f"avito.{package}.")`), `public_domain_methods()`
      (filter by `value.__qualname__.startswith(f"{domain_class.__name__}.")`),
      and `write_domain_pages()` (currently writes one `::: avito.<package>` and does
      not use class helpers). The builder extension in M1 must reuse
      this logic for `async_domain.py` + `AsyncDomainObject` descendants, and
      `write_domain_pages()` must move to explicit class directives sync → async
      and not rely solely on `avito.<package>.__all__`. Without this, the reference will be
      asymmetric.
- [x] Read `scripts/lint_architecture.py` and `scripts/lint_docstrings.py`:
      current checks look only at `domain.py` and `ast.FunctionDef`. M1 must
      extend them to `async_domain.py` and `ast.AsyncFunctionDef`.
- [x] Read `avito/core/deprecation.py`: the current `deprecated_method` returns a
      sync wrapper. M1 must add an async-aware wrapper before porting the
      deprecated methods of `cpa`/`ads`.
- [x] `grep -rn "@deprecated_method\|deprecated_method(" avito/cpa/ avito/ads/` —
      record the **exact** number of sync deprecated methods that require async doubles.
      At the time of writing the plan: 3 in `avito/cpa/domain.py:491,541,585` and 4 in
      `avito/ads/domain.py:1416,1457,1523,1558` — totaling 7. The async-aware wrapper in
      `deprecation.py` is a mandatory artifact of M1, without which M6 (`cpa`) and M11 (`ads`)
      cannot close. If the actual number diverges from the recorded one — update
      the sequencing table and DoD M6/M11 before the start of M1.
- [x] Read `avito/core/swagger_linter.py::_validate_factory` in full and record
      current behavior: which fields of the binding it gates on (`factory`, `factory_args`),
      how it resolves the factory on `AvitoClient`, what it considers an error. M1 must extend
      it with class-gated coverage (see Swagger section). Without full understanding of the current
      logic, the extension risks weakening the invariant for sync bindings.
- [x] **Run pre-flight locally, record results in a tracked artifact**:
      a new file `docs/dev/preflight-async-m1.md` is created and committed in
      a separate pre-flight commit (before opening M1) capturing **all** of the
      following in machine-readable form:
      (1) the actual list of `_access_token`/`_refresh_token`/`_autoteka_access_token`
      probes in `tests/` (paths + line numbers);
      (2) the actual `Paginator` usage sites in `avito/` (4 expected, paths
      + line numbers);
      (3) the actual `len(...)` / `[idx]` / `bool(...)` / slice usages on
      `PaginatedList[T]` across `avito/` and `tests/`;
      (4) the actual count and locations of `@deprecated_method` in
      `avito/cpa/` and `avito/ads/` (7 expected, with line numbers);
      (5) the existing `^async def test_` lines (expected: empty);
      (6) the result (pass/fail) of the `_operation_specs_for_sdk_method`
      smoke test on an async stub, and the chosen fallback (none / primary /
      secondary) with a one-paragraph justification;
      (7) the concrete diff baseline: `/tmp/baseline_nodeids.txt` and
      `/tmp/baseline_main.txt` are produced and their sha256 sums are
      recorded in the artifact (the actual files are not committed —
      only the hashes, for later reproducibility);
      (8) the Python interpreter version, Poetry lockfile hash, and `httpx`
      version in use at pre-flight time.
      Without `docs/dev/preflight-async-m1.md` in the M1 PR diff, the PR is
      not opened. The artifact is referenced from the M1 PR description and
      is not deleted by M-final (it remains permanent provenance for the
      async migration).

### M1 — Foundation (1 PR)

DoD:
- [ ] `make check` green: test, typecheck (mypy strict), lint (ruff),
      swagger-lint --strict, architecture-lint, async-parity-lint,
      docstring-lint, build.
- [ ] `make docs-strict` green: M1 edits `STYLEGUIDE.md`,
      `swagger-binding-subsystem.md` and `domain-architecture-v2.md` + extends
      `_gen_reference.py` (see the table "Existing, modified in M1"). Without editing
      `STYLEGUIDE.md`, the plan formally contradicts the normative sync-only text.
      Without a green docs-strict, we cannot guarantee that the reference builder in M2-PoC
      will see the first `Async<X>`. If at M1 there is not a single `Async<X>` yet — the builder
      is verified to be neutral (sync reference is generated identically to baseline).
- [ ] Test coverage of the foundation is no lower than the sync analogs (sample check via `coverage report`).
- [ ] Smoke test: `AsyncAvitoClient` via `AsyncFakeTransport.as_client(authenticated=True)`
      (without respx) makes one authorized request; `/token` is actually called
      via `AsyncTokenClient`; after 401 the cache is cleared and `/token` is called
      again; retry on 429 fires; `Authorization` and `Idempotency-Key`
      are propagated; `aclose()` correctly closes `httpx.AsyncClient` and
      `AsyncAuthProvider`.
- [ ] Ownership test: `AsyncTransport.aclose()` closes the passed
      `httpx.AsyncClient`, because that is the chosen mirror policy of the current sync
      `Transport.close()`. The test separately covers idempotent double-close.
- [ ] The async auth public surface mirrors sync: `AsyncAvitoClient.auth()` returns
      `AsyncAuthProvider`, and `token_flow()` / `alternate_token_flow()` return
      async token clients with `variant="async"` bindings.
- [ ] Async client diagnostic/closed contract mirrors sync: `debug_info()` returns
      `TransportDebugInfo` after `__aenter__`; `auth()` and `debug_info()` fail before
      initialization with an understandable `RuntimeError`; after `aclose()` they and future factory
      methods fail with `ClientClosedError`; repeated `aclose()` is a no-op.
- [ ] The documentation `swagger-binding-subsystem.md` reflects variant and class-gated coverage.
- [ ] `AsyncSwaggerFakeTransport` is added and exported from `avito.testing`; the async
      contract suite is green for discovered async bindings (`auth` in M1, domains
      appear later).
- [ ] Public sync surface is unchanged — formal: pass/fail statuses
      **only of baseline nodeids from `/tmp/baseline_nodeids.txt`** are identical to
      the baseline test from `main` (see pre-flight). New async tests do not participate
      in the comparison. Any divergence on old nodeids = blocker.
- [ ] Phase 1a (`_merge_headers` refactor) is split out as a separate commit inside the PR — for bisect-friendly history.
- [ ] **`pyproject.toml` contains `asyncio_default_fixture_loop_scope = "function"`** in `[tool.pytest.ini_options]` next to `asyncio_mode = "strict"`. At the time of M1 `filterwarnings = error` is not configured in the project, so the absence of this option will not break pytest immediately, but `pytest-asyncio` 0.23+ will start emitting `PytestDeprecationWarning` on every async test — this accumulates in output and blocks future enabling of `filterwarnings = error`. We enable it preventively.
- [ ] **`_validate_factory(variant="async")` is green for async auth bindings without a single domain factory on `AsyncAvitoClient`**. The class-gated predicate: factory-check is not run on an async binding whose class does not yet have `Async<X>` in the domain, and skips bindings without `factory` in the decorator. Locked in by the unit test `tests/core/test_swagger_linter.py::test_validate_factory_async_skips_unported_classes`.
- [ ] **The resolver `_operation_specs_for_sdk_method` for `async_domain.py`**: the pre-flight smoke test is green (resolution via `__globals__` works with `from ...operations import SOME_SPEC`). If pre-flight is red — in this same M1 PR, the primary fallback (AST resolution from the source file) **or** the secondary fallback (class-level `__operation_specs__`) is applied. Any fallback is locked in `swagger_linter.py` with the test `tests/core/test_swagger_linter.py::test_resolve_specs_from_async_domain`.
- [ ] **`AsyncOperationExecutor` retry resolution mirrors sync**: the test `tests/core/test_async_executor.py::test_executor_retry_resolution_matches_sync` is parameterized with the `(retry, spec.retry)` triple and compares the result with sync `OperationExecutor`.
- [ ] **`AsyncAuthProvider.invalidate_token` is sync and idempotent**: the test `tests/auth/test_async_provider.py::test_invalidate_token_is_sync_and_idempotent` is green.
- [ ] **`httpx.AsyncClient` is created with default limits** (without override). A test forbidding SDK-side tuning of limits is not needed in M1; the M-final DoD has a fan-out ≤ 6 check.
- [ ] **`AsyncTransport.request()` calls `await self._rate_limiter.acquire()` before each httpx call and `observe_response()` after a successful response** — exact mirror of sync `Transport.request()` (lines 148, 183). Locked in by two tests: `tests/core/test_async_transport.py::test_request_acquires_rate_limiter_before_httpx_call` (5 parallel coroutines on one transport — tokens are spent one at a time, not in a batch) and `::test_request_calls_observe_response_after_success` (post-condition).
- [ ] **`_request_binary_async` module-level helper in `avito/core/operations.py`** is an async mirror of sync `_request_binary`. Accepts `AsyncOperationTransport` Protocol, returns `BinaryResponse` with the same fields. Closed-test: `tests/core/test_async_executor.py::test_binary_branch_uses_request_binary_async_helper`.
- [ ] **End-to-end binary-branch coverage in M1 (synthetic, before any domain port)**:
      to prove the full async pipeline works for `response_kind == "binary"`
      **before** M12 `orders` lights it up via `OrderLabel.download()`, M1 adds
      one synthetic binding inside the test suite (not in production code) —
      a `_TestBinaryDomain` with an `async def download(...)` method decorated
      with `@swagger_operation(..., variant="async")` over a fake
      `OperationSpec` with `response_kind == "binary"`. Test
      `tests/core/test_async_executor.py::test_async_executor_full_binary_pipeline`
      drives the spec end-to-end through `AsyncSwaggerFakeTransport` →
      `AsyncOperationExecutor` → `_request_binary_async` →
      `BinaryResponse`, and asserts that `content`, `content_type`, `filename`,
      `status_code`, `headers` match the response body byte-for-byte. Without
      this, M1 ships an executor whose binary branch is verified only at the
      unit level (`test_binary_branch_uses_request_binary_async_helper`) —
      regressions across executor + transport + fake-transport interaction
      would only be caught in M12, weeks later. The synthetic binding lives
      in `tests/_fixtures/synthetic_binary_domain.py` and is excluded from
      `swagger_discovery._iter_domain_modules` (its module path does not
      start with `avito.`).
- [ ] **`AsyncRateLimiter` lives in `avito/core/_async_rate_limit.py`** (not inside `async_transport.py`). Symmetric to sync `avito/core/rate_limit.py`.
- [ ] **`scripts/lint_async_parity.py` exports `iter_async_classes()` as a public API** — used by the M-final verification script and any external tool that needs the canonical list of `Async<X>` classes.
- [ ] CHANGELOG `## [Unreleased]` in the root `CHANGELOG.md` is updated with:
      `- Фундамент Async API: AsyncTransport,
      AsyncAuthProvider, AsyncOperationExecutor, AsyncPaginatedList,
      AsyncAvitoClient (без factory-методов доменов); RateLimitState вынесен в shared`.

### M2-PoC — Proof-of-concept of the template (a separate PR, before reworking domains)

**The goal of this step is to validate the template on a minimal domain and at the same time close
`tariffs` completely.** This is not a "partial domain PR": at merge time `tariffs` must
have an async surface, tests, swagger coverage, and reference 1:1. The PoC may return
feedback like "the `AsyncPaginator` contract needs to be extended", "discovery does not see
the spec", "mypy strict complains about return covariance" — and that is a normal expected
outcome. All contract changes are made in **the same PR**, and if the changes require
rework of the M1 foundation, the PoC is rolled back, the foundation is reworked in a separate
PR, after which the PoC is reopened. M3 does not start until M2-PoC is green and
`tariffs` is closed at 100%.

The PoC takes `tariffs` (1 sync operation with binding) — minimal surface without
pagination, without autoteka-flow, without write methods. That is enough to poke
all foundation layers in one end-to-end scenario.

DoD M2-PoC:
- [ ] `avito/tariffs/async_domain.py` is created, `AsyncTariff` mirrors `Tariff`
      exactly on 1 public method.
- [ ] `AsyncTariff` contains class-level metadata mirroring `Tariff`:
      `__swagger_domain__ = "tariffs"`, `__sdk_factory__ = "tariff"`,
      `__sdk_factory_args__ = {"tariff_id": "path.tariff_id"}`.
- [ ] `avito/tariffs/__init__.py` exports `AsyncTariff` next to `Tariff`.
- [ ] `AsyncAvitoClient.tariff()` factory method returns `AsyncTariff`.
- [ ] `tests/domains/tariffs/test_tariffs_async.py` contains an async double of the sync
      golden-path scenario and additional async-risk scenarios: 401, 429,
      transport error. All tests are green.
- [ ] `make check` is green, including `swagger-lint --strict` (for `tariffs` async-coverage
      1:1 is now required).
- [ ] `scripts/lint_async_parity.py` is green.
- [ ] `tests/contracts/test_async_swagger_contracts.py` is green for async auth +
      `tariffs`.
- [ ] The generated reference docs `docs/site/reference/domains/tariffs.md`
      contain an async section.
- [ ] **`_gen_reference.py` is validated on a real domain**: after the builder extension in M1, on M2-PoC it sees `AsyncTariff` for the first time and must generate a reference page with both classes (`Tariff` + `AsyncTariff`). `make docs-strict` is green, in the generated `site/reference/domains/tariffs/` or `site/reference/domains/tariffs.html` both sections are present. If the builder requires polish — it is included in the same PR (this is what the PoC is for). Specifically in `_gen_reference.py`: `public_domain_packages()` additionally returns the package if `*/async_domain.py` exists; `public_domain_classes()` imports `avito.<package>.domain` and `avito.<package>.async_domain` directly, not just `avito.<package>.__all__`; `Async<X>` is filtered through `cls.__name__.startswith("Async")` + `issubclass(AsyncDomainObject)`; `write_domain_pages()` writes explicit mkdocstrings directives for each class in the order `Tariff` → `AsyncTariff`, not one shared `::: avito.tariffs`; `EXCLUDED_PACKAGES` remains the same; for `auth` (excluded) async classes do not get a reference.
- [ ] **Lessons learned are recorded** in `docs/site/explanations/async-domain-template.md`
      (a new file): the `async_domain.py` file template, a domain port checklist,
      pitfalls discovered. This document becomes normative for M3+.
- [ ] If in the course of the PoC contract changes are needed (`AsyncPaginator`/`AsyncFakeTransport`/
      `swagger_linter`/`AsyncAuthProvider`), they are **made in the same PR** or split out
      into a separate M1.5-PR, but **before** the start of M3.
- [ ] The root `CHANGELOG.md` (`## [Unreleased]`) is updated with:
      `- Async-поддержка домена tariffs: AsyncTariff (PoC шаблона)`.

### M3…M12 + M-final — Closing domains (one PR per domain)

**Sequencing constraints** — what blocks what (after a green M2-PoC):

| Stage | Must come after | Reason |
|---|---|---|
| M3 `ratings` | M2-PoC | basic template without specifics; serves as the second sanity check of the foundation |
| M4 `accounts` | M2-PoC, M3 | first domain with `AsyncPaginatedList` — validates pagination before M11 |
| M5 `realty` | M2-PoC | no pagination; parallel with M3/M6/M7/M8/M9 |
| M6 `cpa` | M2-PoC + async-aware `deprecated_method` already merged in M1 | 3 deprecated methods in `cpa/domain.py` |
| M7 `messenger` | M2-PoC | no pagination; parallel with M3/M5/M6/M8/M9 |
| M8 `jobs` | M2-PoC | webhook methods (REST), no pagination; parallel |
| M9 `promotion` | M2-PoC | no pagination; parallel |
| M10 `autoteka` | M2-PoC | autoteka token flow — independent part of auth |
| M11 `ads` | **M4 (`accounts`)** + async-aware `deprecated_method` from M1 | the complex `Ad.list` first-page reuse is tested after the simple `AsyncPaginatedList`; 4 deprecated methods in `ads/domain.py` |
| M12 `orders` | M2-PoC | independent; idempotency is critical, but is not blocked by another domain |
| M-final | **all M3…M12 + M10** | `AsyncAvitoClient.account_health` aggregates all domains; `_safe_summary_async` is symmetric to sync `_safe_summary`; M10 is mandatory for the autoteka concurrent first-touch test (see the M3…M12 table below) |

**Parallelism**: after M2-PoC you can open M3, M5, M6, M7, M8, M9, M10, M12 in
any order (including in parallel). M4 is a mandatory gate before M11. M-final is
last. The cumulative parity invariant (see DoD M3…M12) guarantees that the merge
order of parallel PRs does not matter: each merge leaves the linter green
for all already ported domains.

The order in the table below (increasing complexity; the simplest went into the PoC):

| # | Domain | Sync methods with binding | Specifics |
|---|---|---|---|
| M3 | `ratings` | 4 | no pagination |
| M4 | `accounts` | 8 | first `AsyncPaginatedList` (`get_operations_history`, `list_items_by_employee`); async `_resolve_account_user_id` |
| M5 | `realty` | 7 | no pagination |
| M6 | `cpa` | 14 | no pagination |
| M7 | `messenger` | 18 | no pagination |
| M8 | `jobs` | 25 | webhook methods (REST) |
| M9 | `promotion` | 24 | no pagination |
| M10 | `autoteka` | 26 | uses autoteka token flow → end-to-end check of `AsyncAuthProvider.get_autoteka_access_token` + `_autoteka_refresh_lock` under load: **20 concurrent coroutines** in `asyncio.gather(...)` start the first `get_autoteka_access_token()`; the counter of the mocked `/token` route after `await gather(...)` must be **exactly 1**. Locked in by the test `tests/auth/test_async_provider.py::test_autoteka_concurrent_first_touch_single_token_request`. |
| M11 | `ads` | 28 | second and third `AsyncPaginatedList` (`Ad.list`, `AutoloadReport.list`); complex offset/limit first-page reuse in `Ad.list` (`avito/ads/domain.py:266`) |
| M12 | `orders` | 45 | the largest; idempotency is critical |
| M-final | — | — | convenience methods of `AsyncAvitoClient`: `account_health`, `listing_health`, and `promotion_summary` (when `item_ids` is given) use `asyncio.TaskGroup` only where all branches are **required-only** and actually independent; `review_summary` remains sequential reviews-then-rating (mixed required+optional, see the "Important TaskGroup subtlety" block); `business_summary` delegates to `account_health`; `chat_summary`/`order_summary` remain sequential leaves; `capabilities` remains CPU-only without network probe requests. `asyncio.gather(return_exceptions=True)` is forbidden. Aggregator fan-out ≤ 6 in-flight tasks. Final hardening; `docs/site/how-to/async.md`; CHANGELOG `## [Unreleased]` → `## [2.1.0]` (a roundup of accumulated entries from M1…M12 + a record of convenience methods). |

Contents of each M3…M12:

1. `avito/<domain>/async_domain.py` with `Async<X>(AsyncDomainObject)` for **every**
   sync `<X>` in the domain. Imports the same `OperationSpec` from
   `avito/<domain>/operations.py` **explicitly by name**
   (`from avito.<domain>.operations import LIST_SPEC, GET_SPEC, ...`) — otherwise
   `_operation_specs_for_sdk_method` will not be able to resolve the spec via `__globals__`
   and swagger-lint will emit `SWAGGER_OPERATION_SPEC_MISSING`.
2. **Every** `Async<X>` contains class-level metadata mirroring the sync class:
   `__swagger_domain__`, `__sdk_factory__`, `__sdk_factory_args__`. The metadata is not
   considered "duplication" of the Swagger contract: this is SDK discovery/factory metadata
   without which the async class may not enter discovery/reference or may receive
   a green decorator with a missing factory.
3. **Every** public method is decorated with `@swagger_operation(..., variant="async")`
   with the same arguments `(method, path, spec, operation_id, factory, factory_args,
   method_args, deprecated, legacy)` as sync.
4. `avito/<domain>/__init__.py` exports **all** `Async<X>` of the domain next to
   sync classes, so that mkdocstrings, the IDE, and the generated reference see the public
   async surface.
5. Registration of **all** `Async<X>` of the domain in `AsyncAvitoClient` (factory methods by
   names identical to sync).
6. `tests/domains/<domain>/test_<domain>_async.py` is a mirror of
   `tests/domains/<domain>/test_<domain>.py` via `AsyncFakeTransport`. Tests are
   marked with `@pytest.mark.asyncio`. **Every** sync test has an async double
   with the same scenario.
7. If the domain has pagination — the corresponding methods return
   `AsyncPaginatedList[T]` (mirroring sync `PaginatedList[T]`). M4 `accounts` is
   the first domain with `AsyncPaginatedList`; M11 `ads` validates the complex first-page
   reuse in `Ad.list`.
8. The generated reference `docs/site/reference/domains/<domain>.md` is augmented with
   an async section (or a second column).
9. If the domain has write methods with `dry_run` — the async double implements the same
   contract: when `dry_run=True` the transport is **not called** (the test verifies
   `count(method=..., path=...) == 0`).
10. If the domain has idempotency-key behavior — async tests explicitly verify
   propagation of the `Idempotency-Key` header.

### Definition of done for each M3…M12 — close the domain at 100%, no work left over

"100%" is defined verifiably. All items below are **mandatory**, not "nice to have":

- [ ] **Method coverage 1:1**: for each public sync method of the domain there is an
      async double; `scripts/lint_async_parity.py` is green for the domain.
      Local check: `python -c "from avito.<domain>.domain import *; from
      avito.<domain>.async_domain import *"` + `scripts/lint_async_parity.py`
      without allowlist/skip for the current domain.
- [ ] **Test coverage scenario-by-scenario**: every scenario from
      `tests/domains/<domain>/test_<domain>.py` has an async double with the same
      business meaning. Additional async tests are allowed and required where
      they cover async-specific risks (401 refresh via async auth,
      cancellation, concurrent pagination/fake transport, async rate limiter).
      The test counts do not have to be equal; the async count must be **no less**
      than sync count, and the PR description contains a short mapping table
      `sync test -> async test`. Covered: golden path, 401,
      403, 422, 429, transport error/timeout, pagination (if any), idempotency
      (for write), `dry_run` (if there is one in sync).
- [ ] **Swagger-lint coverage 1:1 for the domain**: `swagger-lint --strict` after the stage
      requires an async binding for **every** swagger operation of this domain; class-gated
      coverage gating is enabled, and the domain is no longer "empty by async". No
      exceptions/skips for individual methods.
- [ ] **Async Swagger contract coverage**: `tests/contracts/test_async_swagger_contracts.py`
      calls **every** async binding of the domain via `AsyncSwaggerFakeTransport` and
      validates the request/response/error contract. This is a mandatory Swagger-spec
      compliance test, so it is allowed by the STYLEGUIDE.
- [ ] **Documentation**: the generated `docs/site/reference/domains/<domain>.md` contains an async section for
      **all** ported classes; `make docs-strict` is green; links and code
      examples compile.
- [ ] **No TODOs/FIXMEs/`pytest.skip`/`xfail` in added files**:
      `git diff main..HEAD -- avito/<domain>/ tests/domains/<domain>/ | grep -E
      "TODO|FIXME|@pytest.mark.skip|xfail"` is empty. Any deferral of work = blocker.
- [ ] **Error messages in Russian only** (STYLEGUIDE.md, "Errors" section):
      all new `raise <AvitoError>("...")` in `async_domain.py` are written in Russian,
      without English inclusions. Code review checklist; `make lint` does not catch this directly,
      but mixed languages are a formal blocker. If the sync analog already
      uses English (legacy) — leave it as is in sync, and in async
      write in Russian and open a separate issue for sync migration.
- [ ] **`make check` is green locally and in CI**.
- [ ] **AsyncAvitoClient is fully configured for the domain**: factory methods return
      ready objects, lifecycle (`aclose`/`__aexit__`) correctly closes all
      domain resources.
- [ ] **Sync regression = 0**: the list of pass/fail of sync tests is identical to the previous
      stage (sanity check via comparing `pytest -q --tb=no` before and after).
- [ ] **Cumulative parity invariant**: after the merge `scripts/lint_async_parity.py`
      and `tests/contracts/test_async_swagger_contracts.py` are green for **all** already
      ported domains (including the current one). The stage cannot weaken the invariant
      for previous domains.
- [ ] **No work "later"**: reopening a PR with the phrase "I'll finish it in the next PR"
      is forbidden. If scope does not close — the PR is split or expanded, but
      no partial domain is left in main.
- [ ] **Per-class split escape hatch (M11/M12 only, by explicit decision)**: for
      `M11 ads` (3 classes: `Ad`/`AutoloadProfile`/`AutoloadReport`, 28 ops) and
      `M12 orders` (45 ops, the largest domain) the «no partial domain» rule is
      **softened by exception**: it is allowed to split the domain into a sequence of
      per-class PRs (`M11a Ad`, `M11b AutoloadProfile`, `M11c AutoloadReport`;
      `M12a–M12N` partitioned by `OperationSpec` group), provided that **each
      sub-PR is itself class-complete**: every method of the included class has
      an async double, swagger-lint per-class is 1:1, async-parity-lint is green
      for the included class. Class-gated coverage in `swagger_linter.py`
      already supports this (see Swagger section). Constraints:
      (1) the split must be declared in the M11/M12 design comment **before** the
      first sub-PR is opened, with the full list of sub-PRs and their order;
      (2) the cumulative parity invariant still applies — each sub-PR leaves
      `make swagger-lint --strict` green for all already ported classes;
      (3) the `M11`/`M12` row in the sequencing table is replaced with the
      sub-PR list, and `M-final` waits for the **last** sub-PR.
      For all other domains (M3…M10) the «no partial domain» rule is hard:
      one PR closes one whole domain at 100%. The exception exists strictly to
      keep code-review tractable on `ads` and `orders`; it must not be invoked
      retroactively to «rescue» a stuck PR on other domains.
- [ ] **CHANGELOG is updated via per-PR fragments**: each M3…M12 PR adds **one
      file** under `CHANGELOG.d/<PR-номер>-async-<domain>.md` with the content:
      ```markdown
      ### Added
      - Async-поддержка домена <domain>: Async<X>, Async<Y> (#<PR-номер>)
      ```
      The root `CHANGELOG.md` is **not** edited per-PR. M-final aggregates all
      `CHANGELOG.d/*.md` fragments into one `## [2.1.0] - YYYY-MM-DD` section,
      then deletes the fragments. Rationale: 12 parallel PRs editing a single
      `## [Unreleased]` block are guaranteed to merge-conflict on every rebase;
      separate fragment files have no shared lines and merge cleanly.
      Implementation:
      (1) M1 PR creates `CHANGELOG.d/.gitkeep` and `CHANGELOG.d/README.md`
      describing the format;
      (2) `make check` (via a new `scripts/check_changelog_fragments.py`)
      verifies each fragment matches the schema (one `### Added`/`### Changed`/
      `### Fixed` block, no `## [...]` headings, valid markdown);
      (3) M-final concatenates fragments in PR-number order, prepends
      `## [2.1.0] - YYYY-MM-DD`, appends to `CHANGELOG.md`, and `git rm
      CHANGELOG.d/*.md` (keeping `.gitkeep` and `README.md`).
      M1 itself does **not** use a fragment — its CHANGELOG line («Фундамент
      Async API») is added directly to `## [Unreleased]` of the root file
      (single PR, no conflict risk), and M-final moves it into `## [2.1.0]`
      together with the fragment aggregate.

### Definition of done for M-final — release 2.1.0

"Final hardening" is defined verifiably:

- [ ] **Convenience methods are implemented per the classification table** (aggregator / alias / leaf / CPU-only). Code review verifies: `asyncio.TaskGroup` is placed only in branches with actually independent network calls (`account_health`, `listing_health`, `review_summary`, `promotion_summary` when `item_ids` is given); in `business_summary` — `return await self.account_health(...)` without `TaskGroup`; `chat_summary` and `order_summary` are sequential; `capabilities` does not make network probe requests and does not use `TaskGroup`. Any violation = blocker.
- [ ] **Fan-out ≤ 6 is enforced by a real test, not just code review**: `tests/test_async_client_aggregators.py::test_account_health_fanout_does_not_exceed_six`
      drives `AsyncAvitoClient.account_health(...)` through `AsyncFakeTransport`
      with an instrumented `_handle` that records the **maximum number of
      simultaneously in-flight requests** observed during the call (counter
      incremented at the start of `_handle`, decremented after the response is
      returned, peak captured under `_handle_lock`). The assertion is
      `assert peak <= 6`. The same instrumentation is applied to
      `listing_health`, `review_summary` (peak ≤ 1 — sequential),
      `promotion_summary(item_ids=[...])` (peak ≤ 2), and
      `business_summary` (delegates to `account_health`, peak ≤ 6). A single
      shared `FanoutPeakRecorder` helper in `avito/testing/async_fake_transport.py`
      provides the counter; aggregator tests opt in via
      `AsyncFakeTransport(fanout_recorder=recorder)`. This locks the contract
      against future drift: if a domain in the future adds a new branch and
      pushes peak past 6, the test fails before the PR is merged.
- [ ] **`_safe_summary_async` lives in the same module as sync `_safe_summary`** — `avito/client.py` (extraction into a shared `avito/summary/_helpers.py` is allowed, but requires simultaneous moving of sync `_safe_summary`; partial extraction is forbidden, so as not to split symmetric helpers across different files). The import in `avito/async_client.py` is explicit (`from avito.client import _safe_summary, _safe_summary_async`). Circularity does not arise: `avito/client.py` does not import `avito/async_client.py`, so the import graph remains acyclic; verified by the command `python -c "import avito.async_client"` without errors and `python -c "import avito.client"` without errors.
- [ ] **The package version is bumped to 2.1.0**: `poetry version 2.1.0`, the change in `pyproject.toml` is recorded in the M-final PR. CHANGELOG `## [Unreleased]` → `## [2.1.0] - YYYY-MM-DD`, the accumulated lines M1…M12 + the entry about convenience methods and `AsyncAvitoClient` aggregators are aggregated into one section. `git tag v2.1.0` is set after merging M-final.
- [ ] **`AsyncSwaggerFakeTransport` contract suite is complete**: `tests/contracts/test_async_swagger_contracts.py`
      calls all async bindings (204 Swagger operations, including auth bindings)
      and checks success/error/request-body schema, like the sync contract suite.
- [ ] **`docs/site/how-to/async.md` is written**: lifecycle contract (`async with` is mandatory), an example with `AsyncFakeTransport`, a migration guide "how to rewrite a sync call to async", limitations (`AsyncPaginatedList` not list-API, full-buffer download, no streaming). Links from `docs/site/index.md` and `docs/site/how-to/index.md`. **Mandatory dedicated section "Использование под ASGI (FastAPI / aiohttp / Starlette)"** with concrete recipes:
      (1) **FastAPI lifespan pattern** — `AsyncAvitoClient` is created and
      `__aenter__`'d inside `@asynccontextmanager async def lifespan(app)`,
      stored on `app.state.avito`, and `aclose()`'d on shutdown. The client
      lives one event loop = the app's main loop; FastAPI dependencies access
      it via `Depends(lambda req: req.app.state.avito)`. Code example
      ≥ 15 lines, runnable.
      (2) **aiohttp `cleanup_ctx`** — analog with `aiohttp.web.AppKey` and
      `app.cleanup_ctx.append(avito_client_ctx)`.
      (3) **Per-worker isolation under Gunicorn/Uvicorn** — one
      `AsyncAvitoClient` per worker process (each worker has its own loop);
      forbidden to share across processes via fork-after-init.
      (4) **Forbidden pattern** — calling `AsyncAvitoClient.from_env()` at
      module import time and `__aenter__`'ing it in a request handler: this
      attaches `httpx.AsyncClient` to whichever loop touched it first, and any
      subsequent loop change (test client, background scheduler) gives
      cross-loop UB. Section explicitly shows the broken pattern with a `# ❌`
      comment and explains the failure mode.
      (5) **Background tasks (`asyncio.create_task`, `BackgroundTasks`)** —
      same loop as the request → safe to reuse the app-level client; a
      separate process-pool worker → not safe, must build its own client.
- [ ] **README/site wording is updated**: `README.md`, `mkdocs.yml`, `docs/site/index.md`,
      `docs/site/reference/client.md`, `docs/site/reference/pagination.md`,
      `docs/site/reference/testing.md` no longer call the SDK only synchronous.
- [ ] **`make check` + `make docs-strict` are green**; `scripts/lint_async_parity.py`
      and `tests/contracts/test_async_swagger_contracts.py` are green for all 11 API domains
      + auth bindings.
- [ ] **Cumulative coverage**: after M-final swagger-lint --strict requires a mutual 1:1 (sync + async) for all 204 operations. Any miss = blocker; no "we'll finish in 2.1.1".
- [ ] **CHANGELOG release-ready**: the 2.1.0 entry contains: the Async API foundation, one line per ported domain (aggregated from `## [Unreleased]` entries of M1…M12), `AsyncAvitoClient` convenience methods. 2.1.0 release notes are assembled mechanically — that is the discipline check of M3…M12.

## Verification (how to check that the plan worked)

### M1
```bash
poetry install
make test                                 # sync + new async unit tests
make typecheck                            # mypy strict — all Awaitable[T], AsyncPaginatedList[T] are correct
make lint                                 # ruff
make swagger-lint                         # sync 1:1; async auth 1:1, domain expected is empty
make async-parity-lint                    # static Async<X> ↔ X checks, not pytest
make check                                # final gate
poetry run pytest tests/core/test_async_transport.py tests/core/test_async_pagination.py \
  tests/core/test_async_executor.py tests/core/test_async_client_lifecycle.py \
  tests/auth/test_async_provider.py tests/contracts/test_async_swagger_contracts.py
```

Manual smoke (M1, in a test — not on production; via `AsyncFakeTransport`, without `respx`):
```python
import asyncio
from avito.testing.async_fake_transport import AsyncFakeTransport
from avito.core.types import RequestContext

async def main():
    async with (
        AsyncFakeTransport()
        .add_json("POST", "/token", {"access_token": "old", "expires_in": 3600})
        .add_json("POST", "/token", {"access_token": "new", "expires_in": 3600})
        .add_json("GET", "/core/v1/accounts/self", {"error": "expired"}, status_code=401)
        .add_json("GET", "/core/v1/accounts/self", {"id": 1})
        .as_client(authenticated=True)
    ) as client:
        payload = await client.transport.request_json(
            "GET", "/core/v1/accounts/self",
            context=RequestContext("smoke"),
        )
        assert payload == {"id": 1}
        assert client.transport.debug_info().requires_auth is True

asyncio.run(main())
```

`AsyncFakeTransport` is built on `httpx.MockTransport(self._handle)` over
`httpx.AsyncClient` — that is already a self-sufficient interception mechanism; `respx` on top of it
is redundant. `respx` is worth using only if a smoke needs a unique matcher
that `add_json`/`add` does not cover (none such at the current stage).

### M2-PoC (proof-of-concept)
```bash
poetry run pytest tests/domains/tariffs/                  # sync + async for tariffs
make async-parity-lint                                    # parity for tariffs as a static lint
poetry run pytest tests/contracts/test_async_swagger_contracts.py
make swagger-lint                                         # async-coverage 1:1 for tariffs
make check
# Artifact: docs/site/explanations/async-domain-template.md is created
```

### Each M3…M12 (closing the domain at 100%)
```bash
# Sync regression baseline (sanity)
poetry run pytest -q --tb=no tests/domains/<domain>/test_<domain>.py > /tmp/sync_before.txt

# After applying changes:
poetry run pytest tests/domains/<domain>/                 # sync + async
poetry run pytest -q --tb=no tests/domains/<domain>/test_<domain>.py > /tmp/sync_after.txt
diff /tmp/sync_before.txt /tmp/sync_after.txt             # must be empty

make async-parity-lint                                    # parity for all closed domains
poetry run pytest tests/contracts/test_async_swagger_contracts.py
make swagger-lint                                         # async-coverage 1:1 for this domain

# Dirty traces — empty output
git diff main..HEAD -- avito/<domain>/ tests/domains/<domain>/ \
  | grep -E "TODO|FIXME|@pytest.mark.skip|xfail" || echo "OK: no leftover work"

# Cumulative counters (async tests no fewer than sync; scenario mapping in the PR description)
sync_count=$(poetry run pytest --collect-only -q tests/domains/<domain>/test_<domain>.py | grep -c "::test_")
async_count=$(poetry run pytest --collect-only -q tests/domains/<domain>/test_<domain>_async.py | grep -c "::test_")
test "$async_count" -ge "$sync_count" && echo "OK: async $async_count >= sync $sync_count"

make check
make docs-strict
```

### M-final
```bash
make check
make docs-strict
poetry run pytest                                          # full set

# Version and release notes
poetry version 2.1.0                                       # bump to 2.1.0
grep -E "^## \[2\.1\.0\]" CHANGELOG.md                     # the 2.1.0 section exists
grep -E "^## \[Unreleased\]" CHANGELOG.md                  # Unreleased is empty or contains only the heading

# CHANGELOG.d/ fragments are aggregated and removed (only .gitkeep + README.md remain)
ls CHANGELOG.d/ | grep -vE "^(\.gitkeep|README\.md)$" \
  && echo "FAIL: leftover changelog fragments" || echo "OK: fragments aggregated"

# Fan-out ≤ 6 enforced for all aggregator convenience methods
poetry run pytest tests/test_async_client_aggregators.py -k "fanout"

# After build, the reference contains both surfaces in each domain.
# We get the list of Async<X> classes dynamically from the parity linter (the same source
# of truth used in make async-parity-lint), and do not hardcode — otherwise
# any addition/rename of a class requires manual editing of the script.
poetry run mkdocs build --strict 2>&1 | tee /tmp/mkdocs.log
poetry run python -c "
from scripts.lint_async_parity import iter_async_classes
for cls in iter_async_classes():
    print(cls.__name__)
" > /tmp/async_class_names.txt
while IFS= read -r cls; do
  grep -R -q "$cls" site/reference/domains || echo "MISSING async section: $cls"
done < /tmp/async_class_names.txt

# After merge
git tag v2.1.0
git push --tags
```

After M-final:
- swagger-lint --strict requires mutual 1:1 coverage (sync + async) for all 11 API domains and
  auth bindings;
- `scripts/lint_async_parity.py` and `tests/contracts/test_async_swagger_contracts.py`
  are green for all domains;
- `pyproject.toml` version = 2.1.0; the root `CHANGELOG.md` contains `## [2.1.0]` with an aggregated
  history of M1…M12 + convenience methods;
- `docs/site/reference/domains/<domain>/` for each domain shows both class
  surfaces (sync + async);
- 2.1.0 release with CHANGELOG: "dual-mode SDK, AsyncAvitoClient".

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Divergence of retry/auth logic between sync and async | All non-IO logic lives in `_transport_shared.py` and `_cache.py`; both wrappers delegate. |
| `RateLimiter` is not applicable to async (sleep + `threading.Lock` baked into `acquire()`) | Decomposition into three parts: pure `RateLimitState.compute_delay()` in shared (no sleep, no lock), sync `RateLimiter` on top (`threading.Lock` + `time.sleep`), separate `AsyncRateLimiter` (`asyncio.Lock` + `await asyncio.sleep`). State is **not** shared between modes — sync and async transports are independent. |
| `_resolve_user_id` in async diverges from the sync fallback order | The async double repeats the current sync helper: argument → `settings.user_id` → raw `/core/v1/accounts/self` via transport. The public Swagger binding for `/core/v1/accounts/self` is covered by `AsyncAccount.get_self()`, not the internal helper. |
| `download_binary` in async may implicitly become streaming, diverging from sync | M1 fixes the full-buffer semantics (`await response.aread()`), like sync. Streaming is a separate API after 2.1.0 with a symmetric sync analog. Locked in by the test `test_download_binary_full_buffer_matches_sync`. |
| An M-final convenience method is implemented as "sync with a wrapped await" (loss of parallelism) OR a leaf/CPU-only method is wrapped in an unnecessary `TaskGroup` | The M-final DoD verifies the classification by actual sync code: `TaskGroup` only for independent network branches (`account_health`, `listing_health`, `review_summary`, `promotion_summary` when `item_ids`); `business_summary` is an alias; `chat_summary`/`order_summary` are sequential; `capabilities` is CPU-only without network probes. |
| Class-gated swagger-coverage applied per-domain → a large domain (`ads`) cannot be split, or a mini-domain with two classes requires finishing before the merge | Class-gated is applied **per-class**: `Async<X>` exists ↔ all operations of class `<X>` must have an async binding. The absence of `Async<Y>` in the same domain does not block merging class `Async<X>`. The M3…M12 DoD still requires closing the domain at 100%. |
| `from_env` initializes loop-dependent resources outside the loop → cross-loop UB | `from_env` is sync, SDK-managed resources (`httpx.AsyncClient`, `asyncio.Lock`) are created in `__aenter__`. If an external `http_client` is passed by the user, the transport binds to it only in `__aenter__`. Access to `transport`/`auth_provider` before `__aenter__` raises `RuntimeError` with an understandable message. Locked in by the test `test_access_before_aenter_raises`. |
| `AsyncAvitoClient` implements only domain factories and forgets the public diagnostic/closed contract of the sync client | M1 includes `auth()`, `debug_info()`, `_ensure_open()`, `_require_transport()`, `ClientClosedError` after `aclose()`, and a check of `AsyncAvitoClient.debug_info()` in `_gen_reference.py.ensure_debug_info_exists()`. |
| 2.1.0 release notes cannot be assembled mechanically because PR M3…M12 have no CHANGELOG entries | The M3…M12 DoD requires a `## [Unreleased]` line in the root `CHANGELOG.md` per PR. M-final aggregates the accumulated content into `## [2.1.0]`. |
| `_merge_headers` covertly does sync IO (`get_access_token()`) | Phase 1a as the first step refactors the contract: the helper takes an already-resolved `bearer_token: str | None`. Without this, the shared layer is not IO-agnostic, and the vary logic spreads. |
| `AsyncPaginatedList` does not inherit `list` → service expectations break | We document in the docstring; `scripts/lint_async_parity.py` allows `PaginatedList[T]` ↔ `AsyncPaginatedList[T]`. The list API is not deliberately replicated. |
| `AsyncPaginator` does not cover the helper usage `Paginator(...).as_list(...)` | The contract of `AsyncPaginator` is symmetric to sync (`iter_pages`/`collect`/`as_list`); all 4 current usage sites are covered through methods that return `AsyncPaginatedList[T]`. |
| Auth bindings do not enter async coverage | `_NON_DOMAIN_BINDING_MODULES` is augmented strictly with `"avito.auth.async_token_client"`; class-gated coverage is gated on the presence of `AsyncTokenClient`/`AsyncAlternateTokenClient`. |
| `Async<X>` has decorators but no class-level `__sdk_factory__` / `__swagger_domain__` → discovery/reference/factory checks are incomplete | The DoD M2…M12 requires mirror class metadata for each `Async<X>`, and `scripts/lint_async_parity.py` compares sync/async metadata and fails on absence. |
| Double-decoration of one function | The current `__swagger_binding__` protection remains; sync and async are different functions. |
| Race on the main refresh token in async | `asyncio.Lock` (`_refresh_lock`) in `AsyncAuthProvider` + double-checked pattern (like sync, but via `await`). |
| Race on the autoteka token in async | A separate `_autoteka_refresh_lock` + double-checked in `get_autoteka_access_token()`. The sync provider remains without a new thread-safety contract in M1, so as not to change sync semantics; async gets explicit protection, because concurrent first-touch through one event loop is a regular scenario. |
| `asyncio.Lock` created outside an event loop → cross-loop UB | `AsyncAuthProvider` is created inside `AsyncAvitoClient` (via `__aenter__` or `_from_transport`); the docstring explicitly warns "do not reuse across event loops". Python 3.10+ lazily binds the lock to the loop on first `await`. |
| Migration of `_access_token` to `TokenCache` breaks `tests/core/test_authentication.py:122-127` | `AuthProvider` keeps `@property`/setter shims for all three private fields; the shim is marked with a legacy comment and is removed in a separate PR. |
| `_operation_specs_for_sdk_method` does not find a spec from `async_domain.py` | Pre-flight smoke test with an async method + explicit spec import; the current implementation via `unwrapped_method.__globals__` (`swagger_linter.py:578-601`) must work, because `from ...operations import SOME_SPEC` puts the spec into the module's `__globals__`. If it does not work — fix in Phase 1b. |
| Convenience methods (`account_health`, …) lose the main user-value of async (parallelism) or change error semantics | M-final requires `asyncio.TaskGroup` only for independent subqueries and preserves sync error semantics: required branches propagate `AvitoError`, optional branches go through `_safe_summary_async`. It is forbidden to implement "sync wrapped in await" and forbidden to turn a required error into an unavailable section. |
| `asyncio.gather(return_exceptions=True)` swallows `CancelledError` in convenience methods | Forbidden; `asyncio.TaskGroup` is used (Python 3.11+, our floor is 3.12+). On cancellation of an outer call, TaskGroup atomically cancels all child tasks without losing cancellation. |
| The retry loop catches `asyncio.CancelledError` and loops cancellation | Shared `_decide_*_retry` and the `Transport`/`AsyncTransport` wrappers catch only retryable `httpx.TimeoutException` / `httpx.NetworkError`, not `BaseException` and not all of `httpx.RequestError`. Locked in by the test `test_cancelled_error_is_not_retried`. |
| `AsyncAvitoClient.__aenter__` leaves partially-initialized state on error | `__aenter__` is wrapped in `try/except BaseException`: on any exception it calls the idempotent `aclose()` and re-raises. Locked in by the test `test_aenter_rollback_on_partial_failure`. |
| Ownership of an external `httpx.AsyncClient` is not defined — potential resource leak or double-close | M1 explicitly chooses to mirror the current sync behavior: `AsyncTransport.aclose()` closes the passed `httpx.AsyncClient`. This is locked in by a test. An alternative `_owns_client` policy is only possible in a separate PR for sync and async simultaneously. |
| `AsyncFakeTransport` desynchronizes on `asyncio.gather` | `_handle_lock = asyncio.Lock()` serializes match-and-record; **created in `__init__`**, not lazily (lazy creation is a race on lock initialization itself). Locked in by the test `test_async_fake_transport_concurrent_handle`. |
| The M1 smoke goes through `AsyncFakeTransport` without an auth provider and does not verify OAuth/401 refresh | `AsyncFakeTransport.as_client(authenticated=True)` and `build(authenticated=True)` create `AsyncAuthProvider` + async token clients on the same `MockTransport`; the smoke must verify real `/token` calls, `Authorization`, invalidate after 401, and a repeated token fetch. |
| Existing `async def test_*` in the repository are silently skipped after `asyncio_mode = "strict"` | Pre-flight `grep -rn "^async def test_" tests/` records all such tests before M1; the marker `@pytest.mark.asyncio` is added in a separate pre-flight commit. |
| `len(PaginatedList)` / `paginated[0]` in code break when trying to migrate to `AsyncPaginatedList` | Pre-flight `grep` records all list-API usages. `AsyncPaginatedList` deliberately does not replicate the list API; each case is replaced with `await materialize()` / `loaded_count` in the async double or remains sync-only. |
| Hidden work "later" in domain PRs (TODO/FIXME/skip) | The DoD M3…M12 explicitly requires empty output of `grep -E "TODO|FIXME|@pytest.mark.skip|xfail"` over the diff; async tests must be no fewer than sync tests, and the PR description contains a mapping `sync test -> async test`; the PR is not merged with partial coverage of the domain. |
| The PoC discovers that the foundation (M1) is insufficient | This is exactly the purpose of the PoC: feedback from M2-PoC → fixes to the foundation in the same PR or M1.5-PR; the `tariffs` domain after fixes is closed at 100%, like the rest. M3 does not start until M2-PoC is green. |
| `AsyncTokenClient._request_token` is looped through the main auth provider | Internally, an independent `AsyncTransport` with `auth_provider=None` is created (mirror of sync `TokenClient._build_transport()`). |
| Sync behavior changed silently in Phase 1 | The M1 DoD includes a baseline-diff only on nodeids of existing tests with main; new async tests do not participate in the comparison. Any divergence on old nodeids blocks the merge. Phase 1a — a separate commit for bisect. |
| `_gen_reference.py` builds the reference only from sync `*/domain.py` or writes one common `::: avito.<package>` → `Async<X>` are silently absent from the reference, `make docs-strict` remains green, but publishing is incomplete | M1 must extend the builder (`public_domain_packages` picks up `async_domain.py`, `public_domain_classes` filters `Async<X>` through `AsyncDomainObject` inheritance, `public_domain_methods` — through `value.__qualname__.startswith(f"{cls.__name__}.")`) and move `write_domain_pages()` to explicit class directives sync → async. Pre-flight records the current filter points. M2-PoC validates on `tariffs`. |
| The package version is not bumped in M-final → 2.1.0 release published under the old version | The M-final DoD requires `poetry version 2.1.0` + `## [2.1.0] - YYYY-MM-DD` in CHANGELOG in one PR. `git tag v2.1.0` after merge. |
| `_safe_summary_async` is moved to a separate module, sync `_safe_summary` stays in `client.py` → symmetric helpers in different files | The M-final DoD requires: either both in `avito/client.py`, or both in `avito/summary/_helpers.py`. Partial extraction is forbidden. |
| Concurrent iteration of one `AsyncPaginatedList` mutates a shared `_cursor` → the user gets silent data corruption | Fail-fast contract: a second `__aiter__` on an active instance raises `RuntimeError`; fan-out is done via `await materialize()` or a separate `AsyncPaginatedList` per consumer. |
| English in new error messages of `async_domain.py` (STYLEGUIDE.md violation) | The M3…M12 DoD includes an explicit item "error messages in Russian only"; code review verifies every `raise <AvitoError>("...")`. |
| `AsyncSwaggerFakeTransport` is not synchronized with sync `SwaggerFakeTransport` | Added in M1 as a thin async mirror over shared schema/argument helpers. `tests/contracts/test_async_swagger_contracts.py` walks discovered `variant="async"` bindings at each stage and in M-final covers all 204 operations. |
| `pytest-asyncio` 0.23+ emits `PytestDeprecationWarning` without `asyncio_default_fixture_loop_scope` → noise accumulates in pytest output, blocks future enabling of `filterwarnings = error` | M1 must add `asyncio_default_fixture_loop_scope = "function"` in `[tool.pytest.ini_options]` next to `asyncio_mode = "strict"`. At the time of M1, `filterwarnings = error` is not yet enabled (preventive defense). Locked in the M1 DoD. |
| `_validate_factory(variant="async")` fails on async auth bindings in M1 (no domain factory on `AsyncAvitoClient`) OR misses a missing async factory in M3+ | Class-gated implementation: factory-check is skipped on async bindings without `Async<X>` in the domain and on bindings without `factory` in the decorator. The test `test_validate_factory_async_skips_unported_classes` locks in the behavior for M1, the test `test_validate_factory_async_requires_factory_for_ported_class` — for M2-PoC+. |
| `_operation_specs_for_sdk_method` does not find a spec from `async_domain.py`, and Phase 1b runs into this in the middle without a plan | The fallback is laid out **before** the start of M1 (see Swagger section): primary — AST resolution from the source file, secondary — class-level `__operation_specs__`. The pre-flight smoke test selects one of the options **before** opening the M1 PR; the decision is recorded in the PR description. |
| `AsyncOperationExecutor` takes retry only from the argument or only from `spec.retry` → divergence with sync executor goes unnoticed | The M1 DoD includes a parameterized test `test_executor_retry_resolution_matches_sync` on three triples `(retry, spec.retry, expected)`, comparing the result with sync `OperationExecutor`. |
| `httpx.AsyncClient` with default limits + unlimited fan-out in M-final convenience methods → pool starvation | M1 fixes default `httpx.Limits` (no override). The M-final DoD requires fan-out ≤ 6 in-flight tasks per aggregator. The current sync aggregators fit within this limit (max ~5 branches in `account_health`). |
| `review_summary` async with TaskGroup cancels an in-flight optional `reviews` task on a required `rating` error → changes sync semantics | `review_summary` async **must** be sequential reviews-then-rating without TaskGroup, as recorded in the classification table and the "Important TaskGroup subtlety" block. The M-final DoD code review checklist explicitly verifies this. |
| `AsyncAuthProvider.invalidate_token` is made a coroutine with `async with self._refresh_lock` → false protection, increased latency of 401-handling, divergence with sync | The contract is explicitly `def invalidate_token(self) -> None`, no await; the test `test_invalidate_token_is_sync_and_idempotent` locks in synchronicity and idempotency. |
| `AsyncTransport.request()` forgets to call `await self._rate_limiter.acquire()` before the httpx call → state is updated (via `observe_response`), but real serialization does not work, parallel coroutines go out in a batch | Step 3 of the `AsyncTransport.request()` contract explicitly mirrors sync `Transport.request()` line 148: `await self._rate_limiter.acquire()` before each `await self._client.request(...)`. Locked in by the test `test_request_acquires_rate_limiter_before_httpx_call` (5 parallel coroutines on one transport — `RateLimitState._tokens` is updated one at a time before the httpx call). The paired test `test_request_calls_observe_response_after_success` locks in the post-condition. |
| The binary branch of `AsyncOperationExecutor` differs from sync (different helper, different `BinaryResponse` form) → divergence for `OrderLabel.download()` and analogs | Module-level `_request_binary_async(transport, *, spec, path, ...)` mirrors sync `_request_binary` (`avito/core/operations.py:254-278`), both in the same file, both accepting their own `*OperationTransport` Protocol. The test `test_binary_branch_uses_request_binary_async_helper` locks in matching of `BinaryResponse` fields. The M12 domain test `OrderLabel.download()` via `AsyncSwaggerFakeTransport` is a mandatory final gate. |
| The location of `AsyncRateLimiter` is chosen in PR review → bikeshedding, risk of blurring async infrastructure into `async_transport.py` | Locked in: **`avito/core/_async_rate_limit.py`**, symmetrically with sync `avito/core/rate_limit.py`. Any deviation requires explicit justification in the PR description. |
| The list of deprecated methods in `cpa`/`ads` becomes outdated → the async-aware wrapper in `deprecation.py` misses a case, M6/M11 catch the paradox in the middle of development | Pre-flight grep `@deprecated_method` in `avito/cpa/` and `avito/ads/` records the exact number (at the time of writing the plan: 3 + 4 = 7) and locations (`cpa/domain.py:491,541,585`, `ads/domain.py:1416,1457,1523,1558`). Any divergence between pre-flight grep and the current state — update of the sequencing table before the start of M1. |
| The M-final verification script hardcodes ~50 `Async<X>` names → any addition/rename of a class requires manual editing of the script | The M-final script gets the list from `scripts.lint_async_parity.iter_async_classes()` — the single source of truth. The linter must export this function as a public API of the module. |
| `AsyncFakeTransport.as_client(user_id=N)` without `authenticated=True` behaves unclearly for domain tests → the test setup violates sync parity | The contract `as_client(user_id=N, authenticated=False)` is explicitly described: `_resolve_user_id` takes `settings.user_id` without a network request, `auth_provider=None` skips the `Authorization` header. Symmetrically with sync `FakeTransport.as_client(user_id=N)`. Locked in by the test `test_as_client_user_id_skips_self_lookup`. |
