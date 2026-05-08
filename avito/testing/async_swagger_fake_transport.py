"""Async Swagger-aware fake transport placeholder for async contract tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import httpx

from avito.async_client import AsyncAvitoClient
from avito.auth import AuthSettings
from avito.auth.async_token_client import AsyncAlternateTokenClient, AsyncTokenClient
from avito.core.swagger_discovery import DiscoveredSwaggerBinding
from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry
from avito.testing.async_fake_transport import AsyncFakeTransport
from avito.testing.fake_transport import JsonValue, RecordedRequest
from avito.testing.swagger_fake_transport import SwaggerFakeTransport, SwaggerRoute, success_payload


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
        self._sync_helper = SwaggerFakeTransport(registry=registry, base_url=base_url)
        self._swagger_routes: dict[str, SwaggerRoute] = self._sync_helper._swagger_routes

    def add_operation(
        self,
        operation_key: str,
        payload: JsonValue,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncSwaggerFakeTransport:
        """Register response for one Swagger operation key."""

        self._sync_helper.add_operation(
            operation_key,
            payload,
            status_code=status_code,
            headers=headers,
        )
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

        return self._sync_helper.operation(operation_key)

    async def invoke_binding(
        self,
        binding: DiscoveredSwaggerBinding,
        *,
        client: AsyncAvitoClient | None = None,
    ) -> object:
        """Build and invoke async SDK call from discovered Swagger binding metadata."""

        if binding.operation_key is None:
            raise AssertionError(f"Привязка Swagger неоднозначна: {binding.sdk_method}")
        if binding.domain == "auth":
            target = self._build_auth_target(binding)
            method = getattr(target, binding.method_name)
            return await method(**self._build_arguments(binding.method_args, method))
        sdk_client = client or self.as_client(user_id=7)
        target = self._build_target(sdk_client, binding)
        method = getattr(target, binding.method_name)
        return await method(**self._build_arguments(binding.method_args, method))

    async def _handle_recorded(self, request: httpx.Request) -> httpx.Response:
        async with self._handle_lock:
            recorded = RecordedRequest(
                method=request.method.upper(),
                path=request.url.path,
                params=dict(request.url.params),
                headers=dict(request.headers),
                json_body=self._decode_json(request),
                content=request.content,
            )
            self.requests.append(recorded)

            route = self._match_route(recorded)
            self._validate_request(route.operation, recorded)
            response = httpx.Response(
                route.status_code,
                json=route.payload,
                headers=dict(route.headers),
            )
            response.request = request
            return response

    def _build_target(
        self,
        client: AsyncAvitoClient,
        binding: DiscoveredSwaggerBinding,
    ) -> object:
        if binding.factory is None:
            raise AssertionError(f"Binding не содержит AsyncAvitoClient factory: {binding.sdk_method}")
        factory = getattr(client, binding.factory)
        return factory(**self._build_arguments(binding.factory_args, factory))

    def _build_auth_target(self, binding: DiscoveredSwaggerBinding) -> object:
        settings = AuthSettings(
            client_id="fake-client-id",
            client_secret="fake-client-secret",
            refresh_token="fake-refresh-token",
            scope="fake-scope",
            token_url=binding.path,
            alternate_token_url=binding.path,
            autoteka_token_url="/token",
            autoteka_client_id="fake-autoteka-client-id",
            autoteka_client_secret="fake-autoteka-client-secret",
            autoteka_scope="autoteka:read",
        )
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(self._handle),
            base_url=self.base_url,
        )
        if binding.class_name == "AsyncAlternateTokenClient":
            return AsyncAlternateTokenClient(settings=settings, client=client)
        if binding.class_name == "AsyncTokenClient":
            return AsyncTokenClient(settings=settings, client=client)
        raise AssertionError(f"Неподдерживаемый async auth binding: {binding.sdk_method}")

    def _build_arguments(
        self,
        mapping: Mapping[str, str],
        callable_object: Callable[..., object],
    ) -> dict[str, object]:
        return self._sync_helper._build_arguments(mapping, callable_object)

    def _match_route(self, request: RecordedRequest) -> SwaggerRoute:
        return self._sync_helper._match_route(request)

    def _validate_request(self, operation: SwaggerOperation, request: RecordedRequest) -> None:
        self._sync_helper._validate_request(operation, request)


__all__ = ("AsyncSwaggerFakeTransport",)
