"""Сериализация и рендеринг результатов CLI."""

from __future__ import annotations

import json
from base64 import b64encode
from collections.abc import Mapping, Sequence
from dataclasses import Field, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Protocol, cast, runtime_checkable

from avito.cli.context import CliContext
from avito.cli.ui import emit_stdout, sanitize_cli_output
from avito.core.pagination import PaginatedList

DEFAULT_PAGE_LIMIT = 1


@runtime_checkable
class _ModelDumpable(Protocol):
    def model_dump(self) -> Mapping[str, object]:
        """Вернуть публичное JSON-совместимое представление модели."""


@runtime_checkable
class _DictSerializable(Protocol):
    def to_dict(self) -> Mapping[str, object]:
        """Вернуть публичное JSON-совместимое представление модели."""


class _DataclassInstance(Protocol):
    __dataclass_fields__: Mapping[str, Field[object]]


@dataclass(frozen=True, slots=True)
class SerializationOptions:
    """Ограничения сериализации результата CLI."""

    limit: int | None = None
    page_limit: int = DEFAULT_PAGE_LIMIT
    all_items: bool = False


def serialize_cli_result(
    value: object,
    *,
    options: SerializationOptions | None = None,
) -> object:
    """Сериализовать результат SDK или локальной CLI-команды без секретов."""

    serialized = _serialize_value(value, options=options or SerializationOptions())
    return sanitize_cli_output(serialized)


def render_cli_result(
    ctx: CliContext,
    value: object,
    *,
    options: SerializationOptions | None = None,
) -> str:
    """Подготовить результат CLI для stdout в выбранном режиме вывода."""

    serialized = serialize_cli_result(value, options=options)
    if ctx.json_output:
        return json.dumps(serialized, ensure_ascii=False, sort_keys=True)
    if ctx.plain:
        return _render_plain(serialized)
    if ctx.table or _is_collection_payload(serialized):
        return _render_table(serialized, wide=ctx.wide)
    return _render_grouped(serialized)


def emit_cli_result(
    ctx: CliContext,
    value: object,
    *,
    options: SerializationOptions | None = None,
    essential: bool = True,
) -> None:
    """Напечатать сериализованный результат CLI в stdout."""

    emit_stdout(ctx, render_cli_result(ctx, value, options=options), essential=essential)


def _serialize_value(value: object, *, options: SerializationOptions) -> object:
    if isinstance(value, PaginatedList):
        return _serialize_paginated_list(value, options=options)
    if isinstance(value, _ModelDumpable):
        return _serialize_value(value.model_dump(), options=options)
    if isinstance(value, _DictSerializable):
        return _serialize_value(value.to_dict(), options=options)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes | bytearray):
        return b64encode(bytes(value)).decode("ascii")
    if is_dataclass(value):
        return _serialize_dataclass(cast(_DataclassInstance, value), options=options)
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_value(item, options=options)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_serialize_value(item, options=options) for item in value]
    return value


def _serialize_dataclass(
    value: _DataclassInstance,
    *,
    options: SerializationOptions,
) -> dict[str, object]:
    return {
        field.name: _serialize_value(getattr(value, field.name), options=options)
        for field in value.__dataclass_fields__.values()
        if not field.name.startswith("_") and field.name != "raw_payload"
    }


def _serialize_paginated_list(
    value: PaginatedList[object],
    *,
    options: SerializationOptions,
) -> dict[str, object]:
    items = _paginated_snapshot(value, options=options)
    visible_items = items
    if options.limit is not None:
        visible_items = items[: options.limit]
    serialized_items = [_serialize_value(item, options=options) for item in visible_items]
    return {
        "items": serialized_items,
        "pagination": {
            "loaded_count": value.loaded_count,
            "known_total": value.known_total,
            "source_total": value.source_total,
            "is_materialized": value.is_materialized,
            "limit": options.limit,
            "page_limit": None if options.all_items else max(1, options.page_limit),
            "truncated": _pagination_is_truncated(
                value,
                loaded_items=len(items),
                visible_items=len(visible_items),
            ),
        },
    }


def _paginated_snapshot(
    value: PaginatedList[object],
    *,
    options: SerializationOptions,
) -> list[object]:
    if options.all_items:
        return value.materialize()

    page_limit = max(1, options.page_limit)
    loaded_count = value.loaded_count
    loaded_pages = 1 if loaded_count > 0 else 0
    if loaded_pages == 0:
        _load_next_page(value)
        loaded_count = value.loaded_count
        loaded_pages = 1

    while loaded_pages < page_limit and not value.is_materialized:
        previous_count = loaded_count
        _load_next_page(value)
        loaded_count = value.loaded_count
        if loaded_count == previous_count:
            break
        loaded_pages += 1

    return list(list.__iter__(value))


def _load_next_page(value: PaginatedList[object]) -> None:
    if value.is_materialized:
        return
    try:
        _ = value[value.loaded_count]
    except IndexError:
        return


def _pagination_is_truncated(
    value: PaginatedList[object],
    *,
    loaded_items: int,
    visible_items: int,
) -> bool:
    if visible_items < loaded_items:
        return True
    return not value.is_materialized


def _render_plain(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool) or value is None:
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _render_grouped(value: object) -> str:
    if isinstance(value, Mapping):
        rows = [
            f"{str(key)}: {_render_cell(item)}"
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        ]
        return "\n".join(rows)
    return _render_plain(value)


def _render_table(value: object, *, wide: bool) -> str:
    rows = _table_rows(value)
    if not rows:
        return ""
    columns = _table_columns(rows, wide=wide)
    widths = {
        column: max(len(column.upper()), *(len(_render_cell(row.get(column))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.upper().ljust(widths[column]) for column in columns)
    body = [
        "  ".join(_render_cell(row.get(column)).ljust(widths[column]) for column in columns).rstrip()
        for row in rows
    ]
    return "\n".join((header, *body))


def _table_rows(value: object) -> list[Mapping[str, object]]:
    if isinstance(value, Mapping) and isinstance(value.get("items"), Sequence):
        return _sequence_table_rows(value["items"])
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return _sequence_table_rows(value)
    if isinstance(value, Mapping):
        return [value]
    return [{"value": value}]


def _sequence_table_rows(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    rows: list[Mapping[str, object]] = []
    for item in value:
        if isinstance(item, Mapping):
            rows.append(item)
        else:
            rows.append({"value": item})
    return rows


def _table_columns(rows: Sequence[Mapping[str, object]], *, wide: bool) -> tuple[str, ...]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            text_key = str(key)
            if text_key not in columns:
                columns.append(text_key)
    if wide:
        return tuple(columns)
    simple_columns = [
        column
        for column in columns
        if all(_is_simple_cell(row.get(column)) for row in rows)
    ]
    return tuple(simple_columns or columns)


def _is_simple_cell(value: object) -> bool:
    return (
        value is None
        or isinstance(value, str | int | float | bool)
        or isinstance(value, datetime | date)
    )


def _render_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _is_collection_payload(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return True
    return isinstance(value, Mapping) and isinstance(value.get("items"), Sequence)


__all__ = (
    "DEFAULT_PAGE_LIMIT",
    "SerializationOptions",
    "emit_cli_result",
    "render_cli_result",
    "serialize_cli_result",
)
