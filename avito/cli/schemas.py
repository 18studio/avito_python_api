"""Типизация и приведение входных параметров CLI."""

from __future__ import annotations

import importlib
import inspect
import types
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Literal, Union, get_args, get_origin, get_type_hints

from avito.cli.errors import CliValidationError
from avito.client import AvitoClient
from avito.core.swagger_discovery import DiscoveredSwaggerBinding

CliParameterSource = Literal["factory", "method"]
CliValueKind = Literal["string", "integer", "float", "boolean", "date", "datetime", "enum", "list", "unknown"]

_CONTROL_PARAMETER_NAMES = frozenset({"timeout", "retry"})
_NONE_TYPE = type(None)
_BOOLEAN_TRUE = frozenset({"1", "true", "yes", "y", "on", "да", "д"})
_BOOLEAN_FALSE = frozenset({"0", "false", "no", "n", "off", "нет", "н"})


@dataclass(frozen=True, slots=True)
class CliParameterSchema:
    """Аргумент CLI-команды, выбранный из Swagger binding metadata."""

    name: str
    source: CliParameterSource
    binding_expression: str
    flag: str
    value_kind: CliValueKind
    required: bool
    multiple: bool
    item_value_kind: CliValueKind | None
    annotation: str
    enum_values: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимое описание параметра."""

        return {
            "name": self.name,
            "source": self.source,
            "binding_expression": self.binding_expression,
            "flag": self.flag,
            "value_kind": self.value_kind,
            "required": self.required,
            "multiple": self.multiple,
            "item_value_kind": self.item_value_kind,
            "annotation": self.annotation,
            "enum_values": list(self.enum_values),
        }


@dataclass(frozen=True, slots=True)
class CoercedParameter:
    """Приведенное значение параметра CLI."""

    name: str
    value: object


@dataclass(frozen=True, slots=True)
class _CallableSchemaContext:
    """Signature and type hints used to build parameter schemas."""

    signature: inspect.Signature
    type_hints: Mapping[str, object]


def build_parameter_schemas(binding: DiscoveredSwaggerBinding) -> tuple[CliParameterSchema, ...]:
    """Построить CLI schema только из factory_args и method_args binding."""

    if binding.factory is None:
        return ()
    factory_context = _context_for_factory(binding.factory)
    method_context = _context_for_sdk_method(binding)
    schemas: list[CliParameterSchema] = []
    schemas.extend(
        _build_schema(
            name=name,
            source="factory",
            expression=expression,
            context=factory_context,
        )
        for name, expression in sorted(binding.factory_args.items())
        if name not in _CONTROL_PARAMETER_NAMES
    )
    schemas.extend(
        _build_schema(
            name=name,
            source="method",
            expression=expression,
            context=method_context,
        )
        for name, expression in sorted(binding.method_args.items())
        if name not in _CONTROL_PARAMETER_NAMES
    )
    return tuple(schemas)


def coerce_cli_values(
    schemas: Sequence[CliParameterSchema],
    raw_values: Mapping[str, Sequence[str]],
    *,
    no_input: bool = False,
) -> dict[str, object]:
    """Привести набор строковых CLI-значений по schema."""

    coerced: dict[str, object] = {}
    for schema in schemas:
        values = tuple(raw_values.get(schema.name, ()))
        if not values:
            if schema.required:
                message = f"Не указан обязательный параметр {schema.flag}."
                if no_input:
                    message = f"{message} Интерактивный ввод отключен."
                raise CliValidationError(message, details={"parameter": schema.name})
            continue
        coerced[schema.name] = coerce_cli_value(schema, values)
    return coerced


def coerce_cli_value(schema: CliParameterSchema, values: Sequence[str]) -> object:
    """Привести одно CLI-значение или повторяющийся флаг по schema."""

    if schema.multiple or schema.value_kind == "list":
        item_kind = schema.item_value_kind or "string"
        return [
            _coerce_scalar(schema, item, value_kind=item_kind)
            for item in _split_list_values(values)
        ]
    if len(values) != 1:
        raise CliValidationError(
            f"Параметр {schema.flag} нельзя передавать несколько раз.",
            details={"parameter": schema.name, "values": list(values)},
        )
    return _coerce_scalar(schema, values[0], value_kind=schema.value_kind)


def _context_for_factory(factory_name: str) -> _CallableSchemaContext:
    """Построить schema context для AvitoClient factory."""

    factory = getattr(AvitoClient, factory_name)
    return _context_for_callable(factory)


def _context_for_sdk_method(binding: DiscoveredSwaggerBinding) -> _CallableSchemaContext:
    """Построить schema context для публичного SDK method."""

    module = importlib.import_module(binding.module)
    domain_class = getattr(module, binding.class_name)
    method = getattr(domain_class, binding.method_name)
    return _context_for_callable(method)


def _context_for_callable(callable_object: Callable[..., object]) -> _CallableSchemaContext:
    """Построить schema context для callable object."""

    return _CallableSchemaContext(
        signature=inspect.signature(callable_object),
        type_hints=get_type_hints(callable_object),
    )


def _build_schema(
    *,
    name: str,
    source: CliParameterSource,
    expression: str,
    context: _CallableSchemaContext,
) -> CliParameterSchema:
    """Построить schema для одного selected binding argument."""

    parameter = context.signature.parameters.get(name)
    annotation: object = object
    required = True
    if parameter is not None:
        annotation = _resolve_annotation(context, parameter)
        required = parameter.default is inspect.Parameter.empty
    value_kind, item_value_kind, enum_values = _classify_annotation(name, annotation)
    return CliParameterSchema(
        name=name,
        source=source,
        binding_expression=expression,
        flag=_flag_for_name(name),
        value_kind=value_kind,
        required=required,
        multiple=value_kind == "list",
        item_value_kind=item_value_kind,
        annotation=_annotation_label(annotation),
        enum_values=enum_values,
    )


def _resolve_annotation(context: _CallableSchemaContext, parameter: inspect.Parameter) -> object:
    """Вернуть resolved type annotation для parameter."""

    annotation = context.type_hints.get(parameter.name)
    if annotation is not None:
        return annotation
    if parameter.annotation is inspect.Parameter.empty:
        return object
    return parameter.annotation


def _classify_annotation(
    name: str,
    annotation: object,
) -> tuple[CliValueKind, CliValueKind | None, tuple[str, ...]]:
    """Классифицировать type annotation в CLI value kind."""

    normalized = _strip_optional(annotation)
    origin = get_origin(normalized)
    if origin in {list, tuple, Sequence}:
        item_annotation = _first_type_arg(normalized)
        item_kind, _nested_item_kind, enum_values = _classify_annotation(name, item_annotation)
        return "list", item_kind, enum_values
    if _is_union_origin(origin):
        return _classify_union(name, normalized)
    if isinstance(normalized, type) and issubclass(normalized, Enum):
        return "enum", None, _enum_values(normalized)
    if normalized is bool:
        return "boolean", None, ()
    if normalized is int:
        return "integer", None, ()
    if normalized is float:
        return "float", None, ()
    if normalized is datetime:
        return "datetime", None, ()
    if normalized is date:
        return "date", None, ()
    if normalized is str:
        return _string_kind_for_name(name), None, ()
    if normalized is object:
        return "unknown", None, ()
    return "unknown", None, ()


def _classify_union(
    name: str,
    annotation: object,
) -> tuple[CliValueKind, CliValueKind | None, tuple[str, ...]]:
    """Классифицировать union annotation в CLI value kind."""

    choices = tuple(argument for argument in get_args(annotation) if argument is not _NONE_TYPE)
    enum_choices = tuple(choice for choice in choices if isinstance(choice, type) and issubclass(choice, Enum))
    if enum_choices:
        enum_type = enum_choices[0]
        return "enum", None, _enum_values(enum_type)
    if datetime in choices:
        return "datetime", None, ()
    if date in choices:
        return _string_kind_for_name(name), None, ()
    if int in choices and _integer_name(name):
        return "integer", None, ()
    if str in choices:
        return _string_kind_for_name(name), None, ()
    if bool in choices:
        return "boolean", None, ()
    if int in choices:
        return "integer", None, ()
    if float in choices:
        return "float", None, ()
    return "unknown", None, ()


def _strip_optional(annotation: object) -> object:
    """Убрать None из Optional annotation, если это единственный wrapper."""

    origin = get_origin(annotation)
    if not _is_union_origin(origin):
        return annotation
    choices = tuple(argument for argument in get_args(annotation) if argument is not _NONE_TYPE)
    if len(choices) == 1:
        return choices[0]
    return annotation


def _is_union_origin(origin: object) -> bool:
    """Проверить, является ли origin union type."""

    return origin in {Union, types.UnionType}


def _first_type_arg(annotation: object) -> object:
    """Вернуть первый generic type argument или str по умолчанию."""

    arguments = get_args(annotation)
    if not arguments:
        return str
    return arguments[0]


def _string_kind_for_name(name: str) -> CliValueKind:
    """Уточнить string-like kind по имени параметра."""

    if "date_time" in name or name.endswith("_at") or name.endswith("_time"):
        return "datetime"
    if "date" in name or name.endswith("_from") or name.endswith("_to"):
        return "date"
    return "string"


def _integer_name(name: str) -> bool:
    """Проверить, выглядит ли имя параметра как integer id."""

    return name == "id" or name.endswith("_id") or name.endswith("_ids")


def _enum_values(enum_type: type[Enum]) -> tuple[str, ...]:
    """Вернуть допустимые строковые enum values."""

    return tuple(str(item.value) for item in enum_type)


def _annotation_label(annotation: object) -> str:
    """Вернуть стабильную подпись annotation для coverage report."""

    if annotation is object:
        return "object"
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)


def _flag_for_name(name: str) -> str:
    """Преобразовать parameter name в CLI flag."""

    normalized = name.replace("_", "-")
    return f"--{normalized}"


def _split_list_values(values: Sequence[str]) -> tuple[str, ...]:
    """Развернуть repeated и comma-separated list values."""

    items: list[str] = []
    for value in values:
        for item in value.split(","):
            normalized = item.strip()
            if normalized:
                items.append(normalized)
    return tuple(items)


def _coerce_scalar(
    schema: CliParameterSchema,
    value: str,
    *,
    value_kind: CliValueKind,
) -> object:
    """Привести scalar CLI value к schema kind."""

    normalized = value.strip()
    if value_kind == "string" or value_kind == "unknown":
        return value
    if value_kind == "integer":
        return _coerce_int(schema, normalized)
    if value_kind == "float":
        return _coerce_float(schema, normalized)
    if value_kind == "boolean":
        return _coerce_bool(schema, normalized)
    if value_kind == "date":
        return _coerce_date(schema, normalized)
    if value_kind == "datetime":
        return _coerce_datetime(schema, normalized)
    if value_kind == "enum":
        return _coerce_enum(schema, normalized)
    if value_kind == "list":
        raise CliValidationError(
            f"Параметр {schema.flag} имеет вложенный список, который CLI не поддерживает.",
            details={"parameter": schema.name},
        )
    raise CliValidationError(
        f"Параметр {schema.flag} имеет неподдерживаемый тип.",
        details={"parameter": schema.name, "value_kind": value_kind},
    )


def _coerce_int(schema: CliParameterSchema, value: str) -> int:
    """Привести CLI value к int."""

    try:
        return int(value, 10)
    except ValueError as exc:
        raise CliValidationError(
            f"Параметр {schema.flag} должен быть целым числом.",
            details={"parameter": schema.name, "value": value},
        ) from exc


def _coerce_float(schema: CliParameterSchema, value: str) -> float:
    """Привести CLI value к float."""

    try:
        return float(value)
    except ValueError as exc:
        raise CliValidationError(
            f"Параметр {schema.flag} должен быть числом.",
            details={"parameter": schema.name, "value": value},
        ) from exc


def _coerce_bool(schema: CliParameterSchema, value: str) -> bool:
    """Привести CLI value к bool."""

    normalized = value.lower()
    if normalized in _BOOLEAN_TRUE:
        return True
    if normalized in _BOOLEAN_FALSE:
        return False
    raise CliValidationError(
        f"Параметр {schema.flag} должен быть boolean-значением.",
        details={"parameter": schema.name, "value": value},
    )


def _coerce_date(schema: CliParameterSchema, value: str) -> date:
    """Привести CLI value к date."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CliValidationError(
            f"Параметр {schema.flag} должен быть датой в формате YYYY-MM-DD.",
            details={"parameter": schema.name, "value": value},
        ) from exc


def _coerce_datetime(schema: CliParameterSchema, value: str) -> datetime:
    """Привести CLI value к datetime."""

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CliValidationError(
            f"Параметр {schema.flag} должен быть датой-временем в ISO-формате.",
            details={"parameter": schema.name, "value": value},
        ) from exc


def _coerce_enum(schema: CliParameterSchema, value: str) -> str:
    """Проверить CLI value против enum values."""

    normalized = value.lower()
    for enum_value in schema.enum_values:
        if value == enum_value or normalized == enum_value.lower():
            return enum_value
    allowed = ", ".join(schema.enum_values)
    raise CliValidationError(
        f"Параметр {schema.flag} должен быть одним из значений: {allowed}.",
        details={"parameter": schema.name, "value": value, "allowed": list(schema.enum_values)},
    )


__all__ = (
    "CliParameterSchema",
    "CliParameterSource",
    "CliValueKind",
    "CoercedParameter",
    "build_parameter_schemas",
    "coerce_cli_value",
    "coerce_cli_values",
)
