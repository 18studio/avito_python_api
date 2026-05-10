"""Корневая команда CLI для avito-py."""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

import click

from avito.cli import commands as api_commands
from avito.cli.accounts import account_group
from avito.cli.context import CliContext
from avito.cli.errors import CliUsageError, InvalidFlagCombinationError
from avito.cli.help import render_registry_help
from avito.cli.local import completion_group, config_group, doctor_command, status_command
from avito.cli.registry import ApiCommandRecord, HelperCommandRecord, build_cli_registry
from avito.cli.safety import SafetyOptions
from avito.cli.serialization import emit_cli_result
from avito.cli.ui import emit_stdout

PACKAGE_NAME = "avito-py"

def package_version() -> str:
    """Return installed package version for CLI output."""

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _validate_output_flags(json_output: bool, plain: bool, table: bool, wide: bool) -> None:
    output_flags = {
        "--json": json_output,
        "--plain": plain,
        "--table": table,
        "--wide": wide,
    }
    selected = [name for name, enabled in output_flags.items() if enabled]
    if len(selected) > 1:
        raise InvalidFlagCombinationError(
            "Флаги --json, --plain, --table и --wide нельзя использовать вместе.",
            details={"selected_flags": selected},
        )


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

    cli_context = CliContext(
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
    ctx.obj = cli_context
    _validate_output_flags(json_output=json_output, plain=plain, table=table, wide=wide)


@app.command()
@click.pass_obj
def version(ctx: CliContext) -> None:
    """Показать версию avito-py."""

    version_value = package_version()
    if ctx.json_output:
        emit_stdout(ctx, json.dumps({"version": version_value}, ensure_ascii=False))
        return
    emit_stdout(ctx, f"avito-py {version_value}", essential=False)


@app.command("help", context_settings={"ignore_unknown_options": True})
@click.argument("topic", nargs=-1)
@click.pass_context
def help_command(ctx: click.Context, topic: tuple[str, ...]) -> None:
    """Показать справку по командам."""

    parent = ctx.parent
    if parent is None:
        click.echo(ctx.get_help())
        return
    if not topic:
        click.echo(parent.get_help())
        return

    registry_help = render_registry_help(topic)
    if registry_help is not None:
        click.echo(registry_help)
        return

    command_context = _resolve_help_topic(parent, topic)
    click.echo(command_context.get_help())


def _resolve_help_topic(parent: click.Context, topic: tuple[str, ...]) -> click.Context:
    command: click.Command = parent.command
    command_context = parent
    for part in topic:
        if not isinstance(command, click.Group):
            raise CliUsageError(
                "Команда не содержит вложенную справку.",
                details={"topic": topic},
            )
        nested = command.get_command(command_context, part)
        if nested is None:
            raise CliUsageError(
                "Команда для справки не найдена.",
                details={"topic": topic},
            )
        command = nested
        command_context = click.Context(command, info_name=part, parent=command_context)
    return command_context


app.add_command(account_group)
app.add_command(config_group)
app.add_command(status_command)
app.add_command(doctor_command)
app.add_command(completion_group)


def _register_api_commands(root: click.Group) -> None:
    registry = build_cli_registry()
    for api_command in registry.api_commands:
        if not api_command.implemented:
            continue
        group = _resource_group(root, api_command.resource)
        group.add_command(_build_api_click_command(api_command))
    for helper_command in registry.helper_commands:
        if not helper_command.implemented:
            continue
        group = _resource_group(root, helper_command.resource)
        group.add_command(_build_helper_click_command(helper_command))


def _resource_group(root: click.Group, resource: str) -> click.Group:
    existing = root.get_command(click.Context(root), resource)
    if isinstance(existing, click.Group):
        return existing
    if existing is not None:
        raise CliUsageError(
            "Команда API конфликтует с существующей CLI-командой.",
            details={"resource": resource},
        )
    group = click.Group(name=resource, help=f"Команды ресурса {resource}.")
    root.add_command(group)
    return group


def _build_api_click_command(command: ApiCommandRecord) -> click.Command:
    params = _parameter_click_options(command)
    params.extend(_safety_click_options(command))

    @click.pass_context
    def callback(click_context: click.Context, /, **raw_options: object) -> None:
        ctx = click_context.find_object(CliContext)
        if ctx is None:
            raise CliUsageError("Контекст CLI не найден.")
        safety_options = _safety_options_from_click(command, raw_options)
        raw_values = _raw_values_from_click(raw_options)
        result = api_commands.invoke_api_command(
            ctx,
            command,
            raw_values,
            safety_options=safety_options,
        )
        emit_cli_result(ctx, result)

    return click.Command(
        name=command.action,
        params=params,
        callback=callback,
        help=command.description,
    )


def _build_helper_click_command(command: HelperCommandRecord) -> click.Command:
    params = _parameter_click_options(command)

    @click.pass_context
    def callback(click_context: click.Context, /, **raw_options: object) -> None:
        ctx = click_context.find_object(CliContext)
        if ctx is None:
            raise CliUsageError("Контекст CLI не найден.")
        result = api_commands.invoke_helper_command(
            ctx,
            command,
            _raw_values_from_click(raw_options),
        )
        emit_cli_result(ctx, result)

    return click.Command(
        name=command.action,
        params=params,
        callback=callback,
        help=command.description,
    )


def _parameter_click_options(
    command: ApiCommandRecord | HelperCommandRecord,
) -> list[click.Parameter]:
    return [
        click.Option(
            param_decls=(parameter.flag,),
            multiple=parameter.multiple,
            required=False,
            metavar="VALUE",
            help=f"Параметр SDK `{parameter.name}`.",
        )
        for parameter in command.parameters
    ]


def _safety_click_options(command: ApiCommandRecord) -> list[click.Parameter]:
    if command.safety in {"read", "local"}:
        return []
    options: list[click.Parameter] = [
        click.Option(
            param_decls=("--yes",),
            is_flag=True,
            help="Выполнить команду без интерактивного подтверждения.",
        ),
        click.Option(
            param_decls=("--confirm",),
            metavar="VALUE",
            help="Точно подтвердить выполнение команды.",
        ),
    ]
    if command.safety_policy.dry_run_supported:
        options.append(
            click.Option(
                param_decls=("--dry-run",),
                is_flag=True,
                help="Показать план без применения изменений.",
            )
        )
    return options


def _safety_options_from_click(
    command: ApiCommandRecord,
    raw_options: dict[str, object],
) -> SafetyOptions:
    if command.safety in {"read", "local"}:
        return SafetyOptions()
    return SafetyOptions(
        yes=bool(raw_options.pop("yes", False)),
        confirm=_optional_string(raw_options.pop("confirm", None)),
        dry_run=bool(raw_options.pop("dry_run", False)),
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _raw_values_from_click(raw_options: dict[str, object]) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {}
    for name, value in raw_options.items():
        if value is None:
            continue
        if isinstance(value, tuple):
            if value:
                values[name] = tuple(str(item) for item in value)
            continue
        values[name] = (str(value),)
    return values


_register_api_commands(app)


def main() -> None:
    """Run the avito CLI application."""

    app.main(prog_name="avito", standalone_mode=True)
