"""Tests for CLI input schema metadata and coercion."""

from __future__ import annotations

from datetime import date, datetime
from typing import cast

import pytest

from avito.cli.errors import CliValidationError
from avito.cli.registry import ApiCommandRecord, build_cli_registry
from avito.cli.schemas import (
    CliParameterSchema,
    CliValueKind,
    coerce_cli_value,
    coerce_cli_values,
)


def test_generated_parameter_metadata_uses_binding_arguments_only() -> None:
    registry = build_cli_registry()

    command = _api_command(registry.api_commands, "account.get-balance")

    assert [parameter.name for parameter in command.parameters] == ["user_id"]
    assert command.factory_args == {"user_id": "path.user_id"}
    assert command.method_args == {}
    assert command.parameters[0].source == "factory"
    assert command.parameters[0].value_kind == "integer"
    assert command.parameters[0].required is False


def test_generated_parameter_metadata_excludes_timeout_and_retry_controls() -> None:
    registry = build_cli_registry()

    names = {
        parameter.name
        for command in registry.api_commands
        for parameter in command.parameters
    }
    flags = {
        parameter.flag
        for command in registry.api_commands
        for parameter in command.parameters
    }

    assert "timeout" not in names
    assert "retry" not in names
    assert "--timeout" not in flags
    assert "--retry" not in flags


def test_generated_metadata_classifies_dates_enums_and_lists() -> None:
    registry = build_cli_registry()

    history = _api_command(registry.api_commands, "account.get-operations-history")
    apply = _api_command(registry.api_commands, "application.apply")
    budget = _api_command(registry.api_commands, "autostrategy-campaign.create-budget")

    assert _parameter(history, "date_from").value_kind == "datetime"
    assert _parameter(history, "date_to").value_kind == "datetime"
    assert _parameter(apply, "ids").value_kind == "list"
    assert _parameter(apply, "ids").item_value_kind == "string"
    assert _parameter(budget, "campaign_type").value_kind == "enum"
    assert _parameter(budget, "campaign_type").enum_values


def test_coercion_supports_primitive_date_datetime_enum_and_list_values() -> None:
    schemas = (
        _schema("user_id", "--user-id", "integer"),
        _schema("price", "--price", "float"),
        _schema("enabled", "--enabled", "boolean"),
        _schema("date_from", "--date-from", "date"),
        _schema("created_at", "--created-at", "datetime"),
        _schema("campaign_type", "--campaign-type", "enum", enum_values=("vas", "cpa")),
        _schema("item_ids", "--item-ids", "list", item_value_kind="integer"),
    )

    coerced = coerce_cli_values(
        schemas,
        {
            "user_id": ("123",),
            "price": ("12.5",),
            "enabled": ("да",),
            "date_from": ("2026-05-10",),
            "created_at": ("2026-05-10T12:30:00Z",),
            "campaign_type": ("CPA",),
            "item_ids": ("1,2", "3"),
        },
        no_input=True,
    )

    assert coerced["user_id"] == 123
    assert coerced["price"] == 12.5
    assert coerced["enabled"] is True
    assert coerced["date_from"] == date(2026, 5, 10)
    assert coerced["created_at"] == datetime.fromisoformat("2026-05-10T12:30:00+00:00")
    assert coerced["campaign_type"] == "cpa"
    assert coerced["item_ids"] == [1, 2, 3]


def test_repeated_flags_and_comma_separated_values_are_equivalent() -> None:
    schema = _schema("ids", "--ids", "list", item_value_kind="string")

    repeated = coerce_cli_value(schema, ("one", "two"))
    comma_separated = coerce_cli_value(schema, ("one,two",))

    assert repeated == comma_separated


def test_invalid_values_raise_russian_validation_error() -> None:
    schema = _schema("user_id", "--user-id", "integer")

    with pytest.raises(CliValidationError) as exc_info:
        coerce_cli_value(schema, ("not-number",))

    assert exc_info.value.code == "VALIDATION_FAILED"
    assert "Параметр --user-id должен быть целым числом." in exc_info.value.message


def test_missing_required_value_with_no_input_raises_validation_error() -> None:
    schema = _schema("date_from", "--date-from", "date", required=True)

    with pytest.raises(CliValidationError) as exc_info:
        coerce_cli_values((schema,), {}, no_input=True)

    assert exc_info.value.code == "VALIDATION_FAILED"
    assert "Интерактивный ввод отключен" in exc_info.value.message


def _schema(
    name: str,
    flag: str,
    value_kind: str,
    *,
    required: bool = False,
    item_value_kind: str | None = None,
    enum_values: tuple[str, ...] = (),
) -> CliParameterSchema:
    return CliParameterSchema(
        name=name,
        source="method",
        binding_expression=f"body.{name}",
        flag=flag,
        value_kind=cast(CliValueKind, value_kind),
        required=required,
        multiple=value_kind == "list",
        item_value_kind=cast(CliValueKind | None, item_value_kind),
        annotation=value_kind,
        enum_values=enum_values,
    )


def _api_command(
    commands: tuple[ApiCommandRecord, ...],
    command_id: str,
) -> ApiCommandRecord:
    matches = tuple(record for record in commands if record.command_id == command_id)
    assert len(matches) == 1
    return matches[0]


def _parameter(command: ApiCommandRecord, name: str) -> CliParameterSchema:
    matches = tuple(parameter for parameter in command.parameters if parameter.name == name)
    assert len(matches) == 1
    return matches[0]
