"""Tests for CLI UI helpers and global output flags."""

from __future__ import annotations

import os

from click.testing import CliRunner

from avito.cli.app import app


def test_quiet_suppresses_non_essential_success_output() -> None:
    result = CliRunner().invoke(app, ["--quiet", "version"])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_quiet_keeps_json_command_result() -> None:
    result = CliRunner().invoke(app, ["--json", "--quiet", "version"])

    assert result.exit_code == 0
    assert result.stdout.startswith('{"version":')
    assert result.stderr == ""


def test_verbose_global_flag_is_accepted() -> None:
    result = CliRunner().invoke(app, ["--verbose", "version"])

    assert result.exit_code == 0
    assert result.stdout.startswith("avito-py ")


def test_debug_global_flag_is_accepted_on_success() -> None:
    result = CliRunner().invoke(app, ["--debug", "version"])

    assert result.exit_code == 0
    assert result.stdout.startswith("avito-py ")
    assert result.stderr == ""


def test_no_color_disables_error_color() -> None:
    result = CliRunner().invoke(
        app,
        ["--no-color", "--plain", "--table", "version"],
        color=True,
    )

    assert result.exit_code == 2
    assert "\x1b[" not in result.stderr


def test_no_color_environment_disables_error_color() -> None:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"

    result = CliRunner(env=env).invoke(
        app,
        ["--plain", "--table", "version"],
        color=True,
    )

    assert result.exit_code == 2
    assert "\x1b[" not in result.stderr
