"""Async Swagger-aware fake transport placeholder for async contract tests."""

from __future__ import annotations

from collections.abc import Mapping

from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry
from avito.testing.async_fake_transport import AsyncFakeTransport
from avito.testing.fake_transport import JsonValue
from avito.testing.swagger_fake_transport import SwaggerRoute, success_payload


class AsyncSwaggerFakeTransport(AsyncFakeTransport):
    """Async fake transport that registers routes by Swagger operation key."""

    def __init__(
        self,
        *,
        registry: SwaggerRegistry,
        base_url: str = "https://api.avito.ru",
    ) -> None:
        super().__init__(base_url=base_url)
        self.registry = registry
        self._swagger_routes: dict[str, SwaggerRoute] = {}

    def add_operation(
        self,
        operation_key: str,
        payload: JsonValue,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncSwaggerFakeTransport:
        """Register response for one Swagger operation key."""

        operation = self.operation(operation_key)
        self._swagger_routes[operation.key] = SwaggerRoute(
            operation=operation,
            payload=payload,
            status_code=status_code,
            headers=dict(headers or {}),
        )
        self.add_json(operation.method, operation.path, payload, status_code=status_code)
        return self

    def add_success_operation(
        self,
        operation_key: str,
        *,
        payload: JsonValue | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncSwaggerFakeTransport:
        """Register a deterministic success response for one Swagger operation."""

        operation = self.operation(operation_key)
        status_code = int(operation.responses[0].status_code)
        return self.add_operation(
            operation_key,
            success_payload(operation) if payload is None else payload,
            status_code=status_code,
            headers=headers,
        )

    def operation(self, operation_key: str) -> SwaggerOperation:
        """Return operation by key or raise an assertion error."""

        for operation in self.registry.operations:
            if operation.key == operation_key:
                return operation
        raise AssertionError(f"Swagger operation not found: {operation_key}")


__all__ = ("AsyncSwaggerFakeTransport",)
