"""Tests for CLI command adapter extension point."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import TracebackType

import pytest

from avito.cli.adapters import (
    AdapterMetadata,
    ClientFactory,
    CommandInvocationEngine,
    RegisteredCommandAdapter,
    build_command_adapter_registry,
)
from avito.cli.commands import invoke_api_command
from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
)
from avito.cli.context import CliContext
from avito.cli.errors import CliValidationError
from avito.cli.help import render_registry_help
from avito.cli.registry import ApiCommandRecord, CliRegistry, build_cli_registry
from avito.config import AvitoSettings
from scripts.lint_cli_coverage import lint_cli_registry_adapters


def test_adapter_transforms_cli_input_and_uses_shared_public_sdk_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _adapter_command("account.get-balance", adapter_id="test-input")
    adapter_registry = build_command_adapter_registry(
        (
            RegisteredCommandAdapter(
                metadata=AdapterMetadata(
                    adapter_id="test-input",
                    owner="cli",
                    reason="Тестовая нормализация CLI-only параметра.",
                ),
                adapter=_RenamingAdapter(source_name="profile_user", target_name="user_id"),
            ),
        )
    )
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))
    monkeypatch.setattr(
        "avito.cli.commands.get_command_adapter_registry",
        lambda: adapter_registry,
    )

    result = invoke_api_command(
        _ctx(),
        command,
        {"profile_user": ("123",)},
        client_factory=factory,
    )

    assert result == {"ok": True}
    assert factory.constructed_client_ids == ["main-client"]
    assert factory.client.entered == 1
    assert factory.client.exited == 1
    assert factory.client.account_calls == [123]
    assert factory.client.account_domain.get_balance_calls == [{}]


def test_adapter_errors_are_sanitized_and_mapped_to_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _adapter_command("account.get-balance", adapter_id="bad-input")
    adapter_registry = build_command_adapter_registry(
        (
            RegisteredCommandAdapter(
                metadata=AdapterMetadata(
                    adapter_id="bad-input",
                    owner="cli",
                    reason="Тестовая обработка ошибки adapter.",
                ),
                adapter=_FailingAdapter(),
            ),
        )
    )
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))
    monkeypatch.setattr(
        "avito.cli.commands.get_command_adapter_registry",
        lambda: adapter_registry,
    )

    with pytest.raises(CliValidationError) as exc_info:
        invoke_api_command(_ctx(), command, {"user_id": ("123",)})

    assert exc_info.value.code == "VALIDATION_FAILED"
    assert "secret-token" not in exc_info.value.message
    assert exc_info.value.details == {
        "adapter_id": "bad-input",
        "command_id": "account.get-balance",
        "error_type": "OSError",
    }


def test_adapter_registry_rejects_duplicate_adapter_ids() -> None:
    first = RegisteredCommandAdapter(
        metadata=AdapterMetadata(
            adapter_id="duplicate",
            owner="cli",
            reason="Первый adapter.",
        ),
        adapter=_RenamingAdapter(source_name="a", target_name="b"),
    )
    second = RegisteredCommandAdapter(
        metadata=AdapterMetadata(
            adapter_id="duplicate",
            owner="cli",
            reason="Второй adapter.",
        ),
        adapter=_RenamingAdapter(source_name="a", target_name="b"),
    )

    with pytest.raises(ValueError, match="повторяется"):
        build_command_adapter_registry((first, second))


def test_adapter_lint_rejects_unknown_duplicate_and_unused_adapter_ids() -> None:
    registry = build_cli_registry()
    unknown_command = _adapter_command("account.get-balance", adapter_id="unknown")
    duplicate_adapter = RegisteredCommandAdapter(
        metadata=AdapterMetadata(
            adapter_id="duplicate",
            owner="cli",
            reason="Повторяющийся adapter.",
        ),
        adapter=_RenamingAdapter(source_name="a", target_name="b"),
    )
    adapter_registry = replace(
        build_command_adapter_registry(
            (
                RegisteredCommandAdapter(
                    metadata=AdapterMetadata(
                        adapter_id="unused",
                        owner="cli",
                        reason="Неиспользуемый adapter.",
                    ),
                    adapter=_RenamingAdapter(source_name="a", target_name="b"),
                ),
            )
        ),
        adapters=(duplicate_adapter, duplicate_adapter),
    )
    linted_registry = _registry_with_command(registry, unknown_command)

    errors = lint_cli_registry_adapters(linted_registry, adapter_registry)
    codes = {error.code for error in errors}

    assert "CLI_ADAPTER_UNKNOWN" in codes
    assert "CLI_ADAPTER_DUPLICATE" in codes
    assert "CLI_ADAPTER_UNUSED" in codes


def test_adapter_backed_command_help_and_report_keep_serializable_adapter_id() -> None:
    registry = build_cli_registry()
    command = _adapter_command("account.get-balance", adapter_id="test-input")
    adapter_registry = build_command_adapter_registry(
        (
            RegisteredCommandAdapter(
                metadata=AdapterMetadata(
                    adapter_id="test-input",
                    owner="cli",
                    reason="Тестовая нормализация CLI-only параметра.",
                ),
                adapter=_RenamingAdapter(source_name="profile_user", target_name="user_id"),
            ),
        )
    )
    registry_with_adapter = _registry_with_command(registry, command)

    help_text = render_registry_help(
        ("account", "get-balance"),
        registry=registry_with_adapter,
    )
    errors = lint_cli_registry_adapters(registry_with_adapter, adapter_registry)

    assert help_text is not None
    assert "Справка: avito account get-balance" in help_text
    command_report = next(
        item
        for item in registry_with_adapter.to_dict()["api_commands"]
        if item["command_id"] == "account.get-balance"
    )
    assert command_report["adapter_id"] == "test-input"
    assert errors == ()


def _adapter_command(command_id: str, *, adapter_id: str) -> ApiCommandRecord:
    matches = tuple(
        command for command in build_cli_registry().api_commands if command.command_id == command_id
    )
    assert len(matches) == 1
    return replace(matches[0], implemented=True, adapter_id=adapter_id)


def _registry_with_command(registry: CliRegistry, command: ApiCommandRecord) -> CliRegistry:
    return replace(
        registry,
        api_commands=tuple(
            command if existing.command_id == command.command_id else existing
            for existing in registry.api_commands
        ),
    )


def _write_accounts(tmp_path: Path, *, active_profile: str) -> None:
    account = StoredAccount(
        name=active_profile,
        client_id=f"{active_profile}-client",
        client_secret=f"{active_profile}-secret",
    )
    AccountStore(tmp_path).save(AccountsDocument(accounts=(account,)))
    ConfigStore(tmp_path).save(CliConfigDocument(active_profile=active_profile))


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


class _RenamingAdapter:
    def __init__(self, *, source_name: str, target_name: str) -> None:
        self.source_name = source_name
        self.target_name = target_name

    def invoke(
        self,
        ctx: CliContext,
        command: ApiCommandRecord,
        raw_values: Mapping[str, Sequence[str]],
        *,
        engine: CommandInvocationEngine,
        client_factory: ClientFactory | None = None,
    ) -> object:
        normalized = dict(raw_values)
        normalized[self.target_name] = raw_values[self.source_name]
        return engine(ctx, command, normalized, client_factory=client_factory)


class _FailingAdapter:
    def invoke(
        self,
        ctx: CliContext,
        command: ApiCommandRecord,
        raw_values: Mapping[str, Sequence[str]],
        *,
        engine: CommandInvocationEngine,
        client_factory: ClientFactory | None = None,
    ) -> object:
        raise OSError("secret-token must not leak")


class _RecordingClientFactory:
    def __init__(self) -> None:
        self.constructed_client_ids: list[str] = []
        self.client = _RecordingClient()

    def __call__(self, settings: AvitoSettings) -> _RecordingClient:
        self.constructed_client_ids.append(settings.auth.client_id)
        return self.client


class _RecordingClient:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.account_calls: list[int | None] = []
        self.account_domain = _RecordingAccountDomain()

    def __enter__(self) -> _RecordingClient:
        self.entered += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exited += 1

    def account(self, user_id: int | None = None) -> _RecordingAccountDomain:
        self.account_calls.append(user_id)
        return self.account_domain


class _RecordingAccountDomain:
    def __init__(self) -> None:
        self.get_balance_calls: list[dict[str, object]] = []

    def get_balance(self) -> dict[str, bool]:
        self.get_balance_calls.append({})
        return {"ok": True}
