"""Внутренние валидаторы входных данных доменного слоя."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from avito.core.exceptions import ValidationError

DateInput = date | datetime | str


def validate_non_empty(name: str, items: Sequence[object]) -> None:
    """Проверяет, что последовательность содержит хотя бы один элемент."""
    if not items:
        raise ValidationError(f"`{name}` должен содержать хотя бы один элемент.")


def validate_positive_int(name: str, value: int) -> None:
    """Проверяет, что значение является положительным целым числом."""
    if value <= 0:
        raise ValidationError(f"`{name}` должен быть положительным целым числом.")


def validate_non_empty_string(name: str, value: str) -> None:
    """Проверяет, что строка не является пустой или состоящей из пробелов."""
    if not value.strip():
        raise ValidationError(f"`{name}` не может быть пустой строкой.")


def validate_string_items(name: str, values: Sequence[str]) -> None:
    """Проверяет, что список строк непустой и каждая строка непустая."""
    validate_non_empty(name, values)
    for index, value in enumerate(values):
        validate_non_empty_string(f"{name}[{index}]", value)


def serialize_iso_date(name: str, value: DateInput) -> str:
    """Проверяет ISO-дату и сериализует значение в YYYY-MM-DD."""

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"`{name}` не может быть пустой строкой.")
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(normalized).isoformat()
        except ValueError as exc:
            raise ValidationError(f"`{name}` должен быть датой в ISO-формате.") from exc


def serialize_iso_datetime(name: str, value: DateInput) -> str:
    """Проверяет ISO/RFC3339 datetime и сохраняет строковое представление."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"`{name}` не может быть пустой строкой.")
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"`{name}` должен быть датой или временем в ISO-формате.") from exc
    return normalized


__all__ = (
    "DateInput",
    "serialize_iso_date",
    "serialize_iso_datetime",
    "validate_non_empty",
    "validate_non_empty_string",
    "validate_positive_int",
    "validate_string_items",
)
