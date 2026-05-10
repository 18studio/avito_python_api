"""Tests for local CLI account commands."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import TextIO

from click.testing import CliRunner

from avito.cli import accounts
from avito.cli.app import app


def test_account_add_reloads_and_sets_initial_active_account(tmp_path: Path) -> None:
    runner = _runner(tmp_path)

    add_result = runner.invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--client-secret-stdin",
            "--endpoint",
            "https://example.test",
            "--user-id",
            "123",
        ],
        input="client-secret\n",
    )
    current_result = runner.invoke(app, ["--json", "account", "current"])

    assert add_result.exit_code == 0
    assert "client-secret" not in add_result.output
    assert current_result.exit_code == 0
    payload = json.loads(current_result.stdout)
    assert payload["active_profile"] == "main"
    assert payload["account"]["client_id"] == "client-id"
    assert payload["account"]["client_secret"] == "***"
    assert payload["account"]["base_url"] == "https://example.test"
    assert "client-secret" not in current_result.stdout


def test_account_add_rejects_duplicate_name(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    args = [
        "account",
        "add",
        "main",
        "--client-id",
        "client-id",
        "--client-secret",
        "client-secret",
    ]

    first_result = runner.invoke(app, args)
    second_result = runner.invoke(app, args)

    assert first_result.exit_code == 0
    assert second_result.exit_code == 7
    assert "CONFIG_INVALID" in second_result.stderr


def test_account_use_current_and_delete_clear_active_account(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    _add_account(runner, "first")
    _add_account(runner, "second")

    use_result = runner.invoke(app, ["account", "use", "second"])
    current_result = runner.invoke(app, ["--json", "account", "current"])
    delete_result = runner.invoke(app, ["account", "delete", "second", "--yes"])
    missing_current_result = runner.invoke(app, ["account", "current"])

    assert use_result.exit_code == 0
    assert json.loads(current_result.stdout)["active_profile"] == "second"
    assert delete_result.exit_code == 0
    assert missing_current_result.exit_code == 7
    assert "Активная учетная запись не выбрана" in missing_current_result.stderr


def test_account_remove_is_delete_alias(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    _add_account(runner, "main")

    result = runner.invoke(app, ["--json", "account", "remove", "main", "--confirm", "main"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"deleted": "main"}


def test_account_list_json_masks_secrets(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    _add_account(runner, "main", secret="raw-secret")

    result = runner.invoke(app, ["--json", "account", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["accounts"][0]["client_secret"] == "***"
    assert "raw-secret" not in result.stdout


def test_account_add_no_input_without_secret_fails_without_prompt(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["--no-input", "account", "add", "main", "--client-id", "client-id"],
    )

    assert result.exit_code == 4
    assert "AUTH_REQUIRED" in result.stderr


def test_account_add_prompts_for_missing_client_id(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["account", "add", "main", "--client-secret", "client-secret"],
        input="prompt-client-id\n",
    )

    assert result.exit_code == 0
    assert "Client ID" in result.output
    assert "prompt-client-id" in result.output


def test_account_add_prompts_for_missing_account_name(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["account", "add", "--client-id", "client-id", "--client-secret", "client-secret"],
        input="main\n",
    )

    assert result.exit_code == 0
    assert "Имя учетной записи" in result.output
    assert "Учетная запись добавлена: main" in result.output


def test_account_add_no_input_without_client_id_fails_without_prompt(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["--no-input", "account", "add", "main", "--client-secret", "client-secret"],
    )

    assert result.exit_code == 4
    assert "AUTH_REQUIRED" in result.stderr
    assert "интерактивный ввод отключен" in result.stderr


def test_account_add_no_input_without_account_name_fails_without_prompt(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["--no-input", "account", "add", "--client-id", "client-id", "--client-secret", "client-secret"],
    )

    assert result.exit_code == 2
    assert "CLI_USAGE_ERROR" in result.stderr
    assert "Интерактивный ввод отключен" in result.stderr


def test_account_add_accepts_ticket_aliases_api_key_and_endpoint(tmp_path: Path) -> None:
    runner = _runner(tmp_path)

    result = runner.invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--api-key",
            "api-secret",
            "--endpoint",
            "https://endpoint.test",
        ],
    )
    current_result = runner.invoke(app, ["--json", "account", "current"])

    assert result.exit_code == 0
    payload = json.loads(current_result.stdout)
    assert payload["account"]["base_url"] == "https://endpoint.test"
    assert "api-secret" not in current_result.stdout


def test_account_add_hidden_prompt_path(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        ["account", "add", "main", "--client-id", "client-id"],
        input="prompt-secret\n",
    )

    assert result.exit_code == 0
    assert "Client Secret" in result.output
    assert "prompt-secret" not in result.output


def test_client_secret_stdin_reads_one_secret_value(tmp_path: Path) -> None:
    runner = _runner(tmp_path)

    result = runner.invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--client-secret-stdin",
        ],
        input="stdin-secret\n",
    )
    current_result = runner.invoke(app, ["--json", "account", "current"])

    assert result.exit_code == 0
    assert "stdin-secret" not in result.output
    assert json.loads(current_result.stdout)["account"]["client_secret"] == "***"


def test_client_secret_stdin_rejects_tty_stdin(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class TtyInput(StringIO):
        def isatty(self) -> bool:
            return True

    def fake_text_stream(name: str) -> TextIO:
        assert name == "stdin"
        return TtyInput("stdin-secret\n")

    monkeypatch.setattr(accounts.click, "get_text_stream", fake_text_stream)

    result = _runner(tmp_path).invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--client-secret-stdin",
        ],
    )

    assert result.exit_code == 2
    assert "неинтерактивный stdin" in result.stderr


def test_secret_flags_are_mutually_exclusive(tmp_path: Path) -> None:
    result = _runner(tmp_path).invoke(
        app,
        [
            "account",
            "add",
            "main",
            "--client-id",
            "client-id",
            "--client-secret",
            "client-secret",
            "--api-key",
            "api-secret",
        ],
    )

    assert result.exit_code == 2
    assert "INVALID_FLAG_COMBINATION" in result.stderr


def _runner(tmp_path: Path) -> CliRunner:
    return CliRunner(env={"AVITO_PY_HOME": str(tmp_path / "home")})


def _add_account(runner: CliRunner, name: str, *, secret: str = "client-secret") -> None:
    result = runner.invoke(
        app,
        [
            "account",
            "add",
            name,
            "--client-id",
            f"{name}-client",
            "--client-secret",
            secret,
        ],
    )
    assert result.exit_code == 0
