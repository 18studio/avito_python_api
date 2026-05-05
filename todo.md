# STYLEGUIDE Compliance TODO

Repository: `/Users/n.baryshnikov/Projects/avito_python_api`

This file tracks the remaining work from the STYLEGUIDE compliance audit.

Legend:

- `[ ]` Not started or still open.
- `[~]` Partially done or blocked.
- `[x]` Already done / background context only.

## Current Baseline

These checks passed during the audit:

- `[x]` `poetry run python scripts/lint_architecture.py`: `errors=0`
- `[x]` `poetry run mypy avito`
- `[x]` `poetry run ruff check .`
- `[x]` `poetry run python scripts/lint_swagger_bindings.py --strict`: 23 specs, 204 operations, bound 204, errors 0
- `[x]` `poetry run pytest`: 2051 tests

Important constraints:

- Keep Swagger contract tests. `STYLEGUIDE.md` now explicitly requires them.
- Public SDK methods must keep one-to-one Swagger bindings.
- Public API changes require reference-ready docstrings and `CHANGELOG.md` entries.

Open items as of 2026-05-05:

- `[~]` Task 10: final gate is blocked until full `make check` can complete.
- `[x]` Task 12: `idempotency_key` audit outside `promotion`.
- `[x]` Task 13: `ClientClosedError`.
- `[ ]` Task 14: CHANGELOG gate.
- `[ ]` Task 15: per-operation override documentation.

## Remaining Execution Order

1. Public docstrings and per-operation override documentation.
2. CHANGELOG gate.
3. Final gate.

## Task Status

### 1. `[x]` Synchronize Exception Contract

Status:

- Completed. Verified on 2026-05-05.
- `AvitoError` has explicit `attempt`, `method`, `endpoint`, and `request_id` fields.
- `Transport._map_http_error()` populates the fields for mapped HTTP errors.
- Transport tests cover structured error fields.
- Exception reference docs include the fields.

What to do:

- Add explicit `attempt`, `method`, and `endpoint` fields to `AvitoError`.
- Populate these fields in `Transport._map_http_error()`.
- Pass `attempt` for retry exhaustion and transport-level exceptions.
- Keep existing `metadata` behavior for compatibility, but do not rely on metadata as the only public source of these fields.
- Update error mapping and security tests.
- Update exception reference docs.

Files:

- `avito/core/exceptions.py`
- `avito/core/transport.py`
- `tests/core/test_transport.py`
- `tests/core/test_authentication.py`
- `docs/site/reference/exceptions.md`

Verify:

```bash
poetry run pytest tests/core/test_transport.py tests/core/test_authentication.py
```

### 2. `[x]` Add Per-Request Transport Debug Logging

Status:

- Completed. Verified on 2026-05-05.
- `Transport` emits `transport http exchange` debug logs with `operation`, `endpoint`, `method`, `attempt`, `status`, `latency_ms`, and `request_id`.
- Tests verify sensitive fields are not logged.
- Diagnostics and retry docs describe the structured log fields.

What to do:

- Emit a debug log for every real HTTP request/response.
- Include structured fields: `operation`, `endpoint`, `method`, `attempt`, `status`, `latency_ms`, `request_id`.
- Do not log bodies, secrets, auth headers, or idempotency keys.
- Keep retry logs, but align field names with the standard set where possible.
- Add or update `caplog` tests.
- Update diagnostics/retry docs.

Files:

- `avito/core/transport.py`
- `tests/core/test_transport.py`
- `docs/site/explanations/transport-and-retries.md`
- `docs/site/how-to/diagnostics-and-logging.md`

Verify:

```bash
poetry run pytest tests/core/test_transport.py
```

### 3. `[x]` Fix Optional Positional Public Parameter

Status:

- Completed. Verified on 2026-05-05.
- `Account.get_balance()` now accepts `user_id` as keyword-only.
- Account and Swagger contract tests pass.

What to do:

- Change `Account.get_balance(user_id=None, *, ...)` to `Account.get_balance(*, user_id=None, ...)`.
- Update call sites and documentation snippets if needed.
- Decide whether to treat this as a breaking public signature change.
- If compatibility is required, document an explicit exception or deprecation path before changing.

Files:

- `avito/accounts/domain.py`
- `tests/domains/accounts/test_accounts.py`
- `docs/site/how-to/account-profile.md`
- `README.md`

Verify:

```bash
poetry run pytest tests/domains/accounts/test_accounts.py tests/contracts/test_swagger_contracts.py
```

### 4. `[x]` Resolve `AVITO_SECRET` Alias Policy

Status:

- Completed. Verified on 2026-05-05.
- `AVITO_SECRET` moved to deprecated aliases.
- `AuthSettings.supported_env_vars()` returns only official aliases.
- Using `AVITO_SECRET` emits `DeprecationWarning`.
- Config tests and changelog cover the deprecation.

Problem:

- `STYLEGUIDE.md` forbids generic env aliases like `SECRET` / `TOKEN`.
- The current official alias `AVITO_SECRET` conflicts with that rule.

Preferred fix:

- Keep `AVITO_SECRET` temporarily for backward compatibility.
- Emit a deprecation warning when it is used.
- Remove it from the official documented config contract.
- Add a `CHANGELOG.md` entry.

Alternative:

- Add a documented STYLEGUIDE exception. This weakens the config rule and is not preferred.

Files:

- `avito/auth/settings.py`
- `avito/_env.py`
- `tests/core/test_configuration.py`
- `README.md`
- `docs/site/reference/config.md`
- `docs/site/how-to/auth-and-config.md`
- `CHANGELOG.md`

Verify:

```bash
poetry run pytest tests/core/test_configuration.py
```

### 5. `[x]` Validate Date/Time String Inputs

Status:

- Completed. Verified on 2026-05-05.
- Shared helpers exist in `avito/core/validation.py`: `DateInput`, `serialize_iso_date()`, and `serialize_iso_datetime()`.
- `cpa`, `realty`, `jobs`, `messenger`, and `orders` use these helpers for date-like public inputs.
- Domain tests verify invalid date strings raise `ValidationError` before transport.

What to do:

- Introduce shared validation/serialization helpers for public date and datetime inputs.
- Use the `ads` pattern as the model: `date | datetime | str` plus ISO validation before transport.
- Review public date-like `str` parameters in:
  - `cpa`
  - `realty`
  - `jobs`
  - `messenger`
  - `orders`
- Invalid strings must raise `ValidationError` before transport.

Reference:

- Good current pattern: `avito/ads/domain.py::_serialize_stats_date`
- Risk examples:
  - `avito/cpa/domain.py`
  - `avito/realty/domain.py`
  - `avito/jobs/domain.py`

Verify:

```bash
poetry run pytest tests/domains/cpa/test_cpa.py tests/domains/realty/test_realty.py tests/domains/jobs/test_jobs.py tests/domains/messenger/test_messenger.py tests/domains/orders/test_orders.py
```

### 6. `[x]` Convert Closed Swagger Value Sets to Enums

Status:

- Completed. Verified on 2026-05-05.
- Added enums for `orders.transition`, jobs billing/employment/schedule/experience fields, and ads grouping fields.
- Tests verify enum inputs, string compatibility, and unknown value rejection.
- `mypy`, affected domain tests, and Swagger binding lint pass.

What to do:

- Identify public request/model fields where Swagger defines a closed set but the SDK uses open `str`.
- Start with:
  - `orders.transition`
  - `jobs.billing_type`
  - `jobs.employment`
  - `jobs.schedule`
  - `jobs.experience`
  - `ads` spendings `grouping`
- Place enums next to the models that use them.
- Public method signatures should prefer enum types, optionally accepting corresponding string literals via internal normalization.
- Unknown upstream response values should map to `UNKNOWN` or typed fallback with warning.

Files:

- `avito/orders/models.py`
- `avito/orders/domain.py`
- `avito/jobs/models.py`
- `avito/jobs/domain.py`
- `avito/ads/models.py`
- `avito/ads/domain.py`
- `docs/avito/api/*.json`

Verify:

```bash
poetry run mypy avito
poetry run pytest tests/domains/orders/test_orders.py tests/domains/jobs/test_jobs.py tests/domains/ads/test_ads.py
poetry run python scripts/lint_swagger_bindings.py --strict
```

### 7. `[x]` Make Public Docstrings Reference-Ready

Status:

- Completed. Verified on 2026-05-05.
- `make docs-strict` and `scripts/lint_docstrings.py` pass.
- Swagger-bound public method docstrings include per-call `timeout` and `retry`
  contract details, return models, and SDK exception context.

What to do:

- Rewrite short public domain method docstrings so they describe the real public contract.
- For each public API method, document:
  - business action;
  - public arguments;
  - return SDK model;
  - pagination behavior, if any;
  - dry-run and idempotency behavior, if any;
  - `timeout` and `retry` overrides;
  - common SDK exceptions.
- Do not keep `Raises: AvitoError ...` as the only exception contract detail.
- Enforce this with docs/static lint, not pytest.

Priority domains:

- `accounts`
- `ads`
- `promotion`
- `messenger`
- `tariffs`

Verify:

```bash
make docs-strict
```

### 8. `[x]` Align Pytest Suite With Updated STYLEGUIDE

Status:

- Completed. Verified on 2026-05-05.
- `tests/contracts/test_docstring_contracts.py` is gone.
- Docstring checks live in `scripts/lint_docstrings.py` and are wired into `make quality` / `make docs-strict`.
- Swagger contract tests remain in pytest.

What to do:

- Keep Swagger contract tests.
- Move non-behavioral documentation/style checks out of pytest.
- Review:
  - `tests/contracts/test_docstring_contracts.py`
  - public-surface assertions in `tests/contracts/test_client_contracts.py`
  - non-Swagger linter unit tests in `tests/core/test_swagger_linter.py`
- Preserve tests that prove runtime behavior or Swagger contract coverage.
- Move pure style/doc checks to static linter or docs linter invoked from `make check`.

Verify:

```bash
poetry run pytest
poetry run python scripts/lint_architecture.py
make docs-strict
```

### 9. `[x]` Extend Static Architecture Lint

Status:

- Completed for architecture checks. Verified on 2026-05-05.
- `scripts/lint_architecture.py` now checks optional positional public parameters, date-like string parameters, forbidden official env aliases, required public exception fields, unbound public methods, missing `OperationSpec` execution, and raw public returns.
- Deeper timeout/retry docstring enforcement is still open separately in task 15.

Implemented checks:

- Optional positional parameters in public domain methods.
- Public date-like `str` parameters without validation/serialization helper.
- Forbidden generic official env aliases.
- Public exception fields required by the guide.
- Unbound public domain methods.
- Public domain methods that do not execute an `OperationSpec`.
- Public methods returning raw `dict` or `Any`.

Files:

- `scripts/lint_architecture.py`
- `Makefile`

Verify:

```bash
poetry run python scripts/lint_architecture.py
make check
```

### 10. `[~]` Final Gate

Status:

- Re-attempted on 2026-05-05 after tasks 7 and 11.
- Local gates passed: `pytest`, `mypy`, `ruff`, `lint_architecture`, `lint_docstrings`, local `lint_swagger_bindings --strict`, `docs-strict`, and `poetry build`.
- Full `make swagger-lint` / `make check` is still blocked because `scripts/download_avito_api_specs.py --clean` times out against `https://developers.avito.ru/api-catalog`.
- The catalog refresh failed both normally and with escalated network access, so the remaining blocker is external download stability rather than a local lint/test failure.

Run after all fixes are complete:

```bash
make swagger-lint
poetry run pytest
poetry run mypy avito
poetry run ruff check .
poetry run python scripts/lint_architecture.py
make docs-strict
make check
```

### 11. `[x]` Align DELETE With Non-Idempotent Retry Policy

Status:

- Completed. Verified on 2026-05-05.
- `DELETE` without `idempotency_key` is not retried by default even though
  `RetryPolicy.retryable_methods` includes `DELETE`.
- `DELETE` with `idempotency_key` keeps the same `Idempotency-Key` across retry attempts.
- `DELETE` with explicit operation-level retry opt-in can be retried.
- Retry docs now describe the transport-level non-idempotent method guard.

Problem:

- STYLEGUIDE says non-idempotent HTTP methods are not retried by default.
- This includes `POST`, `PATCH`, and `DELETE` without an explicit safe marker.
- Current transport retry blocking applies only to `POST` and `PATCH`; `DELETE` can still follow `RetryPolicy.retryable_methods`.

What to do:

- Extend `Transport._is_retryable_attempt()` or equivalent to treat `DELETE` like `POST` and `PATCH`.
- Retry `DELETE` only when an `idempotency_key` is present or the operation has explicit opt-in.
- Ensure `RetryPolicy.retryable_methods` default does not override this transport-level rule.
- Add tests:
  - `DELETE` without key on 5xx/timeout is not retried;
  - `DELETE` with `idempotency_key` is retried by normal rules;
  - `DELETE` with explicit per-operation override is retried.
- Update retry docs.

Files:

- `avito/core/transport.py`
- `avito/core/retries.py`
- `tests/core/test_transport.py`
- `docs/site/explanations/transport-and-retries.md`

Verify:

```bash
poetry run pytest tests/core/test_transport.py
```

### 12. `[x]` Audit `idempotency_key` Outside `promotion`

Status:

- `avito/promotion/domain.py` already has full coverage.
- Completed. Verified on 2026-05-05.
- Write operations outside `promotion` now expose and forward `idempotency_key` where the
  SDK performs a mutating logical call. CPA complaint creation and Realty write/report
  operations were the remaining gaps.
- Domain tests cover `Idempotency-Key` forwarding outside `promotion`, including stable
  header reuse across a retry chain.

What to do:

- Check write operations in:
  - `orders`
  - `ratings`
  - `messenger`
  - `cpa`
  - `jobs`
  - `realty`
  - `autoload`
- Compare Swagger specs in `docs/avito/api/` to identify POST/PATCH/DELETE operations with upstream idempotency support.
- For each matching public method, add keyword-only `idempotency_key: str | None = None`.
- Pass the same key through `OperationExecutor` to `Transport` for every retry attempt in one logical call.
- In each write-method docstring, state that without `idempotency_key` the method is not retried on network errors.
- Add a contract test for the `Idempotency-Key` header and verify it is stable across retries.

Files:

- `avito/orders/domain.py`
- `avito/ratings/domain.py`
- `avito/messenger/domain.py`
- `avito/cpa/domain.py`
- `avito/jobs/domain.py`
- `avito/realty/domain.py`
- `avito/autoload/domain.py`
- `tests/domains/<domain>/`
- `tests/core/test_transport.py`

Verify:

```bash
poetry run pytest tests/domains/ tests/core/test_transport.py
```

### 13. `[x]` Add `ClientClosedError`

Status:

- Completed. Verified on 2026-05-05.
- Added `ClientClosedError(AvitoError)` and exported it from `avito` and `avito.core`.
- `AvitoClient._ensure_open()` now raises `ClientClosedError` instead of `ConfigurationError`.
- Tests prove closed-client calls fail before any HTTP request is sent.
- Exception docs, client docs, diagnostics docs, error model docs, and changelog describe the new lifecycle error.

Problem:

- Calls on a closed client currently raise `ConfigurationError("Клиент закрыт; ...")`.
- This is technically a domain error, but semantically lifecycle errors should not be configuration errors.

What to do:

- Add `ClientClosedError(AvitoError)` in `avito/core/exceptions.py`.
- Replace the raise in `AvitoClient._ensure_open()` with `ClientClosedError`.
- Keep the message in Russian.
- Update exception docs and changelog.
- Add a test proving that a public method called after `close()` raises `ClientClosedError` and does not call `httpx`.

Compatibility note:

- Users catching `AvitoError` keep working.
- Users catching `ConfigurationError` for closed-client lifecycle errors will see a behavior change.
- A deprecation period is not required because the old exception was not a published lifecycle contract.

Files:

- `avito/core/exceptions.py`
- `avito/client.py`
- `tests/core/test_client_lifecycle.py`
- `docs/site/reference/exceptions.md`
- `CHANGELOG.md`

Verify:

```bash
poetry run pytest tests/core/ tests/contracts/
```

### 14. `[ ]` Add CHANGELOG Gate

Problem:

- STYLEGUIDE requires a `CHANGELOG.md` entry for each public change.
- There is no automatic check in `Makefile` or CI.

What to do:

- Add `scripts/check_changelog.py`.
- If `avito/**` changed relative to the base branch, require `CHANGELOG.md` to be changed in the same diff.
- Wire the check into `make check`, or into CI only if local branch comparisons are too brittle.
- Document the policy in `CONTRIBUTING.md`.

Files:

- `scripts/check_changelog.py`
- `Makefile`
- `.github/workflows/ci.yml`, if present and used
- `CONTRIBUTING.md`

Verify:

```bash
poetry run python scripts/check_changelog.py
```

### 15. `[~]` Audit Per-Operation Override Documentation

Status:

- Partially complete.
- Current Swagger-bound method docstrings mention both `timeout` and `retry`.
- Remaining work is to enforce this with static lint so regressions fail locally.

Problem:

- `timeout` and `retry` overrides are already implemented in `OperationExecutor.execute()`.
- Docstring coverage is uneven.
- STYLEGUIDE treats supported per-operation overrides as part of the public contract.

What to do:

- Extend static lint so every public method with `@swagger_operation` has docstring coverage for `timeout` and `retry`.
- Fix missing docstrings in:
  - `accounts`
  - `ads`
  - `promotion`
  - `messenger`
  - `tariffs`
  - `orders`
  - `cpa`
  - `jobs`
  - `realty`
  - `ratings`
  - `autoload`
- Optionally add a shared template in `docs/site/explanations/` and link to it from docstrings.

Files:

- `scripts/lint_architecture.py`, or new `scripts/lint_docstrings.py`
- `avito/*/domain.py`
- `docs/site/explanations/`

Verify:

```bash
poetry run python scripts/lint_architecture.py
make docs-strict
```

## Already Implemented Context

These items were confirmed during the audit and do not need separate TODO work unless regressions are found:

- `[x]` Per-operation overrides exist in `avito/core/operations.py`.
- `[x]` `idempotency_key` is covered in `promotion`.
- `[x]` `User-Agent` and `user_agent_suffix` are implemented.
- `[x]` `Retry-After` handling is implemented.
- `[x]` `to_dict()` / `model_dump()` serialization helpers are implemented.
- `[x]` Unknown enum warnings are once-per-process.
- `[x]` Diataxis docs structure exists.
- `[x]` `avito.testing` namespace exposes `FakeTransport`, `FakeResponse`, and `SwaggerFakeTransport`.
- `[x]` No public `**kwargs` were found during the audit.
- `[x]` No `logging.basicConfig` usage was found during the audit.
- `[x]` No dead code was found in `avito/core/{swagger,operations,deprecation}.py`.
- `[x]` `PaginatedList[T]` annotations were correct during the audit.

## History

- 2026-05-03: Created plan from STYLEGUIDE compliance audit.
- 2026-05-03: Recorded clean baseline: architecture lint, mypy, ruff, swagger-lint, and full pytest all pass.
- 2026-05-03: Noted that `STYLEGUIDE.md` explicitly requires Swagger-spec compliance tests and permits contract-focused introspection for Swagger coverage.
- 2026-05-03: Added tasks 11-15 after deeper audit.
- 2026-05-05: Architecture lint was partially extended; final `make check` remained blocked by Avito API catalog timeout.
- 2026-05-05: Rewritten into explicit status checklist for easier execution.
- 2026-05-05: Completed task 11, aligning DELETE retry behavior with the non-idempotent retry policy.
- 2026-05-05: Completed task 7 by filling remaining public docstring contract gaps.
- 2026-05-05: Re-ran task 10 gates; local checks pass, full gate remains blocked by Avito API catalog timeout.
- 2026-05-05: Completed task 12 by adding missing `idempotency_key` support to CPA complaint
  creation and Realty write/report operations, with focused domain tests.
- 2026-05-05: Completed task 13 by adding `ClientClosedError` for closed-client lifecycle
  calls and updating tests, docs, exports, and changelog.
