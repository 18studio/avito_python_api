# STYLEGUIDE Compliance Action Plan

## Context Snapshot

Repository: `/Users/n.baryshnikov/Projects/avito_python_api`

User request: deep audit of project compliance with `STYLEGUIDE.md`, then preserve an action plan for fixing mismatches.

Current audit results:

- `poetry run python scripts/lint_architecture.py` passed: `errors=0`
- `poetry run mypy avito` passed
- `poetry run ruff check .` passed
- `poetry run python scripts/lint_swagger_bindings.py --strict` passed: 23 specs, 204 operations, bound 204, errors 0
- `poetry run pytest` passed: 2051 tests

Important context:

- `STYLEGUIDE.md` was updated to explicitly require Swagger-spec compliance tests and allow discovery/signature/schema introspection when it proves SDK-to-Swagger coverage.
- The audit found the project is broadly aligned with domain architecture v2, but several normative mismatches remain.
- Do not remove Swagger contract tests; they are now explicitly required by the guide.

## Action Plan

### 1. Synchronize Exception Contract

- Add explicit `attempt`, `method`, and `endpoint` fields to `AvitoError`.
- Populate these fields in `Transport._map_http_error()`.
- Pass `attempt` for retry exhaustion and transport-level exceptions.
- Keep existing `metadata` behavior for compatibility, but do not rely on metadata as the only public source of these fields.
- Update error mapping and security tests.

Relevant files:

- `avito/core/exceptions.py`
- `avito/core/transport.py`
- `tests/core/test_transport.py`
- `tests/core/test_authentication.py`
- `docs/site/reference/exceptions.md`

Verification:

```bash
poetry run pytest tests/core/test_transport.py tests/core/test_authentication.py
```

### 2. Add Per-Request Transport Debug Logging

- Emit a debug log for every real HTTP request/response.
- Include structured fields: `operation`, `endpoint`, `method`, `attempt`, `status`, `latency_ms`, `request_id`.
- Do not log body, secrets, auth headers, or idempotency keys.
- Keep retry logs, but align field naming with the standard set where possible.
- Add or update tests using `caplog`.

Relevant files:

- `avito/core/transport.py`
- `tests/core/test_transport.py`
- `docs/site/explanations/transport-and-retries.md`
- `docs/site/how-to/diagnostics-and-logging.md`

Verification:

```bash
poetry run pytest tests/core/test_transport.py
```

### 3. Fix Optional Positional Public Parameter

- Change `Account.get_balance(user_id=None, *, ...)` to `Account.get_balance(*, user_id=None, ...)`.
- Update call sites and documentation snippets if needed.
- Decide whether this is acceptable as a breaking public signature change. If not, document an explicit compatibility exception or deprecation path before changing.

Relevant files:

- `avito/accounts/domain.py`
- `tests/domains/accounts/test_accounts.py`
- `docs/site/how-to/account-profile.md`
- `README.md`

Verification:

```bash
poetry run pytest tests/domains/accounts/test_accounts.py tests/contracts/test_swagger_contracts.py
```

### 4. Resolve `AVITO_SECRET` Alias Policy

- `STYLEGUIDE.md` forbids generic env aliases like `SECRET` / `TOKEN`.
- Current official alias `AVITO_SECRET` conflicts with that rule.
- Preferred path:
  - keep it temporarily for backward compatibility;
  - emit a deprecation warning when it is used;
  - remove it from the official documented config contract;
  - add a `CHANGELOG.md` entry.
- Alternative path: add a documented exception to the guide, but that weakens the config rule.

Relevant files:

- `avito/auth/settings.py`
- `avito/_env.py`
- `tests/core/test_configuration.py`
- `README.md`
- `docs/site/reference/config.md`
- `docs/site/how-to/auth-and-config.md`
- `CHANGELOG.md`

Verification:

```bash
poetry run pytest tests/core/test_configuration.py
```

### 5. Validate Date/Time String Inputs

- Introduce shared validation/serialization helpers for date and datetime public inputs.
- Use the `ads` domain approach as a model: `date | datetime | str` plus ISO validation before transport.
- Review domains with public date-like `str` parameters:
  - `cpa`
  - `realty`
  - `jobs`
  - `messenger`
  - `orders`
- Invalid strings should raise `ValidationError` before transport.

Relevant examples:

- Good current pattern: `avito/ads/domain.py::_serialize_stats_date`
- Risk examples:
  - `avito/cpa/domain.py`
  - `avito/realty/domain.py`
  - `avito/jobs/domain.py`

Verification:

```bash
poetry run pytest tests/domains/cpa/test_cpa.py tests/domains/realty/test_realty.py tests/domains/jobs/test_jobs.py tests/domains/messenger/test_messenger.py tests/domains/orders/test_orders.py
```

### 6. Convert Closed Swagger Value Sets to Enums

- Identify public request/model fields where Swagger defines a closed set but SDK uses open `str`.
- Start with clear cases:
  - `orders.transition`
  - `jobs.billing_type`
  - `jobs.employment`
  - `jobs.schedule`
  - `jobs.experience`
  - `ads` spendings `grouping`
- Place enums next to the models that use them.
- Public method signatures should prefer enum types, optionally accepting corresponding string literals via internal normalization.
- Unknown upstream response values should map to `UNKNOWN` or typed fallback with warning.

Relevant files:

- `avito/orders/models.py`
- `avito/orders/domain.py`
- `avito/jobs/models.py`
- `avito/jobs/domain.py`
- `avito/ads/models.py`
- `avito/ads/domain.py`
- `docs/avito/api/*.json`

Verification:

```bash
poetry run mypy avito
poetry run pytest tests/domains/orders/test_orders.py tests/domains/jobs/test_jobs.py tests/domains/ads/test_ads.py
poetry run python scripts/lint_swagger_bindings.py --strict
```

### 7. Make Public Docstrings Reference-Ready

- Many public domain methods have short docstrings that do not describe all required contract details.
- For each public API method, document:
  - business action;
  - public arguments;
  - return SDK model;
  - pagination behavior, if any;
  - dry-run and idempotency behavior, if any;
  - `timeout` and `retry` overrides;
  - common SDK exceptions.
- Do not keep `Raises: AvitoError ...` as the only contract detail.
- This should be enforced by docs/static lint, not pytest.

Priority domains:

- `accounts`
- `ads`
- `promotion`
- `messenger`
- `tariffs`

Verification:

```bash
make docs-strict
```

### 8. Align Pytest Suite With Updated STYLEGUIDE

- Keep Swagger contract tests.
- Move non-behavioral documentation/style checks out of pytest.
- Review these tests:
  - `tests/contracts/test_docstring_contracts.py`
  - public-surface assertions in `tests/contracts/test_client_contracts.py`
  - non-Swagger linter unit tests in `tests/core/test_swagger_linter.py`
- Preserve tests that prove runtime behavior or Swagger contract coverage.
- Move pure style/doc checks to static linter or docs linter invoked from `make check`.

Verification:

```bash
poetry run pytest
poetry run python scripts/lint_architecture.py
make docs-strict
```

### 9. Extend Static Architecture Lint

- Add checks for issues discovered manually:
  - optional positional parameters in public domain methods;
  - public date-like `str` parameters without validation/serialization helper;
  - forbidden generic env aliases;
  - public exception fields required by the guide;
  - public docstring structure, if automatic enforcement is desired.
- Keep these in `scripts/lint_architecture.py` or a dedicated static/docs linter, not pytest.

Relevant files:

- `scripts/lint_architecture.py`
- `Makefile`

Verification:

```bash
poetry run python scripts/lint_architecture.py
make check
```

### 10. Final Gate

Run after the fixes are complete:

```bash
make swagger-lint
poetry run pytest
poetry run mypy avito
poetry run ruff check .
poetry run python scripts/lint_architecture.py
make docs-strict
make check
```

### 11. Align DELETE With Non-Idempotent Retry Policy

STYLEGUIDE §415: «Non-idempotent HTTP methods (POST, PATCH, DELETE without an explicit safe marker) are not retried by default». Сейчас в `avito/core/transport.py:513–514` блокировка ретраев без `idempotency_key` действует только на `POST`/`PATCH`; `DELETE` обрабатывается общей политикой `RetryPolicy.retryable_methods`.

Шаги:

- Расширить условие в `Transport._is_retryable_attempt()` (или эквивалентный метод) до `{"POST", "PATCH", "DELETE"}`: ретрай только при наличии `idempotency_key` или явного per-operation opt-in.
- Убедиться, что `RetryPolicy.retryable_methods` по умолчанию не содержит `DELETE`, либо что `Transport` имеет приоритет.
- Добавить тесты:
  - `DELETE` без ключа на 5xx/timeout не ретраится;
  - `DELETE` с `idempotency_key` ретраится по общим правилам;
  - `DELETE` с явным per-operation override ретраится.
- Обновить `docs/site/explanations/transport-and-retries.md`.

Файлы:

- `avito/core/transport.py`
- `avito/core/retries.py`
- `tests/core/test_transport.py`
- `docs/site/explanations/transport-and-retries.md`

Verification:

```bash
poetry run pytest tests/core/test_transport.py
```

### 12. Сквозной аудит `idempotency_key` за пределами `promotion`

Аудит подтвердил полное покрытие в `avito/promotion/domain.py`. Нужно явно проверить остальные домены с write-операциями: `orders`, `ratings`, `messenger`, `cpa`, `jobs`, `realty`, `autoload`. STYLEGUIDE §424–426: при наличии у upstream поддержки идемпотентности — параметр обязан быть в публичной сигнатуре.

Шаги:

- Сверить со Swagger-спецификациями в `docs/avito/api/`, какие POST/PATCH/DELETE upstream поддерживают идемпотентность (заголовок/параметр).
- Для каждого такого метода добавить `idempotency_key: str | None = None` keyword-only.
- Прокинуть значение через `OperationExecutor` в `Transport`; ключ передаётся одним и тем же значением через все retry-попытки одного логического вызова.
- В docstring каждого write-метода явно зафиксировать: «без `idempotency_key` метод не ретраится на сетевых ошибках».
- Добавить контрактный тест на `Idempotency-Key` header (один и тот же на все попытки).

Файлы:

- `avito/orders/domain.py`, `avito/ratings/domain.py`, `avito/messenger/domain.py`, `avito/cpa/domain.py`, `avito/jobs/domain.py`, `avito/realty/domain.py`, `avito/autoload/domain.py`
- соответствующие `tests/domains/<domain>/`

Verification:

```bash
poetry run pytest tests/domains/ tests/core/test_transport.py
```

### 13. Выделить `ClientClosedError`

STYLEGUIDE §183: вызов на закрытом клиенте обязан бросать доменную ошибку. Сейчас `avito/client.py:573–574` бросает `ConfigurationError("Клиент закрыт; ...")`. Технически это доменная ошибка, но семантически lifecycle ≠ конфигурация: пользователь, ловящий `ConfigurationError`, неожиданно получит ошибки закрытого клиента.

Шаги:

- Добавить `ClientClosedError(AvitoError)` в `avito/core/exceptions.py`.
- Заменить raise в `_ensure_open()` на `ClientClosedError`.
- Сообщение оставить на русском.
- Обновить `docs/site/reference/exceptions.md` и `CHANGELOG.md` (раздел `Changed`/`Added`).
- Добавить тест: вызов любого публичного метода после `close()` бросает `ClientClosedError` и не уходит в `httpx`.
- Обратная совместимость: т.к. `ConfigurationError` и `ClientClosedError` оба наследники `AvitoError`, ловящие `AvitoError` пользователи не сломаются. Ловящие `ConfigurationError` — да, но это ожидаемое поведение по STYLEGUIDE; задепрекейтить переходный период не требуется (сообщение оставалось в Russian, контракт не публиковался).

Файлы:

- `avito/core/exceptions.py`
- `avito/client.py`
- `tests/core/test_client_lifecycle.py` (создать или дополнить существующий)
- `docs/site/reference/exceptions.md`
- `CHANGELOG.md`

Verification:

```bash
poetry run pytest tests/core/ tests/contracts/
```

### 14. CHANGELOG-гейт

STYLEGUIDE §710 и §923: запись в `CHANGELOG.md` обязательна для каждого публичного изменения. Сейчас файл присутствует, но автоматического чека нет ни в `Makefile`, ни в `.github/workflows/`.

Шаги:

- Добавить скрипт `scripts/check_changelog.py`: при diff в `avito/**` относительно базовой ветки требовать модификации `CHANGELOG.md` в том же diff.
- Подключить в `make check` (опционально — только если запущено в CI: проверять переменную окружения).
- Альтернатива: GitHub Actions job, который сравнивает изменённые пути через `git diff --name-only origin/main...HEAD`.
- Документировать политику в `CONTRIBUTING.md` (создать при отсутствии).

Файлы:

- `scripts/check_changelog.py` (новый)
- `Makefile`
- `.github/workflows/ci.yml` (если используется)
- `CONTRIBUTING.md`

Verification:

```bash
poetry run python scripts/check_changelog.py
```

### 15. Сквозной аудит документации per-operation overrides

STYLEGUIDE §388, §687: список поддерживаемых per-operation override'ов — часть публичного контракта и должен быть задокументирован в docstring **каждого** публичного метода. Реализация (`timeout`, `retry` в `OperationExecutor.execute()`) уже есть, но docstring-покрытие неравномерное между доменами.

Шаги (примыкает к разделу 7, но более узкий и автоматизируемый):

- Расширить статический линтер из раздела 9 проверкой: для каждого публичного метода с `@swagger_operation` в docstring должны присутствовать секции/маркеры `timeout` и `retry`.
- Прогнать линтер, исправить пропуски в `accounts`, `ads`, `promotion`, `messenger`, `tariffs`, `orders`, `cpa`, `jobs`, `realty`, `ratings`, `autoload`.
- Добавить общий шаблон в `docs/site/explanations/` со ссылкой из docstring (рекомендация, не норма).

Файлы:

- `scripts/lint_architecture.py` (или `scripts/lint_docstrings.py`)
- все `avito/*/domain.py`

Verification:

```bash
poetry run python scripts/lint_architecture.py
make docs-strict
```

## Recommended Execution Order

1. Exception contract and transport logging.
2. `Account.get_balance` signature.
3. `AVITO_SECRET` alias policy.
4. Date/time validation.
5. Closed value-set enums.
6. DELETE retry policy alignment (раздел 11).
7. Idempotency_key audit (раздел 12).
8. `ClientClosedError` (раздел 13).
9. Public docstrings + per-operation overrides docstring audit (разделы 7 и 15 совместно).
10. Pytest/static-lint alignment.
11. Static lint expansion.
12. CHANGELOG-гейт (раздел 14).
13. Final gate.

## Changelog

- 2026-05-03: Created plan from STYLEGUIDE compliance audit.
- 2026-05-03: Recorded current clean baseline: architecture lint, mypy, ruff, swagger-lint, and full pytest all pass.
- 2026-05-03: Noted that `STYLEGUIDE.md` now explicitly requires Swagger-spec compliance tests and permits contract-focused introspection for Swagger coverage.
- 2026-05-03: Added sections 11–15 after deep audit. Confirmed already-implemented: per-operation overrides (`avito/core/operations.py:137`), `idempotency_key` в `promotion`, `User-Agent` + `user_agent_suffix` (`avito/config.py:35`, `avito/core/transport.py:430–442`), `Retry-After` honor (`avito/core/transport.py:486–494`, `696–709`), explicit `to_dict()`/`model_dump()` (`avito/core/serialization.py:35–50`), once-per-process unknown-enum warnings (`avito/core/enums.py:9, 22–28`), Diátaxis-структура (tutorials/how-to/reference/explanations с `idempotency.md`, `pagination.md`, `per-operation-overrides.md`, `transport-and-retries.md`), `avito.testing` namespace (`FakeTransport`, `FakeResponse`, `SwaggerFakeTransport`), отсутствие `**kwargs` на публичных методах, отсутствие `logging.basicConfig`, отсутствие dead code в `avito/core/{swagger,operations,deprecation}.py`, корректные `PaginatedList[T]` аннотации.
