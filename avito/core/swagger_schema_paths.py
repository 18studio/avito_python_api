"""Validation helpers for Swagger binding body path expressions."""

from __future__ import annotations

from dataclasses import dataclass

from avito.core.swagger_names import swagger_field_aliases
from avito.core.swagger_registry import SwaggerSchema


class SwaggerSchemaPathError(ValueError):
    """Binding expression path cannot be resolved against a Swagger schema."""


@dataclass(frozen=True, slots=True)
class SwaggerBodyPathSegment:
    """One segment of a restricted body path expression."""

    name: str
    raw_name: str
    array: bool = False


@dataclass(frozen=True, slots=True)
class SwaggerBodyPath:
    """Parsed restricted body path expression."""

    expression: str
    segments: tuple[SwaggerBodyPathSegment, ...]
    leaf_schema: SwaggerSchema

    @property
    def leaf_name(self) -> str:
        return self.segments[-1].name


def parse_body_path(path: str) -> tuple[SwaggerBodyPathSegment, ...]:
    """Parse `field`, `items[]` and `items[].field` body path syntax."""

    if not path:
        raise SwaggerSchemaPathError("body path не может быть пустым.")
    segments: list[SwaggerBodyPathSegment] = []
    for raw_segment in path.split("."):
        if not raw_segment:
            raise SwaggerSchemaPathError(f"Некорректный body path `{path}`.")
        array = raw_segment.endswith("[]")
        name = raw_segment.removesuffix("[]")
        if not name:
            raise SwaggerSchemaPathError(f"Некорректный body path segment `{raw_segment}`.")
        segments.append(SwaggerBodyPathSegment(name=name, raw_name=raw_segment, array=array))
    return tuple(segments)


def resolve_body_path(schema: SwaggerSchema, path: str) -> SwaggerBodyPath:
    """Resolve a parsed body path against normalized Swagger schema metadata."""

    current = schema
    segments = parse_body_path(path)
    for segment in segments:
        raw_property = _maybe_resolve_property(current, segment.raw_name)
        if raw_property is not None:
            current = raw_property
            continue
        current = _resolve_property(current, segment.name, path)
        if segment.array:
            if not current.is_array or current.items is None:
                raise SwaggerSchemaPathError(
                    f"`{segment.name}[]` указывает на не-array schema в `{path}`."
                )
            current = current.items
    return SwaggerBodyPath(expression=path, segments=segments, leaf_schema=current)


def _maybe_resolve_property(schema: SwaggerSchema, name: str) -> SwaggerSchema | None:
    if not schema.is_object:
        return None
    return schema.properties.get(name)


def _resolve_property(schema: SwaggerSchema, name: str, path: str) -> SwaggerSchema:
    if not schema.is_object:
        raise SwaggerSchemaPathError(f"`{name}` указывает на не-object schema в `{path}`.")
    if name in schema.properties:
        return schema.properties[name]
    for property_name, property_schema in schema.properties.items():
        if name in swagger_field_aliases(property_name):
            return property_schema
    raise SwaggerSchemaPathError(f"Swagger schema не содержит поле `{name}` в `{path}`.")


__all__ = (
    "SwaggerBodyPath",
    "SwaggerBodyPathSegment",
    "SwaggerSchemaPathError",
    "parse_body_path",
    "resolve_body_path",
)
