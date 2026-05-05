"""Иерархия исключений SDK Avito."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

_SECRET_KEYS = (
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "client_secret",
    "secret",
    "password",
)


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and any(secret in key.lower() for secret in _SECRET_KEYS)


def sanitize_metadata(value: object) -> object:
    """Удаляет секреты из диагностических метаданных исключения."""

    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if _is_secret_key(key):
                sanitized[str(key)] = "***"
            else:
                sanitized[str(key)] = sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_metadata(item) for item in value)
    if isinstance(value, str) and any(secret in value.lower() for secret in _SECRET_KEYS):
        return "***"
    return value


@dataclass(slots=True, frozen=True)
class AvitoError(Exception):
    """Базовое исключение SDK с безопасными диагностическими метаданными."""

    message: str
    status_code: int | None = None
    error_code: str | None = None
    operation: str | None = None
    attempt: int | None = None
    method: str | None = None
    endpoint: str | None = None
    details: object | None = None
    retry_after: float | None = None
    request_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    payload: object | None = None
    headers: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        sanitized_payload = sanitize_metadata(self.payload)
        sanitized_details = sanitize_metadata(self.details)
        sanitized_headers = (
            sanitize_metadata(dict(self.headers)) if self.headers is not None else None
        )
        sanitized_metadata = sanitize_metadata(dict(self.metadata))
        Exception.__init__(self, self.message)
        object.__setattr__(self, "payload", sanitized_payload)
        object.__setattr__(self, "details", sanitized_details)
        object.__setattr__(self, "headers", sanitized_headers)
        object.__setattr__(self, "metadata", sanitized_metadata)

    @property
    def status(self) -> int | None:
        """HTTP-статус ответа API."""

        return self.status_code

    def __str__(self) -> str:
        details: list[str] = [self.message]
        if self.operation is not None:
            details.append(f"operation={self.operation}")
        if self.attempt is not None:
            details.append(f"attempt={self.attempt}")
        if self.method is not None:
            details.append(f"method={self.method}")
        if self.endpoint is not None:
            details.append(f"endpoint={self.endpoint}")
        if self.status_code is not None:
            details.append(f"status={self.status_code}")
        if self.error_code is not None:
            details.append(f"code={self.error_code}")
        if self.retry_after is not None:
            details.append(f"retry_after={self.retry_after}")
        if self.request_id is not None:
            details.append(f"request_id={self.request_id}")
        return " ".join(details)


class TransportError(AvitoError):
    """Сбой HTTP-транспорта до получения корректного ответа API."""


class AuthenticationError(AvitoError):
    """Ошибка аутентификации: неверные credentials или истёкший токен (HTTP 401)."""


class AuthorizationError(AvitoError):
    """Ошибка авторизации: недостаточно прав для операции (HTTP 403)."""


class ValidationError(AvitoError):
    """API отклонил запрос из-за некорректных параметров (HTTP 400, 422)."""


class ConfigurationError(AvitoError):
    """SDK сконфигурирован некорректно — ошибка обнаружена до выполнения HTTP-запроса."""


class ClientClosedError(AvitoError):
    """Вызов выполнен после закрытия `AvitoClient`."""


class RateLimitError(AvitoError):
    """Превышен лимит запросов API (HTTP 429)."""


class ConflictError(AvitoError):
    """Операция конфликтует с текущим состоянием upstream-ресурса (HTTP 409)."""


class UnsupportedOperationError(AvitoError):
    """Операция не поддерживается публичным Avito API или данным endpoint (HTTP 405, 501)."""


class UpstreamApiError(AvitoError):
    """Неизвестная ошибка upstream API вне специализированных типов SDK."""


class ResponseMappingError(AvitoError):
    """Не удалось безопасно преобразовать ответ API в ожидаемый тип."""


__all__ = (
    "AuthenticationError",
    "AuthorizationError",
    "AvitoError",
    "ClientClosedError",
    "ConfigurationError",
    "ConflictError",
    "RateLimitError",
    "ResponseMappingError",
    "TransportError",
    "UnsupportedOperationError",
    "UpstreamApiError",
    "ValidationError",
    "sanitize_metadata",
)
