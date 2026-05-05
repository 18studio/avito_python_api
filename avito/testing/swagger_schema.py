"""Strict Swagger JSON schema helpers for SDK contract tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from avito.core.swagger_registry import SwaggerSchema

JsonValue = Mapping[str, object] | list[object] | str | int | float | bool | None


def generate_schema_value(schema: SwaggerSchema) -> JsonValue:
    """Build deterministic JSON value that covers all fields in a Swagger schema."""

    if schema.enum:
        value = schema.enum[0]
        if _value_matches_kind(value, schema.kind):
            return _json_value(value)
    if schema.kind == "object":
        return {
            name: generate_schema_value(property_schema)
            for name, property_schema in schema.properties.items()
        }
    if schema.kind == "array":
        if schema.items is None:
            raise AssertionError("Swagger array schema не содержит items.")
        return [generate_schema_value(schema.items)]
    if schema.kind == "union":
        if not schema.variants:
            raise AssertionError("Swagger union schema не содержит variants.")
        return generate_schema_value(schema.variants[0])
    if schema.kind == "string":
        return "value"
    if schema.kind == "integer":
        return 1
    if schema.kind == "number":
        return 1.5
    if schema.kind == "boolean":
        return True
    if schema.kind == "null":
        return None
    raise AssertionError(f"Неподдерживаемый Swagger schema kind: {schema.kind}")


def validate_schema_value(value: object, schema: SwaggerSchema, *, path: str) -> None:
    """Validate JSON value keys and types against a normalized Swagger schema."""

    if value is None and schema.nullable:
        return
    if schema.kind == "union":
        variant_errors: list[str] = []
        for variant in schema.variants:
            try:
                validate_schema_value(value, variant, path=path)
            except AssertionError as exc:
                variant_errors.append(str(exc))
            else:
                return
        raise AssertionError(
            f"{path}: значение не соответствует ни одному варианту: {variant_errors}"
        )
    if schema.kind == "object":
        if not isinstance(value, Mapping):
            raise AssertionError(f"{path}: ожидался object, получен {_json_type(value)}.")
        missing = sorted(name for name in schema.required if name not in value)
        if missing:
            raise AssertionError(f"{path}: отсутствуют обязательные поля {missing}.")
        extra = sorted(str(name) for name in value if name not in schema.properties)
        if extra and schema.properties:
            raise AssertionError(f"{path}: лишние поля {extra}.")
        for name, item in value.items():
            property_schema = schema.properties.get(str(name))
            if property_schema is None:
                continue
            validate_schema_value(item, property_schema, path=f"{path}.{name}")
        return
    if schema.kind == "array":
        if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
            raise AssertionError(f"{path}: ожидался array, получен {_json_type(value)}.")
        if schema.items is None:
            raise AssertionError(f"{path}: Swagger array schema не содержит items.")
        for index, item in enumerate(value):
            validate_schema_value(item, schema.items, path=f"{path}[{index}]")
        return
    if not _value_matches_kind(value, schema.kind):
        raise AssertionError(f"{path}: ожидался {schema.kind}, получен {_json_type(value)}.")


def _value_matches_kind(value: object, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "null":
        return value is None
    if kind == "object":
        return isinstance(value, Mapping)
    if kind == "array":
        return isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray)
    return False


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return "array"
    return type(value).__name__


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise AssertionError(f"Swagger enum value не является JSON scalar: {value!r}")


__all__ = ("generate_schema_value", "validate_schema_value")
