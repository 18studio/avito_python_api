"""Tests for shell completion commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from avito.cli.app import app


def test_completion_commands_render_shell_instructions() -> None:
    runner = CliRunner()

    bash = runner.invoke(app, ["completion", "bash"])
    zsh = runner.invoke(app, ["completion", "zsh"])
    fish = runner.invoke(app, ["completion", "fish"])

    assert bash.exit_code == 0
    assert "_AVITO_COMPLETE=bash_source avito" in bash.stdout
    assert zsh.exit_code == 0
    assert "_AVITO_COMPLETE=zsh_source avito" in zsh.stdout
    assert fish.exit_code == 0
    assert "_AVITO_COMPLETE=fish_source avito | source" in fish.stdout


def test_completion_json_output_is_stable() -> None:
    result = CliRunner().invoke(app, ["--json", "completion", "bash"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "completion": {
            "command": 'eval "$(_AVITO_COMPLETE=bash_source avito)"',
            "shell": "bash",
        }
    }
