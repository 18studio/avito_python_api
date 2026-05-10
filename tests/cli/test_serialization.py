"""Tests for CLI result serialization and pagination rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from avito.cli.context import CliContext
from avito.cli.serialization import (
    SerializationOptions,
    render_cli_result,
    serialize_cli_result,
)
from avito.core.models import ApiModel
from avito.core.pagination import PaginatedList
from avito.core.types import JsonPage


class _Status(StrEnum):
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class _SdkModel(ApiModel):
    item_id: int
    status: _Status
    created_at: datetime
    client_secret: str


@dataclass(frozen=True, slots=True)
class _LocalModel:
    name: str
    today: date
    tags: tuple[str, ...]


def test_sdk_model_serializes_through_public_contract_and_masks_secrets() -> None:
    model = _SdkModel(
        item_id=10,
        status=_Status.ACTIVE,
        created_at=datetime(2026, 5, 10, 12, 30, 0),
        client_secret="raw-secret",
    )

    result = serialize_cli_result(model)

    assert result == {
        "item_id": 10,
        "status": "active",
        "created_at": "2026-05-10T12:30:00",
        "client_secret": "***",
    }


def test_cli_local_dataclasses_enums_dates_lists_and_primitives_serialize_safely() -> None:
    result = serialize_cli_result(
        {
            "model": _LocalModel(
                name="local",
                today=date(2026, 5, 10),
                tags=("a", "b"),
            ),
            "enabled": True,
            "count": 2,
            "binary": b"abc",
        }
    )

    assert result == {
        "model": {
            "name": "local",
            "today": "2026-05-10",
            "tags": ["a", "b"],
        },
        "enabled": True,
        "count": 2,
        "binary": "YWJj",
    }


def test_paginated_result_defaults_to_one_loaded_page_without_unbounded_fetch() -> None:
    calls: list[int] = []
    pages = {
        1: JsonPage(items=[_LocalModel("one", date(2026, 5, 10), ())], page=1, per_page=1, total=3),
        2: JsonPage(items=[_LocalModel("two", date(2026, 5, 11), ())], page=2, per_page=1, total=3),
        3: JsonPage(items=[_LocalModel("three", date(2026, 5, 12), ())], page=3, per_page=1, total=3),
    }

    def fetch(page: int | None, cursor: str | None) -> JsonPage[_LocalModel]:
        resolved_page = page or 1
        calls.append(resolved_page)
        return pages[resolved_page]

    items = PaginatedList(fetch)

    result = serialize_cli_result(items)

    assert calls == [1]
    assert result == {
        "items": [
            {
                "name": "one",
                "today": "2026-05-10",
                "tags": [],
            }
        ],
        "pagination": {
            "loaded_count": 1,
            "known_total": 3,
            "source_total": None,
            "is_materialized": False,
            "limit": None,
            "page_limit": 1,
            "truncated": True,
        },
    }


def test_paginated_result_materializes_only_with_explicit_all_option() -> None:
    calls: list[int] = []
    pages = {
        1: JsonPage(items=[1], page=1, per_page=1, total=2),
        2: JsonPage(items=[2], page=2, per_page=1, total=2),
    }

    def fetch(page: int | None, cursor: str | None) -> JsonPage[int]:
        resolved_page = page or 1
        calls.append(resolved_page)
        return pages[resolved_page]

    items = PaginatedList(fetch)

    result = serialize_cli_result(items, options=SerializationOptions(all_items=True))

    assert calls == [1, 2]
    assert result == {
        "items": [1, 2],
        "pagination": {
            "loaded_count": 2,
            "known_total": 2,
            "source_total": None,
            "is_materialized": True,
            "limit": None,
            "page_limit": None,
            "truncated": False,
        },
    }


def test_json_and_human_rendering_use_same_sanitized_payload() -> None:
    value = [{"item_id": 1, "name": "First", "client_secret": "raw-secret"}]

    json_output = render_cli_result(_ctx(json_output=True), value)
    table_output = render_cli_result(_ctx(table=True), value)
    grouped_output = render_cli_result(_ctx(), {"item_id": 1, "name": "First"})

    assert json.loads(json_output) == [
        {"client_secret": "***", "item_id": 1, "name": "First"}
    ]
    assert table_output == "ITEM_ID  NAME   CLIENT_SECRET\n1        First  ***"
    assert grouped_output == "item_id: 1\nname: First"
    assert "raw-secret" not in json_output
    assert "raw-secret" not in table_output


def _ctx(
    *,
    json_output: bool = False,
    table: bool = False,
) -> CliContext:
    return CliContext(
        profile=None,
        config=None,
        json_output=json_output,
        plain=False,
        table=table,
        wide=False,
        quiet=False,
        no_input=True,
        no_color=True,
        verbose=False,
        debug=False,
        timeout=None,
    )
