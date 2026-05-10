"""Безопасный вывод CLI в stdout и stderr."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

import click

from avito.cli.context import CliContext
from avito.core.exceptions import sanitize_metadata


def sanitize_cli_output(value: object) -> object:
    """Удаляет секреты из CLI-диагностики перед любым выводом."""

    return sanitize_metadata(value)


def color_enabled(ctx: CliContext | None) -> bool:
    """Возвращает, можно ли использовать ANSI-цвет для текущего запуска."""

    if os.environ.get("NO_COLOR") == "1":
        return False
    return ctx is not None and not ctx.no_color


def emit_stdout(ctx: CliContext, message: str, *, essential: bool = True) -> None:
    """Печатает результат команды в stdout с учетом quiet-режима."""

    if ctx.quiet and not essential:
        return
    click.echo(message)


def emit_stderr(
    ctx: CliContext | None,
    message: str,
    *,
    fg: str | None = None,
    essential: bool = True,
) -> None:
    """Печатает диагностическое сообщение в stderr с учетом quiet-режима."""

    if ctx is not None and ctx.quiet and not essential:
        return
    click.secho(message, err=True, fg=fg, color=color_enabled(ctx))


def emit_json_stderr(payload: Mapping[str, object]) -> None:
    """Печатает JSON-диагностику в stderr."""

    click.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True), err=True)


__all__ = (
    "color_enabled",
    "emit_json_stderr",
    "emit_stderr",
    "emit_stdout",
    "sanitize_cli_output",
)
