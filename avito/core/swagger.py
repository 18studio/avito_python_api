"""Swagger operation binding metadata for public SDK methods."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ParamSpec, TypeVar

from avito.core.exceptions import ConfigurationError

P = ParamSpec("P")
R = TypeVar("R")

_PATH_PARAMETER_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")
_EMPTY_MAPPING: Mapping[str, str] = MappingProxyType({})


def _freeze_mapping(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return _EMPTY_MAPPING
    return MappingProxyType(dict(value))


def _normalize_method(method: str) -> str:
    normalized = method.strip().upper()
    if not normalized:
        raise ConfigurationError("HTTP-метод Swagger binding не может быть пустым.")
    return normalized


def _normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized.startswith("/"):
        raise ConfigurationError("Swagger path должен начинаться с `/`.")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    without_parameters = _PATH_PARAMETER_RE.sub("", normalized)
    if "{" in without_parameters or "}" in without_parameters:
        raise ConfigurationError("Swagger path должен использовать параметры в формате `{name}`.")
    return normalized


@dataclass(frozen=True, slots=True)
class SwaggerOperationBinding:
    """Связь публичного SDK-метода с одной Swagger/OpenAPI operation."""

    method: str
    path: str
    spec: str | None = None
    operation_id: str | None = None
    factory: str | None = None
    factory_args: Mapping[str, str] = field(default_factory=lambda: _EMPTY_MAPPING)
    method_args: Mapping[str, str] = field(default_factory=lambda: _EMPTY_MAPPING)
    deprecated: bool = False
    legacy: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _normalize_method(self.method))
        object.__setattr__(self, "path", _normalize_path(self.path))
        object.__setattr__(self, "factory_args", _freeze_mapping(self.factory_args))
        object.__setattr__(self, "method_args", _freeze_mapping(self.method_args))


def swagger_operation(
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
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Записывает Swagger binding metadata на публичный SDK-метод."""

    binding = SwaggerOperationBinding(
        method=method,
        path=path,
        spec=spec,
        operation_id=operation_id,
        factory=factory,
        factory_args=_freeze_mapping(factory_args),
        method_args=_freeze_mapping(method_args),
        deprecated=deprecated,
        legacy=legacy,
    )

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        if hasattr(func, "__swagger_binding__") or hasattr(func, "__swagger_bindings__"):
            raise ConfigurationError("Несколько Swagger binding-ов на одном SDK method запрещены.")
        func.__swagger_binding__ = binding  # type: ignore[attr-defined]
        return func

    return decorate


__all__ = ("SwaggerOperationBinding", "swagger_operation")
