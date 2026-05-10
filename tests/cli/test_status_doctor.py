"""Tests for CLI status and doctor commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from avito.cli.app import app


def test_status_reports_ready_account_without_network(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    _add_account(runner)

    result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)["status"]
    assert payload["ready"] is True
    assert payload["selected_profile"] == "main"
    assert payload["account_found"] is True
    assert payload["network_checked"] is False


def test_status_reports_missing_account_as_not_ready(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(app, ["--json", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)["status"]
    assert payload["ready"] is False
    assert payload["selected_profile"] is None
    assert payload["configured_accounts"] == 0


def test_doctor_reports_ok_for_valid_local_files(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    _add_account(runner)

    result = runner.invoke(app, ["--json", "doctor"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)["doctor"]
    assert payload["status"] == "ok"
    assert payload["issues"] == []
    assert payload["network_checked"] is False


def test_doctor_reports_malformed_config_without_leaking_secrets(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text("{invalid", encoding="utf-8")
    (home / "accounts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "accounts": [
                    {
                        "name": "main",
                        "client_id": "client-id",
                        "client_secret": "raw-secret",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _runner(tmp_path).invoke(app, ["--json", "doctor"])

    assert result.exit_code == 7
    assert "CONFIG_INVALID" in result.stderr
    assert "raw-secret" not in result.stdout
    assert "raw-secret" not in result.stderr
    payload = json.loads(result.stdout)["doctor"]
    assert payload["status"] == "error"
    assert payload["issues"][0]["name"] == "config"


def _runner(tmp_path: Path) -> CliRunner:
    return CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})


def _add_account(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--client-secret",
            "client-secret",
        ],
    )
    assert result.exit_code == 0
