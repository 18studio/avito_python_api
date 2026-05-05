"""Validation rules for Swagger operation bindings."""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import textwrap
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from types import ModuleType

from avito.client import AvitoClient
from avito.core.deprecation import DeprecatedSdkSymbol
from avito.core.operations import OperationSpec
from avito.core.swagger_discovery import DiscoveredSwaggerBinding, SwaggerBindingDiscovery
from avito.core.swagger_registry import (
    SwaggerOperation,
    SwaggerRegistry,
    normalize_swagger_method,
    normalize_swagger_path,
)
from avito.core.swagger_report import SwaggerReportError
from avito.core.swagger_schema_paths import SwaggerSchemaPathError, resolve_body_path

_API_DOMAINS = frozenset(
    {
        "accounts",
        "ads",
        "autoteka",
        "cpa",
        "jobs",
        "messenger",
        "orders",
        "promotion",
        "ratings",
        "realty",
        "tariffs",
    }
)
_TEST_CONSTANTS = frozenset(
    {
        "account_id",
        "action_id",
        "call_id",
        "campaign_id",
        "chat_id",
        "dictionary_id",
        "item_id",
        "limit",
        "message_id",
        "order_id",
        "parcel_id",
        "report_id",
        "resume_id",
        "scoring_id",
        "tariff_id",
        "task_id",
        "user_id",
        "url",
        "vacancy_id",
        "value",
        "vehicle_id",
    }
)


def lint_swagger_bindings(
    registry: SwaggerRegistry,
    discovery: SwaggerBindingDiscovery,
    *,
    strict: bool = False,
) -> tuple[SwaggerReportError, ...]:
    """Validate discovered SDK bindings against the Swagger registry."""

    operations_by_key = {operation.key: operation for operation in registry.operations}
    spec_names = {spec.name for spec in registry.specs}
    errors: list[SwaggerReportError] = []

    errors.extend(_validate_legacy_stacked_binding_metadata(discovery))
    errors.extend(_validate_single_binding_per_sdk_method(discovery.bindings))
    errors.extend(_validate_duplicate_bindings(discovery.bindings))
    if strict:
        errors.extend(_validate_complete_bindings(registry.operations, discovery.bindings))
        errors.extend(_validate_operation_spec_coverage(registry, discovery.bindings))
        errors.extend(_validate_json_body_model_coverage(registry, discovery.bindings))
    for binding in discovery.bindings:
        operation = _resolve_bound_operation(
            binding=binding,
            operations_by_key=operations_by_key,
            spec_names=spec_names,
            errors=errors,
        )
        sdk_method = _load_sdk_method(binding)
        if operation is not None:
            errors.extend(_validate_operation_metadata(binding, operation, sdk_method))
            errors.extend(_validate_binding_expressions(binding, operation))
        errors.extend(_validate_factory(binding))
        errors.extend(_validate_sdk_method_signature(binding, sdk_method))

    return tuple(errors)


def _validate_operation_spec_coverage(
    registry: SwaggerRegistry,
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> tuple[SwaggerReportError, ...]:
    operations_by_key = {operation.key: operation for operation in registry.operations}
    used_specs: set[int] = set()
    errors: list[SwaggerReportError] = []

    for binding in bindings:
        if binding.domain not in _API_DOMAINS:
            continue
        operation = operations_by_key.get(binding.operation_key or "")
        sdk_method = _load_sdk_method(binding)
        specs = _operation_specs_for_sdk_method(sdk_method)
        if len(specs) != 1:
            errors.append(
                SwaggerReportError(
                    code="SWAGGER_OPERATION_SPEC_MISSING",
                    message=(
                        f"{binding.sdk_method}: public API method должен исполнять "
                        "ровно один OperationSpec через `_execute(...)`."
                    ),
                    operation_key=binding.operation_key,
                    sdk_method=binding.sdk_method,
                )
            )
            continue

        spec = specs[0]
        used_specs.add(id(spec))
        if operation is not None:
            errors.extend(_validate_operation_spec_matches_binding(binding, operation, spec))

    errors.extend(_validate_no_unbound_operation_specs(used_specs))
    return tuple(errors)


def _validate_operation_spec_matches_binding(
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    spec: OperationSpec[object],
) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    if normalize_swagger_method(spec.method) != operation.method:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_OPERATION_SPEC_METHOD_MISMATCH",
                message=(
                    f"{binding.sdk_method}: OperationSpec method `{spec.method}` "
                    f"не совпадает со Swagger method `{operation.method}`."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    if normalize_swagger_path(spec.path) != operation.path:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_OPERATION_SPEC_PATH_MISMATCH",
                message=(
                    f"{binding.sdk_method}: OperationSpec path `{spec.path}` "
                    f"не совпадает со Swagger path `{operation.path}`."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    return tuple(errors)


def _validate_json_body_model_coverage(
    registry: SwaggerRegistry,
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> tuple[SwaggerReportError, ...]:
    operations_by_key = {operation.key: operation for operation in registry.operations}
    errors: list[SwaggerReportError] = []

    for binding in bindings:
        if binding.domain not in _API_DOMAINS:
            continue
        operation = operations_by_key.get(binding.operation_key or "")
        if operation is None:
            continue
        specs = _operation_specs_for_sdk_method(_load_sdk_method(binding))
        if len(specs) != 1:
            continue
        errors.extend(
            _validate_operation_json_body_models(
                binding=binding,
                operation=operation,
                spec=specs[0],
            )
        )

    return tuple(errors)


def _validate_operation_json_body_models(
    *,
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    spec: OperationSpec[object],
) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    request_body = operation.request_body
    if request_body is not None and _has_json_content(request_body.content_types):
        if request_body.schema is None:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_REQUEST_SCHEMA_UNPARSED",
                    message=f"{operation.key}: requestBody schema не разобрана.",
                )
            )
        if spec.request_model is None:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_REQUEST_MODEL_MISSING",
                    message=f"{operation.key}: {spec.name} без request_model.",
                )
            )

    for response in operation.success_responses:
        if not _has_json_content(response.content_types):
            continue
        if response.schema is None:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_RESPONSE_SCHEMA_UNPARSED",
                    message=(
                        f"{operation.key} {response.status_code}: "
                        "response schema не разобрана."
                    ),
                )
            )
        if spec.response_kind == "json" and spec.response_model is None:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_RESPONSE_MODEL_MISSING",
                    message=f"{operation.key} {response.status_code}: {spec.name} без response_model.",
                )
            )

    for response in operation.error_responses:
        if not _has_json_content(response.content_types):
            continue
        if response.schema is None:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_ERROR_SCHEMA_UNPARSED",
                    message=(
                        f"{operation.key} {response.status_code}: "
                        "error schema не разобрана."
                    ),
                )
            )
        if response.status_code not in spec.error_models:
            errors.append(
                _contract_error(
                    binding=binding,
                    code="SWAGGER_CONTRACT_ERROR_MODEL_MISSING",
                    message=f"{operation.key} {response.status_code}: {spec.name} без error_model.",
                )
            )

    return tuple(errors)


def _has_json_content(content_types: Sequence[str]) -> bool:
    return any("application/json" in content_type for content_type in content_types)


def _contract_error(
    *,
    binding: DiscoveredSwaggerBinding,
    code: str,
    message: str,
) -> SwaggerReportError:
    return SwaggerReportError(
        code=code,
        message=message,
        operation_key=binding.operation_key,
        sdk_method=binding.sdk_method,
    )


def _validate_no_unbound_operation_specs(used_specs: set[int]) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    for module_name, spec_name, spec in _iter_api_domain_operation_specs():
        if id(spec) in used_specs:
            continue
        errors.append(
            SwaggerReportError(
                code="SWAGGER_OPERATION_SPEC_UNBOUND",
                message=(
                    f"{module_name}.{spec_name}: OperationSpec не связан с публичным "
                    "Swagger binding."
                ),
                operation_key=None,
                sdk_method=None,
            )
        )
    return tuple(errors)


def _validate_legacy_stacked_binding_metadata(
    discovery: SwaggerBindingDiscovery,
) -> tuple[SwaggerReportError, ...]:
    return tuple(
        SwaggerReportError(
            code="SWAGGER_BINDING_METHOD_MULTIPLE",
            message=f"{sdk_method}: legacy metadata `__swagger_bindings__` запрещена.",
            operation_key=None,
            sdk_method=sdk_method,
        )
        for sdk_method in discovery.legacy_binding_methods
    )


def _validate_single_binding_per_sdk_method(
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> tuple[SwaggerReportError, ...]:
    grouped: defaultdict[str, list[DiscoveredSwaggerBinding]] = defaultdict(list)
    for binding in bindings:
        grouped[binding.sdk_method].append(binding)

    errors: list[SwaggerReportError] = []
    for sdk_method, method_bindings in sorted(grouped.items()):
        if len(method_bindings) < 2:
            continue
        operation_keys = ", ".join(
            binding.operation_key or "<ambiguous>" for binding in method_bindings
        )
        for binding in method_bindings:
            errors.append(
                SwaggerReportError(
                    code="SWAGGER_BINDING_METHOD_MULTIPLE",
                    message=(
                        f"{sdk_method}: один SDK method связан с несколькими Swagger "
                        f"operations: {operation_keys}."
                    ),
                    operation_key=binding.operation_key,
                    sdk_method=sdk_method,
                )
            )
    return tuple(errors)


def _validate_complete_bindings(
    operations: Sequence[SwaggerOperation],
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> tuple[SwaggerReportError, ...]:
    bound_operation_keys = {
        binding.operation_key for binding in bindings if binding.operation_key is not None
    }
    errors: list[SwaggerReportError] = []
    for operation in operations:
        if operation.key in bound_operation_keys:
            continue
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_MISSING",
                message=f"{operation.key}: для Swagger operation не найден SDK binding.",
                operation_key=operation.key,
                sdk_method=None,
            )
        )
    return tuple(errors)


def _validate_duplicate_bindings(
    bindings: Sequence[DiscoveredSwaggerBinding],
) -> tuple[SwaggerReportError, ...]:
    grouped: defaultdict[str, list[DiscoveredSwaggerBinding]] = defaultdict(list)
    for binding in bindings:
        if binding.operation_key is not None:
            grouped[binding.operation_key].append(binding)

    errors: list[SwaggerReportError] = []
    for operation_key, operation_bindings in sorted(grouped.items()):
        if len(operation_bindings) < 2:
            continue
        methods = ", ".join(binding.sdk_method for binding in operation_bindings)
        for binding in operation_bindings:
            errors.append(
                SwaggerReportError(
                    code="SWAGGER_BINDING_DUPLICATE",
                    message=(
                        f"{operation_key}: несколько SDK binding-ов указывают на одну "
                        f"Swagger operation: {methods}."
                    ),
                    operation_key=operation_key,
                    sdk_method=binding.sdk_method,
                )
            )
    return tuple(errors)


def _resolve_bound_operation(
    *,
    binding: DiscoveredSwaggerBinding,
    operations_by_key: Mapping[str, SwaggerOperation],
    spec_names: set[str],
    errors: list[SwaggerReportError],
) -> SwaggerOperation | None:
    if binding.operation_key is None:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_AMBIGUOUS",
                message=(
                    f"{binding.sdk_method}: Swagger operation нельзя определить однозначно. "
                    "Укажите `spec` в binding или class-level metadata."
                ),
                operation_key=None,
                sdk_method=binding.sdk_method,
            )
        )
        return None

    if binding.spec not in spec_names:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_SPEC_NOT_FOUND",
                message=f"{binding.sdk_method}: Swagger spec не найден: {binding.spec}.",
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            )
        )
        return None

    operation = operations_by_key.get(binding.operation_key)
    if operation is None:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_NOT_FOUND",
                message=(
                    f"{binding.sdk_method}: Swagger operation не найдена: {binding.operation_key}."
                ),
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            )
        )
    return operation


def _validate_operation_metadata(
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    sdk_method: Callable[..., object] | None,
) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    if binding.operation_id is not None and binding.operation_id != operation.operation_id:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_OPERATION_ID_MISMATCH",
                message=(
                    f"{binding.sdk_method}: operation_id `{binding.operation_id}` "
                    f"не совпадает со Swagger operation_id `{operation.operation_id}`."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    if binding.deprecated != operation.deprecated:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_DEPRECATED_MISMATCH",
                message=(
                    f"{binding.sdk_method}: deprecated={binding.deprecated} не совпадает "
                    f"со Swagger deprecated={operation.deprecated}."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    if binding.legacy and not operation.deprecated:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_LEGACY_MISMATCH",
                message=(
                    f"{binding.sdk_method}: legacy=True разрешён только для deprecated "
                    "Swagger operation или явного исключения."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    if operation.deprecated and not binding.legacy:
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_LEGACY_REQUIRED",
                message=(
                    f"{binding.sdk_method}: deprecated Swagger operation должна иметь "
                    "legacy=True в binding."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    if operation.deprecated and not _has_runtime_deprecation(sdk_method):
        errors.append(
            SwaggerReportError(
                code="SWAGGER_BINDING_DEPRECATION_WARNING_MISSING",
                message=(
                    f"{binding.sdk_method}: deprecated public method должен иметь runtime "
                    "DeprecationWarning через `deprecated_method`."
                ),
                operation_key=operation.key,
                sdk_method=binding.sdk_method,
            )
        )
    return tuple(errors)


def _validate_factory(binding: DiscoveredSwaggerBinding) -> tuple[SwaggerReportError, ...]:
    if binding.domain == "auth" and binding.factory is None:
        return ()
    if binding.factory is None:
        return (
            SwaggerReportError(
                code="SWAGGER_BINDING_FACTORY_MISSING",
                message=f"{binding.sdk_method}: binding должен указывать AvitoClient factory.",
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            ),
        )

    factory = getattr(AvitoClient, binding.factory, None)
    if not callable(factory):
        return (
            SwaggerReportError(
                code="SWAGGER_BINDING_FACTORY_NOT_FOUND",
                message=f"{binding.sdk_method}: AvitoClient factory не найден: {binding.factory}.",
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            ),
        )

    return _validate_signature_mapping(
        binding=binding,
        signature=inspect.signature(factory),
        mapping=binding.factory_args,
        subject=f"factory `{binding.factory}`",
        code_prefix="SWAGGER_BINDING_FACTORY",
    )


def _validate_sdk_method_signature(
    binding: DiscoveredSwaggerBinding,
    sdk_method: Callable[..., object] | None,
) -> tuple[SwaggerReportError, ...]:
    if sdk_method is None:
        return (
            SwaggerReportError(
                code="SWAGGER_BINDING_SDK_METHOD_NOT_FOUND",
                message=f"{binding.sdk_method}: SDK method не найден при signature validation.",
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            ),
        )
    return _validate_signature_mapping(
        binding=binding,
        signature=inspect.signature(sdk_method),
        mapping=binding.method_args,
        subject="SDK method",
        code_prefix="SWAGGER_BINDING_METHOD",
    )


def _operation_specs_for_sdk_method(
    sdk_method: Callable[..., object] | None,
) -> tuple[OperationSpec[object], ...]:
    if sdk_method is None:
        return ()
    unwrapped_method = inspect.unwrap(sdk_method)
    try:
        source = inspect.getsource(unwrapped_method)
    except (OSError, TypeError):
        return ()
    tree = ast.parse(textwrap.dedent(source))
    specs: list[OperationSpec[object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_execute_call(node):
            continue
        if not node.args:
            continue
        spec_name = _name(node.args[0])
        if spec_name is None:
            continue
        spec = unwrapped_method.__globals__.get(spec_name)
        if isinstance(spec, OperationSpec):
            specs.append(spec)
    return tuple(specs)


def _iter_api_domain_operation_specs() -> tuple[tuple[str, str, OperationSpec[object]], ...]:
    specs: list[tuple[str, str, OperationSpec[object]]] = []
    for domain in sorted(_API_DOMAINS):
        for module in _iter_domain_operation_modules(domain):
            for name, value in vars(module).items():
                if isinstance(value, OperationSpec):
                    specs.append((module.__name__, name, value))
    return tuple(specs)


def _iter_domain_operation_modules(domain: str) -> tuple[ModuleType, ...]:
    root_module_name = f"avito.{domain}.operations"
    module = importlib.import_module(root_module_name)
    modules: list[ModuleType] = [module]
    module_path = getattr(module, "__path__", None)
    if module_path is None:
        return tuple(modules)
    for info in pkgutil.walk_packages(module_path, prefix=f"{root_module_name}."):
        modules.append(importlib.import_module(info.name))
    return tuple(modules)


def _is_execute_call(node: ast.Call) -> bool:
    name = _call_name(node.func)
    return name in {"self._execute", "_execute"} or name.endswith("._execute")


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _attribute_name(node)
    return ""


def _attribute_name(node: ast.Attribute) -> str:
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _validate_binding_expressions(
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    errors.extend(
        _validate_expression_mapping(
            binding=binding,
            operation=operation,
            mapping=binding.factory_args,
            subject="factory_args",
        )
    )
    errors.extend(
        _validate_expression_mapping(
            binding=binding,
            operation=operation,
            mapping=binding.method_args,
            subject="method_args",
        )
    )
    return tuple(errors)


def _validate_expression_mapping(
    *,
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    mapping: Mapping[str, str],
    subject: str,
) -> tuple[SwaggerReportError, ...]:
    errors: list[SwaggerReportError] = []
    for argument_name, expression in sorted(mapping.items()):
        errors.extend(
            _validate_expression(
                binding=binding,
                operation=operation,
                subject=subject,
                argument_name=argument_name,
                expression=expression,
            )
        )
    return tuple(errors)


def _validate_expression(
    *,
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    subject: str,
    argument_name: str,
    expression: str,
) -> tuple[SwaggerReportError, ...]:
    if expression == "body":
        if operation.request_body is None:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_BODY_MISSING",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        "`body`, но Swagger operation не содержит requestBody."
                    ),
                ),
            )
        return ()

    prefix, separator, field_name = expression.partition(".")
    if not separator or not field_name:
        return (
            _expression_error(
                binding=binding,
                code="SWAGGER_BINDING_EXPRESSION_INVALID",
                message=(
                    f"{binding.sdk_method}: {subject}.{argument_name} содержит "
                    f"некорректное expression `{expression}`."
                ),
            ),
        )

    if prefix == "path":
        return _validate_parameter_expression(
            binding=binding,
            operation=operation,
            subject=subject,
            argument_name=argument_name,
            expression=expression,
            field_name=field_name,
            location="path",
        )
    if prefix == "query":
        return _validate_parameter_expression(
            binding=binding,
            operation=operation,
            subject=subject,
            argument_name=argument_name,
            expression=expression,
            field_name=field_name,
            location="query",
        )
    if prefix == "header":
        return _validate_parameter_expression(
            binding=binding,
            operation=operation,
            subject=subject,
            argument_name=argument_name,
            expression=expression,
            field_name=field_name,
            location="header",
        )
    if prefix == "body":
        request_body = operation.request_body
        if request_body is None:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_BODY_MISSING",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        f"`{expression}`, но Swagger operation не содержит requestBody."
                    ),
                ),
            )
        if not request_body.schema_extracted:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_BODY_SCHEMA_UNSUPPORTED",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        f"`{expression}`, но requestBody schema не поддержана для "
                        "field-level validation."
                    ),
                ),
            )
        if request_body.schema is None:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_BODY_SCHEMA_UNSUPPORTED",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        f"`{expression}`, но requestBody schema не разобрана."
                    ),
                ),
            )
        try:
            resolve_body_path(request_body.schema, field_name)
        except SwaggerSchemaPathError as exc:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_BODY_FIELD_NOT_FOUND",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        f"`{expression}`, но {exc}"
                    ),
                ),
            )
        return ()
    if prefix == "constant":
        if field_name not in _TEST_CONSTANTS:
            return (
                _expression_error(
                    binding=binding,
                    code="SWAGGER_BINDING_CONSTANT_NOT_FOUND",
                    message=(
                        f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                        f"неизвестную test constant `{field_name}`."
                    ),
                ),
            )
        return ()
    return (
        _expression_error(
            binding=binding,
            code="SWAGGER_BINDING_EXPRESSION_UNKNOWN",
            message=(
                f"{binding.sdk_method}: {subject}.{argument_name} использует "
                f"запрещённый expression prefix `{prefix}`."
            ),
        ),
    )


def _validate_parameter_expression(
    *,
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
    subject: str,
    argument_name: str,
    expression: str,
    field_name: str,
    location: str,
) -> tuple[SwaggerReportError, ...]:
    parameter_names = {
        parameter.name for parameter in operation.parameters if parameter.location == location
    }
    if field_name in parameter_names:
        return ()
    return (
        _expression_error(
            binding=binding,
            code=f"SWAGGER_BINDING_{location.upper()}_PARAMETER_NOT_FOUND",
            message=(
                f"{binding.sdk_method}: {subject}.{argument_name} указывает на "
                f"`{expression}`, но Swagger operation не содержит {location}-parameter "
                f"`{field_name}`."
            ),
        ),
    )


def _expression_error(
    *,
    binding: DiscoveredSwaggerBinding,
    code: str,
    message: str,
) -> SwaggerReportError:
    return SwaggerReportError(
        code=code,
        message=message,
        operation_key=binding.operation_key,
        sdk_method=binding.sdk_method,
    )


def _load_sdk_method(binding: DiscoveredSwaggerBinding) -> Callable[..., object] | None:
    module = importlib.import_module(binding.module)
    cls = getattr(module, binding.class_name, None)
    method = getattr(cls, binding.method_name, None)
    return method if callable(method) else None


def _has_runtime_deprecation(method: Callable[..., object] | None) -> bool:
    metadata = getattr(method, "__sdk_deprecation__", None)
    return isinstance(metadata, DeprecatedSdkSymbol)


def _validate_signature_mapping(
    *,
    binding: DiscoveredSwaggerBinding,
    signature: inspect.Signature,
    mapping: Mapping[str, str],
    subject: str,
    code_prefix: str,
) -> tuple[SwaggerReportError, ...]:
    parameters = _mappable_parameters(signature)
    parameter_names = set(parameters)
    errors: list[SwaggerReportError] = []

    for argument_name in sorted(set(mapping) - parameter_names):
        errors.append(
            SwaggerReportError(
                code=f"{code_prefix}_ARG_UNKNOWN",
                message=(
                    f"{binding.sdk_method}: {subject} не содержит параметр `{argument_name}`."
                ),
                operation_key=binding.operation_key,
                sdk_method=binding.sdk_method,
            )
        )

    for argument_name, parameter in parameters.items():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if argument_name not in mapping:
            errors.append(
                SwaggerReportError(
                    code=f"{code_prefix}_ARG_REQUIRED",
                    message=(
                        f"{binding.sdk_method}: обязательный параметр {subject} "
                        f"`{argument_name}` не покрыт mapping-ом."
                    ),
                    operation_key=binding.operation_key,
                    sdk_method=binding.sdk_method,
                )
            )
    return tuple(errors)


def _mappable_parameters(
    signature: inspect.Signature,
) -> Mapping[str, inspect.Parameter]:
    return {
        name: parameter
        for name, parameter in signature.parameters.items()
        if name != "self"
        and parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }


__all__ = ("lint_swagger_bindings",)
