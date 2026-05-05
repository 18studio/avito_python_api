"""Base model classes and serializers for v2 domain architecture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum

from avito.core.fields import get_api_field_name
from avito.core.serialization import SerializableModel

JsonValue = Mapping[str, object] | list[object] | str | int | float | bool | None


class ApiModel(SerializableModel):
    """Base class for public typed API response models."""


@dataclass(slots=True, frozen=True)
class ApiErrorPayload(ApiModel):
    """Typed wrapper for Swagger-declared error response bodies."""

    payload: object

    @classmethod
    def from_payload(cls, payload: object) -> ApiErrorPayload:
        """Preserve the upstream error payload for typed exception mapping."""

        return cls(payload=payload)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible diagnostic representation."""

        return {"payload": serialize_api_value(self.payload)}

    def model_dump(self) -> dict[str, object]:
        """Compatible alias for pydantic-like public contract."""

        return self.to_dict()


class RequestModel:
    """Base class for request and query dataclasses with API-name serialization."""

    def to_payload(self) -> object:
        """Serialize dataclass fields into JSON-compatible request body."""

        return _serialize_dataclass(self)

    def to_params(self) -> dict[str, object]:
        """Serialize dataclass fields into query params."""

        return _serialize_dataclass(self)


@dataclass(slots=True, frozen=True)
class EmptyRequest(RequestModel):
    """Explicit empty JSON request body for Swagger operations that declare one."""

    def to_payload(self) -> dict[str, object]:
        """Serialize to an empty JSON object."""

        return {}


def serialize_api_value(value: object) -> object:
    """Serialize one request/query value into a JSON-compatible structure."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, RequestModel):
        return value.to_payload()
    if isinstance(value, SerializableModel):
        return value.to_dict()
    if is_dataclass(value):
        return _serialize_dataclass(value)
    if isinstance(value, Mapping):
        return {
            str(key): serialize_api_value(item) for key, item in value.items() if item is not None
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [serialize_api_value(item) for item in value if item is not None]
    return value


def _serialize_dataclass(instance: object) -> dict[str, object]:
    if not is_dataclass(instance):
        raise TypeError("RequestModel supports dataclass instances only.")
    payload: dict[str, object] = {}
    for item in fields(instance):
        value = getattr(instance, item.name)
        if value is None or item.name.startswith("_") or item.name == "raw_payload":
            continue
        api_name = get_api_field_name(item.name, item.metadata)
        payload[api_name] = serialize_api_value(value)
    return payload


__all__ = (
    "ApiErrorPayload",
    "ApiModel",
    "EmptyRequest",
    "JsonValue",
    "RequestModel",
    "serialize_api_value",
)
