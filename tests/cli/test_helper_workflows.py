"""Tests for public helper workflow CLI commands."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import pytest
from click.testing import CliRunner

from avito.cli.app import app
from avito.cli.commands import invoke_helper_command
from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
)
from avito.cli.context import CliContext
from avito.cli.registry import HelperCommandRecord, build_cli_registry
from avito.config import AvitoSettings

_HELPER_COMMANDS = build_cli_registry().helper_commands


def test_helper_metadata_covers_public_workflows_and_business_summary_exclusion() -> None:
    registry = build_cli_registry()

    assert {record.command_id for record in registry.helper_commands} == {
        "account-health.show",
        "capabilities.show",
        "chat-summary.show",
        "listing-health.show",
        "order-summary.show",
        "promotion-summary.show",
        "review-summary.show",
    }
    assert all(record.implemented for record in registry.helper_commands)
    assert {
        exclusion.command_id
        for exclusion in registry.exclusions
        if exclusion.category == "helper"
    } == {"business-summary.show"}


def test_helper_invocation_uses_public_client_method_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _helper_command("listing-health.show")
    factory = _RecordingHelperClientFactory()
    _write_account(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    result = invoke_helper_command(
        _ctx(),
        command,
        {
            "user_id": ("7",),
            "limit": ("3",),
            "page_size": ("2",),
            "date_from": ("2026-05-01",),
        },
        client_factory=factory,
    )

    assert result["helper"] == "listing_health"
    assert factory.constructed_client_ids == ["client-id"]
    assert factory.client.entered == 1
    assert factory.client.exited == 1
    assert factory.client.calls["listing_health"][0]["user_id"] == 7
    assert factory.client.calls["listing_health"][0]["limit"] == 3


def test_helper_commands_do_not_conflict_with_api_or_local_commands() -> None:
    registry = build_cli_registry()
    helper_paths = {(record.resource, record.action) for record in registry.helper_commands}
    api_paths = {(record.resource, record.action) for record in registry.api_commands}
    local_paths = {(record.resource, record.action) for record in registry.local_commands}

    assert helper_paths.isdisjoint(api_paths)
    assert helper_paths.isdisjoint(local_paths)


def test_helper_help_is_registered_without_creating_account_files(tmp_path: Path) -> None:
    command = _helper_command("promotion-summary.show")
    home = tmp_path / "home"

    result = CliRunner(env={"AVITO_PY_HOME": str(home)}).invoke(
        app,
        [command.resource, command.action, "--help"],
    )

    assert result.exit_code == 0
    assert command.description in result.output
    assert "--item-ids" in result.output
    assert not home.exists()


def test_helper_json_output_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_account(tmp_path)
    factory = _RecordingHelperClientFactory()
    monkeypatch.setattr(
        "avito.cli.commands._default_client_factory",
        factory,
    )

    result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(
        app,
        [
            "--profile",
            "main",
            "--json",
            "--no-input",
            "capabilities",
            "show",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "raw-secret" not in result.output
    assert "***" in result.output
    assert factory.client.calls["capabilities"] == [{}]


def test_all_helper_commands_are_registered_and_execute_through_fake_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_account(tmp_path)

    for command in _HELPER_COMMANDS:
        factory = _RecordingHelperClientFactory()
        monkeypatch.setattr(
            "avito.cli.commands._default_client_factory",
            factory,
        )
        args = [
            "--profile",
            "main",
            "--json",
            "--no-input",
            command.resource,
            command.action,
            *_cli_args(command),
        ]

        result = CliRunner(env={"AVITO_PY_HOME": str(tmp_path)}).invoke(app, args)

        assert result.exit_code == 0, result.output
        assert factory.client.calls[command.sdk_method_name]


def _helper_command(command_id: str) -> HelperCommandRecord:
    matches = [record for record in _HELPER_COMMANDS if record.command_id == command_id]
    assert len(matches) == 1
    return matches[0]


def _cli_args(command: HelperCommandRecord) -> tuple[str, ...]:
    args: list[str] = []
    for parameter in command.parameters:
        args.extend((parameter.flag, _value_for_parameter(parameter.name)))
    return tuple(args)


def _value_for_parameter(name: str) -> str:
    if name in {"user_id", "limit", "page_size", "listing_limit", "listing_page_size"}:
        return "7"
    if name in {"date_from", "date_to"}:
        return "2026-05-01"
    if name == "item_ids":
        return "101,102"
    return "value"


def _write_account(tmp_path: Path) -> None:
    account = StoredAccount(
        name="main",
        client_id="client-id",
        client_secret="client-secret",
        user_id=7,
    )
    AccountStore(tmp_path).save(AccountsDocument(accounts=(account,)))
    ConfigStore(tmp_path).save(CliConfigDocument(active_profile="main"))


def _ctx() -> CliContext:
    return CliContext(
        profile="main",
        config=None,
        json_output=False,
        plain=False,
        table=False,
        wide=False,
        quiet=False,
        no_input=True,
        no_color=True,
        verbose=False,
        debug=False,
        timeout=None,
    )


class _RecordingHelperClientFactory:
    def __init__(self) -> None:
        self.constructed_client_ids: list[str] = []
        self.client = _RecordingHelperClient()

    def __call__(self, settings: AvitoSettings) -> _RecordingHelperClient:
        self.constructed_client_ids.append(settings.auth.client_id)
        return self.client


class _RecordingHelperClient:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.calls: dict[str, list[dict[str, object]]] = {
            "account_health": [],
            "listing_health": [],
            "chat_summary": [],
            "order_summary": [],
            "review_summary": [],
            "promotion_summary": [],
            "capabilities": [],
        }

    def __enter__(self) -> _RecordingHelperClient:
        self.entered += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exited += 1

    def account_health(self, **kwargs: object) -> dict[str, object]:
        return self._record("account_health", kwargs)

    def listing_health(self, **kwargs: object) -> dict[str, object]:
        return self._record("listing_health", kwargs)

    def chat_summary(self, **kwargs: object) -> dict[str, object]:
        return self._record("chat_summary", kwargs)

    def order_summary(self) -> dict[str, object]:
        return self._record("order_summary", {})

    def review_summary(self) -> dict[str, object]:
        return self._record("review_summary", {})

    def promotion_summary(self, **kwargs: object) -> dict[str, object]:
        return self._record("promotion_summary", kwargs)

    def capabilities(self) -> dict[str, object]:
        result = self._record("capabilities", {})
        result["client_secret"] = "raw-secret"
        return result

    def _record(self, name: str, kwargs: dict[str, object]) -> dict[str, object]:
        self.calls[name].append(kwargs)
        return {"helper": name, "kwargs": kwargs}
