"""Локальные команды учетных записей CLI."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace

import click

from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    JsonValue,
    StoredAccount,
    resolve_cli_home,
)
from avito.cli.context import CliContext
from avito.cli.errors import (
    CliAuthRequiredError,
    CliConfigFileError,
    CliUsageError,
    InvalidFlagCombinationError,
)
from avito.cli.ui import emit_stdout


@click.group(name="account")
@click.help_option("-h", "--help", help="Показать справку и выйти.")
def account_group() -> None:
    """Управлять локальными учетными записями."""


@account_group.command("add")
@click.argument("account_name", metavar="ACCOUNT-NAME")
@click.option("--client-id", required=True, metavar="CLIENT-ID", help="Client ID учетной записи.")
@click.option(
    "--client-secret",
    metavar="CLIENT-SECRET",
    help="Client Secret. Значение может попасть в историю shell.",
)
@click.option(
    "--api-key",
    metavar="API-KEY",
    help="Совместимый alias для --client-secret. Значение может попасть в историю shell.",
)
@click.option(
    "--client-secret-stdin",
    is_flag=True,
    help="Прочитать Client Secret одной строкой из stdin.",
)
@click.option("--endpoint", metavar="URL", help="Alias для базового URL Avito API.")
@click.option("--user-id", type=int, metavar="USER-ID", help="ID пользователя Avito.")
@click.option("--scope", metavar="SCOPE", help="OAuth scope для учетной записи.")
@click.pass_obj
def add_account(
    ctx: CliContext,
    account_name: str,
    client_id: str,
    client_secret: str | None,
    api_key: str | None,
    client_secret_stdin: bool,
    endpoint: str | None,
    user_id: int | None,
    scope: str | None,
) -> None:
    """Добавить локальную учетную запись без сетевых вызовов."""

    secret = _resolve_client_secret(
        ctx,
        client_secret=client_secret,
        api_key=api_key,
        client_secret_stdin=client_secret_stdin,
    )
    account_store = _account_store()
    config_store = _config_store(ctx)
    document = account_store.load()
    if _find_account(document, account_name) is not None:
        raise CliConfigFileError(
            "Учетная запись с таким именем уже существует.",
            details={"account_name": account_name},
        )

    account = StoredAccount(
        name=account_name,
        client_id=client_id,
        client_secret=secret,
        base_url=endpoint or "https://api.avito.ru",
        user_id=user_id,
        scope=scope,
    )
    updated = replace(document, accounts=(*document.accounts, account))
    account_store.save(updated)

    config = config_store.load()
    if config.active_profile is None:
        config_store.save(replace(config, active_profile=account_name))

    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"account": account.to_json(mask_secrets=True)}))
        return
    emit_stdout(ctx, f"Учетная запись добавлена: {account_name}")


@account_group.command("list")
@click.pass_obj
def list_accounts(ctx: CliContext) -> None:
    """Показать локальные учетные записи."""

    document = _account_store().load()
    config = _config_store(ctx).load()
    active_profile = _effective_profile(ctx, config)
    if ctx.json_output:
        emit_stdout(
            ctx,
            _json_dump(
                {
                    "active_profile": active_profile,
                    "accounts": [
                        _account_summary(account, active=account.name == active_profile)
                        for account in document.accounts
                    ],
                }
            ),
        )
        return

    if not document.accounts:
        emit_stdout(ctx, "Локальные учетные записи не настроены.")
        return

    rows = [
        (
            account.name,
            "да" if account.name == active_profile else "",
            account.client_id,
            account.base_url,
        )
        for account in document.accounts
    ]
    emit_stdout(ctx, _render_table(("ИМЯ", "АКТИВНА", "CLIENT ID", "URL"), rows))


@account_group.command("use")
@click.argument("account_name", metavar="ACCOUNT-NAME")
@click.pass_obj
def use_account(ctx: CliContext, account_name: str) -> None:
    """Сделать учетную запись активной."""

    document = _account_store().load()
    if _find_account(document, account_name) is None:
        raise CliConfigFileError(
            "Учетная запись не найдена.",
            details={"account_name": account_name},
        )

    config_store = _config_store(ctx)
    config_store.save(replace(config_store.load(), active_profile=account_name))
    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"active_profile": account_name}))
        return
    emit_stdout(ctx, f"Активная учетная запись: {account_name}")


@account_group.command("current")
@click.pass_obj
def current_account(ctx: CliContext) -> None:
    """Показать активную учетную запись."""

    config = _config_store(ctx).load()
    active_profile = _effective_profile(ctx, config)
    if active_profile is None:
        raise CliConfigFileError("Активная учетная запись не выбрана.")

    account = _find_account(_account_store().load(), active_profile)
    if account is None:
        raise CliConfigFileError(
            "Активная учетная запись не найдена в локальном хранилище.",
            details={"active_profile": active_profile},
        )

    if ctx.json_output:
        emit_stdout(
            ctx,
            _json_dump({"active_profile": active_profile, "account": account.to_json(mask_secrets=True)}),
        )
        return

    emit_stdout(
        ctx,
        "\n".join(
            (
                f"Активная учетная запись: {account.name}",
                "",
                f"Client ID: {account.client_id}",
                f"URL:       {account.base_url}",
                f"User ID:   {account.user_id if account.user_id is not None else '-'}",
            )
        ),
    )


@account_group.command("delete")
@click.argument("account_name", metavar="ACCOUNT-NAME")
@click.option("--yes", is_flag=True, help="Удалить без интерактивного подтверждения.")
@click.option("--confirm", metavar="ACCOUNT-NAME", help="Подтвердить имя удаляемой учетной записи.")
@click.pass_obj
def delete_account(ctx: CliContext, account_name: str, yes: bool, confirm: str | None) -> None:
    """Удалить локальную учетную запись."""

    _delete_account(ctx, account_name=account_name, yes=yes, confirm=confirm)


account_group.add_command(
    click.Command(
        name="remove",
        params=delete_account.params,
        callback=delete_account.callback,
        help="Alias для `account delete`.",
    )
)


def _delete_account(ctx: CliContext, *, account_name: str, yes: bool, confirm: str | None) -> None:
    """Удалить account с интерактивной или явной проверкой имени."""

    if yes and confirm is not None:
        raise InvalidFlagCombinationError("Флаги --yes и --confirm нельзя использовать вместе.")
    if not yes and confirm != account_name:
        if ctx.no_input:
            raise CliUsageError(
                "Удаление требует подтверждения.",
                details={"account_name": account_name},
            )
        entered = click.prompt(
            f"Введите имя учетной записи `{account_name}` для подтверждения",
            type=str,
        )
        if entered != account_name:
            raise CliUsageError("Подтверждение удаления не совпадает с именем учетной записи.")

    account_store = _account_store()
    document = account_store.load()
    account = _find_account(document, account_name)
    if account is None:
        raise CliConfigFileError(
            "Учетная запись не найдена.",
            details={"account_name": account_name},
        )

    remaining = tuple(item for item in document.accounts if item.name != account.name)
    account_store.save(replace(document, accounts=remaining))

    config_store = _config_store(ctx)
    config = config_store.load()
    if _effective_profile(ctx, config) == account_name and ctx.profile is None:
        config_store.save(replace(config, active_profile=None))

    if ctx.json_output:
        emit_stdout(ctx, _json_dump({"deleted": account_name}))
        return
    emit_stdout(ctx, f"Учетная запись удалена: {account_name}")


def _resolve_client_secret(
    ctx: CliContext,
    *,
    client_secret: str | None,
    api_key: str | None,
    client_secret_stdin: bool,
) -> str:
    """Получить client secret из одного разрешенного источника."""

    selected = [
        name
        for name, enabled in (
            ("--client-secret", client_secret is not None),
            ("--api-key", api_key is not None),
            ("--client-secret-stdin", client_secret_stdin),
        )
        if enabled
    ]
    if len(selected) > 1:
        raise InvalidFlagCombinationError(
            "Флаги --client-secret, --api-key и --client-secret-stdin нельзя использовать вместе.",
            details={"selected_flags": selected},
        )
    if client_secret is not None:
        return _require_non_empty_secret(client_secret)
    if api_key is not None:
        return _require_non_empty_secret(api_key)
    if client_secret_stdin:
        return _read_client_secret_stdin()
    if ctx.no_input:
        raise CliAuthRequiredError(
            "Client Secret не передан, а интерактивный ввод отключен.",
        )
    return _require_non_empty_secret(
        click.prompt("Client Secret", hide_input=True, confirmation_prompt=False, type=str)
    )


def _read_client_secret_stdin() -> str:
    """Прочитать ровно одну строку client secret из stdin."""

    stream = click.get_text_stream("stdin")
    if stream.isatty():
        raise CliUsageError("--client-secret-stdin требует неинтерактивный stdin.")
    value = stream.read()
    if value.endswith("\n"):
        value = value[:-1]
    if value.endswith("\r"):
        value = value[:-1]
    if "\n" in value or "\r" in value:
        raise CliUsageError("--client-secret-stdin принимает ровно одну строку.")
    return _require_non_empty_secret(value)


def _require_non_empty_secret(value: str) -> str:
    """Проверить, что client secret не пустой."""

    if not value:
        raise CliAuthRequiredError("Client Secret не может быть пустым.")
    return value


def _account_store() -> AccountStore:
    """Создать store учетных записей для текущего CLI home."""

    return AccountStore(resolve_cli_home())


def _config_store(ctx: CliContext) -> ConfigStore:
    """Создать store конфигурации с учетом флага --config."""

    return ConfigStore(resolve_cli_home(), path=ctx.config)


def _find_account(document: AccountsDocument, account_name: str) -> StoredAccount | None:
    """Найти account по имени в документе хранилища."""

    for account in document.accounts:
        if account.name == account_name:
            return account
    return None


def _effective_profile(ctx: CliContext, config: CliConfigDocument) -> str | None:
    """Вернуть профиль из CLI-флага или локальной конфигурации."""

    if ctx.profile is not None:
        return ctx.profile
    return config.active_profile


def _account_summary(account: StoredAccount, *, active: bool) -> dict[str, JsonValue]:
    """Собрать безопасную JSON-сводку account для вывода."""

    payload = account.to_json(mask_secrets=True)
    payload["active"] = active
    return payload


def _json_dump(payload: dict[str, object]) -> str:
    """Сериализовать payload в стабильный JSON."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _render_table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    """Отрендерить простую выровненную таблицу."""

    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    lines = ["  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))]
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


__all__ = ("account_group",)
