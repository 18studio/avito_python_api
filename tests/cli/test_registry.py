"""Tests for CLI command registry metadata."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from avito.cli.registry import (
    ApiCommandRecord,
    build_cli_registry,
    kebab_case,
    validate_cli_registry,
)
from avito.core.swagger_discovery import discover_swagger_bindings
from avito.core.swagger_registry import load_swagger_registry


def test_registry_builds_without_account_files_or_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AVITO_PY_HOME", str(home))

    def fail_client_init(self: object) -> None:
        raise AssertionError("AvitoClient must not be constructed by registry")

    monkeypatch.setattr("avito.client.AvitoClient.__init__", fail_client_init)

    registry = build_cli_registry()

    assert registry.to_dict()["summary"] == {
        "api_command_candidates": 162,
        "api_exclusions": 42,
        "helper_command_candidates": 7,
        "helper_exclusions": 1,
        "local_commands": 16,
        "aliases": 1,
        "execution_smoke_exclusions": 0,
    }
    assert not home.exists()


def test_registry_represents_every_sync_binding_as_candidate_or_exclusion() -> None:
    swagger_registry = load_swagger_registry()
    discovery = discover_swagger_bindings(registry=swagger_registry)
    registry = build_cli_registry(swagger_registry=swagger_registry, discovery=discovery)

    sync_bindings = tuple(
        binding
        for binding in discovery.bindings
        if binding.variant == "sync" and binding.operation_key is not None
    )
    command_operation_keys = {record.operation_key for record in registry.api_commands}
    excluded_operation_keys = {
        exclusion.operation_key
        for exclusion in registry.exclusions
        if exclusion.category == "api"
    }

    assert len(sync_bindings) == 204
    assert len(command_operation_keys) == 162
    assert len(excluded_operation_keys) == 42
    assert command_operation_keys.isdisjoint(excluded_operation_keys)
    assert command_operation_keys | excluded_operation_keys == {
        binding.operation_key for binding in sync_bindings
    }


def test_api_command_records_preserve_swagger_and_sdk_metadata() -> None:
    registry = build_cli_registry()

    command = _api_command(registry.api_commands, "account.get-balance")

    assert command.operation_key == (
        "Информацияопользователе.json GET /core/v1/accounts/{user_id}/balance"
    )
    assert command.resource == "account"
    assert command.action == "get-balance"
    assert command.sdk_module == "avito.accounts.domain"
    assert command.sdk_class == "Account"
    assert command.sdk_method_name == "get_balance"
    assert command.sdk_method == "avito.accounts.domain.Account.get_balance"
    assert command.factory == "account"
    assert command.factory_args == {"user_id": "path.user_id"}
    assert command.method_args == {}
    assert command.spec == "Информацияопользователе.json"
    assert command.http_method == "GET"
    assert command.path == "/core/v1/accounts/{user_id}/balance"
    assert command.operation_id == "getUserBalance"
    assert command.domain == "accounts"
    assert command.deprecated is False
    assert command.legacy is False
    assert len(command.parameters) == 1
    parameter = command.parameters[0]
    assert parameter.name == "user_id"
    assert parameter.source == "factory"
    assert parameter.binding_expression == "path.user_id"
    assert parameter.flag == "--user-id"
    assert parameter.value_kind == "integer"


def test_registry_keeps_record_categories_separate() -> None:
    registry = build_cli_registry()

    assert _api_command(registry.api_commands, "account.get-self").factory == "account"
    assert {record.command_id for record in registry.helper_commands} == {
        "account-health.show",
        "capabilities.show",
        "chat-summary.show",
        "listing-health.show",
        "order-summary.show",
        "promotion-summary.show",
        "review-summary.show",
    }
    assert {record.command_id for record in registry.local_commands} >= {
        "account.add",
        "account.delete",
        "help.show",
        "version.show",
    }
    assert [alias.alias_id for alias in registry.aliases] == ["account.remove"]
    assert {
        exclusion.category
        for exclusion in registry.exclusions
    } == {"api", "helper"}


def test_registry_records_include_help_metadata() -> None:
    registry = build_cli_registry()

    api_command = _api_command(registry.api_commands, "account.get-self")
    helper_command = registry.helper_commands[0]
    local_command = registry.local_commands[0]

    assert api_command.description
    assert api_command.examples[0].startswith("avito account get-self")
    assert api_command.safety == "read"
    assert api_command.safety_summary
    assert api_command.output_hint == "object"
    assert helper_command.examples
    assert helper_command.safety == "read"
    assert local_command.examples
    assert local_command.safety in {"local", "destructive"}


def test_registry_rejects_local_api_command_collision() -> None:
    registry = build_cli_registry()
    colliding_local = replace(
        registry.local_commands[0],
        command_id="account.get-self-local",
        resource="account",
        action="get-self",
    )
    invalid_registry = replace(
        registry,
        local_commands=(colliding_local, *registry.local_commands[1:]),
    )

    with pytest.raises(ValueError, match="конфликт команд"):
        validate_cli_registry(invalid_registry)


def test_registry_rejects_alias_collision_and_unknown_target() -> None:
    registry = build_cli_registry()
    colliding_alias = replace(
        registry.aliases[0],
        alias_id="account.get-self",
        resource="account",
        action="get-self",
    )
    unknown_target_alias = replace(
        registry.aliases[0],
        alias_id="account.unknown",
        target_command_id="account.unknown-target",
    )

    with pytest.raises(ValueError, match="конфликтует с canonical command"):
        validate_cli_registry(replace(registry, aliases=(colliding_alias,)))

    with pytest.raises(ValueError, match="неизвестную команду"):
        validate_cli_registry(replace(registry, aliases=(unknown_target_alias,)))


def test_registry_report_is_json_compatible_and_deterministic() -> None:
    first = build_cli_registry().to_dict()
    second = build_cli_registry().to_dict()

    first_text = json.dumps(first, ensure_ascii=False, sort_keys=True)
    second_text = json.dumps(second, ensure_ascii=False, sort_keys=True)

    assert first_text == second_text
    assert json.loads(first_text) == first


def test_api_command_ids_are_canonical_and_unique() -> None:
    registry = build_cli_registry()
    command_ids = [record.command_id for record in registry.api_commands]
    operation_keys = [record.operation_key for record in registry.api_commands]
    flags = [
        parameter.flag
        for command in registry.api_commands
        for parameter in command.parameters
    ]

    assert len(command_ids) == len(set(command_ids))
    assert len(operation_keys) == len(set(operation_keys))
    assert all(flag.startswith("--") for flag in flags)
    assert all("_" not in flag for flag in flags)


def test_kebab_case_rejects_empty_names() -> None:
    with pytest.raises(ValueError):
        kebab_case("___")


def _api_command(
    commands: tuple[ApiCommandRecord, ...],
    command_id: str,
) -> ApiCommandRecord:
    matches = [record for record in commands if record.command_id == command_id]
    counts = Counter(record.command_id for record in commands)
    assert counts[command_id] == 1
    return matches[0]
