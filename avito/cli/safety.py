"""Safety checks for CLI commands that can change upstream state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

from avito.cli.context import CliContext
from avito.cli.errors import CliUsageError, InvalidFlagCombinationError

if TYPE_CHECKING:
    from avito.cli.registry import ApiCommandRecord, SafetyKind


@dataclass(frozen=True, slots=True)
class CommandSafetyPolicy:
    """Reviewed safety policy for one CLI command."""

    kind: SafetyKind
    confirmation_required: bool
    dry_run_supported: bool
    review_note: str

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible safety metadata."""

        return {
            "kind": self.kind,
            "confirmation_required": self.confirmation_required,
            "dry_run_supported": self.dry_run_supported,
            "review_note": self.review_note,
        }


@dataclass(frozen=True, slots=True)
class SafetyOptions:
    """Safety flags supplied by the user for one command invocation."""

    yes: bool = False
    confirm: str | None = None
    dry_run: bool = False


def validate_safety_options(
    ctx: CliContext,
    command: ApiCommandRecord,
    options: SafetyOptions,
) -> None:
    """Validate write safety flags before constructing the SDK client."""

    if options.yes and options.confirm is not None:
        raise InvalidFlagCombinationError("Флаги --yes и --confirm нельзя использовать вместе.")
    if options.dry_run and not command.safety_policy.dry_run_supported:
        raise CliUsageError(
            "Команда не поддерживает --dry-run.",
            details={"command_id": command.command_id},
        )
    if not command.safety_policy.confirmation_required:
        return
    if options.yes:
        return
    expected = confirmation_value(command)
    if options.confirm == expected:
        return
    if ctx.no_input:
        raise CliUsageError(
            "Команда требует подтверждения.",
            details={"command_id": command.command_id, "confirm": expected},
        )
    entered = click.prompt(
        f"Введите `{expected}` для подтверждения команды {command.resource} {command.action}",
        type=str,
    )
    if entered != expected:
        raise CliUsageError("Подтверждение не совпадает с ожидаемым значением.")


def confirmation_value(command: ApiCommandRecord) -> str:
    """Return the exact confirmation value for an API command."""

    return command.command_id


__all__ = (
    "CommandSafetyPolicy",
    "SafetyOptions",
    "confirmation_value",
    "validate_safety_options",
)
