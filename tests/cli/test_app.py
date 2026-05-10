"""Tests for the root CLI shell."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

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
