"""Baseline Swagger binding coverage report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from avito.core.swagger_discovery import DiscoveredSwaggerBinding, SwaggerBindingDiscovery
from avito.core.swagger_factory_map import FactoryDomainMappingReport
from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry, SwaggerValidationError


@dataclass(frozen=True, slots=True)
class SwaggerReportError:
    """JSON-compatible validation error for Swagger binding reports."""

    code: str
    message: str
    operation_key: str | None = None
    sdk_method: str | None = None


@dataclass(frozen=True, slots=True)
class SwaggerBindingReport:
    """Non-authoritative baseline report for Swagger operation binding rollout."""

    registry: SwaggerRegistry
    discovery: SwaggerBindingDiscovery
    errors: tuple[SwaggerReportError, ...] = ()
    factory_mapping: FactoryDomainMappingReport | None = None

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible report data."""

        binding_groups = _group_bindings_by_operation_key(self.discovery.bindings)
        operation_entries = [
            _build_operation_entry(operation, binding_groups.get(operation.key, ()))
            for operation in self.registry.operations
        ]
        binding_entries = [_build_binding_entry(binding) for binding in self.discovery.bindings]
        duplicate_operations = sum(1 for bindings in binding_groups.values() if len(bindings) > 1)
        ambiguous_bindings = sum(
            1 for binding in self.discovery.bindings if binding.operation_key is None
        )
        bound_operations = sum(1 for entry in operation_entries if entry["status"] == "bound")
        unbound_operations = sum(1 for entry in operation_entries if entry["status"] == "unbound")

        return {
            "summary": {
                "specs": len(self.registry.specs),
                "operations_total": len(self.registry.operations),
                "deprecated_operations": len(self.registry.deprecated_operations),
                "bound": bound_operations,
                "unbound": unbound_operations,
                "duplicate": duplicate_operations,
                "ambiguous": ambiguous_bindings,
            },
            "operations": operation_entries,
            "bindings": binding_entries,
            "factory_mapping": (
                self.factory_mapping.to_dict() if self.factory_mapping is not None else None
            ),
            "errors": [
                *[_build_registry_error_entry(error) for error in self.registry.errors],
                *[_build_report_error_entry(error) for error in self.errors],
            ],
        }


def build_swagger_binding_report(
    registry: SwaggerRegistry,
    discovery: SwaggerBindingDiscovery,
    errors: Sequence[SwaggerReportError] = (),
    factory_mapping: FactoryDomainMappingReport | None = None,
) -> SwaggerBindingReport:
    """Build a baseline coverage report from Swagger specs and discovered bindings."""

    return SwaggerBindingReport(
        registry=registry,
        discovery=discovery,
        errors=tuple(errors),
        factory_mapping=factory_mapping,
    )


def _group_bindings_by_operation_key(
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> Mapping[str, tuple[DiscoveredSwaggerBinding, ...]]:
    grouped: defaultdict[str, list[DiscoveredSwaggerBinding]] = defaultdict(list)
    for binding in bindings:
        if binding.operation_key is None:
            continue
        grouped[binding.operation_key].append(binding)
    return {
        operation_key: tuple(operation_bindings)
        for operation_key, operation_bindings in grouped.items()
    }


def _build_operation_entry(
    operation: SwaggerOperation,
    bindings: tuple[DiscoveredSwaggerBinding, ...],
) -> dict[str, object]:
    if not bindings:
        status = "unbound"
        binding_entry: object = None
    elif len(bindings) == 1:
        status = "bound"
        binding_entry = _binding_reference(bindings[0])
    else:
        status = "duplicate"
        binding_entry = [_binding_reference(binding) for binding in bindings]

    return {
        "spec": operation.spec,
        "method": operation.method,
        "path": operation.path,
        "operation_id": operation.operation_id,
        "deprecated": operation.deprecated,
        "status": status,
        "binding": binding_entry,
    }


def _build_binding_entry(binding: DiscoveredSwaggerBinding) -> dict[str, object]:
    return {
        "module": binding.module,
        "class": binding.class_name,
        "method": binding.method_name,
        "sdk_method": binding.sdk_method,
        "operation_key": binding.operation_key,
        "spec": binding.spec,
        "http_method": binding.method,
        "path": binding.path,
        "operation_id": binding.operation_id,
        "factory": binding.factory,
        "factory_args": dict(binding.factory_args),
        "method_args": dict(binding.method_args),
        "deprecated": binding.deprecated,
        "legacy": binding.legacy,
        "status": "ambiguous" if binding.operation_key is None else "mapped",
    }


def _binding_reference(binding: DiscoveredSwaggerBinding) -> dict[str, object]:
    return {
        "module": binding.module,
        "class": binding.class_name,
        "method": binding.method_name,
        "sdk_method": binding.sdk_method,
    }


def _build_registry_error_entry(error: SwaggerValidationError) -> dict[str, object]:
    return {
        "code": error.code,
        "message": error.message,
        "operation_key": error.operation_key,
        "sdk_method": None,
    }


def _build_report_error_entry(error: SwaggerReportError) -> dict[str, object]:
    return {
        "code": error.code,
        "message": error.message,
        "operation_key": error.operation_key,
        "sdk_method": error.sdk_method,
    }


__all__ = ("SwaggerBindingReport", "SwaggerReportError", "build_swagger_binding_report")
