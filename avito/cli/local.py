"""Локальные команды конфигурации, диагностики и shell completion."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Literal

import click

from avito.cli.config import (
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    JsonValue,
    resolve_cli_home,
)
from avito.cli.context import CliContext
from avito.cli.errors import CliConfigFileError, CliError, CliUsageError
from avito.cli.ui import emit_stdout

ConfigKey = Literal["active-profile"]
ShellName = Literal["bash", "zsh", "fish"]

_CONFIG_KEYS: frozenset[ConfigKey] = frozenset({"active-profile"})


@click.group(name="config")
@click.help_option("-h", "--help", help="Показать справку и выйти.")
def config_group() -> None:
    """Управлять локальной конфигурацией CLI."""


@config_group.command("get")
@click.argument("key", metavar="KEY")
@click.option("--show-source", is_flag=True, help="Показать источник значения.")
@click.pass_obj
def config_get(ctx: CliContext, key: str, show_source: bool) -> None:
    """Показать значение локальной конфигурации."""

    config_key = _parse_config_key(key)
    entry = _config_entry(ctx, config_key)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"config": {config_key: entry}}))
        return
    if show_source:
        emit_stdout(ctx, f"{config_key}: {entry['value'] or '-'} ({entry['source']})")
        return
    emit_stdout(ctx, str(entry["value"] or ""))


@config_group.command("set")
@click.argument("key", metavar="KEY")
@click.argument("value", metavar="VALUE")
@click.pass_obj
def config_set(ctx: CliContext, key: str, value: str) -> None:
    """Сохранить значение локальной конфигурации."""

    config_key = _parse_config_key(key)
    if not value:
        raise CliUsageError("Значение конфигурации не может быть пустым.")
    store = _config_store(ctx)
    document = store.load()
    if config_key == "active-profile":
        updated = replace(document, active_profile=value)
    store.save(updated)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"config": {config_key: value}}))
        return
    emit_stdout(ctx, f"Конфигурация обновлена: {config_key}")


@config_group.command("unset")
@click.argument("key", metavar="KEY")
@click.pass_obj
def config_unset(ctx: CliContext, key: str) -> None:
    """Удалить значение локальной конфигурации."""

    config_key = _parse_config_key(key)
    store = _config_store(ctx)
    document = store.load()
    if config_key == "active-profile":
        updated = replace(document, active_profile=None)
    store.save(updated)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"config": {config_key: None}}))
        return
    emit_stdout(ctx, f"Конфигурация очищена: {config_key}")


@config_group.command("list")
@click.option("--show-source", is_flag=True, help="Показать источник каждого значения.")
@click.pass_obj
def config_list(ctx: CliContext, show_source: bool) -> None:
    """Показать локальную конфигурацию."""

    entries = {key: _config_entry(ctx, key) for key in sorted(_CONFIG_KEYS)}
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"config": entries}))
        return
    lines: list[str] = []
    for key, entry in entries.items():
        if show_source:
            lines.append(f"{key}: {entry['value'] or '-'} ({entry['source']})")
        else:
            lines.append(f"{key}: {entry['value'] or '-'}")
    emit_stdout(ctx, "\n".join(lines))


@click.command(name="status")
@click.help_option("-h", "--help", help="Показать справку и выйти.")
@click.pass_obj
def status_command(ctx: CliContext) -> None:
    """Показать локальную готовность CLI без сетевых вызовов."""

    payload = _status_payload(ctx)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"status": payload}))
        return
    ready_label = "готов" if payload["ready"] else "не готов"
    lines = [
        f"Статус CLI: {ready_label}",
        f"Профиль:    {payload['selected_profile'] or '-'}",
        f"Источник:   {payload['profile_source']}",
        f"Аккаунт:    {'найден' if payload['account_found'] else 'не найден'}",
        f"Каталог:    {payload['cli_home']}",
        "Сеть:       не проверялась",
    ]
    emit_stdout(ctx, "\n".join(lines))


@click.command(name="doctor")
@click.help_option("-h", "--help", help="Показать справку и выйти.")
@click.pass_obj
def doctor_command(ctx: CliContext) -> None:
    """Проверить локальные файлы CLI и показать диагностику."""

    payload = _doctor_payload(ctx)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"doctor": payload}))
    else:
        lines = [f"Диагностика CLI: {payload['status']}"]
        issues = payload["issues"]
        if isinstance(issues, list) and issues:
            lines.append("")
            lines.extend(_format_issue(issue) for issue in issues)
        else:
            lines.append("Проблемы не найдены.")
        emit_stdout(ctx, "\n".join(lines))
    if payload["status"] != "ok":
        raise CliConfigFileError(
            "Локальная диагностика нашла проблемы.",
            details=payload,
        )


@click.group(name="completion")
@click.help_option("-h", "--help", help="Показать справку и выйти.")
def completion_group() -> None:
    """Показать команды подключения shell completion."""


@completion_group.command("bash")
@click.pass_obj
def completion_bash(ctx: CliContext) -> None:
    """Показать подключение completion для bash."""

    _emit_completion(ctx, "bash")


@completion_group.command("zsh")
@click.pass_obj
def completion_zsh(ctx: CliContext) -> None:
    """Показать подключение completion для zsh."""

    _emit_completion(ctx, "zsh")


@completion_group.command("fish")
@click.pass_obj
def completion_fish(ctx: CliContext) -> None:
    """Показать подключение completion для fish."""

    _emit_completion(ctx, "fish")


def _config_entry(ctx: CliContext, key: ConfigKey) -> dict[str, JsonValue]:
    """Вернуть значение config key вместе с источником."""

    store = _config_store(ctx)
    document = store.load()
    if key == "active-profile":
        if ctx.profile is not None:
            return {
                "value": ctx.profile,
                "source": "cli",
                "path": None,
            }
        if document.active_profile is not None:
            return {
                "value": document.active_profile,
                "source": "config",
                "path": str(store.path),
            }
        return {
            "value": None,
            "source": "default",
            "path": None,
        }


def _status_payload(ctx: CliContext) -> dict[str, JsonValue]:
    """Собрать payload локальной готовности CLI."""

    home = resolve_cli_home()
    config_store = _config_store(ctx)
    account_store = AccountStore(home)
    config = config_store.load()
    accounts = account_store.load()
    selected_profile = ctx.profile or config.active_profile
    account_found = (
        selected_profile is not None
        and any(account.name == selected_profile for account in accounts.accounts)
    )
    return {
        "ready": selected_profile is not None and account_found,
        "cli_home": str(home),
        "config_path": str(config_store.path),
        "accounts_path": str(account_store.path),
        "selected_profile": selected_profile,
        "profile_source": _profile_source(ctx, config),
        "account_found": account_found,
        "configured_accounts": len(accounts.accounts),
        "network_checked": False,
    }


def _doctor_payload(ctx: CliContext) -> dict[str, JsonValue]:
    """Собрать payload диагностики локальных CLI files."""

    home = resolve_cli_home()
    config_store = _config_store(ctx)
    account_store = AccountStore(home)
    issues: list[JsonValue] = []
    _load_for_doctor("config", config_store.path, config_store.load, issues)
    _load_for_doctor("accounts", account_store.path, account_store.load, issues)
    status = "ok" if not issues else "error"
    return {
        "status": status,
        "cli_home": str(home),
        "config_path": str(config_store.path),
        "accounts_path": str(account_store.path),
        "issues": issues,
        "network_checked": False,
    }


def _load_for_doctor(
    name: str,
    path: Path,
    loader: Callable[[], object],
    issues: list[JsonValue],
) -> None:
    """Загрузить локальный файл и добавить issue при CLI error."""

    try:
        loader()
    except CliError as exc:
        issues.append(
            {
                "name": name,
                "path": str(path),
                "severity": "error",
                "code": exc.code,
                "message": exc.message,
            }
        )


def _format_issue(issue: object) -> str:
    """Отформатировать одну diagnostic issue для human output."""

    if not isinstance(issue, dict):
        return "- Некорректная диагностическая запись."
    return (
        f"- {issue.get('name', '-')}: {issue.get('message', '-')}"
        f" [{issue.get('code', '-')}]"
    )


def _emit_completion(ctx: CliContext, shell: ShellName) -> None:
    """Напечатать команду подключения shell completion."""

    command = _completion_command(shell)
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"completion": {"shell": shell, "command": command}}))
        return
    emit_stdout(
        ctx,
        "\n".join(
            (
                f"Shell completion для {shell}:",
                "",
                command,
                "",
                "Добавьте эту команду в профиль shell, если completion нужен постоянно.",
            )
        ),
    )


def _completion_command(shell: ShellName) -> str:
    """Вернуть shell-specific команду completion."""

    if shell == "bash":
        return 'eval "$(_AVITO_COMPLETE=bash_source avito)"'
    if shell == "zsh":
        return 'eval "$(_AVITO_COMPLETE=zsh_source avito)"'
    return "_AVITO_COMPLETE=fish_source avito | source"


def _profile_source(ctx: CliContext, config: CliConfigDocument) -> str:
    """Определить источник выбранного профиля."""

    if ctx.profile is not None:
        return "cli"
    if config.active_profile is not None:
        return "config"
    return "none"


def _parse_config_key(value: str) -> ConfigKey:
    """Проверить и нормализовать ключ локальной конфигурации."""

    if value == "active-profile":
        return "active-profile"
    raise CliUsageError(
        "Ключ конфигурации не поддерживается.",
        details={"key": value, "supported_keys": sorted(_CONFIG_KEYS)},
    )


def _config_store(ctx: CliContext) -> ConfigStore:
    """Создать ConfigStore с учетом --config."""

    return ConfigStore(resolve_cli_home(), path=ctx.config)


def _json_dump(payload: dict[str, object]) -> str:
    """Сериализовать payload в стабильный JSON."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


__all__ = (
    "completion_group",
    "config_group",
    "doctor_command",
    "status_command",
)
