"""Shared Swagger field-name normalization helpers."""

from __future__ import annotations

import re

_FIRST_CAP_RE = re.compile("(.)([A-Z][a-z]+)")
_ALL_CAP_RE = re.compile("([a-z0-9])([A-Z])")


def swagger_field_aliases(field_name: str) -> tuple[str, ...]:
    """Return Swagger field name and its SDK-style snake_case alias."""

    aliases = [field_name]
    normalized_field_name = field_name.replace("IDs", "Ids")
    snake_case = _ALL_CAP_RE.sub(
        r"\1_\2",
        _FIRST_CAP_RE.sub(r"\1_\2", normalized_field_name),
    ).lower()
    if snake_case not in aliases:
        aliases.append(snake_case)
    return tuple(aliases)


__all__ = ("swagger_field_aliases",)
