"""Swagger/OpenAPI registry used by binding linting tools."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from avito.core.swagger_names import swagger_field_aliases

HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put", "trace"})
DEFAULT_SWAGGER_API_DIR = Path("docs/avito/api")

_PATH_PARAMETER_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")

JsonObject = dict[str, object]


class SwaggerRegistryError(Exception):
    """Ошибка чтения или валидации локального Swagger corpus."""


@dataclass(frozen=True, slots=True)
class SwaggerValidationError:
    """Нефатальная ошибка валидации Swagger operation, найденная при разборе specs."""

    code: str
    message: str
    operation_key: str | None = None


@dataclass(frozen=True, slots=True)
class SwaggerParameter:
    """Параметр Swagger operation после разрешения локальных `$ref`."""

    name: str
    location: str
    required: bool


@dataclass(frozen=True, slots=True)
class SwaggerRequestBody:
    """Metadata request body для validation binding expressions."""

    required: bool
    content_types: tuple[str, ...]
    field_names: tuple[str, ...]
    schema_extracted: bool
    schema: SwaggerSchema | None = None


@dataclass(frozen=True, slots=True)
class SwaggerResponse:
    """Минимальная metadata Swagger response для contract tests."""

    status_code: str
    content_types: tuple[str, ...]
    schema: SwaggerSchema | None = None

    @property
    def is_success(self) -> bool:
        return self.status_code.isdigit() and 200 <= int(self.status_code) < 300

    @property
    def is_error(self) -> bool:
        return self.status_code == "default" or (
            self.status_code.isdigit() and int(self.status_code) >= 400
        )


@dataclass(frozen=True, slots=True)
class SwaggerSchema:
    """Normalized JSON schema subset used by strict SDK contract tests."""

    kind: str
    properties: Mapping[str, SwaggerSchema] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    items: SwaggerSchema | None = None
    variants: tuple[SwaggerSchema, ...] = ()
    nullable: bool = False
    enum: tuple[object, ...] = ()

    @property
    def is_object(self) -> bool:
        return self.kind == "object"

    @property
    def is_array(self) -> bool:
        return self.kind == "array"


@dataclass(frozen=True, slots=True)
class SwaggerOperation:
    """Одна Swagger/OpenAPI operation с normalized identity."""

    spec: str
    method: str
    path: str
    operation_id: str | None
    deprecated: bool
    parameters: tuple[SwaggerParameter, ...]
    request_body: SwaggerRequestBody | None
    responses: tuple[SwaggerResponse, ...]

    @property
    def key(self) -> str:
        return f"{self.spec} {self.method} {self.path}"

    @property
    def path_parameters(self) -> tuple[SwaggerParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.location == "path")

    @property
    def query_parameters(self) -> tuple[SwaggerParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.location == "query")

    @property
    def header_parameters(self) -> tuple[SwaggerParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.location == "header")

    @property
    def success_responses(self) -> tuple[SwaggerResponse, ...]:
        return tuple(response for response in self.responses if response.is_success)

    @property
    def error_responses(self) -> tuple[SwaggerResponse, ...]:
        return tuple(response for response in self.responses if response.is_error)


@dataclass(frozen=True, slots=True)
class SwaggerSpec:
    """Один Swagger/OpenAPI файл и извлечённые из него операции."""

    name: str
    path: Path
    operations: tuple[SwaggerOperation, ...]


@dataclass(frozen=True, slots=True)
class SwaggerRegistry:
    """Полный локальный Swagger corpus."""

    specs: tuple[SwaggerSpec, ...]
    errors: tuple[SwaggerValidationError, ...] = ()

    @property
    def operations(self) -> tuple[SwaggerOperation, ...]:
        return tuple(operation for spec in self.specs for operation in spec.operations)

    @property
    def deprecated_operations(self) -> tuple[SwaggerOperation, ...]:
        return tuple(operation for operation in self.operations if operation.deprecated)


def load_swagger_registry(
    api_dir: Path = DEFAULT_SWAGGER_API_DIR,
    *,
    strict: bool = False,
) -> SwaggerRegistry:
    """Загружает и валидирует все Swagger/OpenAPI specs из каталога."""

    spec_paths = tuple(sorted(api_dir.glob("*.json")))
    if not spec_paths:
        raise SwaggerRegistryError(f"В каталоге {api_dir} не найдены JSON-файлы Swagger.")

    errors: list[SwaggerValidationError] = []
    specs = tuple(_load_spec(path, errors) for path in spec_paths)
    _validate_unique_operation_keys(specs, errors)
    registry = SwaggerRegistry(specs=specs, errors=tuple(errors))
    if strict and registry.errors:
        messages = "; ".join(error.message for error in registry.errors)
        raise SwaggerRegistryError(messages)
    return registry


def normalize_swagger_method(method: str) -> str:
    """Возвращает normalized HTTP method для operation identity."""

    normalized = method.strip().upper()
    if not normalized:
        raise SwaggerRegistryError("HTTP-метод Swagger operation не может быть пустым.")
    return normalized


def normalize_swagger_path(path: str) -> str:
    """Возвращает normalized Swagger path для operation identity."""

    normalized = path.strip()
    if not normalized.startswith("/"):
        raise SwaggerRegistryError(f"Swagger path должен начинаться с `/`: {path}")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    without_parameters = _PATH_PARAMETER_RE.sub("", normalized)
    if "{" in without_parameters or "}" in without_parameters:
        raise SwaggerRegistryError(
            f"Swagger path должен использовать параметры в формате `{{name}}`: {path}"
        )
    return normalized


def _load_spec(path: Path, errors: list[SwaggerValidationError]) -> SwaggerSpec:
    try:
        # `json.loads()` возвращает object на границе JSON-декодирования.
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise SwaggerRegistryError(f"Файл {path} содержит некорректный JSON: {exc}") from exc
    spec = _require_mapping(raw, f"{path}")
    paths = _require_mapping(spec.get("paths"), f"{path}: поле paths")

    operations: list[SwaggerOperation] = []
    for raw_path, raw_path_item in sorted(paths.items()):
        if not isinstance(raw_path, str):
            raise SwaggerRegistryError(f"{path}: ключ paths должен быть строкой.")
        path_item = _require_mapping(raw_path_item, f"{path}: path item {raw_path}")
        path_parameters = _extract_parameters(
            spec=spec,
            parameters=_optional_sequence(
                path_item.get("parameters"), f"{path}: {raw_path}.parameters"
            ),
            source=f"{path}: {raw_path}.parameters",
        )
        for raw_method, raw_operation in sorted(path_item.items()):
            if not isinstance(raw_method, str) or raw_method.lower() not in HTTP_METHODS:
                continue
            operation = _require_mapping(raw_operation, f"{path}: {raw_path}.{raw_method}")
            operation_parameters = _extract_parameters(
                spec=spec,
                parameters=_optional_sequence(
                    operation.get("parameters"),
                    f"{path}: {raw_path}.{raw_method}.parameters",
                ),
                source=f"{path}: {raw_path}.{raw_method}.parameters",
            )
            normalized_path = normalize_swagger_path(raw_path)
            parameters = (*path_parameters, *operation_parameters)
            normalized_path = _normalize_path_parameter_aliases(
                path=normalized_path,
                parameters=parameters,
            )
            _validate_path_parameters(
                spec_name=path.name,
                method=normalize_swagger_method(raw_method),
                path=normalized_path,
                parameters=parameters,
                errors=errors,
            )
            operations.append(
                SwaggerOperation(
                    spec=path.name,
                    method=normalize_swagger_method(raw_method),
                    path=normalized_path,
                    operation_id=_optional_string(operation.get("operationId")),
                    deprecated=operation.get("deprecated") is True,
                    parameters=parameters,
                    request_body=_extract_request_body(
                        spec=spec,
                        raw_request_body=operation.get("requestBody"),
                    ),
                    responses=_extract_responses(operation.get("responses"), spec=spec),
                )
            )

    return SwaggerSpec(name=path.name, path=path, operations=tuple(operations))


def _extract_parameters(
    *,
    spec: Mapping[str, object],
    parameters: Iterable[object],
    source: str,
) -> tuple[SwaggerParameter, ...]:
    extracted: list[SwaggerParameter] = []
    for index, raw_parameter in enumerate(parameters):
        parameter = _resolve_ref(spec, raw_parameter, f"{source}[{index}]")
        name = _required_string(parameter.get("name"), f"{source}[{index}].name")
        location = _required_string(parameter.get("in"), f"{source}[{index}].in")
        extracted.append(
            SwaggerParameter(
                name=name,
                location=location,
                required=parameter.get("required") is True,
            )
        )
    return tuple(extracted)


def _extract_request_body(
    *,
    spec: Mapping[str, object],
    raw_request_body: object,
) -> SwaggerRequestBody | None:
    if raw_request_body is None:
        return None
    request_body = _resolve_component_ref(
        spec=spec,
        raw_value=raw_request_body,
        source="requestBody",
        component_name="requestBodies",
    )
    content = _require_mapping(request_body.get("content"), "requestBody.content")
    field_names: set[str] = set()
    schema_extracted = True
    schema_count = 0
    selected_schema: SwaggerSchema | None = None
    for content_type, raw_media_type in content.items():
        media_type = _require_mapping(
            raw_media_type,
            f"requestBody.content.{content_type}",
        )
        raw_schema = media_type.get("schema")
        if raw_schema is None:
            schema_extracted = False
            continue
        schema_count += 1
        parsed_schema = _extract_schema(
            spec=spec,
            raw_schema=raw_schema,
            source=f"requestBody.content.{content_type}.schema",
            seen_refs=frozenset(),
        )
        if parsed_schema is None:
            schema_extracted = False
        elif selected_schema is None or str(content_type) == "application/json":
            selected_schema = parsed_schema
        extracted = _extract_schema_field_names(
            spec=spec,
            raw_schema=raw_schema,
            source=f"requestBody.content.{content_type}.schema",
            seen_refs=frozenset(),
        )
        if extracted is None:
            schema_extracted = False
            continue
        field_names.update(extracted)
    if schema_count == 0:
        schema_extracted = False
    return SwaggerRequestBody(
        required=request_body.get("required") is True,
        content_types=tuple(sorted(str(content_type) for content_type in content)),
        field_names=tuple(sorted(field_names)),
        schema_extracted=schema_extracted,
        schema=selected_schema,
    )


def _extract_responses(
    raw_responses: object,
    *,
    spec: Mapping[str, object],
) -> tuple[SwaggerResponse, ...]:
    responses = _require_mapping(raw_responses, "responses")
    extracted: list[SwaggerResponse] = []
    for raw_status_code, raw_response in sorted(responses.items()):
        if not isinstance(raw_status_code, str):
            raise SwaggerRegistryError("responses должен использовать строковые status codes.")
        response = _resolve_component_ref(
            spec=spec,
            raw_value=raw_response,
            source=f"responses.{raw_status_code}",
            component_name="responses",
        )
        content = response.get("content")
        content_types: tuple[str, ...] = ()
        selected_schema: SwaggerSchema | None = None
        if isinstance(content, Mapping):
            content_types = tuple(sorted(str(content_type) for content_type in content))
            for content_type, raw_media_type in content.items():
                media_type = _require_mapping(
                    raw_media_type,
                    f"responses.{raw_status_code}.content.{content_type}",
                )
                raw_schema = media_type.get("schema")
                if raw_schema is None:
                    continue
                parsed_schema = _extract_schema(
                    spec=spec,
                    raw_schema=raw_schema,
                    source=f"responses.{raw_status_code}.content.{content_type}.schema",
                    seen_refs=frozenset(),
                )
                if parsed_schema is not None and (
                    selected_schema is None or str(content_type) == "application/json"
                ):
                    selected_schema = parsed_schema
        extracted.append(
            SwaggerResponse(
                status_code=raw_status_code,
                content_types=content_types,
                schema=selected_schema,
            )
        )
    return tuple(extracted)


def _validate_path_parameters(
    *,
    spec_name: str,
    method: str,
    path: str,
    parameters: tuple[SwaggerParameter, ...],
    errors: list[SwaggerValidationError],
) -> None:
    path_parameter_names = set(_PATH_PARAMETER_RE.findall(path))
    described_path_parameter_names = {
        parameter.name for parameter in parameters if parameter.location == "path"
    }
    if path_parameter_names != described_path_parameter_names:
        missing = sorted(path_parameter_names - described_path_parameter_names)
        extra = sorted(described_path_parameter_names - path_parameter_names)
        operation_key = f"{spec_name} {method} {path}"
        errors.append(
            SwaggerValidationError(
                code="SWAGGER_PATH_PARAMETER_MISMATCH",
                message=(
                    f"{operation_key}: path parameters не совпадают с URL "
                    f"(missing={missing}, extra={extra})."
                ),
                operation_key=operation_key,
            )
        )


def _normalize_path_parameter_aliases(
    *,
    path: str,
    parameters: tuple[SwaggerParameter, ...],
) -> str:
    """Normalizes path placeholders to described path parameter names."""

    described_path_parameters = tuple(
        parameter for parameter in parameters if parameter.location == "path"
    )
    if not described_path_parameters:
        return path

    described_by_token: dict[str, str | None] = {}
    for parameter in described_path_parameters:
        token = _parameter_name_token(parameter.name)
        if token in described_by_token:
            described_by_token[token] = None
        else:
            described_by_token[token] = parameter.name

    def replace(match: re.Match[str]) -> str:
        raw_name = match.group(1)
        described_name = described_by_token.get(_parameter_name_token(raw_name))
        if described_name is None:
            return match.group(0)
        return f"{{{described_name}}}"

    return _PATH_PARAMETER_RE.sub(replace, path)


def _parameter_name_token(name: str) -> str:
    return name.replace("_", "").lower()


def _validate_unique_operation_keys(
    specs: tuple[SwaggerSpec, ...],
    errors: list[SwaggerValidationError],
) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for spec in specs:
        for operation in spec.operations:
            if operation.key in seen:
                duplicates.append(operation.key)
            seen.add(operation.key)
    if duplicates:
        for operation_key in sorted(duplicates):
            errors.append(
                SwaggerValidationError(
                    code="SWAGGER_DUPLICATE_OPERATION_KEY",
                    message=f"Найден duplicate Swagger operation key: {operation_key}",
                    operation_key=operation_key,
                )
            )


def _resolve_ref(
    spec: Mapping[str, object], raw_value: object, source: str
) -> Mapping[str, object]:
    return _resolve_component_ref(
        spec=spec,
        raw_value=raw_value,
        source=source,
        component_name="parameters",
    )


def _resolve_component_ref(
    *,
    spec: Mapping[str, object],
    raw_value: object,
    source: str,
    component_name: str,
) -> Mapping[str, object]:
    value = _require_mapping(raw_value, source)
    raw_ref = value.get("$ref")
    if raw_ref is None:
        return value
    ref = _required_string(raw_ref, f"{source}.$ref")
    prefix = f"#/components/{component_name}/"
    if not ref.startswith(prefix):
        raise SwaggerRegistryError(
            f"{source}: поддерживаются только локальные refs components/{component_name}."
        )
    object_name = ref.removeprefix(prefix)
    components = _require_mapping(spec.get("components"), "components")
    component = _require_mapping(components.get(component_name), f"components.{component_name}")
    return _require_mapping(component.get(object_name), ref)


def _extract_schema_field_names(
    *,
    spec: Mapping[str, object],
    raw_schema: object,
    source: str,
    seen_refs: frozenset[str],
) -> set[str] | None:
    schema = _require_mapping(raw_schema, source)
    raw_ref = schema.get("$ref")
    if raw_ref is not None:
        ref = _required_string(raw_ref, f"{source}.$ref")
        if ref in seen_refs:
            return None
        prefix = "#/components/schemas/"
        if not ref.startswith(prefix):
            return None
        schema_name = ref.removeprefix(prefix)
        components = _require_mapping(spec.get("components"), "components")
        schemas = _require_mapping(components.get("schemas"), "components.schemas")
        resolved = _require_mapping(schemas.get(schema_name), ref)
        return _extract_schema_field_names(
            spec=spec,
            raw_schema=resolved,
            source=ref,
            seen_refs=seen_refs | frozenset({ref}),
        )

    fields: set[str] = set()
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        for field_name in properties:
            fields.update(_field_name_aliases(str(field_name)))

    composed_fields = _extract_composed_schema_field_names(
        spec=spec,
        schema=schema,
        source=source,
        seen_refs=seen_refs,
    )
    if composed_fields is None:
        return None
    fields.update(composed_fields)

    if fields:
        return fields
    if schema.get("type") == "object" and isinstance(properties, Mapping):
        return fields
    return None


def _extract_schema(
    *,
    spec: Mapping[str, object],
    raw_schema: object,
    source: str,
    seen_refs: frozenset[str],
) -> SwaggerSchema | None:
    schema = _require_mapping(raw_schema, source)
    raw_ref = schema.get("$ref")
    if raw_ref is not None:
        ref = _required_string(raw_ref, f"{source}.$ref")
        if ref in seen_refs:
            return SwaggerSchema(kind="object")
        prefix = "#/components/schemas/"
        if not ref.startswith(prefix):
            return None
        schema_name = ref.removeprefix(prefix)
        components = _require_mapping(spec.get("components"), "components")
        schemas = _require_mapping(components.get("schemas"), "components.schemas")
        resolved = _require_mapping(schemas.get(schema_name), ref)
        return _extract_schema(
            spec=spec,
            raw_schema=resolved,
            source=ref,
            seen_refs=seen_refs | frozenset({ref}),
        )

    composed_schema = _extract_composed_schema(
        spec=spec,
        schema=schema,
        source=source,
        seen_refs=seen_refs,
    )
    if composed_schema is not None:
        return composed_schema

    raw_type = schema.get("type")
    nullable = schema.get("nullable") is True
    raw_enum = schema.get("enum")
    enum_values = tuple(raw_enum) if isinstance(raw_enum, list) else ()
    if isinstance(raw_type, Mapping):
        nested_type = raw_type.get("type")
        nested_enum = raw_type.get("enum")
        if isinstance(nested_enum, list) and not enum_values:
            enum_values = tuple(nested_enum)
        raw_type = nested_type if isinstance(nested_type, str | list) else None
    if isinstance(raw_type, list):
        non_null_types = tuple(item for item in raw_type if item != "null")
        nullable = nullable or len(non_null_types) != len(raw_type)
        raw_type = non_null_types[0] if len(non_null_types) == 1 else None
    if raw_type is None and "properties" in schema:
        raw_type = "object"
    if raw_type is None and "items" in schema:
        raw_type = "array"
    if raw_type is None and enum_values:
        raw_type = _infer_enum_type(enum_values)
    if raw_type is None and "additionalProperties" in schema:
        raw_type = "object"
    if raw_type is None and ("minimum" in schema or "maximum" in schema):
        example = schema.get("example")
        raw_type = (
            "integer" if isinstance(example, int) and not isinstance(example, bool) else "number"
        )
    if isinstance(raw_type, str) and raw_type not in {
        "object",
        "array",
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }:
        raw_type = _infer_enum_type(enum_values)
    if raw_type is None:
        return None
    if raw_type == "object":
        properties: dict[str, SwaggerSchema] = {}
        raw_properties = schema.get("properties")
        if isinstance(raw_properties, Mapping):
            for property_name, raw_property_schema in raw_properties.items():
                property_schema = _extract_schema(
                    spec=spec,
                    raw_schema=raw_property_schema,
                    source=f"{source}.properties.{property_name}",
                    seen_refs=seen_refs,
                )
                if property_schema is None:
                    return None
                properties[str(property_name)] = property_schema
        return SwaggerSchema(
            kind="object",
            properties=properties,
            required=_known_required_field_names(schema.get("required"), properties, source),
            nullable=nullable,
            enum=enum_values,
        )
    if raw_type == "array":
        raw_items = schema.get("items")
        if raw_items is None:
            item_kind = _infer_enum_type(enum_values)
            if item_kind is None:
                return None
            return SwaggerSchema(
                kind="array",
                items=SwaggerSchema(kind=item_kind, enum=enum_values),
                nullable=nullable,
                enum=enum_values,
            )
        items = _extract_schema(
            spec=spec,
            raw_schema=raw_items,
            source=f"{source}.items",
            seen_refs=seen_refs,
        )
        if items is None:
            return None
        return SwaggerSchema(
            kind="array",
            items=items,
            nullable=nullable,
            enum=enum_values,
        )
    if raw_type in {"string", "integer", "number", "boolean", "null"}:
        return SwaggerSchema(kind=str(raw_type), nullable=nullable, enum=enum_values)
    return None


def _extract_composed_schema(
    *,
    spec: Mapping[str, object],
    schema: Mapping[str, object],
    source: str,
    seen_refs: frozenset[str],
) -> SwaggerSchema | None:
    raw_all_of = schema.get("allOf")
    if raw_all_of is not None:
        if not isinstance(raw_all_of, list):
            return None
        if len(raw_all_of) == 1:
            single_schema = _extract_schema(
                spec=spec,
                raw_schema=raw_all_of[0],
                source=f"{source}.allOf[0]",
                seen_refs=seen_refs,
            )
            if single_schema is not None:
                return SwaggerSchema(
                    kind=single_schema.kind,
                    properties=single_schema.properties,
                    required=single_schema.required,
                    items=single_schema.items,
                    variants=single_schema.variants,
                    nullable=single_schema.nullable or schema.get("nullable") is True,
                    enum=single_schema.enum,
                )
        merged_properties: dict[str, SwaggerSchema] = {}
        required: set[str] = set()
        nullable = schema.get("nullable") is True
        for index, raw_item in enumerate(raw_all_of):
            item_schema = _extract_schema(
                spec=spec,
                raw_schema=raw_item,
                source=f"{source}.allOf[{index}]",
                seen_refs=seen_refs,
            )
            if item_schema is None and _is_description_only_schema(raw_item):
                continue
            if item_schema is None or not item_schema.is_object:
                return None
            merged_properties.update(item_schema.properties)
            required.update(item_schema.required)
            nullable = nullable or item_schema.nullable
        required.update(_required_field_names(schema.get("required"), source))
        return SwaggerSchema(
            kind="object",
            properties=merged_properties,
            required=tuple(name for name in sorted(required) if name in merged_properties),
            nullable=nullable,
        )

    for keyword in ("oneOf", "anyOf"):
        raw_variants = schema.get(keyword)
        if raw_variants is None:
            continue
        if not isinstance(raw_variants, list):
            return None
        variants: list[SwaggerSchema] = []
        for index, raw_item in enumerate(raw_variants):
            item_schema = _extract_schema(
                spec=spec,
                raw_schema=raw_item,
                source=f"{source}.{keyword}[{index}]",
                seen_refs=seen_refs,
            )
            if item_schema is None:
                return None
            variants.append(item_schema)
        return SwaggerSchema(
            kind="union",
            variants=tuple(variants),
            nullable=schema.get("nullable") is True,
        )
    return None


def _required_field_names(value: object, source: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SwaggerRegistryError(f"{source}.required должно быть списком.")
    return tuple(sorted(str(item) for item in value))


def _known_required_field_names(
    value: object,
    properties: Mapping[str, SwaggerSchema],
    source: str,
) -> tuple[str, ...]:
    return tuple(name for name in _required_field_names(value, source) if name in properties)


def _is_description_only_schema(value: object) -> bool:
    return isinstance(value, Mapping) and set(value) <= {"description", "title"}


def _infer_enum_type(values: tuple[object, ...]) -> str | None:
    if all(isinstance(value, str) for value in values):
        return "string"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "integer"
    if all(isinstance(value, int | float) and not isinstance(value, bool) for value in values):
        return "number"
    return None


def _extract_composed_schema_field_names(
    *,
    spec: Mapping[str, object],
    schema: Mapping[str, object],
    source: str,
    seen_refs: frozenset[str],
) -> set[str] | None:
    fields: set[str] = set()
    for keyword in ("allOf", "oneOf", "anyOf"):
        raw_items = schema.get(keyword)
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            return None
        for index, raw_item in enumerate(raw_items):
            extracted = _extract_schema_field_names(
                spec=spec,
                raw_schema=raw_item,
                source=f"{source}.{keyword}[{index}]",
                seen_refs=seen_refs,
            )
            if extracted is None:
                return None
            fields.update(extracted)
    return fields


def _field_name_aliases(field_name: str) -> set[str]:
    return set(swagger_field_aliases(field_name))


def _optional_sequence(value: object, source: str) -> tuple[object, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SwaggerRegistryError(f"{source} должно быть списком.")
    return tuple(value)


def _require_mapping(value: object, source: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise SwaggerRegistryError(f"{source} должно быть JSON object.")
    return cast(JsonObject, value)


def _required_string(value: object, source: str) -> str:
    if not isinstance(value, str) or not value:
        raise SwaggerRegistryError(f"{source} должно быть непустой строкой.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = (
    "DEFAULT_SWAGGER_API_DIR",
    "SwaggerOperation",
    "SwaggerParameter",
    "SwaggerRegistry",
    "SwaggerRegistryError",
    "SwaggerRequestBody",
    "SwaggerResponse",
    "SwaggerSchema",
    "SwaggerSpec",
    "SwaggerValidationError",
    "load_swagger_registry",
    "normalize_swagger_method",
    "normalize_swagger_path",
)
