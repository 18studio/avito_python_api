"""Общие transport-типы и типизированные контейнеры ответов."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal

from avito._env import parse_env_float, resolve_env_aliases

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
RetryOverride = Literal["default", "enabled", "disabled"]


@dataclass(slots=True, frozen=True)
class ApiTimeouts:
    """Явные таймауты для HTTP-запросов SDK."""

    ENV_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "connect": ("AVITO_TIMEOUT_CONNECT",),
        "read": ("AVITO_TIMEOUT_READ",),
        "write": ("AVITO_TIMEOUT_WRITE",),
        "pool": ("AVITO_TIMEOUT_POOL",),
    }

    connect: float = 5.0
    read: float = 15.0
    write: float = 15.0
    pool: float = 5.0

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> ApiTimeouts:
        """Загружает таймауты из process environment и optional `.env` файла."""

        resolved_values = resolve_env_aliases(cls.ENV_ALIASES, env_file=env_file)
        parsed_values: dict[str, float] = {
            field_name: parse_env_float(value, field_name=field_name)
            for field_name, value in resolved_values.items()
        }
        return cls(**parsed_values)


@dataclass(slots=True, frozen=True)
class RequestContext:
    """Контекст запроса transport-слоя с политиками retry и auth."""

    operation_name: str
    allow_retry: bool = False
    retry_disabled: bool = False
    requires_auth: bool = True
    timeout: ApiTimeouts | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class BinaryResponse:
    """Типизированный бинарный ответ API."""

    content: bytes
    content_type: str | None
    filename: str | None
    status_code: int
    headers: Mapping[str, str]


@dataclass(slots=True, frozen=True)
class TransportDebugInfo:
    """Безопасный снимок transport-конфигурации для диагностики интеграции."""

    base_url: str
    user_id: int | None
    requires_auth: bool
    timeout_connect: float
    timeout_read: float
    timeout_write: float
    timeout_pool: float
    retry_max_attempts: int
    retryable_methods: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class JsonPage[ItemT]:
    """Типизированная страница результатов списочного ответа."""

    items: list[ItemT]
    total: int | None = None
    source_total: int | None = None
    page: int | None = None
    per_page: int | None = None
    next_cursor: str | None = None
    has_next_page: bool | None = None

    @property
    def has_next(self) -> bool:
        """Показывает, есть ли следующая страница или курсор."""

        if self.has_next_page is not None:
            return self.has_next_page
        if self.next_cursor:
            return True
        if self.total is None or self.page is None or self.per_page is None:
            return False
        return self.page * self.per_page < self.total


__all__ = (
    "ApiTimeouts",
    "BinaryResponse",
    "HttpMethod",
    "JsonPage",
    "RequestContext",
    "RetryOverride",
    "TransportDebugInfo",
)
