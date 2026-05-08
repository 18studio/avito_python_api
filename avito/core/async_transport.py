"""Асинхронный transport-слой SDK поверх `httpx.AsyncClient`."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

import httpx

from avito.core import _transport_shared as shared
from avito.core._async_rate_limit import AsyncRateLimiter
from avito.core.exceptions import ResponseMappingError, TransportError
from avito.core.retries import RetryDecision
from avito.core.types import BinaryResponse, HttpMethod, RequestContext, TransportDebugInfo

if TYPE_CHECKING:
    from avito.auth.async_provider import AsyncAuthProvider
    from avito.config import AvitoSettings

_LOGGER = logging.getLogger("avito.transport")


class AsyncTransport:
    """Выполняет HTTP-запросы асинхронно, применяет retry и маппит ошибки API."""

    def __init__(
        self,
        settings: AvitoSettings,
        *,
        auth_provider: AsyncAuthProvider | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._auth_provider = auth_provider
        self._retry_policy = settings.retry_policy
        self._client = client or httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            timeout=shared.build_httpx_timeout(settings.timeouts),
        )
        self._sleep = sleep
        self._rate_limiter = AsyncRateLimiter(settings.retry_policy, sleep=sleep)
        self._user_agent = shared.build_user_agent(settings.user_agent_suffix)

    async def __aenter__(self) -> AsyncTransport:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    @property
    def auth_provider(self) -> AsyncAuthProvider | None:
        """Возвращает auth provider transport-слоя, если он настроен."""

        return self._auth_provider

    def debug_info(self) -> TransportDebugInfo:
        """Возвращает безопасный снимок transport-конфигурации без секретов."""

        return TransportDebugInfo(
            base_url=str(self._client.base_url),
            user_id=self._settings.user_id,
            requires_auth=self._auth_provider is not None,
            timeout_connect=self._settings.timeouts.connect,
            timeout_read=self._settings.timeouts.read,
            timeout_write=self._settings.timeouts.write,
            timeout_pool=self._settings.timeouts.pool,
            retry_max_attempts=self._retry_policy.max_attempts,
            retryable_methods=self._retry_policy.retryable_methods,
        )

    async def aclose(self) -> None:
        """Закрывает внутренний экземпляр `httpx.AsyncClient`."""

        await self._client.aclose()

    async def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """Выполняет запрос и возвращает успешный `httpx.Response`."""

        normalized_path = shared.normalize_path(path)
        bearer_token = (
            await self._auth_provider.get_access_token()
            if context.requires_auth and self._auth_provider is not None
            else None
        )
        request_headers = shared.merge_headers(
            context=context,
            headers=headers,
            idempotency_key=idempotency_key,
            user_agent=self._user_agent,
            bearer_token=bearer_token,
        )
        timeout = shared.build_httpx_timeout(context.timeout or self._settings.timeouts)
        attempt = 0
        unauthorized_refresh_used = False

        while True:
            attempt += 1
            limiter_delay = await self._rate_limiter.acquire()
            if limiter_delay > 0.0:
                _LOGGER.info(
                    "transport rate limit delay",
                    extra={
                        "operation": context.operation_name,
                        "endpoint": shared.safe_endpoint(normalized_path),
                        "method": method,
                        "attempt": attempt,
                        "delay_ms": int(limiter_delay * 1000),
                        "reason": "client_rate_limit",
                    },
                )
            try:
                started_at = time.perf_counter()
                response = await self._client.request(
                    method=method,
                    url=normalized_path,
                    params=shared.normalize_params(params),
                    json=json_body,
                    data=data,
                    files=shared.normalize_files(files),
                    headers=request_headers,
                    content=content,
                    timeout=timeout,
                )
                self._log_http_exchange(
                    operation=context.operation_name,
                    endpoint=normalized_path,
                    method=method,
                    attempt=attempt,
                    status=response.status_code,
                    latency_ms=shared.elapsed_ms(started_at),
                    request_id=shared.extract_request_id(response.headers),
                )
                self._rate_limiter.observe_response(headers=response.headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                self._log_http_exchange(
                    operation=context.operation_name,
                    endpoint=normalized_path,
                    method=method,
                    attempt=attempt,
                    status=None,
                    latency_ms=shared.elapsed_ms(started_at),
                    request_id=None,
                )
                decision = shared.decide_transport_retry(
                    retry_policy=self._retry_policy,
                    method=method,
                    attempt=attempt,
                    context=context,
                    is_timeout=isinstance(exc, httpx.TimeoutException),
                    idempotency_key=idempotency_key,
                )
                if decision.should_retry:
                    self._log_retry(
                        operation=context.operation_name,
                        endpoint=normalized_path,
                        method=method,
                        attempt=attempt,
                        status=None,
                        decision=decision,
                    )
                    await self._sleep(decision.delay_seconds)
                    continue
                raise TransportError(
                    str(exc),
                    operation=context.operation_name,
                    attempt=attempt,
                    method=method,
                    endpoint=shared.safe_endpoint(normalized_path),
                    metadata={"timeout": isinstance(exc, httpx.TimeoutException)},
                ) from exc

            if response.status_code == 401 and context.requires_auth and self._auth_provider is not None:
                if unauthorized_refresh_used:
                    raise shared.map_http_error(
                        response,
                        operation=context.operation_name,
                        attempt=attempt,
                    )
                unauthorized_refresh_used = True
                self._auth_provider.invalidate_token()
                refreshed_headers = dict(request_headers)
                refreshed_headers["Authorization"] = (
                    f"Bearer {await self._auth_provider.get_access_token()}"
                )
                request_headers = refreshed_headers
                continue

            if response.status_code == 429 or 500 <= response.status_code < 600:
                decision = shared.decide_http_retry(
                    retry_policy=self._retry_policy,
                    method=method,
                    attempt=attempt,
                    context=context,
                    response=response,
                    idempotency_key=idempotency_key,
                )
                if decision.should_retry:
                    self._log_retry(
                        operation=context.operation_name,
                        endpoint=normalized_path,
                        method=method,
                        attempt=attempt,
                        status=response.status_code,
                        decision=decision,
                    )
                    await self._sleep(decision.delay_seconds)
                    continue
                raise shared.map_http_error(
                    response,
                    operation=context.operation_name,
                    attempt=attempt,
                )

            if response.is_error:
                raise shared.map_http_error(
                    response,
                    operation=context.operation_name,
                    attempt=attempt,
                )
            return response

    async def request_json(
        self,
        method: HttpMethod,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> object:
        """Выполняет запрос и возвращает JSON-ответ."""

        response = await self.request(
            method,
            path,
            context=context,
            params=params,
            json_body=json_body,
            data=data,
            files=files,
            headers=headers,
            idempotency_key=idempotency_key,
        )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ResponseMappingError(
                "Ответ API не является корректным JSON.",
                status_code=response.status_code,
                operation=context.operation_name,
                metadata={"content_type": response.headers.get("content-type")},
                payload=response.text,
                headers=dict(response.headers),
            ) from exc

    async def download_binary(
        self,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> BinaryResponse:
        """Выполняет запрос и возвращает полный бинарный ответ."""

        response = await self.request("GET", path, context=context, params=params, headers=headers)
        content = await response.aread()
        return BinaryResponse(
            content=content,
            content_type=response.headers.get("content-type"),
            filename=shared.extract_filename(response.headers.get("content-disposition")),
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    def _log_retry(
        self,
        *,
        operation: str,
        endpoint: str,
        method: str,
        attempt: int,
        status: int | None,
        decision: RetryDecision,
    ) -> None:
        _LOGGER.info(
            "transport retry",
            extra={
                "operation": operation,
                "endpoint": shared.safe_endpoint(endpoint),
                "method": method,
                "attempt": attempt,
                "status": status,
                "delay_ms": int(decision.delay_seconds * 1000),
                "reason": decision.reason,
            },
        )

    def _log_http_exchange(self, **extra: object) -> None:
        _LOGGER.debug(
            "transport http exchange",
            extra={**extra, "endpoint": shared.safe_endpoint(str(extra["endpoint"]))},
        )


__all__ = ("AsyncTransport",)
