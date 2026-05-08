"""Shared pure helpers for sync and async transport implementations."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import json
import platform
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from io import BytesIO
from typing import cast
from urllib.parse import quote, urlsplit

import httpx

from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AvitoError,
    ConflictError,
    RateLimitError,
    UnsupportedOperationError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.retries import RetryDecision, RetryPolicy
from avito.core.types import ApiTimeouts, RequestContext

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


@dataclass(slots=True)
class RateLimitState:
    """Pure token-bucket state shared by sync and async rate limiters."""

    enabled: bool
    rate: float
    capacity: int
    tokens: float
    updated_at: float
    blocked_until: float = 0.0

    @classmethod
    def from_policy(cls, policy: RetryPolicy, *, now: float) -> RateLimitState:
        """Build rate limit state from retry policy settings."""
        capacity = max(policy.rate_limit_burst, 0)
        return cls(
            enabled=policy.rate_limit_enabled,
            rate=max(policy.rate_limit_requests_per_second, 0.0),
            capacity=capacity,
            tokens=float(capacity),
            updated_at=now,
        )

    def compute_delay(self, now: float) -> float:
        """Return required delay and reserve a token when it can proceed now."""

        if not self.enabled or self.rate <= 0.0 or self.capacity <= 0:
            return 0.0
        self._refill(now)
        blocked_delay = max(self.blocked_until - now, 0.0)
        if blocked_delay > 0.0:
            return blocked_delay
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        return (1.0 - self.tokens) / self.rate

    def observe_response(self, *, now: float, headers: Mapping[str, str]) -> None:
        """Update cooldown from upstream rate-limit headers."""

        if not self.enabled or self.rate <= 0.0:
            return
        remaining = _get_header(headers, "x-ratelimit-remaining")
        if remaining is None:
            return
        try:
            remaining_count = int(remaining)
        except ValueError:
            return
        if remaining_count <= 0:
            self.blocked_until = max(self.blocked_until, now + 1.0 / self.rate)
            self.tokens = min(self.tokens, 0.0)

    def _refill(self, now: float) -> None:
        """Refill available rate limit tokens."""
        elapsed = max(now - self.updated_at, 0.0)
        if elapsed > 0.0:
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)
            self.updated_at = now


def build_httpx_timeout(timeouts: ApiTimeouts) -> httpx.Timeout:
    """Convert SDK timeout config to `httpx.Timeout`."""

    return httpx.Timeout(
        connect=timeouts.connect,
        read=timeouts.read,
        write=timeouts.write,
        pool=timeouts.pool,
    )


def normalize_path(path: str) -> str:
    """Normalize path."""
    stripped = path.strip()
    if not stripped:
        return "/"
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return stripped
    has_trailing_slash = stripped.endswith("/")
    segments = [quote(segment, safe=":@%") for segment in stripped.strip("/").split("/") if segment]
    normalized = "/" + "/".join(segments)
    if has_trailing_slash and normalized != "/":
        normalized += "/"
    return normalized


def normalize_params(params: Mapping[str, object] | None) -> QueryParams | None:
    """Normalize params."""
    if params is None:
        return None
    normalized: dict[str, QueryParamValue] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            normalized[key] = [normalize_query_scalar(item) for item in value]
        else:
            normalized[key] = normalize_query_scalar(value)
    return normalized


def normalize_query_scalar(value: object) -> QueryScalar:
    """Normalize query scalar."""
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


def normalize_files(files: Mapping[str, object] | None) -> RequestFiles | None:
    """Normalize files."""
    if files is None:
        return None
    return {key: normalize_file_value(value) for key, value in files.items()}


def normalize_file_value(value: object) -> FileValue:
    """Normalize file value."""
    if isinstance(value, bytes | str | BytesIO):
        return value
    if isinstance(value, tuple):
        return value
    raise TypeError("Неподдерживаемый тип файла для multipart upload.")


def merge_headers(
    *,
    context: RequestContext,
    headers: Mapping[str, str] | None,
    idempotency_key: str | None,
    user_agent: str,
    bearer_token: str | None,
) -> dict[str, str]:
    """Merge request headers with an already resolved bearer token."""

    merged: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": user_agent,
    }
    merged.update(dict(context.headers))
    if headers is not None:
        merged.update(dict(headers))
    if idempotency_key is not None:
        merged["Idempotency-Key"] = idempotency_key
    if bearer_token is not None:
        merged["Authorization"] = f"Bearer {bearer_token}"
    return merged


def build_user_agent(user_agent_suffix: str | None) -> str:
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
    if user_agent_suffix is not None:
        user_agent += f" {user_agent_suffix}"
    return user_agent


def decide_transport_retry(
    *,
    retry_policy: RetryPolicy,
    method: str,
    attempt: int,
    context: RequestContext,
    is_timeout: bool,
    idempotency_key: str | None,
) -> RetryDecision:
    """Decide transport retry."""
    if attempt >= retry_policy.max_attempts:
        return RetryDecision(False)
    if not retry_policy.retry_on_transport_error:
        return RetryDecision(False)
    if not is_retryable_request(
        retry_policy=retry_policy,
        method=method,
        context=context,
        idempotency_key=idempotency_key,
    ):
        return RetryDecision(False)
    return RetryDecision(
        True,
        reason="timeout" if is_timeout else "transport_error",
        delay_seconds=retry_policy.compute_backoff(attempt),
    )


def decide_http_retry(
    *,
    retry_policy: RetryPolicy,
    method: str,
    attempt: int,
    context: RequestContext,
    response: httpx.Response,
    idempotency_key: str | None,
) -> RetryDecision:
    """Decide http retry."""
    if attempt >= retry_policy.max_attempts:
        return RetryDecision(False)
    if not is_retryable_request(
        retry_policy=retry_policy,
        method=method,
        context=context,
        idempotency_key=idempotency_key,
    ):
        return RetryDecision(False)
    if response.status_code == 429:
        if not retry_policy.retry_on_rate_limit:
            return RetryDecision(False)
        delay = get_retry_after_seconds(response.headers)
        if response.headers.get("retry-after") is None:
            delay = retry_policy.compute_backoff(attempt)
        if delay > retry_policy.max_rate_limit_wait_seconds:
            return RetryDecision(False)
        return RetryDecision(True, reason="rate_limit", delay_seconds=delay)
    if 500 <= response.status_code < 600 and retry_policy.retry_on_server_error:
        return RetryDecision(
            True,
            reason="server_error",
            delay_seconds=retry_policy.compute_backoff(attempt),
        )
    return RetryDecision(False)


def is_retryable_request(
    *,
    retry_policy: RetryPolicy,
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
    if normalized_method == "DELETE" and idempotency_key is None and not context.allow_retry:
        return False
    return retry_policy.is_retryable_method(normalized_method, explicit_retry=context.allow_retry)


def map_http_error(
    response: httpx.Response,
    *,
    operation: str | None = None,
    attempt: int | None = None,
) -> Exception:
    """Map http error."""
    payload = safe_payload(response)
    message = extract_message(payload) or f"HTTP {response.status_code}"
    error_code = extract_error_code(payload)
    details = extract_error_details(payload)
    retry_after = get_retry_after_seconds(response.headers) if response.status_code == 429 else None
    request_id = extract_request_id(response.headers)
    headers = dict(response.headers)
    method = response.request.method
    endpoint = response.request.url.path
    metadata = {"method": method, "path": endpoint}
    error_type: type[AvitoError]
    if response.status_code == 401:
        error_type = AuthenticationError
    elif response.status_code == 403:
        error_type = AuthorizationError
    elif response.status_code in {400, 422}:
        error_type = ValidationError
    elif response.status_code == 409:
        error_type = ConflictError
    elif response.status_code == 429:
        error_type = RateLimitError
    elif response.status_code in {405, 501}:
        error_type = UnsupportedOperationError
    else:
        error_type = UpstreamApiError
    return error_type(
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


def safe_payload(response: httpx.Response) -> object:
    """Return a safe payload."""
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text
    return response.text


def extract_message(payload: object) -> str | None:
    """Extract message."""
    if isinstance(payload, dict):
        for key in ("message", "error_description", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(payload, str) and payload:
        return payload
    return None


def extract_error_code(payload: object) -> str | None:
    """Extract error code."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("code") or payload.get("error")
    return value if isinstance(value, str) else None


def extract_error_details(payload: object) -> object | None:
    """Extract error details."""
    if not isinstance(payload, Mapping):
        return None
    for key in ("details", "fields", "errors", "violations"):
        value = payload.get(key)
        if value is not None:
            return cast(object, value)
    return None


def extract_request_id(headers: Mapping[str, str]) -> str | None:
    """Extract request id."""
    for key in ("x-request-id", "x-correlation-id", "x-amzn-requestid"):
        value = headers.get(key)
        if value:
            return value
    return None


def get_retry_after_seconds(headers: Mapping[str, str]) -> float:
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


def elapsed_ms(started_at: float) -> int:
    """Return elapsed ms."""
    return max(int((time.perf_counter() - started_at) * 1000), 0)


def safe_endpoint(endpoint: str) -> str:
    """Return a safe endpoint."""
    parsed = urlsplit(endpoint)
    if parsed.scheme or parsed.netloc:
        return parsed.path or "/"
    return endpoint


def extract_filename(content_disposition: str | None) -> str | None:
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


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Return header."""
    value = headers.get(name)
    if value is not None:
        return value
    lowered_name = name.lower()
    for key, item in headers.items():
        if key.lower() == lowered_name:
            return item
    return None
