"""Discovery of Swagger operation bindings on public SDK domain methods."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType, ModuleType
from typing import Literal, cast

from avito.core.domain import AsyncDomainObject, DomainObject
from avito.core.swagger import SwaggerOperationBinding
from avito.core.swagger_registry import (
    SwaggerOperation,
    SwaggerRegistry,
    normalize_swagger_method,
    normalize_swagger_path,
)

_EMPTY_MAPPING: Mapping[str, str] = MappingProxyType({})
_IGNORED_PACKAGES = frozenset({"auth", "core", "summary", "testing"})
_NON_DOMAIN_BINDING_MODULES = ("avito.auth.provider", "avito.auth.async_token_client")


@dataclass(frozen=True, slots=True)
class DiscoveredSwaggerBinding:
    """Effective binding metadata discovered on a public SDK domain method."""

    module: str
    class_name: str
    method_name: str
    domain: str | None
    operation_key: str | None
    spec: str | None
    method: str
    path: str
    operation_id: str | None
    factory: str | None
    factory_args: Mapping[str, str] = field(default_factory=lambda: _EMPTY_MAPPING)
    method_args: Mapping[str, str] = field(default_factory=lambda: _EMPTY_MAPPING)
    deprecated: bool = False
    legacy: bool = False
    variant: Literal["sync", "async"] = "sync"

    @property
    def sdk_method(self) -> str:
        """Run the sdk method helper."""
        return f"{self.module}.{self.class_name}.{self.method_name}"


@dataclass(frozen=True, slots=True)
class SwaggerBindingDiscovery:
    """Result of scanning SDK domain modules for Swagger operation bindings."""

    bindings: tuple[DiscoveredSwaggerBinding, ...]
    legacy_binding_methods: tuple[str, ...] = ()

    @property
    def canonical_map(self) -> Mapping[str, DiscoveredSwaggerBinding]:
        """Run the canonical map helper."""
        mapped = {
            binding.operation_key: binding
            for binding in self.bindings
            if binding.operation_key is not None and binding.variant == "sync"
        }
        return MappingProxyType(mapped)

    @property
    def canonical_map_by_variant(
        self,
    ) -> Mapping[Literal["sync", "async"], Mapping[str, DiscoveredSwaggerBinding]]:
        """Run the canonical map by variant helper."""
        mapped: dict[Literal["sync", "async"], dict[str, DiscoveredSwaggerBinding]] = {
            "sync": {},
            "async": {},
        }
        for binding in self.bindings:
            if binding.operation_key is not None:
                mapped[binding.variant][binding.operation_key] = binding
        return MappingProxyType(
            {
                "sync": MappingProxyType(mapped["sync"]),
                "async": MappingProxyType(mapped["async"]),
            }
        )

    def binding_for(
        self,
        operation_key: str,
        *,
        variant: Literal["sync", "async"] = "sync",
    ) -> DiscoveredSwaggerBinding | None:
        """Return discovered binding by operation key and surface variant."""

        return self.canonical_map_by_variant[variant].get(operation_key)


def discover_swagger_bindings(
    *,
    package_name: str = "avito",
    registry: SwaggerRegistry | None = None,
) -> SwaggerBindingDiscovery:
    """Discovers Swagger bindings without creating `AvitoClient` or doing HTTP work."""

    package = importlib.import_module(package_name)
    domain_modules = tuple(_iter_domain_modules(package, package_name))
    non_domain_modules = tuple(
        importlib.import_module(name) for name in _NON_DOMAIN_BINDING_MODULES
    )
    bindings: list[DiscoveredSwaggerBinding] = []
    legacy_binding_methods: list[str] = []
    for module in (*domain_modules, *non_domain_modules):
        module_bindings, module_legacy_methods = _discover_module_bindings(module, registry)
        bindings.extend(module_bindings)
        legacy_binding_methods.extend(module_legacy_methods)
    return SwaggerBindingDiscovery(
        bindings=tuple(bindings),
        legacy_binding_methods=tuple(sorted(set(legacy_binding_methods))),
    )


def _iter_domain_modules(package: ModuleType, package_name: str) -> tuple[ModuleType, ...]:
    """Run the iter domain modules helper."""
    package_paths = getattr(package, "__path__", None)
    if package_paths is None:
        return ()

    modules: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(package_paths):
        if not module_info.ispkg or module_info.name in _IGNORED_PACKAGES:
            continue
        for suffix in ("domain", "async_domain"):
            module_name = f"{package_name}.{module_info.name}.{suffix}"
            if importlib.util.find_spec(module_name) is None:
                continue
            modules.append(importlib.import_module(module_name))
    return tuple(modules)


def _discover_module_bindings(
    module: ModuleType,
    registry: SwaggerRegistry | None,
) -> tuple[tuple[DiscoveredSwaggerBinding, ...], tuple[str, ...]]:
    """Run the discover module bindings helper."""
    bindings: list[DiscoveredSwaggerBinding] = []
    legacy_binding_methods: list[str] = []
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        if not _is_discoverable_binding_class(cls):
            continue
        if cls.__name__.startswith("_"):
            continue
        for method_name, func in inspect.getmembers(cls, inspect.isfunction):
            if method_name.startswith("_"):
                continue
            sdk_method = f"{module.__name__}.{cls.__name__}.{method_name}"
            if hasattr(func, "__swagger_bindings__"):
                legacy_binding_methods.append(sdk_method)
            raw_binding = _method_binding(func)
            if raw_binding is not None:
                bindings.append(
                    _build_effective_binding(
                        module=module,
                        cls=cls,
                        method_name=method_name,
                        binding=raw_binding,
                        registry=registry,
                    )
                )
    return tuple(bindings), tuple(legacy_binding_methods)


def _is_discoverable_binding_class(cls: type[object]) -> bool:
    """Return whether discoverable binding class."""
    if issubclass(cls, DomainObject) and cls is not DomainObject:
        return True
    if issubclass(cls, AsyncDomainObject) and cls is not AsyncDomainObject:
        return True
    return _optional_string(getattr(cls, "__swagger_domain__", None)) is not None


def _method_binding(func: object) -> SwaggerOperationBinding | None:
    """Run the method binding helper."""
    raw_binding = getattr(func, "__swagger_binding__", None)
    if isinstance(raw_binding, SwaggerOperationBinding):
        return raw_binding
    return None


def _build_effective_binding(
    *,
    module: ModuleType,
    cls: type[object],
    method_name: str,
    binding: SwaggerOperationBinding,
    registry: SwaggerRegistry | None,
) -> DiscoveredSwaggerBinding:
    """Build effective binding."""
    method = normalize_swagger_method(binding.method)
    path = normalize_swagger_path(binding.path)
    spec = binding.spec or _optional_string(getattr(cls, "__swagger_spec__", None))
    if spec is None and registry is not None:
        spec = _resolve_spec(registry.operations, method=method, path=path)
    operation_key = f"{spec} {method} {path}" if spec is not None else None
    class_factory_args = _optional_mapping(getattr(cls, "__sdk_factory_args__", None))
    if registry is not None and operation_key is not None and not binding.factory_args:
        operation = _operation_by_key(registry.operations, operation_key)
        class_factory_args = _filter_factory_args_for_operation(class_factory_args, operation)
    return DiscoveredSwaggerBinding(
        module=module.__name__,
        class_name=cls.__name__,
        method_name=method_name,
        domain=_optional_string(getattr(cls, "__swagger_domain__", None)),
        operation_key=operation_key,
        spec=spec,
        method=method,
        path=path,
        operation_id=binding.operation_id,
        factory=binding.factory or _optional_string(getattr(cls, "__sdk_factory__", None)),
        factory_args=binding.factory_args or class_factory_args,
        method_args=binding.method_args,
        deprecated=binding.deprecated,
        legacy=binding.legacy,
        variant=binding.variant,
    )


def _operation_by_key(
    operations: tuple[SwaggerOperation, ...],
    operation_key: str,
) -> SwaggerOperation | None:
    """Run the operation by key helper."""
    for operation in operations:
        if operation.key == operation_key:
            return operation
    return None


def _filter_factory_args_for_operation(
    factory_args: Mapping[str, str],
    operation: SwaggerOperation | None,
) -> Mapping[str, str]:
    """Run the filter factory args for operation helper."""
    if operation is None or not factory_args:
        return factory_args
    parameter_names = {
        f"{parameter.location}.{parameter.name}" for parameter in operation.parameters
    }
    filtered = {
        argument_name: expression
        for argument_name, expression in factory_args.items()
        if expression == "body"
        or expression.startswith("body.")
        or expression.startswith("constant.")
        or expression in parameter_names
    }
    return MappingProxyType(filtered)


def _resolve_spec(
    operations: tuple[SwaggerOperation, ...],
    *,
    method: str,
    path: str,
) -> str | None:
    """Resolve spec."""
    matches = [
        operation.spec
        for operation in operations
        if operation.method == method and operation.path == path
    ]
    return matches[0] if len(matches) == 1 else None


def _optional_string(value: object) -> str | None:
    """Run the optional string helper."""
    return value if isinstance(value, str) and value else None


def _optional_mapping(value: object) -> Mapping[str, str]:
    """Run the optional mapping helper."""
    if value is None:
        return _EMPTY_MAPPING
    if not isinstance(value, Mapping):
        return _EMPTY_MAPPING
    return MappingProxyType(
        {str(key): str(item) for key, item in cast(Mapping[object, object], value).items()}
    )


__all__ = (
    "DiscoveredSwaggerBinding",
    "SwaggerBindingDiscovery",
    "discover_swagger_bindings",
)
