# Pre-flight Async M1

Generated: 2026-05-08

Repository HEAD: `b633764633b1fa79f537dbe2955dc91614e1caf8`

This artifact records the local pre-flight required before PR M1 of the dual-mode SDK
plan. The goal is provenance, not implementation: it captures the current sync-only
state, known probes, baseline hashes, and the resolver smoke decision.

## Environment

```yaml
python_requires: ">=3.12,<4.0"
python_runtime: "3.14.0 (main, Oct 28 2025, 12:11:51) [Clang 20.1.4 ]"
pytest: "8.4.2"
httpx: "0.28.1"
poetry_lock_sha256: "08a6425ee9317b1b9074184ee1e03f0f57ff793c5b37ade73cdc33316246e7b3"
```

`pyproject.toml` currently has no `pytest-asyncio`, `asyncio_mode`,
`asyncio_default_fixture_loop_scope`, or `filterwarnings` entries. M1 must add the
asyncio pytest settings described in `todo.md`.

## Private Auth Cache Probes

Command:

```bash
rg -n "\._access_token|\._refresh_token|\._autoteka_access_token" tests
```

Result:

```text
tests/core/test_authentication.py:123:    provider._access_token = replace(
tests/core/test_authentication.py:124:        provider._access_token,  # type: ignore[arg-type, attr-defined]
```

Decision: the M1 `AuthProvider` property shim for `_access_token` is sufficient for
the current test suite. There are no direct `_refresh_token` or
`_autoteka_access_token` probes in `tests/` today, but the planned shims can still cover
all three fields for compatibility.

## Paginator Usage

Command:

```bash
rg -n "\bPaginator\b" avito
```

Domain call sites:

```text
avito/accounts/domain.py:170:        return Paginator(fetch_page).as_list(first_page=fetch_page(1, None))
avito/accounts/domain.py:383:        return Paginator(fetch_page).as_list(first_page=fetch_page(1, None))
avito/ads/domain.py:266:        return Paginator(
avito/ads/domain.py:1183:        return Paginator(fetch_page).as_list(first_page=fetch_page(1, None))
```

Infrastructure/import references also found:

```text
avito/accounts/domain.py:36:    Paginator,
avito/ads/domain.py:76:    Paginator,
avito/core/pagination.py:183:class Paginator[ItemT]:
avito/core/pagination.py:230:__all__ = ("PaginatedList", "Paginator", "PageFetcher")
avito/core/__init__.py:21:from avito.core.pagination import PaginatedList, Paginator
avito/core/__init__.py:55:    "Paginator",
```

Decision: current public domain usage ends in `.as_list(...)`; there is no direct
public domain return of `Paginator`.

## PaginatedList List-API Consumers

Broad command used to find list-like consumers around current pagination tests and
domains:

```bash
rg -n "\bPaginatedList\b|\bPaginator\b|\.materialize\(\)|\[[0-9]+\]" \
  avito/accounts/domain.py avito/ads/domain.py \
  tests/domains/accounts/test_accounts.py tests/domains/ads/test_ads.py \
  tests/core/test_transport.py tests/contracts/test_swagger_contracts.py
```

Relevant runtime/list-API observations:

```text
tests/domains/accounts/test_accounts.py:56:    assert len(history.materialize()) == 1
tests/domains/accounts/test_accounts.py:57:    assert history[0].operation_type == "payment"
tests/domains/accounts/test_accounts.py:126:    assert items[0].title == "Объявление"
tests/domains/ads/test_ads.py:39:    assert items[3].item_id == 104
tests/domains/ads/test_ads.py:41:    assert [item.title for item in items.materialize()] == [
tests/domains/ads/test_ads.py:70:    assert [item.item_id for item in items.materialize()] == [101, 102, 103]
tests/domains/ads/test_ads.py:90:    assert [item.item_id for item in items.materialize()] == list(range(101, 126))
tests/core/test_transport.py:752:    assert items[0] == 1
tests/core/test_transport.py:753:    assert items[3] == 4
tests/core/test_transport.py:756:    assert items.materialize() == [1, 2, 3, 4, 5]
tests/core/test_transport.py:765:    assert empty.materialize() == []
tests/core/test_transport.py:774:        _ = items[2]
tests/contracts/test_swagger_contracts.py:335:    assert isinstance(result, PaginatedList)
tests/contracts/test_swagger_contracts.py:336:    assert isinstance(result[0], EmployeeItem)
```

Decision: async doubles must replace direct indexing/length assumptions with
`await materialize()` or `loaded_count` where the behavior is ported. Existing sync-only
tests stay unchanged.

## Existing Async Tests

Command:

```bash
rg -n "^async def test_" tests
```

Result: no matches.

Decision: enabling `asyncio_mode = "strict"` in M1 will not newly skip any existing
async tests, because none exist today.

## Deprecated Public Methods

Command:

```bash
rg -n "@deprecated_method|deprecated_method\(" avito/cpa avito/ads
```

Result:

```text
avito/cpa/domain.py:491:    @deprecated_method(
avito/cpa/domain.py:541:    @deprecated_method(
avito/cpa/domain.py:585:    @deprecated_method(
avito/ads/domain.py:1416:    @deprecated_method(
avito/ads/domain.py:1457:    @deprecated_method(
avito/ads/domain.py:1523:    @deprecated_method(
avito/ads/domain.py:1558:    @deprecated_method(
```

Decision: the plan's expected count is current: 3 in `cpa`, 4 in `ads`, 7 total.
M1 must make `deprecated_method` async-aware before M6/M11.

## OperationSpec Resolver Smoke

Smoke:

```python
from avito.core.operations import OperationSpec

SOME_SPEC = OperationSpec(name="smoke", method="GET", path="/smoke")

class AsyncSmokeDomain:
    async def m(self):
        return await self._execute(SOME_SPEC)
```

Runner result:

```text
pass
1
smoke
```

Decision: `_operation_specs_for_sdk_method` currently resolves an async method's
module-level `SOME_SPEC` through `inspect.unwrap(method).__globals__`. M1 does not need
the AST fallback or class-level `__operation_specs__` fallback unless later edits change
this behavior.

## Reference Builder Join Points

Current state of `docs/site/assets/_gen_reference.py`:

```yaml
public_domain_packages: "PACKAGE_ROOT.glob(\"*/domain.py\")"
excluded_packages: ["auth", "core", "testing"]
public_domain_classes:
  imports: "avito.<package>"
  source: "__all__"
  class_filter: "issubclass(value, DomainObject)"
  module_filter: "value.__module__.startswith(f\"avito.{package}.\")"
public_domain_methods:
  predicate: "inspect.isfunction"
  public_filter: "not name.startswith(\"_\")"
  qualname_filter: "value.__qualname__.startswith(f\"{domain_class.__name__}.\")"
write_domain_pages: "writes one mkdocstrings directive: ::: avito.<package>"
```

Decision: M1 must extend this to import `domain.py` and `async_domain.py` directly,
filter `AsyncDomainObject` descendants, and write explicit class directives in sync
class -> async class order.

## Architecture And Docstring Linter Join Points

Current state of `scripts/lint_architecture.py`:

```yaml
public_domain_method_paths: "avito/<domain>/domain.py only"
public_method_ast_node: "ast.FunctionDef only"
collect_domain_class_methods: "ast.FunctionDef only"
```

Current state of `scripts/lint_docstrings.py`:

```yaml
paths: "sorted((root / \"avito\").glob(\"*/domain.py\"))"
public_method_ast_node: "ast.FunctionDef only"
```

Decision: M1 must include `async_domain.py` and treat `ast.AsyncFunctionDef` as
equivalent for public async methods and model serializer method collection where relevant.

## Deprecation Wrapper Join Point

Current `avito/core/deprecation.py::deprecated_method` always returns a sync
`wrapped(*args, **kwargs)` and directly returns `method(*args, **kwargs)`.

Decision: M1 must branch on coroutine functions and return an `async def` wrapper that
awaits the original method while preserving `__sdk_deprecation__`.

## Swagger Factory Join Point

Current `avito/core/swagger_linter.py::_validate_factory` behavior:

```yaml
auth_binding_without_factory: "skipped only when binding.domain == \"auth\" and factory is None"
non_auth_without_factory: "SWAGGER_BINDING_FACTORY_MISSING"
factory_lookup: "getattr(AvitoClient, binding.factory, None)"
factory_not_callable: "SWAGGER_BINDING_FACTORY_NOT_FOUND"
signature_check: "_validate_signature_mapping(..., mapping=binding.factory_args)"
variant_awareness: "none"
```

Decision: M1 must make this variant-aware and class-gated for async bindings, while
preserving current sync behavior.

## Baseline

The exact command from `todo.md` failed because this repository currently has no
`tests/auth` directory:

```text
ERROR: file or directory not found: tests/auth
```

Adjusted collection command:

```bash
poetry run pytest --collect-only -q tests/core tests/domains tests/contracts | rg '::' > /tmp/baseline_nodeids.txt
```

Adjusted baseline execution passed by passing nodeids as exact subprocess argv entries,
because parametrized nodeids include spaces and `$(cat /tmp/baseline_nodeids.txt)` splits
them incorrectly:

```text
2070 passed in 10.85s
```

Baseline files:

```yaml
baseline_nodeids:
  path: "/tmp/baseline_nodeids.txt"
  line_count: 2070
  sha256: "373a692216014e9a3cae5c57ccb4e1ca14f94fcf06c484ae8602b141df53a6d9"
baseline_main:
  path: "/tmp/baseline_main.txt"
  sha256: "1820f9dccbad66227dcf5281ab22333c5c7b6ef2ea2df5c0f1fa0cd858c09023"
  result: "2070 passed in 10.85s"
```

Decision: use these adjusted baseline hashes for M1 sync-regression comparison unless
`tests/auth` is created before the M1 branch starts. If that happens, rerun pre-flight and
update this artifact.
