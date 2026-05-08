"""Static async parity lint for ported async domain classes."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterator

import avito
from avito.core.domain import AsyncDomainObject

EXCLUDED_PACKAGES = {"auth", "core", "summary", "testing"}


def iter_async_classes() -> Iterator[type[AsyncDomainObject]]:
    """Yield all public async domain classes in stable order."""

    package_paths = getattr(avito, "__path__", ())
    classes: list[type[AsyncDomainObject]] = []
    for info in pkgutil.iter_modules(package_paths):
        if not info.ispkg or info.name in EXCLUDED_PACKAGES:
            continue
        module_name = f"avito.{info.name}.async_domain"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for _, value in inspect.getmembers(module, inspect.isclass):
            if value.__module__ != module.__name__:
                continue
            if value is AsyncDomainObject:
                continue
            if issubclass(value, AsyncDomainObject):
                classes.append(value)
    yield from sorted(classes, key=lambda cls: (cls.__module__, cls.__name__))


def main() -> int:
    """Run parity lint for currently ported async classes."""

    errors: list[str] = []
    for async_class in iter_async_classes():
        sync_name = async_class.__name__.removeprefix("Async")
        package = async_class.__module__.split(".")[1]
        sync_module = importlib.import_module(f"avito.{package}.domain")
        sync_class = getattr(sync_module, sync_name, None)
        if sync_class is None:
            errors.append(f"{async_class.__module__}.{async_class.__name__}: sync class missing")
            continue
        for attr in ("__swagger_domain__", "__sdk_factory__", "__sdk_factory_args__"):
            if getattr(async_class, attr, None) != getattr(sync_class, attr, None):
                errors.append(f"{async_class.__name__}: metadata mismatch for {attr}")
        sync_methods = _public_methods(sync_class)
        async_methods = _public_methods(async_class)
        if set(sync_methods) != set(async_methods):
            errors.append(f"{async_class.__name__}: public method set mismatch")
            continue
        for name, async_method in async_methods.items():
            if not inspect.iscoroutinefunction(async_method):
                errors.append(f"{async_class.__name__}.{name}: must be async def")
            sync_binding = getattr(sync_methods[name], "__swagger_binding__", None)
            async_binding = getattr(async_method, "__swagger_binding__", None)
            if sync_binding is None or async_binding is None:
                errors.append(f"{async_class.__name__}.{name}: missing swagger binding")
                continue
            sync_key = (
                sync_binding.spec,
                sync_binding.method,
                sync_binding.path,
                sync_binding.operation_id,
            )
            async_key = (
                async_binding.spec,
                async_binding.method,
                async_binding.path,
                async_binding.operation_id,
            )
            if sync_key != async_key or async_binding.variant != "async":
                errors.append(f"{async_class.__name__}.{name}: swagger binding mismatch")
    for error in errors:
        print(error)
    return 1 if errors else 0


def _public_methods(cls: type[object]) -> dict[str, object]:
    return {
        name: value
        for name, value in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_") and value.__qualname__.startswith(f"{cls.__name__}.")
    }


if __name__ == "__main__":
    raise SystemExit(main())
