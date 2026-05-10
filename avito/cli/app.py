"""Корневая команда CLI для avito-py."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import NoReturn

import click

PACKAGE_NAME = "avito-py"


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


def package_version() -> str:
    """Return installed package version for CLI output."""

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _fail_usage(message: str) -> NoReturn:
    raise click.UsageError(message)


def _validate_output_flags(json_output: bool, plain: bool, table: bool, wide: bool) -> None:
    selected = sum((json_output, plain, table, wide))
    if selected > 1:
        _fail_usage("Флаги --json, --plain, --table и --wide нельзя использовать вместе.")


@click.group()
@click.help_option("-h", "--help", help="Показать справку и выйти.")
@click.version_option(
    version=package_version(),
    prog_name="avito-py",
    message="%(prog)s %(version)s",
    help="Показать версию и выйти.",
)
@click.option("--profile", metavar="NAME", help="Профиль учетной записи.")
@click.option(
    "--config",
    type=click.Path(dir_okay=False, path_type=Path),
    metavar="PATH",
    help="Путь к файлу конфигурации.",
)
@click.option("--json", "json_output", is_flag=True, help="Вывести результат в JSON.")
@click.option("--plain", is_flag=True, help="Вывести результат без оформления.")
@click.option("--table", is_flag=True, help="Вывести результат таблицей.")
@click.option("--wide", is_flag=True, help="Показать расширенный табличный вывод.")
@click.option("--quiet", is_flag=True, help="Скрыть необязательный вывод.")
@click.option("--no-input", is_flag=True, help="Не задавать интерактивные вопросы.")
@click.option("--no-color", is_flag=True, help="Отключить цветной вывод.")
@click.option("--verbose", is_flag=True, help="Показать дополнительные сведения.")
@click.option("--debug", is_flag=True, help="Показать отладочные сведения без секретов.")
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.001),
    metavar="SECONDS",
    help="Таймаут SDK-вызовов в секундах.",
)
@click.pass_context
def app(
    ctx: click.Context,
    profile: str | None,
    config: Path | None,
    json_output: bool,
    plain: bool,
    table: bool,
    wide: bool,
    quiet: bool,
    no_input: bool,
    no_color: bool,
    verbose: bool,
    debug: bool,
    timeout: float | None,
) -> None:
    """Командная строка для Avito API SDK."""

    _validate_output_flags(json_output=json_output, plain=plain, table=table, wide=wide)
    ctx.obj = CliContext(
        profile=profile,
        config=config,
        json_output=json_output,
        plain=plain,
        table=table,
        wide=wide,
        quiet=quiet,
        no_input=no_input,
        no_color=no_color,
        verbose=verbose,
        debug=debug,
        timeout=timeout,
    )


@app.command()
@click.pass_obj
def version(ctx: CliContext) -> None:
    """Показать версию avito-py."""

    version_value = package_version()
    if ctx.json_output:
        click.echo(json.dumps({"version": version_value}, ensure_ascii=False))
        return
    if not ctx.quiet:
        click.echo(f"avito-py {version_value}")


@app.command("help", context_settings={"ignore_unknown_options": True})
@click.argument("topic", nargs=-1)
@click.pass_context
def help_command(ctx: click.Context, topic: tuple[str, ...]) -> None:
    """Показать справку по командам."""

    if topic:
        _fail_usage("Подробная справка по вложенным командам появится вместе с командами API.")
    click.echo(ctx.parent.get_help() if ctx.parent is not None else ctx.get_help())


def main() -> None:
    """Run the avito CLI application."""

    app.main(prog_name="avito", standalone_mode=True)
