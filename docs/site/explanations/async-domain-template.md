# Async Domain Template

Async-домен добавляется как `avito/<domain>/async_domain.py` рядом с sync `domain.py`.
Файл содержит `Async<X>(AsyncDomainObject)` для каждого портированного sync-класса.

Минимальный шаблон:

```python
from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride
from avito.core.domain import AsyncDomainObject
from avito.core.swagger import swagger_operation
from avito.<domain>.models import ResultModel
from avito.<domain>.operations import GET_RESULT


@dataclass(slots=True, frozen=True)
class AsyncExample(AsyncDomainObject):
    __swagger_domain__ = "example"
    __sdk_factory__ = "example"
    __sdk_factory_args__ = {"item_id": "path.item_id"}

    item_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/example/{item_id}",
        spec="Example.json",
        operation_id="getExample",
        variant="async",
    )
    async def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> ResultModel:
        return await self._execute(
            GET_RESULT,
            path_params={"item_id": self.item_id},
            timeout=timeout,
            retry=retry,
        )
```

Checklist for each domain port:

- Mirror every public sync method with `async def`.
- Keep class metadata equal to the sync class: `__swagger_domain__`, `__sdk_factory__`,
  and `__sdk_factory_args__`.
- Use the same `OperationSpec`, request/query DTOs, and response models as the sync domain.
- Add `@swagger_operation(..., variant="async")`; do not duplicate schema details in the decorator.
- Return `AsyncPaginatedList[T]` only where the sync method returns `PaginatedList[T]`.
- Export `Async<X>` from `avito/<domain>/__init__.py`.
- Add the matching `AsyncAvitoClient.<factory>()` method when the sync factory exists.
- Add async tests for the golden path and async risks: mapped HTTP errors, retry/rate limit
  behavior where relevant, and transport errors.
- Run `make async-parity-lint`, `make swagger-lint`, the domain tests, and async contracts.

PoC notes from `tariffs`:

- The first real `async_domain.py` exposed that `public_domain_packages()` must deduplicate
  packages when both `domain.py` and `async_domain.py` exist.
- Reference generation must import `domain.py` and `async_domain.py` directly and write separate
  mkdocstrings directives in sync then async order.
