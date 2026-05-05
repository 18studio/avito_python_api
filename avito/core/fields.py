"""Metadata helpers for API field names in request and query models."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import MISSING, Field, field
from typing import TypeVar, cast

_FieldT = TypeVar("_FieldT")
API_FIELD_METADATA_KEY = "api_name"


def api_field(
    api_name: str,
    *,
    default: _FieldT | object = MISSING,
    default_factory: Callable[[], _FieldT] | object = MISSING,
) -> Field[_FieldT]:
    """Create dataclass field metadata for an upstream API field name."""

    if default is not MISSING and default_factory is not MISSING:
        raise TypeError("Нельзя одновременно передавать default и default_factory.")
    metadata = {API_FIELD_METADATA_KEY: api_name}
    if default_factory is not MISSING:
        return cast(
            Field[_FieldT],
            field(
                default_factory=cast(Callable[[], _FieldT], default_factory),
                metadata=metadata,
            ),
        )
    if default is not MISSING:
        return cast(Field[_FieldT], field(default=cast(_FieldT, default), metadata=metadata))
    return cast(Field[_FieldT], field(metadata=metadata))


def get_api_field_name(field_name: str, metadata: object) -> str:
    """Return API field name from dataclass metadata or the Python field name."""

    if isinstance(metadata, Mapping):
        value = metadata.get(API_FIELD_METADATA_KEY)
        if isinstance(value, str) and value:
            return value
    return field_name


__all__ = ("API_FIELD_METADATA_KEY", "api_field", "get_api_field_name")
