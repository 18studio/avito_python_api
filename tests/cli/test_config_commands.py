"""Tests for local CLI config commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from avito.cli.app import app


def test_config_set_get_list_and_unset_active_profile(tmp_path: Path) -> None:
    runner = _runner(tmp_path)

    set_result = runner.invoke(app, ["config", "set", "active-profile", "main"])
    get_result = runner.invoke(app, ["config", "get", "active-profile"])
    list_result = runner.invoke(app, ["--json", "config", "list"])
    unset_result = runner.invoke(app, ["config", "unset", "active-profile"])
    missing_result = runner.invoke(app, ["config", "get", "active-profile"])

    assert set_result.exit_code == 0
    assert get_result.exit_code == 0
    assert get_result.stdout.strip() == "main"
    assert json.loads(list_result.stdout)["config"]["active-profile"]["value"] == "main"
    assert unset_result.exit_code == 0
    assert missing_result.exit_code == 0
    assert missing_result.stdout == "\n"


def test_config_list_show_source_prefers_cli_profile_override(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    runner.invoke(app, ["config", "set", "active-profile", "stored"])

    result = runner.invoke(
        app,
        ["--profile", "override", "--json", "config", "list", "--show-source"],
    )

    assert result.exit_code == 0
    entry = json.loads(result.stdout)["config"]["active-profile"]
    assert entry["value"] == "override"
    assert entry["source"] == "cli"
    assert entry["path"] is None


def test_config_rejects_unknown_key(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(app, ["config", "get", "unknown"])

    assert result.exit_code == 2
    assert "CLI_USAGE_ERROR" in result.stderr
    assert "не поддерживается" in result.stderr


def _runner(tmp_path: Path) -> CliRunner:
    return CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})
