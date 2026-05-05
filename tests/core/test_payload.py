from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import pytest

from avito.core import JsonReader, ResponseMappingError


class Status(StrEnum):
    ACTIVE = "active"
    UNKNOWN = "unknown"


def test_json_reader_reads_typed_values_and_fallback_keys() -> None:
    reader = JsonReader(
        {
            "id": 12,
            "title": "item",
            "price": 10,
            "enabled": True,
            "createdAt": "2026-04-30T09:00:00Z",
            "status": "active",
            "nested": {"value": 1},
            "items": [1, 2],
        }
    )

    assert reader.required_int("missing", "id") == 12
    assert reader.required_str("title") == "item"
    assert reader.required_float("price") == 10.0
    assert reader.required_bool("enabled") is True
    assert reader.required_datetime("createdAt") == datetime(
        2026, 4, 30, 9, 0, tzinfo=UTC
    )
    assert reader.enum(Status, "status") == Status.ACTIVE
    assert reader.mapping("nested") == {"value": 1}
    assert reader.list("items") == [1, 2]


def test_json_reader_rejects_bool_as_int() -> None:
    reader = JsonReader({"id": True})

    with pytest.raises(ResponseMappingError, match="целое число"):
        reader.required_int("id")


def test_json_reader_uses_unknown_enum_fallback() -> None:
    reader = JsonReader({"status": "new-value"})

    assert reader.enum(Status, "status", unknown=Status.UNKNOWN) == Status.UNKNOWN


def test_json_reader_reports_missing_required_field() -> None:
    reader = JsonReader({})

    with pytest.raises(ResponseMappingError, match="обязательное поле"):
        reader.required_str("name")


def test_json_reader_rejects_invalid_payload_type() -> None:
    with pytest.raises(ResponseMappingError, match="JSON-объект"):
        JsonReader("bad")
