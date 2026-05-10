"""Типизированный контекст одного запуска CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CliContext:
    """Глобальные настройки одного запуска CLI."""

    profile: str | None
    config: Path | None
    json_output: bool
    plain: bool
    table: bool
    wide: bool
    quiet: bool
    no_input: bool
    no_color: bool
    verbose: bool
    debug: bool
    timeout: float | None


__all__ = ("CliContext",)
