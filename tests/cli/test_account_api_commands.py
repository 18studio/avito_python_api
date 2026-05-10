"""Vertical smoke tests for first registry-backed account API commands."""

from __future__ import annotations

import json
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
from avito.config import AvitoSettings
from avito.core.swagger_registry import load_swagger_registry
from avito.testing import SwaggerFakeTransport, error_payload


def test_account_get_self_runs_through_generic_cli_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _implemented_api_command("account.get-self")
    fake = SwaggerFakeTransport(registry=load_swagger_registry())
    fake.add_operation(
        command.operation_key,
        {"id": 7, "name": "Иван", "email": "user@example.test", "phone": "+7000"},
    )
    _install_fake_client(monkeypatch, fake)
    _write_account(tmp_path)

    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(
        app,
        ["--profile", "main", "account", "get-self"],
    )

    assert result.exit_code == 0
    assert "user_id: 7" in result.output
    assert "name: Иван" in result.output
    assert fake.count(method="GET", path="/core/v1/accounts/self") == 1


def test_account_get_balance_supports_json_output_and_user_id_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _implemented_api_command("account.get-balance")
    fake = SwaggerFakeTransport(registry=load_swagger_registry())
    fake.add_operation(
        command.operation_key,
        {"user_id": 7, "balance": {"real": 150.5, "bonus": 20.0, "currency": "RUB"}},
    )
    _install_fake_client(monkeypatch, fake)
    _write_account(tmp_path)

    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(
        app,
        ["--json", "--profile", "main", "account", "get-balance", "--user-id", "7"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "bonus": 20.0,
        "currency": "RUB",
        "real": 150.5,
        "total": 170.5,
        "user_id": 7,
    }
    assert fake.count(method="GET", path="/core/v1/accounts/7/balance/") == 1


def test_account_api_command_errors_are_rendered_as_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _implemented_api_command("account.get-self")
    fake = SwaggerFakeTransport(registry=load_swagger_registry())
    fake.add_operation(command.operation_key, error_payload(401), status_code=401)
    _install_fake_client(monkeypatch, fake)
    _write_account(tmp_path)

    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(
        app,
        ["--json", "--profile", "main", "account", "get-self"],
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "code": "AUTH_REQUIRED",
        "exit_code": 4,
        "message": "Ошибка 401",
    }


def test_account_api_command_help_is_registered_without_account_files(tmp_path: Path) -> None:
    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")}).invoke(
        app,
        ["account", "get-balance", "--help"],
    )

    assert result.exit_code == 0
    assert "--user-id" in result.output
    assert "Параметр SDK `user_id`" in result.output
    assert not (tmp_path / "home").exists()


def _implemented_api_command(command_id: str) -> ApiCommandRecord:
    matches = tuple(
        command for command in build_cli_registry().api_commands if command.command_id == command_id
    )
    assert len(matches) == 1
    assert matches[0].implemented is True
    return matches[0]


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
