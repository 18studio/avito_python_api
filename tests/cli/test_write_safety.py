"""Tests for CLI write safety primitives."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import TracebackType

import pytest

from avito.cli.commands import invoke_api_command
from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
)
from avito.cli.context import CliContext
from avito.cli.errors import CliUsageError
from avito.cli.registry import ApiCommandRecord, SafetyKind, build_cli_registry
from avito.cli.safety import CommandSafetyPolicy, SafetyOptions
from avito.config import AvitoSettings


def test_destructive_command_requires_confirmation_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_command(safety="destructive", confirmation_required=True)
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    with pytest.raises(CliUsageError) as exc_info:
        invoke_api_command(
            _ctx(),
            command,
            {},
            safety_options=SafetyOptions(),
            client_factory=factory,
        )

    assert exc_info.value.code == "CLI_USAGE_ERROR"
    assert factory.constructed_client_ids == []


def test_destructive_command_accepts_yes_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_command(safety="destructive", confirmation_required=True)
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    result = invoke_api_command(
        _ctx(),
        command,
        {},
        safety_options=SafetyOptions(yes=True),
        client_factory=factory,
    )

    assert result == {"applied": True}
    assert factory.client.write_domain.apply_calls == [{}]


def test_destructive_command_accepts_exact_confirm_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_command(safety="destructive", confirmation_required=True)
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    invoke_api_command(
        _ctx(),
        command,
        {},
        safety_options=SafetyOptions(confirm=command.command_id),
        client_factory=factory,
    )

    assert factory.client.write_domain.apply_calls == [{}]


def test_dry_run_is_rejected_when_policy_does_not_support_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_command(dry_run_supported=False)
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    with pytest.raises(CliUsageError) as exc_info:
        invoke_api_command(
            _ctx(),
            command,
            {},
            safety_options=SafetyOptions(dry_run=True),
            client_factory=factory,
        )

    assert "--dry-run" in exc_info.value.message
    assert factory.constructed_client_ids == []


def test_supported_dry_run_is_passed_to_sdk_method(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _write_command(dry_run_supported=True)
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path)
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    result = invoke_api_command(
        _ctx(),
        command,
        {},
        safety_options=SafetyOptions(dry_run=True),
        client_factory=factory,
    )

    assert result == {"dry_run": True}
    assert factory.client.write_domain.apply_calls == [{"dry_run": True}]


def _write_command(
    *,
    safety: SafetyKind = "write",
    confirmation_required: bool = False,
    dry_run_supported: bool = False,
) -> ApiCommandRecord:
    base = next(
        command
        for command in build_cli_registry().api_commands
        if command.command_id == "account.get-self"
    )
    return replace(
        base,
        command_id="write-resource.apply",
        resource="write-resource",
        action="apply",
        factory="write_resource",
        factory_args={},
        method_args={},
        parameters=(),
        sdk_method_name="apply",
        sdk_method="tests.cli.test_write_safety._WriteDomain.apply",
        http_method="POST",
        safety=safety,
        safety_summary="Команда может изменить состояние тестового ресурса.",
        safety_policy=CommandSafetyPolicy(
            kind=safety,
            confirmation_required=confirmation_required,
            dry_run_supported=dry_run_supported,
            review_note="Тестовая write safety policy.",
        ),
        implemented=True,
    )


def _write_accounts(tmp_path: Path) -> None:
    account = StoredAccount(
        name="main",
        client_id="main-client",
        client_secret="main-secret",
    )
    AccountStore(tmp_path).save(AccountsDocument(accounts=(account,)))
    ConfigStore(tmp_path).save(CliConfigDocument(active_profile="main"))


def _ctx() -> CliContext:
    return CliContext(
        profile=None,
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


class _RecordingClientFactory:
    def __init__(self) -> None:
        self.constructed_client_ids: list[str] = []
        self.client = _RecordingClient()

    def __call__(self, settings: AvitoSettings) -> _RecordingClient:
        self.constructed_client_ids.append(settings.auth.client_id)
        return self.client


class _RecordingClient:
    def __init__(self) -> None:
        self.write_domain = _WriteDomain()

    def __enter__(self) -> _RecordingClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def write_resource(self) -> _WriteDomain:
        return self.write_domain


class _WriteDomain:
    def __init__(self) -> None:
        self.apply_calls: list[dict[str, object]] = []

    def apply(self, *, dry_run: bool = False) -> dict[str, bool]:
        call: dict[str, object] = {}
        if dry_run:
            call["dry_run"] = dry_run
        self.apply_calls.append(call)
        if dry_run:
            return {"dry_run": True}
        return {"applied": True}
