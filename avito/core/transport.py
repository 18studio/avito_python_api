"""Единый transport-слой SDK поверх `httpx.Client`."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import json
import logging
import platform
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from io import BytesIO
from typing import TYPE_CHECKING, cast
from urllib.parse import quote, urlsplit

import httpx

from avito.core import _transport_shared as shared
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    ResponseMappingError,
    TransportError,
    UnsupportedOperationError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.rate_limit import RateLimiter
from avito.core.retries import RetryDecision
from avito.core.types import (
    ApiTimeouts,
    BinaryResponse,
    HttpMethod,
    RequestContext,
    TransportDebugInfo,
)

if TYPE_CHECKING:
    from avito.auth.provider import AuthProvider
    from avito.config import AvitoSettings

QueryScalar = str | int | float | bool | None
QueryParamValue = QueryScalar | Sequence[QueryScalar]
QueryParams = Mapping[str, QueryParamValue]
FileValue = (
    BytesIO
    | bytes
    | str
    | tuple[str | None, BytesIO | bytes | str]
    | tuple[str | None, BytesIO | bytes | str, str | None]
    | tuple[str | None, BytesIO | bytes | str, str | None, Mapping[str, str]]
)
RequestFiles = Mapping[str, FileValue]
_MIN_RETRY_AFTER_SECONDS = 0.5
_LOGGER = logging.getLogger("avito.transport")


def build_httpx_timeout(timeouts: ApiTimeouts) -> httpx.Timeout:
    """Преобразует SDK-конфигурацию таймаутов в `httpx.Timeout`."""

    return shared.build_httpx_timeout(timeouts)


class Transport:
    """Выполняет HTTP-запросы, применяет retry и маппит ошибки API."""

    def __init__(
        self,
        settings: AvitoSettings,
        *,
        auth_provider: AuthProvider | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Initialize Transport."""
        self._settings = settings
        self._auth_provider = auth_provider
        self._retry_policy = settings.retry_policy
        self._client = client or httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            timeout=build_httpx_timeout(settings.timeouts),
        )
        self._sleep = sleep
        self._rate_limiter = RateLimiter(settings.retry_policy, sleep=sleep)
        self._user_agent = self._build_user_agent()

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

    @property
    def auth_provider(self) -> AuthProvider | None:
        """Возвращает auth provider transport-слоя, если он настроен."""

        return self._auth_provider

    def close(self) -> None:
        """Закрывает внутренний экземпляр `httpx.Client`."""

        self._client.close()

    def request(
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

        normalized_path = self._normalize_path(path)
        bearer_token = (
            self._auth_provider.get_access_token()
            if context.requires_auth and self._auth_provider is not None
            else None
        )
        request_headers = self._merge_headers(
            context=context,
            headers=headers,
            idempotency_key=idempotency_key,
            bearer_token=bearer_token,
        )
        timeout = build_httpx_timeout(context.timeout or self._settings.timeouts)
        attempt = 0
        unauthorized_refresh_used = False

        while True:
            attempt += 1
            limiter_delay = self._rate_limiter.acquire()
            if limiter_delay > 0.0:
                _LOGGER.info(
                    "transport rate limit delay",
                    extra={
                        "operation": context.operation_name,
                        "endpoint": self._safe_endpoint(normalized_path),
                        "method": method,
                        "attempt": attempt,
                        "delay_ms": int(limiter_delay * 1000),
                        "reason": "client_rate_limit",
                    },
                )
            try:
                started_at = time.perf_counter()
                response = self._client.request(
                    method=method,
                    url=normalized_path,
                    params=self._normalize_params(params),
                    json=json_body,
                    data=data,
                    files=self._normalize_files(files),
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
                    latency_ms=self._elapsed_ms(started_at),
                    request_id=self._extract_request_id(response.headers),
                )
                self._rate_limiter.observe_response(
                    headers=response.headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                self._log_http_exchange(
                    operation=context.operation_name,
                    endpoint=normalized_path,
                    method=method,
                    attempt=attempt,
                    status=None,
                    latency_ms=self._elapsed_ms(started_at),
                    request_id=None,
                )
                decision = self._decide_transport_retry(
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
                    self._sleep(decision.delay_seconds)
                    continue
                raise TransportError(
                    str(exc),
                    operation=context.operation_name,
                    attempt=attempt,
                    method=method,
                    endpoint=self._safe_endpoint(normalized_path),
                    metadata={"timeout": isinstance(exc, httpx.TimeoutException)},
                ) from exc

            if (
                response.status_code == 401
                and context.requires_auth
                and self._auth_provider is not None
            ):
                if unauthorized_refresh_used:
                    raise self._map_http_error(
                        response,
                        operation=context.operation_name,
                        attempt=attempt,
                    )
                unauthorized_refresh_used = True
                self._auth_provider.invalidate_token()
                refreshed_headers = dict(request_headers)
                refreshed_headers["Authorization"] = (
                    f"Bearer {self._auth_provider.get_access_token()}"
                )
                request_headers = refreshed_headers
                continue

            if response.status_code == 429:
                decision = self._decide_http_retry(
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
                    self._sleep(decision.delay_seconds)
                    continue
                raise self._map_http_error(
                    response,
                    operation=context.operation_name,
                    attempt=attempt,
                )

            if 500 <= response.status_code < 600:
                decision = self._decide_http_retry(
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
                    self._sleep(decision.delay_seconds)
                    continue
                raise self._map_http_error(
                    response,
                    operation=context.operation_name,
                    attempt=attempt,
                )

            if response.is_error:
                raise self._map_http_error(
                    response,
                    operation=context.operation_name,
                    attempt=attempt,
                )

            return response

    def request_json(
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

        response = self.request(
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

    def download_binary(
        self,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> BinaryResponse:
        """Выполняет запрос и возвращает бинарный ответ."""

        response = self.request(
            "GET",
            path,
            context=context,
            params=params,
            headers=headers,
        )
        return BinaryResponse(
            content=response.content,
            content_type=response.headers.get("content-type"),
            filename=self._extract_filename(response.headers.get("content-disposition")),
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    def _normalize_path(self, path: str) -> str:
        """Normalize path."""
        stripped = path.strip()
        if not stripped:
            return "/"
        if stripped.startswith("http://") or stripped.startswith("https://"):
            return stripped
        has_trailing_slash = stripped.endswith("/")
        segments = [
            quote(segment, safe=":@%") for segment in stripped.strip("/").split("/") if segment
        ]
        normalized = "/" + "/".join(segments)
        if has_trailing_slash and normalized != "/":
            normalized += "/"
        return normalized

    def _normalize_params(self, params: Mapping[str, object] | None) -> QueryParams | None:
        """Normalize params."""
        if params is None:
            return None
        normalized: dict[str, QueryParamValue] = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                normalized[key] = [self._normalize_query_scalar(item) for item in value]
            else:
                normalized[key] = self._normalize_query_scalar(value)
        return normalized

    def _normalize_query_scalar(self, value: object) -> QueryScalar:
        """Normalize query scalar."""
        if isinstance(value, str | int | float | bool):
            return value
        return str(value)

    def _normalize_files(self, files: Mapping[str, object] | None) -> RequestFiles | None:
        """Normalize files."""
        if files is None:
            return None
        return {key: self._normalize_file_value(value) for key, value in files.items()}

    def _normalize_file_value(self, value: object) -> FileValue:
        """Normalize file value."""
        if isinstance(value, bytes | str | BytesIO):
            return value
        if isinstance(value, tuple):
            return value
        raise TypeError("Неподдерживаемый тип файла для multipart upload.")

    def _merge_headers(
        self,
        *,
        context: RequestContext,
        headers: Mapping[str, str] | None,
        idempotency_key: str | None,
        bearer_token: str | None,
    ) -> dict[str, str]:
        """Run the merge headers helper."""
        return shared.merge_headers(
            context=context,
            headers=headers,
            idempotency_key=idempotency_key,
            user_agent=self._user_agent,
            bearer_token=bearer_token,
        )

    def _build_user_agent(self) -> str:
        """Build user agent."""
        try:
            package_version = importlib_metadata.version("avito-py")
        except importlib_metadata.PackageNotFoundError:
            package_version = "0+unknown"
        user_agent = (
            f"avito-py/{package_version} "
            f"python/{platform.python_version()} "
            f"httpx/{httpx.__version__}"
        )
        if self._settings.user_agent_suffix is not None:
            user_agent += f" {self._settings.user_agent_suffix}"
        return user_agent

    def _decide_transport_retry(
        self,
        *,
        method: str,
        attempt: int,
        context: RequestContext,
        is_timeout: bool,
        idempotency_key: str | None,
    ) -> RetryDecision:
        """Decide transport retry."""
        if attempt >= self._retry_policy.max_attempts:
            return RetryDecision(False)
        if not self._retry_policy.retry_on_transport_error:
            return RetryDecision(False)
        if not self._is_retryable_request(
            method=method,
            context=context,
            idempotency_key=idempotency_key,
        ):
            return RetryDecision(False)
        return RetryDecision(
            True,
            reason="timeout" if is_timeout else "transport_error",
            delay_seconds=self._retry_policy.compute_backoff(attempt),
        )

    def _decide_http_retry(
        self,
        *,
        method: str,
        attempt: int,
        context: RequestContext,
        response: httpx.Response,
        idempotency_key: str | None,
    ) -> RetryDecision:
        """Decide http retry."""
        if attempt >= self._retry_policy.max_attempts:
            return RetryDecision(False)
        if not self._is_retryable_request(
            method=method,
            context=context,
            idempotency_key=idempotency_key,
        ):
            return RetryDecision(False)
        if response.status_code == 429:
            if not self._retry_policy.retry_on_rate_limit:
                return RetryDecision(False)
            delay = self._get_retry_after_seconds(response.headers)
            if response.headers.get("retry-after") is None:
                delay = self._retry_policy.compute_backoff(attempt)
            if delay > self._retry_policy.max_rate_limit_wait_seconds:
                return RetryDecision(False)
            return RetryDecision(True, reason="rate_limit", delay_seconds=delay)
        if 500 <= response.status_code < 600 and self._retry_policy.retry_on_server_error:
            return RetryDecision(
                True,
                reason="server_error",
                delay_seconds=self._retry_policy.compute_backoff(attempt),
            )
        return RetryDecision(False)

    def _is_retryable_request(
        self,
        *,
        method: str,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> bool:
        """Return whether retryable request."""
        if context.retry_disabled:
            return False
        normalized_method = method.upper()
        if normalized_method in {"POST", "PATCH"} and idempotency_key is None:
            return False
        if (
            normalized_method == "DELETE"
            and idempotency_key is None
            and not context.allow_retry
        ):
            return False
        return self._retry_policy.is_retryable_method(
            normalized_method,
            explicit_retry=context.allow_retry,
        )

    def _map_http_error(
        self,
        response: httpx.Response,
        *,
        operation: str | None = None,
        attempt: int | None = None,
    ) -> Exception:
        """Map http error."""
        payload = self._safe_payload(response)
        message = self._extract_message(payload) or f"HTTP {response.status_code}"
        error_code = self._extract_error_code(payload)
        details = self._extract_error_details(payload)
        retry_after = (
            self._get_retry_after_seconds(response.headers) if response.status_code == 429 else None
        )
        request_id = self._extract_request_id(response.headers)
        headers = dict(response.headers)
        method = response.request.method
        endpoint = response.request.url.path
        metadata = {
            "method": method,
            "path": endpoint,
        }

        if response.status_code == 401:
            return AuthenticationError(
                message,
                status_code=401,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        if response.status_code == 403:
            return AuthorizationError(
                message,
                status_code=403,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        if response.status_code in {400, 422}:
            return ValidationError(
                message,
                status_code=response.status_code,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        if response.status_code == 409:
            return ConflictError(
                message,
                status_code=409,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        if response.status_code == 429:
            return RateLimitError(
                message,
                status_code=429,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        if response.status_code in {405, 501}:
            return UnsupportedOperationError(
                message,
                status_code=response.status_code,
                error_code=error_code,
                operation=operation,
                attempt=attempt,
                method=method,
                endpoint=endpoint,
                details=details,
                retry_after=retry_after,
                request_id=request_id,
                metadata=metadata,
                payload=payload,
                headers=headers,
            )
        return UpstreamApiError(
            message,
            status_code=response.status_code,
            error_code=error_code,
            operation=operation,
            attempt=attempt,
            method=method,
            endpoint=endpoint,
            details=details,
            retry_after=retry_after,
            request_id=request_id,
            metadata=metadata,
            payload=payload,
            headers=headers,
        )

    def _safe_payload(self, response: httpx.Response) -> object:
        """Return a safe payload."""
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
        return response.text

    def _extract_message(self, payload: object) -> str | None:
        """Extract message."""
        if isinstance(payload, dict):
            for key in ("message", "error_description", "error", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
        if isinstance(payload, str) and payload:
            return payload
        return None

    def _extract_error_code(self, payload: object) -> str | None:
        """Extract error code."""
        if not isinstance(payload, dict):
            return None
        value = payload.get("code") or payload.get("error")
        return value if isinstance(value, str) else None

    def _extract_error_details(self, payload: object) -> object | None:
        """Extract error details."""
        if not isinstance(payload, Mapping):
            return None
        for key in ("details", "fields", "errors", "violations"):
            value = payload.get(key)
            if value is not None:
                return cast(object, value)
        return None

    def _extract_request_id(self, headers: Mapping[str, str]) -> str | None:
        """Extract request id."""
        for key in ("x-request-id", "x-correlation-id", "x-amzn-requestid"):
            value = headers.get(key)
            if value:
                return value
        return None

    def _get_retry_after_seconds(self, headers: Mapping[str, str]) -> float:
        """Return retry after seconds."""
        raw_value = headers.get("retry-after")
        if raw_value is None:
            return _MIN_RETRY_AFTER_SECONDS
        try:
            return max(float(raw_value), 0.0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(raw_value)
            except (TypeError, ValueError):
                return _MIN_RETRY_AFTER_SECONDS
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)

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
        """Log retry."""
        _LOGGER.info(
            "transport retry",
            extra={
                "operation": operation,
                "endpoint": self._safe_endpoint(endpoint),
                "method": method,
                "attempt": attempt,
                "status": status,
                "delay_ms": int(decision.delay_seconds * 1000),
                "reason": decision.reason,
            },
        )

    def _log_http_exchange(
        self,
        *,
        operation: str,
        endpoint: str,
        method: str,
        attempt: int,
        status: int | None,
        latency_ms: int,
        request_id: str | None,
    ) -> None:
        """Log http exchange."""
        _LOGGER.debug(
            "transport http exchange",
            extra={
                "operation": operation,
                "endpoint": self._safe_endpoint(endpoint),
                "method": method,
                "attempt": attempt,
                "status": status,
                "latency_ms": latency_ms,
                "request_id": request_id,
            },
        )

    def _elapsed_ms(self, started_at: float) -> int:
        """Return elapsed ms."""
        return max(int((time.perf_counter() - started_at) * 1000), 0)

    def _safe_endpoint(self, endpoint: str) -> str:
        """Return a safe endpoint."""
        parsed = urlsplit(endpoint)
        if parsed.scheme or parsed.netloc:
            return parsed.path or "/"
        return endpoint

    def _extract_filename(self, content_disposition: str | None) -> str | None:
        """Extract filename."""
        if content_disposition is None:
            return None
        message = Message()
        message["content-disposition"] = content_disposition
        filename = message.get_param("filename", header="content-disposition")
        if isinstance(filename, tuple):
            _, _, decoded_value = filename
            return decoded_value
        return filename


__all__ = ("Transport", "build_httpx_timeout")
