"""Static CLI registry coverage checks."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import click

from avito.cli.adapters import CommandAdapterRegistry, get_command_adapter_registry
from avito.cli.app import app
from avito.cli.registry import (
    ApiCommandRecord,
    CliRegistry,
    ExclusionRecord,
    HelperCommandRecord,
    LocalCommandRecord,
    build_cli_registry,
)
from avito.core.swagger_discovery import discover_swagger_bindings
from avito.core.swagger_registry import load_swagger_registry

Phase = Literal["registry", "read", "write-safety", "write", "strict"]
CommandRecord = ApiCommandRecord | HelperCommandRecord | LocalCommandRecord

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CONTROL_METHOD_FLAGS = frozenset({"--timeout", "--retry"})
_CONTROL_METHOD_NAMES = frozenset({"timeout", "retry"})
_DEPRECATION_POLICY_MARKERS = frozenset({"устаревшая", "совместимая", "исключ"})
_WRITE_WAVES: dict[str, frozenset[str]] = {
    "wave-1": frozenset(
        {
            "rating_profile",
            "review",
            "review_answer",
            "realty_analytics_report",
            "realty_booking",
            "realty_listing",
            "realty_pricing",
            "tariff",
            "account",
            "account_hierarchy",
        }
    ),
    "wave-2": frozenset(
        {
            "ad",
            "ad_promotion",
            "ad_stats",
            "cpa_archive",
            "cpa_auction",
            "cpa_call",
            "cpa_chat",
            "cpa_lead",
            "chat",
            "chat_media",
            "chat_message",
            "chat_webhook",
            "special_offer_campaign",
        }
    ),
    "wave-3": frozenset(
        {
            "application",
            "resume",
            "vacancy",
            "job_dictionary",
            "job_webhook",
            "autoload_archive",
            "autoload_profile",
            "autoload_report",
        }
    ),
    "wave-4": frozenset(
        {
            "order",
            "order_label",
            "delivery_order",
            "delivery_task",
            "sandbox_delivery",
            "stock",
            "promotion_order",
            "autostrategy_campaign",
            "bbip_promotion",
            "trx_promotion",
            "target_action_pricing",
        }
    ),
    "wave-5": frozenset(
        {
            "autoteka_vehicle",
            "autoteka_report",
            "autoteka_monitoring",
            "autoteka_scoring",
            "autoteka_valuation",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class CliCoverageLintError:
    """Single CLI coverage lint violation."""

    code: str
    message: str
    item: str

    def render(self) -> str:
        """Render one text report line."""

        return f"{self.item}: [{self.code}] {self.message}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run CLI coverage lint."""

    parser = argparse.ArgumentParser(description="Проверить coverage registry CLI.")
    parser.add_argument(
        "--phase",
        choices=("registry", "read", "write-safety", "write"),
        default="registry",
        help="Фаза проверки CLI coverage.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Включить строгую проверку полного CLI coverage.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=None,
        help="Factory/domain для ограничения write-проверки; можно передать несколько раз.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Корень репозитория.",
    )
    args = parser.parse_args(argv)

    phase = "strict" if args.strict else cast(Phase, args.phase)
    domains = tuple(args.domain or ())
    errors = lint_cli_coverage(root=args.root, phase=phase, domains=domains)
    report = render_text_report(errors, phase=phase)
    print(report, end="")
    return 1 if errors else 0


def lint_cli_coverage(
    *,
    root: Path = Path("."),
    phase: Phase = "registry",
    domains: Sequence[str] = (),
) -> tuple[CliCoverageLintError, ...]:
    """Return CLI coverage lint violations for the real repository registry."""

    normalized_root = root.resolve()
    if not (normalized_root / "avito").exists():
        return (
            CliCoverageLintError(
                code="CLI_ROOT_INVALID",
                message="Корень репозитория не содержит каталог avito.",
                item=normalized_root.as_posix(),
            ),
        )
    try:
        swagger_registry = load_swagger_registry()
        discovery = discover_swagger_bindings(registry=swagger_registry)
        registry = build_cli_registry(
            swagger_registry=swagger_registry,
            discovery=discovery,
        )
    except ValueError as exc:
        return (
            CliCoverageLintError(
                code="CLI_REGISTRY_INVALID",
                message=str(exc),
                item="registry",
            ),
        )

    errors: list[CliCoverageLintError] = []
    errors.extend(_lint_sync_binding_inventory(registry))
    errors.extend(_lint_names(registry))
    errors.extend(_lint_binding_ownership(registry))
    errors.extend(_lint_aliases(registry))
    errors.extend(_lint_exclusions(registry))
    errors.extend(_lint_parameters(registry))
    errors.extend(_lint_deprecated_policy(registry))
    if phase in {"read", "write-safety", "write", "strict"}:
        errors.extend(_lint_read_phase(registry))
    if phase in {"write-safety", "write", "strict"}:
        errors.extend(_lint_write_safety_phase(registry))
    if phase in {"write", "strict"}:
        errors.extend(_lint_write_phase(registry, domains=domains))
    if phase == "strict":
        errors.extend(_lint_strict_phase(registry))
        errors.extend(_lint_helper_phase(registry))
    errors.extend(lint_cli_registry_adapters(registry, get_command_adapter_registry()))
    return tuple(sorted(errors, key=lambda error: (error.item, error.code, error.message)))


def lint_cli_registry_adapters(
    registry: CliRegistry,
    adapter_registry: CommandAdapterRegistry,
) -> tuple[CliCoverageLintError, ...]:
    """Return adapter metadata lint violations for a CLI registry."""

    return _lint_adapters(registry, adapter_registry)


def render_text_report(errors: Sequence[CliCoverageLintError], *, phase: Phase) -> str:
    """Render deterministic CLI coverage lint report."""

    lines = [f"CLI coverage lint: phase={phase}, errors={len(errors)}"]
    lines.extend(error.render() for error in errors)
    return "\n".join(lines) + "\n"


def _lint_sync_binding_inventory(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    swagger_registry = load_swagger_registry()
    discovery = discover_swagger_bindings(registry=swagger_registry)
    sync_operation_keys = {
        binding.operation_key
        for binding in discovery.bindings
        if binding.variant == "sync" and binding.operation_key is not None
    }
    command_operation_keys = {record.operation_key for record in registry.api_commands}
    excluded_operation_keys = {
        exclusion.operation_key
        for exclusion in registry.exclusions
        if exclusion.category == "api" and exclusion.operation_key is not None
    }

    errors: list[CliCoverageLintError] = []
    for operation_key in sorted(sync_operation_keys - command_operation_keys - excluded_operation_keys):
        errors.append(
            CliCoverageLintError(
                code="CLI_BINDING_MISSING",
                message="Sync Swagger binding отсутствует в registry report.",
                item=operation_key,
            )
        )
    for operation_key in sorted((command_operation_keys | excluded_operation_keys) - sync_operation_keys):
        errors.append(
            CliCoverageLintError(
                code="CLI_BINDING_UNKNOWN",
                message="Registry ссылается на неизвестный sync Swagger binding.",
                item=operation_key,
            )
        )
    for operation_key in sorted(command_operation_keys & excluded_operation_keys):
        errors.append(
            CliCoverageLintError(
                code="CLI_BINDING_DUPLICATE_POLICY",
                message="Swagger binding одновременно покрыт командой и исключением.",
                item=operation_key,
            )
        )
    return tuple(errors)


def _lint_names(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    for record in _canonical_records(registry):
        errors.extend(_lint_command_name(record.command_id, record.resource, record.action))
    for alias in registry.aliases:
        errors.extend(_lint_command_name(alias.alias_id, alias.resource, alias.action))
    return tuple(errors)


def _lint_command_name(
    command_id: str,
    resource: str,
    action: str,
) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    expected_command_id = f"{resource}.{action}"
    if command_id != expected_command_id:
        errors.append(
            CliCoverageLintError(
                code="CLI_COMMAND_ID_INVALID",
                message=f"Command id должен быть `{expected_command_id}`.",
                item=command_id,
            )
        )
    for label, value in (("resource", resource), ("action", action)):
        if _KEBAB_RE.fullmatch(value) is None:
            errors.append(
                CliCoverageLintError(
                    code="CLI_NAME_NOT_KEBAB",
                    message=f"{label} должен быть lowercase kebab-case.",
                    item=command_id,
                )
            )
        if value == "resource-id":
            errors.append(
                CliCoverageLintError(
                    code="CLI_RESOURCE_ID_FORBIDDEN",
                    message="Имя `resource-id` запрещено.",
                    item=command_id,
                )
            )
    return tuple(errors)


def _lint_binding_ownership(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    operation_counts = Counter(record.operation_key for record in registry.api_commands)
    command_counts = Counter(record.command_id for record in registry.api_commands)
    canonical_key_counts = Counter(
        (record.resource, record.action) for record in _canonical_records(registry)
    )
    for operation_key, count in sorted(operation_counts.items()):
        if count > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_BINDING_DUPLICATE_COMMAND",
                    message=f"Swagger binding привязан к {count} canonical API commands.",
                    item=operation_key,
                )
            )
    for command_id, count in sorted(command_counts.items()):
        if count > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_COMMAND_DUPLICATE",
                    message=f"Command id повторяется {count} раз.",
                    item=command_id,
                )
            )
    for key, count in sorted(canonical_key_counts.items()):
        if count > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_COMMAND_COLLISION",
                    message=f"Путь команды занят {count} canonical records.",
                    item=" ".join(key),
                )
            )
    return tuple(errors)


def _lint_aliases(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    command_ids = {record.command_id for record in _canonical_records(registry)}
    canonical_keys = {(record.resource, record.action) for record in _canonical_records(registry)}
    alias_keys = Counter((alias.resource, alias.action) for alias in registry.aliases)
    errors: list[CliCoverageLintError] = []
    for alias in registry.aliases:
        if alias.target_command_id not in command_ids:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ALIAS_TARGET_UNKNOWN",
                    message=f"Alias ссылается на неизвестную команду `{alias.target_command_id}`.",
                    item=alias.alias_id,
                )
            )
        if (alias.resource, alias.action) in canonical_keys:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ALIAS_COLLIDES_WITH_COMMAND",
                    message="Alias не должен занимать canonical command path.",
                    item=alias.alias_id,
                )
            )
        if alias_keys[(alias.resource, alias.action)] > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ALIAS_DUPLICATE_PATH",
                    message="Alias path повторяется.",
                    item=alias.alias_id,
                )
            )
        if not alias.reason:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ALIAS_REASON_MISSING",
                    message="Alias должен содержать причину совместимости.",
                    item=alias.alias_id,
                )
            )
    return tuple(errors)


def _lint_exclusions(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    exclusion_ids = Counter(exclusion.exclusion_id for exclusion in registry.exclusions)
    for exclusion in registry.exclusions:
        if exclusion_ids[exclusion.exclusion_id] > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_EXCLUSION_DUPLICATE",
                    message="Exclusion id повторяется.",
                    item=exclusion.exclusion_id,
                )
            )
        errors.extend(_lint_exclusion_required_fields(exclusion))
    return tuple(errors)


def _lint_exclusion_required_fields(
    exclusion: ExclusionRecord,
) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    required_values = {
        "reason": exclusion.reason,
        "follow_up": exclusion.follow_up,
        "owner": exclusion.owner,
    }
    for field_name, value in required_values.items():
        if not value:
            errors.append(
                CliCoverageLintError(
                    code="CLI_EXCLUSION_METADATA_MISSING",
                    message=f"Exclusion должен содержать `{field_name}`.",
                    item=exclusion.exclusion_id,
                )
            )
    if exclusion.status == "temporary" and not exclusion.target_stage:
        errors.append(
            CliCoverageLintError(
                code="CLI_EXCLUSION_TARGET_STAGE_MISSING",
                message="Temporary exclusion должен содержать target_stage.",
                item=exclusion.exclusion_id,
            )
        )
    if exclusion.category == "api" and exclusion.operation_key is None:
        errors.append(
            CliCoverageLintError(
                code="CLI_API_EXCLUSION_BINDING_MISSING",
                message="API exclusion должен ссылаться на operation_key.",
                item=exclusion.exclusion_id,
            )
        )
    if exclusion.category != "api" and not exclusion.command_id and not exclusion.sdk_method:
        errors.append(
            CliCoverageLintError(
                code="CLI_EXCLUSION_TARGET_MISSING",
                message="Non-API exclusion должен ссылаться на command_id или sdk_method.",
                item=exclusion.exclusion_id,
            )
        )
    return tuple(errors)


def _lint_parameters(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    for record in registry.api_commands:
        errors.extend(_lint_api_command_parameters(record))
    return tuple(errors)


def _lint_api_command_parameters(
    record: ApiCommandRecord,
) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    expected = {
        ("factory", name, expression)
        for name, expression in record.factory_args.items()
    } | {
        ("method", name, expression)
        for name, expression in record.method_args.items()
    }
    actual = {
        (parameter.source, parameter.name, parameter.binding_expression)
        for parameter in record.parameters
    }
    for source, name, expression in sorted(expected - actual):
        errors.append(
            CliCoverageLintError(
                code="CLI_PARAMETER_MISSING",
                message=(
                    f"Binding argument `{source}.{name}` с expression `{expression}` "
                    "не представлен CLI parameter metadata."
                ),
                item=record.command_id,
            )
        )
    for source, name, expression in sorted(actual - expected):
        errors.append(
            CliCoverageLintError(
                code="CLI_PARAMETER_NOT_FROM_BINDING",
                message=(
                    f"CLI parameter `{source}.{name}` с expression `{expression}` "
                    "не выбран из factory_args/method_args."
                ),
                item=record.command_id,
            )
        )
    for parameter in record.parameters:
        if parameter.name == "resource_id" or parameter.flag == "--resource-id":
            errors.append(
                CliCoverageLintError(
                    code="CLI_RESOURCE_ID_FORBIDDEN",
                    message="Параметр `resource_id` / `--resource-id` запрещен.",
                    item=record.command_id,
                )
            )
        if parameter.name in _CONTROL_METHOD_NAMES or parameter.flag in _CONTROL_METHOD_FLAGS:
            errors.append(
                CliCoverageLintError(
                    code="CLI_METHOD_CONTROL_FLAG_FORBIDDEN",
                    message="SDK control parameter нельзя публиковать как method flag.",
                    item=record.command_id,
                )
            )
        if _KEBAB_RE.fullmatch(parameter.flag.removeprefix("--")) is None:
            errors.append(
                CliCoverageLintError(
                    code="CLI_FLAG_NOT_KEBAB",
                    message="CLI flag должен быть lowercase kebab-case.",
                    item=f"{record.command_id} {parameter.flag}",
                )
            )
    return tuple(errors)


def _lint_deprecated_policy(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    intentional_exclusions = {
        exclusion.operation_key
        for exclusion in registry.exclusions
        if exclusion.category == "api" and exclusion.status == "intentional"
    }
    errors: list[CliCoverageLintError] = []
    for record in registry.api_commands:
        if not (record.deprecated or record.legacy):
            continue
        policy_text = " ".join((record.description, record.safety_summary)).lower()
        if record.operation_key in intentional_exclusions:
            continue
        if not any(marker in policy_text for marker in _DEPRECATION_POLICY_MARKERS):
            errors.append(
                CliCoverageLintError(
                    code="CLI_DEPRECATED_POLICY_MISSING",
                    message=(
                        "Deprecated/compatibility binding должен иметь warning/help metadata "
                        "или intentional exclusion."
                    ),
                    item=record.command_id,
                )
            )
    return tuple(errors)


def _lint_read_phase(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    read_commands = [
        record
        for record in registry.api_commands
        if record.http_method in {"GET", "HEAD"}
    ]
    errors: list[CliCoverageLintError] = []
    for record in read_commands:
        if not record.implemented:
            errors.append(
                CliCoverageLintError(
                    code="CLI_READ_COMMAND_NOT_IMPLEMENTED",
                    message="Read-only sync binding должен иметь canonical CLI-команду.",
                    item=record.command_id,
                )
            )
        if record.safety != "read":
            errors.append(
                CliCoverageLintError(
                    code="CLI_READ_SAFETY_INVALID",
                    message="Read-команда должна иметь safety=read.",
                    item=record.command_id,
                )
            )
    required_stage8_ids = {"account.get-balance", "account.get-self"}
    implemented_ids = {record.command_id for record in read_commands if record.implemented}
    for command_id in sorted(required_stage8_ids - implemented_ids):
        errors.append(
            CliCoverageLintError(
                code="CLI_READ_SLICE_MISSING",
                message="Stage 8 read slice должен быть реализован.",
                item=command_id,
            )
        )
    return tuple(errors)


def _lint_write_safety_phase(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    for record in _canonical_records(registry):
        if record.safety_policy.kind != record.safety:
            errors.append(
                CliCoverageLintError(
                    code="CLI_SAFETY_POLICY_KIND_MISMATCH",
                    message="Safety policy kind должен совпадать с command safety.",
                    item=record.command_id,
                )
            )
        if not record.safety_policy.review_note:
            errors.append(
                CliCoverageLintError(
                    code="CLI_SAFETY_POLICY_REVIEW_MISSING",
                    message="Safety policy должен содержать review note.",
                    item=record.command_id,
                )
            )
        if record.safety in {"destructive", "expensive"} and not record.safety_policy.confirmation_required:
            errors.append(
                CliCoverageLintError(
                    code="CLI_SAFETY_CONFIRMATION_MISSING",
                    message="Destructive/expensive команда должна требовать подтверждение.",
                    item=record.command_id,
                )
            )
        if record.safety == "read" and record.safety_policy.confirmation_required:
            errors.append(
                CliCoverageLintError(
                    code="CLI_READ_CONFIRMATION_INVALID",
                    message="Read-команда не должна требовать подтверждение.",
                    item=record.command_id,
                )
            )
        if record.safety == "read" and record.safety_policy.dry_run_supported:
            errors.append(
                CliCoverageLintError(
                    code="CLI_READ_DRY_RUN_INVALID",
                    message="Read-команда не должна публиковать dry-run.",
                    item=record.command_id,
                )
            )
    return tuple(errors)


def _lint_write_phase(
    registry: CliRegistry,
    *,
    domains: Sequence[str],
) -> tuple[CliCoverageLintError, ...]:
    selected_domains = _expand_write_domains(domains)
    write_commands = [
        record
        for record in registry.api_commands
        if record.http_method not in {"GET", "HEAD"}
        and (not selected_domains or record.factory in selected_domains)
    ]
    write_exclusions = [
        exclusion
        for exclusion in registry.exclusions
        if exclusion.category == "api"
        and exclusion.command_id is not None
        and (not selected_domains or _resource_to_factory(exclusion.command_id) in selected_domains)
    ]
    errors: list[CliCoverageLintError] = []
    for record in write_commands:
        if not record.implemented:
            errors.append(
                CliCoverageLintError(
                    code="CLI_WRITE_COMMAND_NOT_IMPLEMENTED",
                    message="Write sync binding должен иметь canonical CLI-команду.",
                    item=record.command_id,
                )
            )
        if record.safety not in {"write", "destructive", "expensive"}:
            errors.append(
                CliCoverageLintError(
                    code="CLI_WRITE_SAFETY_INVALID",
                    message="Write-команда должна иметь write/destructive/expensive safety.",
                    item=record.command_id,
                )
            )
    for exclusion in write_exclusions:
        if exclusion.status == "temporary" and not exclusion.target_stage:
            errors.append(
                CliCoverageLintError(
                    code="CLI_WRITE_EXCLUSION_TARGET_STAGE_MISSING",
                    message="Temporary write exclusion должен содержать target_stage.",
                    item=exclusion.exclusion_id,
                )
            )
    return tuple(errors)


def _lint_strict_phase(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    for exclusion in registry.exclusions:
        if exclusion.status == "temporary":
            errors.append(
                CliCoverageLintError(
                    code="CLI_TEMPORARY_EXCLUSION_EXPIRED",
                    message="Strict mode не допускает temporary exclusions.",
                    item=exclusion.exclusion_id,
                )
            )
        if exclusion.category == "api" and exclusion.status != "intentional":
            errors.append(
                CliCoverageLintError(
                    code="CLI_API_EXCLUSION_NOT_INTENTIONAL",
                    message="API exclusion в strict mode должен быть intentional.",
                    item=exclusion.exclusion_id,
                )
            )
    for record in registry.api_commands:
        if not record.implemented:
            errors.append(
                CliCoverageLintError(
                    code="CLI_API_COMMAND_NOT_IMPLEMENTED",
                    message="Canonical API command в strict mode должна быть реализована.",
                    item=record.command_id,
                )
            )
    errors.extend(_lint_registered_api_commands(registry))
    return tuple(errors)


def _lint_helper_phase(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    helper_exclusion_methods = {
        exclusion.sdk_method
        for exclusion in registry.exclusions
        if exclusion.category == "helper" and exclusion.sdk_method is not None
    }
    errors: list[CliCoverageLintError] = []
    for record in registry.helper_commands:
        if not record.implemented:
            errors.append(
                CliCoverageLintError(
                    code="CLI_HELPER_COMMAND_NOT_IMPLEMENTED",
                    message="Helper workflow должен иметь CLI-команду или exclusion.",
                    item=record.command_id,
                )
            )
        if record.sdk_method in helper_exclusion_methods:
            errors.append(
                CliCoverageLintError(
                    code="CLI_HELPER_DUPLICATE_POLICY",
                    message="Helper workflow одновременно реализован и исключен.",
                    item=record.command_id,
                )
            )
    errors.extend(_lint_registered_helper_commands(registry))
    return tuple(errors)


def _lint_registered_api_commands(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    root_context = click.Context(app)
    errors: list[CliCoverageLintError] = []
    for record in registry.api_commands:
        group = app.get_command(root_context, record.resource)
        if not isinstance(group, click.Group):
            errors.append(
                CliCoverageLintError(
                    code="CLI_API_RESOURCE_NOT_REGISTERED",
                    message="Resource group canonical API command не зарегистрирован.",
                    item=record.command_id,
                )
            )
            continue
        action = group.get_command(root_context, record.action)
        if action is None:
            errors.append(
                CliCoverageLintError(
                    code="CLI_API_ACTION_NOT_REGISTERED",
                    message="Action canonical API command не зарегистрирован.",
                    item=record.command_id,
                )
            )
    return tuple(errors)


def _lint_registered_helper_commands(registry: CliRegistry) -> tuple[CliCoverageLintError, ...]:
    root_context = click.Context(app)
    errors: list[CliCoverageLintError] = []
    for record in registry.helper_commands:
        group = app.get_command(root_context, record.resource)
        if not isinstance(group, click.Group):
            errors.append(
                CliCoverageLintError(
                    code="CLI_HELPER_RESOURCE_NOT_REGISTERED",
                    message="Resource group helper-команды не зарегистрирован.",
                    item=record.command_id,
                )
            )
            continue
        action = group.get_command(root_context, record.action)
        if action is None:
            errors.append(
                CliCoverageLintError(
                    code="CLI_HELPER_ACTION_NOT_REGISTERED",
                    message="Action helper-команды не зарегистрирован.",
                    item=record.command_id,
                )
            )
    return tuple(errors)


def _resource_to_factory(command_id: str) -> str:
    resource = command_id.split(".", maxsplit=1)[0]
    return resource.replace("-", "_")


def _expand_write_domains(domains: Sequence[str]) -> frozenset[str]:
    expanded: set[str] = set()
    for domain in domains:
        normalized = domain.replace("_", "-").lower()
        wave = _WRITE_WAVES.get(normalized)
        if wave is None:
            expanded.add(domain.replace("-", "_"))
            continue
        expanded.update(wave)
    return frozenset(expanded)


def _lint_adapters(
    registry: CliRegistry,
    adapter_registry: CommandAdapterRegistry,
) -> tuple[CliCoverageLintError, ...]:
    errors: list[CliCoverageLintError] = []
    known_adapter_ids = adapter_registry.ids()
    used_adapter_ids: set[str] = set()

    metadata_counts = Counter(adapter.adapter_id for adapter in adapter_registry.adapters)
    for adapter in adapter_registry.adapters:
        if metadata_counts[adapter.adapter_id] > 1:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ADAPTER_DUPLICATE",
                    message="Adapter id повторяется.",
                    item=adapter.adapter_id,
                )
            )
        if not adapter.metadata.owner:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ADAPTER_OWNER_MISSING",
                    message="Adapter metadata должен содержать owner.",
                    item=adapter.adapter_id,
                )
            )
        if not adapter.metadata.reason:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ADAPTER_REASON_MISSING",
                    message="Adapter metadata должен содержать reason.",
                    item=adapter.adapter_id,
                )
            )

    for record in _canonical_records(registry):
        if isinstance(record, LocalCommandRecord):
            continue
        adapter_id = record.adapter_id
        if adapter_id is None:
            continue
        used_adapter_ids.add(adapter_id)
        if adapter_id not in known_adapter_ids:
            errors.append(
                CliCoverageLintError(
                    code="CLI_ADAPTER_UNKNOWN",
                    message=f"Adapter id `{adapter_id}` отсутствует в explicit adapter registry.",
                    item=record.command_id,
                )
            )
    for adapter_id in sorted(known_adapter_ids - used_adapter_ids):
        errors.append(
            CliCoverageLintError(
                code="CLI_ADAPTER_UNUSED",
                message="Adapter id зарегистрирован, но не используется ни одной командой.",
                item=adapter_id,
            )
        )
    return tuple(errors)


def _canonical_records(registry: CliRegistry) -> tuple[CommandRecord, ...]:
    records: list[CommandRecord] = []
    records.extend(registry.api_commands)
    records.extend(registry.helper_commands)
    records.extend(registry.local_commands)
    return tuple(records)


if __name__ == "__main__":
    raise SystemExit(main())
