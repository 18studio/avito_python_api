# Swagger binding subsystem

Swagger binding subsystem связывает локальный OpenAPI corpus с публичной поверхностью SDK. Его задача — доказуемо ответить на два вопроса:

- какая upstream Swagger operation покрыта каким публичным SDK-методом;
- как contract-test runner должен вызвать этот SDK-метод без реального HTTP.

Swagger/OpenAPI-файлы в `docs/avito/api/*.json` остаются единственным источником истины по HTTP-контракту: method, path, parameters, request body, content type, statuses, schemas и operation-level `deprecated`. Binding-и не дублируют эти данные. Они хранят только адресацию между SDK и Swagger.

## Основные компоненты

| Компонент | Файл | Ответственность |
|---|---|---|
| Swagger downloader | `scripts/download_avito_api_specs.py` | Скачивает свежий upstream OpenAPI catalog в `docs/avito/api/` и удаляет stale specs |
| Binding decorator | `avito/core/swagger.py` | Записывает metadata на публичный SDK-метод |
| Swagger registry | `avito/core/swagger_registry.py` | Загружает `docs/avito/api/*.json`, нормализует операции и проверяет базовую валидность specs |
| Binding discovery | `avito/core/swagger_discovery.py` | Находит decorated public domain methods без создания `AvitoClient` и без HTTP |
| Linter | `avito/core/swagger_linter.py`, `scripts/lint_swagger_bindings.py` | Проверяет, что binding-и полные, уникальные, соответствуют Swagger и исполняются через matching `OperationSpec` |
| Report | `avito/core/swagger_report.py` | Формирует JSON report для docs/reference и coverage |
| Factory map | `avito/core/swagger_factory_map.py` | Даёт вспомогательную, неканоническую карту `AvitoClient factory -> domain class -> spec candidates` |
| Contract runner | `avito/testing/swagger_fake_transport.py` | Строит SDK-вызовы по binding metadata и валидирует фактический request/response через Swagger |

Каноническая карта покрытия строится только из `Swagger operation key -> discovered binding`. Markdown inventory не участвует в coverage и не является источником истины.

## Binding metadata

Публичный декоратор:

```python
@swagger_operation(
    method: str,
    path: str,
    *,
    spec: str | None = None,
    operation_id: str | None = None,
    factory: str | None = None,
    factory_args: Mapping[str, str] | None = None,
    method_args: Mapping[str, str] | None = None,
    deprecated: bool = False,
    legacy: bool = False,
)
```

Class-level metadata на domain object задаёт defaults:

```python
__swagger_domain__: str
__swagger_spec__: str
__sdk_factory__: str
__sdk_factory_args__: Mapping[str, str]
```

Приоритет значений:

1. Значения из `@swagger_operation(...)`.
2. Значения из class-level metadata.
3. Auto-resolve через registry, только если `method + normalized_path` совпадает ровно с одной Swagger operation во всём corpus.

Decorator записывает metadata в `func.__swagger_binding__`. Он не меняет
поведение метода и не читает Swagger-файлы на import time. Повторная разметка
того же SDK method запрещена, а устаревшая metadata `__swagger_bindings__`
считается ошибкой.

## Operation identity

Primary key операции:

```text
spec + method + normalized_path
```

Нормализация:

- `method` приводится к uppercase;
- trailing slash удаляется, кроме `/`;
- path хранится в Swagger format: `/path/{param}`;
- path parameter aliases, отличающиеся только стилем записи (`userId`/`user_id`), нормализуются к имени описанного Swagger parameter;
- path остаётся case-sensitive;
- syntax path parameter кроме `{name}` запрещён.

`operation_id` является дополнительной проверкой. Он помогает поймать ошибочный binding, но не является primary identity.

## Expression mappings

`factory_args` и `method_args` описывают, как generated contract data превращается в вызов публичного SDK:

| Expression | Источник |
|---|---|
| `path.<name>` | path parameter Swagger operation |
| `query.<name>` | query parameter Swagger operation |
| `header.<name>` | header parameter Swagger operation |
| `body` | весь request body |
| `body.<field>` | поле request body |
| `body.<array>[].<field>` | поле элемента массива в request body |
| `body.<object>.<field>` | вложенное поле объекта в request body |
| `constant.<name>` | контролируемая тестовая константа |

Expressions не являются Python-кодом. Произвольные callables, dotted paths вне whitelist и transport/request DTO запрещены.

Текущая реализация валидирует `path.*`, `query.*`, `header.*`, наличие `requestBody` для `body`, body paths против request body `SwaggerSchema` и наличие `constant.*` в test constants registry. Body path grammar намеренно ограничена: `body.field`, `body.array[]`, `body.array[].field`, `body.object.field`. Для Swagger properties с camelCase/Pascal acronym naming registry также хранит SDK-style snake_case aliases, чтобы binding мог ссылаться на публичные Python-имена без потери schema-aware проверки.

Registry дополнительно строит normalized JSON schema tree для `requestBody` и всех Swagger responses: object properties, required fields, arrays, scalar JSON types, nullable, enum, `$ref`, `allOf`, `oneOf` и `anyOf`. Неразобранная JSON schema является contract failure, а не пропуском покрытия.

## Discovery

Discovery импортирует пакет `avito`, но не создаёт `AvitoClient`, не читает обязательные env vars и не делает сетевых вызовов. Сканируются публичные domain classes из `avito/<domain>/domain.py` и заранее описанные non-domain exceptions, например low-level auth token bindings.

Игнорируются:

- private methods;
- internal helpers;
- summary/helper methods на `AvitoClient`, если они не соответствуют одной конкретной upstream operation;
- low-level implementation methods без публичного domain binding, кроме
  явно задокументированных non-domain exceptions.

## Linter modes

Основные команды:

```bash
poetry run python scripts/lint_swagger_bindings.py
poetry run python scripts/lint_swagger_bindings.py --strict
poetry run python scripts/lint_swagger_bindings.py --json --strict --output swagger-bindings-report.json
make swagger-update
make swagger-lint
make swagger-coverage
```

Non-strict mode валидирует specs и уже найденные bindings. Strict mode
дополнительно требует, чтобы каждая Swagger operation имела ровно один binding,
каждый API-domain binding исполнялся через ровно один `OperationSpec`, method/path
этого `OperationSpec` совпадали со Swagger operation, а API-domain
`OperationSpec` без публичного binding отсутствовали. `make swagger-lint`
сначала скачивает свежие Swagger/OpenAPI files через `make swagger-update`,
затем запускает strict validation. `make swagger-coverage` дополнительно
запускает полный Swagger contract suite и входит в `make check`.

JSON report используется как стабильный machine-readable API для generated reference и coverage:

```json
{
  "summary": {
    "specs": 23,
    "operations_total": 204,
    "deprecated_operations": 7,
    "bound": 204,
    "unbound": 0,
    "duplicate": 0,
    "ambiguous": 0
  },
  "operations": [],
  "bindings": [],
  "factory_mapping": {},
  "errors": []
}
```

## Deprecated and legacy policy

Operation-level `deprecated: true` in Swagger requires:

- `deprecated=True` on binding;
- `legacy=True` on binding;
- runtime `DeprecationWarning` on the public SDK method through `deprecated_method(...)`.

`legacy=True` on a non-deprecated operation is forbidden unless a separate allowlist entry exists with a reason and removal date. Deprecated schema fields, properties and enum values do not create operation-level legacy requirements.

## Multi-operation SDK methods

The strict invariant is:

```text
each Swagger operation -> exactly one discovered binding
each discovered SDK method -> exactly one Swagger operation
```

One SDK method must not have multiple Swagger bindings. When a user-facing scenario has several upstream modes, the canonical bindings belong to separate documented SDK methods; compatibility wrappers may delegate to those methods but must not carry additional bindings.

## Contract tests

`SwaggerFakeTransport` uses discovered binding metadata to:

1. Build an `AvitoClient` with fake transport.
2. Create the correct domain object through `AvitoClient` factory and `factory_args`.
3. Call the public SDK method with `method_args`.
4. Match the actual HTTP request against Swagger method/path.
5. Validate required path/query/header parameters and request body/content type.
6. Validate actual JSON request bodies against Swagger keys and JSON types.
7. Generate Swagger-shaped success and error response bodies.
8. Return declared Swagger response statuses only.
9. Let normal SDK mapping and exception mapping run.

Contract tests must stay network-free. They are not a replacement for domain tests, but they catch binding drift: a method can be present in docs yet still fail contract invocation if factory args, method args, path, body or status handling are wrong.

The contract suite is exhaustive over the Swagger binding map:

- one request-contract case per discovered binding;
- one error-contract case per numeric Swagger error response;
- one schema-contract case per JSON request body;
- one schema-contract case per JSON success response model;
- one schema-contract case per JSON error response payload;
- deprecated operation bindings are included in the request set and additionally checked for runtime `DeprecationWarning`.

`SwaggerFakeTransport` provides deterministic generated SDK arguments. Schema
contract helpers in `avito/testing/swagger_schema.py` generate payloads from
Swagger schemas and compare actual SDK request payloads by field key and JSON
type. Missing generated arguments, missing `OperationSpec` models, unsupported
schema shapes and request/response/error payload mismatches are contract
failures, not allowlisted gaps.

## API method change checklist

When adding or changing a public API method that corresponds to Avito API:

1. Confirm the upstream operation in `docs/avito/api/*.json`.
2. Add or update the domain method, `OperationSpec`, request/query models, response models, and model-owned payload parsing.
3. Add `@swagger_operation(...)` on the public domain method without schemas/statuses/content types in the decorator.
4. Add or update class-level metadata if the domain class is new.
5. Document the public method through docstring so generated reference explains arguments, return model, pagination/dry-run/idempotency behavior and common exceptions.
6. Add focused domain tests with `FakeTransport`.
7. Add or adjust model tests when response parsing or serialization changes.
8. Ensure the binding is exercised by strict `make swagger-lint` and the exhaustive `SwaggerFakeTransport` contract tests.
9. Update user-facing docs when the method creates a new workflow, changes behavior, or introduces a non-obvious contract.

Minimum local verification for API-surface changes:

```bash
make swagger-lint
poetry run pytest tests/core/test_swagger*.py tests/contracts/test_swagger_contracts.py
poetry run pytest tests/domains/<domain>/
poetry run mypy avito
poetry run ruff check .
```

Before merging a complete API change, run:

```bash
make check
```
