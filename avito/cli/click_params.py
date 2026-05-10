"""Click-параметры с единым интерактивным поведением."""

from __future__ import annotations

import collections.abc as cabc
from typing import Any

import click

from avito.cli.context import CliContext
from avito.cli.errors import CliUsageError, CliValidationError


class RequiredPromptOption(click.Option):
    """Обязательный option, который спрашивает значение до callback."""

    def prompt_for_value(self, ctx: click.Context) -> object:
        """Запросить значение через Click prompt, если интерактивный ввод разрешен."""

        if _no_input(ctx):
            raise self._missing_value_error()
        if self.multiple:
            prompt = self.prompt or self.name or "value"
            return (click.prompt(prompt, type=str),)
        return super().prompt_for_value(ctx)

    def _missing_value_error(self) -> click.ClickException:
        """Создать ошибку отсутствующего значения для non-interactive режима."""

        flag = self.opts[0] if self.opts else self.human_readable_name
        return CliValidationError(
            f"Не указан обязательный параметр {flag}. Интерактивный ввод отключен.",
            details={"parameter": self.name},
        )


class RequiredPromptArgument(click.Argument):
    """Обязательный argument, который спрашивает значение до callback."""

    def __init__(self, param_decls: cabc.Sequence[str], **attrs: Any) -> None:
        """Сохранить prompt label и инициализировать Click argument."""

        self.prompt = str(attrs.pop("prompt"))
        super().__init__(param_decls, **attrs)

    def process_value(self, ctx: click.Context, value: object) -> object:
        """Подставить интерактивно введенное значение, если argument не передан."""

        if self.required and (value == () or self.value_is_missing(value)):
            if _no_input(ctx):
                raise CliUsageError(
                    f"Не указан обязательный аргумент {self.human_readable_name}. "
                    "Интерактивный ввод отключен.",
                    details={"parameter": self.name},
                )
            value = click.prompt(self.prompt, type=str)
        return super().process_value(ctx, value)


def _no_input(ctx: click.Context) -> bool:
    """Вернуть глобальный запрет интерактивного ввода из Click context."""

    cli_context = ctx.find_object(CliContext)
    return cli_context is not None and cli_context.no_input
