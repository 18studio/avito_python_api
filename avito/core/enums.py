"""Общие helper-функции для enum-значений из upstream API."""

from __future__ import annotations

import logging
from enum import Enum, IntEnum

logger = logging.getLogger(__name__)
_warned_unknown_enum_values: set[tuple[str, object]] = set()


def map_enum_or_unknown[T: Enum](
    value: str | None, enum_type: type[T], *, enum_name: str
) -> T | None:
    """Преобразует строку в enum с fallback на UNKNOWN и warning один раз на процесс."""

    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        warning_key = (enum_name, value)
        if warning_key not in _warned_unknown_enum_values:
            _warned_unknown_enum_values.add(warning_key)
            logger.warning(
                "Получено неизвестное значение enum от upstream.",
                extra={"enum": enum_name, "value": value},
            )
        return enum_type.__members__["UNKNOWN"]


def map_int_enum_or_unknown[T: IntEnum](
    value: int | None, enum_type: type[T], *, enum_name: str
) -> T | None:
    """Преобразует целое число в enum с fallback на UNKNOWN и warning один раз на процесс."""

    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        warning_key = (enum_name, value)
        if warning_key not in _warned_unknown_enum_values:
            _warned_unknown_enum_values.add(warning_key)
            logger.warning(
                "Получено неизвестное значение enum от upstream.",
                extra={"enum": enum_name, "value": value},
            )
        return enum_type.__members__["UNKNOWN"]


__all__ = ("map_enum_or_unknown", "map_int_enum_or_unknown")
