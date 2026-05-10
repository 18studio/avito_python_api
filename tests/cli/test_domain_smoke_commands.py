"""Read-only generated API command smoke tests."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from click.testing import CliRunner

from avito.cli.app import app
from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
)
from avito.cli.registry import ApiCommandRecord, build_cli_registry
from avito.cli.schemas import CliParameterSchema, CliValueKind
from avito.config import AvitoSettings
from avito.core.swagger_registry import load_swagger_registry
from avito.testing import SwaggerFakeTransport

_READ_COMMANDS = tuple(
    command
    for command in build_cli_registry().api_commands
    if command.http_method in {"GET", "HEAD"}
)


@pytest.mark.parametrize("command", _READ_COMMANDS, ids=lambda command: command.command_id)
def test_read_only_api_command_is_registered_and_renders_help(
    command: ApiCommandRecord,
    tmp_path: Path,
) -> None:
    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")}).invoke(
        app,
        [command.resource, command.action, "--help"],
    )

    assert result.exit_code == 0
    assert _squash_whitespace(command.description) in _squash_whitespace(result.output)
    for parameter in command.parameters:
        assert parameter.flag in result.output
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("command", _READ_COMMANDS, ids=lambda command: command.command_id)
def test_read_only_api_command_runs_through_fake_transport(
    command: ApiCommandRecord,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = SwaggerFakeTransport(registry=load_swagger_registry())
    fake.add_success_operation(command.operation_key)
    _install_fake_client(monkeypatch, fake)
    _write_account(tmp_path)

    args = ["--profile", "main", command.resource, command.action, *_cli_args(command)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(app, args)

    assert result.exit_code == 0, result.output
    assert fake.count() >= 1


def test_every_read_factory_has_at_least_one_smoke_command() -> None:
    smoked_factories = {command.factory for command in _READ_COMMANDS}
    read_factories = {
        command.factory
        for command in build_cli_registry().api_commands
        if command.http_method in {"GET", "HEAD"}
    }

    assert smoked_factories == read_factories


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    fake: SwaggerFakeTransport,
) -> None:
    def client_factory(settings: AvitoSettings) -> object:
        return fake.as_client(user_id=settings.user_id)

    monkeypatch.setattr("avito.cli.commands._default_client_factory", client_factory)


def _write_account(tmp_path: Path) -> None:
    account = StoredAccount(
        name="main",
        client_id="client-id",
        client_secret="client-secret",
        user_id=7,
    )
    AccountStore(tmp_path).save(AccountsDocument(accounts=(account,)))
    ConfigStore(tmp_path).save(CliConfigDocument(active_profile="main"))


def _cli_args(command: ApiCommandRecord) -> tuple[str, ...]:
    args: list[str] = []
    for parameter in command.parameters:
        args.extend((parameter.flag, _value_for_parameter(parameter)))
    return tuple(args)


def _value_for_parameter(parameter: CliParameterSchema) -> str:
    if parameter.value_kind == "list":
        item_kind = parameter.item_value_kind or "string"
        return ",".join((_value_for_kind(parameter.name, item_kind),))
    return _value_for_kind(parameter.name, parameter.value_kind)


def _value_for_kind(name: str, value_kind: CliValueKind) -> str:
    if value_kind == "integer":
        if name == "user_id":
            return "7"
        return "101"
    if value_kind == "float":
        return "100.5"
    if value_kind == "boolean":
        return "true"
    if value_kind == "date":
        return "2026-05-01"
    if value_kind == "datetime":
        return "2026-05-01T00:00:00+00:00"
    if value_kind == "enum":
        return "value"
    return _string_value(name)


def _string_value(name: str) -> str:
    if name.endswith("_id"):
        return "101"
    if "date" in name or name.endswith("_from") or name.endswith("_to"):
        return "2026-05-01"
    if name.endswith("_slug"):
        return "cars"
    if name == "price":
        return "1500"
    return "value"


def _squash_whitespace(value: str) -> str:
    return " ".join(value.split())
