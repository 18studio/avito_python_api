"""Tests for CLI error rendering."""

from __future__ import annotations

import json

from click.testing import CliRunner

from avito.cli.app import app


def test_human_errors_go_to_stderr() -> None:
    result = CliRunner().invoke(app, ["--plain", "--table", "version"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "INVALID_FLAG_COMBINATION" in result.stderr
    assert "нельзя использовать вместе" in result.stderr


def test_json_errors_are_valid_json_on_stderr() -> None:
    result = CliRunner().invoke(app, ["--json", "--plain", "version"])

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload == {
        "code": "INVALID_FLAG_COMBINATION",
        "exit_code": 2,
        "message": "Флаги --json, --plain, --table и --wide нельзя использовать вместе.",
    }


def test_debug_diagnostics_are_sanitized() -> None:
    result = CliRunner().invoke(
        app,
        ["--debug", "help", "client_secret=super-secret"],
    )

    assert result.exit_code == 2
    assert "details=" in result.stderr
    assert "client_secret" not in result.stderr
    assert "super-secret" not in result.stderr
    assert "***" in result.stderr


def test_json_debug_diagnostics_are_sanitized() -> None:
    result = CliRunner().invoke(
        app,
        ["--json", "--debug", "help", "client_secret=super-secret"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["details"] == {"topic": ["***"]}
    assert "client_secret" not in result.stderr
    assert "super-secret" not in result.stderr


def test_invalid_flag_combinations_exit_with_code_2() -> None:
    result = CliRunner().invoke(app, ["--json", "--plain", "version"])

    assert result.exit_code == 2
