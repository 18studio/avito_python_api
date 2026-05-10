"""Tests for the root CLI shell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from avito.cli.accounts import account_group
from avito.cli.app import app


def test_help_outputs_root_help_without_filesystem_side_effects(tmp_path: Path) -> None:
    runner = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Командная строка для Avito API SDK." in result.output
    assert "--profile" in result.output
    assert not (tmp_path / "home").exists()


def test_help_command_delegates_to_root_help_without_filesystem_side_effects(
    tmp_path: Path,
) -> None:
    runner = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})

    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0
    assert "Командная строка для Avito API SDK." in result.output
    assert "--version" in result.output
    assert not (tmp_path / "home").exists()


def test_help_command_renders_registry_resource_without_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})

    def fail_client_init(self: object) -> None:
        raise AssertionError("AvitoClient must not be constructed by registry help")

    monkeypatch.setattr("avito.client.AvitoClient.__init__", fail_client_init)

    result = runner.invoke(app, ["help", "account"])

    assert result.exit_code == 0
    assert "Справка: avito account" in result.output
    assert "get-self" in result.output
    assert "delete" in result.output
    assert "remove" in result.output
    assert not (tmp_path / "home").exists()


def test_help_command_renders_registry_action_without_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})

    def fail_client_init(self: object) -> None:
        raise AssertionError("AvitoClient must not be constructed by registry help")

    monkeypatch.setattr("avito.client.AvitoClient.__init__", fail_client_init)

    result = runner.invoke(app, ["help", "account", "get-balance"])

    assert result.exit_code == 0
    assert "Справка: avito account get-balance" in result.output
    assert "--user-id" in result.output
    assert "Команда только читает данные Avito API." in result.output
    assert not (tmp_path / "home").exists()


def test_help_command_renders_registry_alias() -> None:
    result = CliRunner().invoke(app, ["help", "account", "remove"])

    assert result.exit_code == 0
    assert "Совместимое имя для `avito account delete`." in result.output


def test_account_remove_alias_reuses_delete_callback() -> None:
    parent_context = None
    delete_command = account_group.get_command(parent_context, "delete")
    remove_command = account_group.get_command(parent_context, "remove")

    assert delete_command is not None
    assert remove_command is not None
    assert remove_command.callback is delete_command.callback


def test_version_command_outputs_human_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.startswith("avito-py ")


def test_version_command_outputs_json_when_requested() -> None:
    result = CliRunner().invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    assert result.output.startswith('{"version":')


def test_version_option_outputs_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "avito" in result.output


def test_version_option_works_outside_project_directory(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [sys.executable, "-m", "avito", "--version"],
        check=False,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("avito-py ")
    assert result.stderr == ""


def test_python_module_entrypoint_uses_cli_help(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "avito", "--help"],
        check=False,
        capture_output=True,
        env={"AVITO_PY_HOME": str(tmp_path / "home")},
        text=True,
    )

    assert result.returncode == 0
    assert "Командная строка для Avito API SDK." in result.stdout
    assert result.stderr == ""
    assert not (tmp_path / "home").exists()


def test_root_global_options_are_accepted_before_subcommand(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    result = CliRunner().invoke(
        app,
        [
            "--profile",
            "main",
            "--config",
            str(config_path),
            "--no-input",
            "--timeout",
            "3.5",
            "version",
        ],
    )

    assert result.exit_code == 0
    assert result.output.startswith("avito-py ")
    assert not config_path.exists()


def test_output_format_flags_are_mutually_exclusive() -> None:
    result = CliRunner().invoke(app, ["--json", "--plain", "version"])

    assert result.exit_code == 2
    assert "нельзя использовать вместе" in result.stderr
