"""Tests for generic CLI invocation through public SDK methods."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import TracebackType

import pytest

from avito.cli.commands import invoke_api_command, map_sdk_error
from avito.cli.config import (
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
)
from avito.cli.context import CliContext
from avito.cli.errors import CliAuthRequiredError, CliError
from avito.cli.registry import ApiCommandRecord, build_cli_registry
from avito.config import AvitoSettings
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    TransportError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.types import ApiTimeouts


def test_invocation_uses_active_profile_and_public_factory_method_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _api_command("account.get-balance")
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    result = invoke_api_command(
        _ctx(),
        command,
        {"user_id": ("123",)},
        client_factory=factory,
    )

    assert result == {"ok": True}
    assert factory.constructed_client_ids == ["main-client"]
    assert factory.client.entered == 1
    assert factory.client.exited == 1
    assert factory.client.account_calls == [123]
    assert factory.client.account_domain.get_balance_calls == [{}]


def test_profile_flag_overrides_active_profile_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _api_command("account.get-balance")
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    invoke_api_command(
        _ctx(profile="other"),
        command,
        {},
        client_factory=factory,
    )

    assert factory.constructed_client_ids == ["other-client"]
    assert factory.client.account_calls == [None]


def test_missing_profile_fails_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _api_command("account.get-balance")
    factory = _RecordingClientFactory()
    AccountStore(tmp_path).save(AccountsDocument())
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    with pytest.raises(CliAuthRequiredError) as exc_info:
        invoke_api_command(_ctx(), command, {}, client_factory=factory)

    assert exc_info.value.code == "AUTH_REQUIRED"
    assert factory.constructed_client_ids == []


def test_root_timeout_is_passed_only_when_sdk_method_accepts_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _api_command("account.get-balance")
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    invoke_api_command(_ctx(timeout=2.5), command, {}, client_factory=factory)

    call = factory.client.account_domain.get_balance_calls[0]
    assert isinstance(call["timeout"], ApiTimeouts)
    assert call["timeout"].connect == 2.5
    assert call["timeout"].read == 2.5
    assert call["timeout"].write == 2.5
    assert call["timeout"].pool == 2.5


def test_root_timeout_is_not_passed_to_method_without_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _api_command("account.get-self")
    factory = _RecordingClientFactory()
    _write_accounts(tmp_path, active_profile="main")
    monkeypatch.setenv("AVITO_PY_HOME", str(tmp_path))

    invoke_api_command(_ctx(timeout=2.5), command, {}, client_factory=factory)

    assert factory.client.account_domain.get_self_calls == [{}]


def test_sdk_exceptions_map_to_documented_cli_errors() -> None:
    command = _api_command("account.get-balance")

    cases = (
        (AuthenticationError("Нужна аутентификация"), "AUTH_REQUIRED", 4),
        (AuthorizationError("Нет прав"), "PERMISSION_DENIED", 5),
        (ValidationError("Некорректный запрос"), "VALIDATION_FAILED", 7),
        (ConflictError("Конфликт"), "CONFLICT", 7),
        (RateLimitError("Слишком много запросов"), "RATE_LIMITED", 6),
        (TransportError("Сетевой сбой"), "TRANSPORT_FAILED", 8),
        (UpstreamApiError("Ошибка API"), "SDK_METHOD_FAILED", 7),
    )

    for error, code, exit_code in cases:
        cli_error = map_sdk_error(error, command=command)
        assert isinstance(cli_error, CliError)
        assert cli_error.code == code
        assert cli_error.exit_code == exit_code


def _write_accounts(tmp_path: Path, *, active_profile: str) -> None:
    accounts = (
        _account("main"),
        _account("other"),
    )
    AccountStore(tmp_path).save(AccountsDocument(accounts=accounts))
    ConfigStore(tmp_path).save(CliConfigDocument(active_profile=active_profile))


def _account(name: str) -> StoredAccount:
    return StoredAccount(
        name=name,
        client_id=f"{name}-client",
        client_secret=f"{name}-secret",
    )


def _ctx(
    *,
    profile: str | None = None,
    timeout: float | None = None,
) -> CliContext:
    return CliContext(
        profile=profile,
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
        timeout=timeout,
    )


def _api_command(command_id: str) -> ApiCommandRecord:
    matches = tuple(
        command for command in build_cli_registry().api_commands if command.command_id == command_id
    )
    assert len(matches) == 1
    return replace(matches[0], implemented=True)


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
        self.get_self_calls: list[dict[str, object]] = []

    def get_balance(self, *, timeout: ApiTimeouts | None = None) -> dict[str, bool]:
        kwargs: dict[str, object] = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        self.get_balance_calls.append(kwargs)
        return {"ok": True}

    def get_self(self) -> dict[str, bool]:
        self.get_self_calls.append({})
        return {"ok": True}
