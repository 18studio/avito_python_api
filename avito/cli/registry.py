"""Метаданные команд CLI, построенные из публичных SDK bindings."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from avito.core.swagger_discovery import (
    DiscoveredSwaggerBinding,
    SwaggerBindingDiscovery,
    discover_swagger_bindings,
)
from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry, load_swagger_registry

CommandCategory = Literal["api", "helper", "local"]
ExclusionCategory = Literal["api", "helper", "execution_smoke"]
ExclusionStatus = Literal["intentional", "temporary"]

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class CliParameterRecord:
    """Аргумент будущей CLI-команды, выбранный из binding metadata."""

    name: str
    source: Literal["factory", "method"]
    binding_expression: str
    flag: str

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные аргумента."""

        return {
            "name": self.name,
            "source": self.source,
            "binding_expression": self.binding_expression,
            "flag": self.flag,
        }


@dataclass(frozen=True, slots=True)
class ApiCommandRecord:
    """Кандидат канонической API-команды из sync Swagger binding."""

    command_id: str
    resource: str
    action: str
    operation_key: str
    sdk_module: str
    sdk_class: str
    sdk_method_name: str
    sdk_method: str
    factory: str
    factory_args: Mapping[str, str]
    method_args: Mapping[str, str]
    parameters: tuple[CliParameterRecord, ...]
    spec: str
    http_method: str
    path: str
    operation_id: str | None
    domain: str | None
    deprecated: bool
    legacy: bool
    adapter_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные API-команды."""

        return {
            "command_id": self.command_id,
            "resource": self.resource,
            "action": self.action,
            "operation_key": self.operation_key,
            "sdk_module": self.sdk_module,
            "sdk_class": self.sdk_class,
            "sdk_method_name": self.sdk_method_name,
            "sdk_method": self.sdk_method,
            "factory": self.factory,
            "factory_args": dict(sorted(self.factory_args.items())),
            "method_args": dict(sorted(self.method_args.items())),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "spec": self.spec,
            "http_method": self.http_method,
            "path": self.path,
            "operation_id": self.operation_id,
            "domain": self.domain,
            "deprecated": self.deprecated,
            "legacy": self.legacy,
            "adapter_id": self.adapter_id,
        }


@dataclass(frozen=True, slots=True)
class HelperCommandRecord:
    """Кандидат команды для публичного non-Swagger helper workflow."""

    command_id: str
    resource: str
    action: str
    sdk_method_name: str
    sdk_method: str
    implemented: bool
    description: str
    adapter_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные helper-команды."""

        return {
            "command_id": self.command_id,
            "resource": self.resource,
            "action": self.action,
            "sdk_method_name": self.sdk_method_name,
            "sdk_method": self.sdk_method,
            "implemented": self.implemented,
            "description": self.description,
            "adapter_id": self.adapter_id,
        }


@dataclass(frozen=True, slots=True)
class LocalCommandRecord:
    """Локальная CLI-команда, не привязанная к Swagger operation."""

    command_id: str
    resource: str
    action: str
    implemented: bool
    description: str

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные локальной команды."""

        return {
            "command_id": self.command_id,
            "resource": self.resource,
            "action": self.action,
            "implemented": self.implemented,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class AliasRecord:
    """Совместимый alias, который не считается канонической командой."""

    alias_id: str
    resource: str
    action: str
    target_command_id: str
    implemented: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные alias."""

        return {
            "alias_id": self.alias_id,
            "resource": self.resource,
            "action": self.action,
            "target_command_id": self.target_command_id,
            "implemented": self.implemented,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    """Документированное исключение из покрытия CLI."""

    exclusion_id: str
    category: ExclusionCategory
    status: ExclusionStatus
    reason: str
    follow_up: str
    owner: str
    operation_key: str | None = None
    sdk_method: str | None = None
    command_id: str | None = None
    target_stage: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные исключения."""

        return {
            "exclusion_id": self.exclusion_id,
            "category": self.category,
            "status": self.status,
            "reason": self.reason,
            "follow_up": self.follow_up,
            "owner": self.owner,
            "operation_key": self.operation_key,
            "sdk_method": self.sdk_method,
            "command_id": self.command_id,
            "target_stage": self.target_stage,
        }


@dataclass(frozen=True, slots=True)
class CliRegistry:
    """Детерминированный registry будущих CLI-команд."""

    api_commands: tuple[ApiCommandRecord, ...]
    helper_commands: tuple[HelperCommandRecord, ...]
    local_commands: tuple[LocalCommandRecord, ...]
    aliases: tuple[AliasRecord, ...]
    exclusions: tuple[ExclusionRecord, ...]

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимый report registry."""

        api_exclusions = tuple(
            exclusion for exclusion in self.exclusions if exclusion.category == "api"
        )
        helper_exclusions = tuple(
            exclusion for exclusion in self.exclusions if exclusion.category == "helper"
        )
        execution_exclusions = tuple(
            exclusion for exclusion in self.exclusions if exclusion.category == "execution_smoke"
        )
        return {
            "summary": {
                "api_command_candidates": len(self.api_commands),
                "api_exclusions": len(api_exclusions),
                "helper_command_candidates": len(self.helper_commands),
                "helper_exclusions": len(helper_exclusions),
                "local_commands": len(self.local_commands),
                "aliases": len(self.aliases),
                "execution_smoke_exclusions": len(execution_exclusions),
            },
            "api_commands": [record.to_dict() for record in self.api_commands],
            "helper_commands": [record.to_dict() for record in self.helper_commands],
            "local_commands": [record.to_dict() for record in self.local_commands],
            "aliases": [record.to_dict() for record in self.aliases],
            "exclusions": [record.to_dict() for record in self.exclusions],
        }


def build_cli_registry(
    *,
    swagger_registry: SwaggerRegistry | None = None,
    discovery: SwaggerBindingDiscovery | None = None,
) -> CliRegistry:
    """Построить registry без создания `AvitoClient` и без сетевых вызовов."""

    resolved_swagger_registry = swagger_registry or load_swagger_registry()
    resolved_discovery = discovery or discover_swagger_bindings(registry=resolved_swagger_registry)
    operations_by_key = {
        operation.key: operation for operation in resolved_swagger_registry.operations
    }
    api_commands: list[ApiCommandRecord] = []
    exclusions: list[ExclusionRecord] = []

    for binding in _sync_bindings(resolved_discovery):
        operation = _operation_for_binding(binding, operations_by_key)
        if binding.factory is None:
            exclusions.append(_build_auth_token_exclusion(binding))
            continue
        api_commands.append(_build_api_command_record(binding, operation))

    helper_commands, helper_exclusions = _build_helper_records()
    exclusions.extend(helper_exclusions)
    return CliRegistry(
        api_commands=tuple(sorted(api_commands, key=lambda record: record.command_id)),
        helper_commands=helper_commands,
        local_commands=_build_local_command_records(),
        aliases=_build_alias_records(),
        exclusions=tuple(sorted(exclusions, key=lambda record: record.exclusion_id)),
    )


def _sync_bindings(
    discovery: SwaggerBindingDiscovery,
) -> tuple[DiscoveredSwaggerBinding, ...]:
    return tuple(
        sorted(
            (
                binding
                for binding in discovery.bindings
                if binding.variant == "sync" and binding.operation_key is not None
            ),
            key=lambda binding: binding.operation_key or "",
        )
    )


def _operation_for_binding(
    binding: DiscoveredSwaggerBinding,
    operations_by_key: Mapping[str, SwaggerOperation],
) -> SwaggerOperation:
    if binding.operation_key is None:
        raise ValueError("Swagger binding без operation_key не может стать API-командой.")
    operation = operations_by_key.get(binding.operation_key)
    if operation is None:
        raise ValueError(f"Swagger operation не найдена: {binding.operation_key}")
    return operation


def _build_api_command_record(
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
) -> ApiCommandRecord:
    if binding.operation_key is None or binding.spec is None or binding.factory is None:
        raise ValueError("API-команда требует operation_key, spec и factory.")
    resource = kebab_case(binding.factory)
    action = kebab_case(binding.method_name)
    return ApiCommandRecord(
        command_id=f"{resource}.{action}",
        resource=resource,
        action=action,
        operation_key=binding.operation_key,
        sdk_module=binding.module,
        sdk_class=binding.class_name,
        sdk_method_name=binding.method_name,
        sdk_method=binding.sdk_method,
        factory=binding.factory,
        factory_args=dict(sorted(binding.factory_args.items())),
        method_args=dict(sorted(binding.method_args.items())),
        parameters=_build_parameter_records(binding),
        spec=binding.spec,
        http_method=operation.method,
        path=operation.path,
        operation_id=operation.operation_id,
        domain=binding.domain,
        deprecated=binding.deprecated or operation.deprecated,
        legacy=binding.legacy,
    )


def _build_parameter_records(
    binding: DiscoveredSwaggerBinding,
) -> tuple[CliParameterRecord, ...]:
    records: list[CliParameterRecord] = []
    for name, expression in sorted(binding.factory_args.items()):
        records.append(_build_parameter_record(name, "factory", expression))
    for name, expression in sorted(binding.method_args.items()):
        records.append(_build_parameter_record(name, "method", expression))
    return tuple(records)


def _build_parameter_record(
    name: str,
    source: Literal["factory", "method"],
    expression: str,
) -> CliParameterRecord:
    return CliParameterRecord(
        name=name,
        source=source,
        binding_expression=expression,
        flag=f"--{kebab_case(name)}",
    )


def _build_auth_token_exclusion(binding: DiscoveredSwaggerBinding) -> ExclusionRecord:
    return ExclusionRecord(
        exclusion_id=f"api.{binding.operation_key}",
        category="api",
        status="intentional",
        reason="Token-client binding не имеет публичной AvitoClient factory в первом CLI release.",
        follow_up="Проектировать отдельный публичный token facade перед добавлением CLI-команды.",
        owner="cli",
        operation_key=binding.operation_key,
        sdk_method=binding.sdk_method,
    )


def _build_helper_records() -> tuple[tuple[HelperCommandRecord, ...], tuple[ExclusionRecord, ...]]:
    helper_commands = (
        _helper("account-health", "show", "account_health", "Health-сводка аккаунта."),
        _helper("listing-health", "show", "listing_health", "Health-сводка объявлений."),
        _helper("chat-summary", "show", "chat_summary", "Сводка сообщений."),
        _helper("order-summary", "show", "order_summary", "Сводка заказов."),
        _helper("review-summary", "show", "review_summary", "Сводка отзывов."),
        _helper("promotion-summary", "show", "promotion_summary", "Сводка продвижения."),
        _helper("capabilities", "show", "capabilities", "Список возможностей SDK."),
    )
    exclusions = (
        ExclusionRecord(
            exclusion_id="helper.business-summary",
            category="helper",
            status="intentional",
            reason="business_summary является compatibility wrapper для account_health.",
            follow_up="Использовать canonical helper account_health; alias возможен только отдельно.",
            owner="cli",
            sdk_method="avito.client.AvitoClient.business_summary",
            command_id="business-summary.show",
        ),
    )
    return helper_commands, exclusions


def _helper(
    resource: str,
    action: str,
    method_name: str,
    description: str,
) -> HelperCommandRecord:
    return HelperCommandRecord(
        command_id=f"{resource}.{action}",
        resource=resource,
        action=action,
        sdk_method_name=method_name,
        sdk_method=f"avito.client.AvitoClient.{method_name}",
        implemented=False,
        description=description,
    )


def _build_local_command_records() -> tuple[LocalCommandRecord, ...]:
    records = (
        LocalCommandRecord("account.add", "account", "add", True, "Добавить учетную запись."),
        LocalCommandRecord("account.list", "account", "list", True, "Показать учетные записи."),
        LocalCommandRecord("account.use", "account", "use", True, "Выбрать активную учетную запись."),
        LocalCommandRecord("account.current", "account", "current", True, "Показать активную учетную запись."),
        LocalCommandRecord("account.delete", "account", "delete", True, "Удалить учетную запись."),
        LocalCommandRecord("version.show", "version", "show", True, "Показать версию."),
        LocalCommandRecord("help.show", "help", "show", True, "Показать справку."),
    )
    return tuple(sorted(records, key=lambda record: record.command_id))


def _build_alias_records() -> tuple[AliasRecord, ...]:
    records = (
        AliasRecord(
            alias_id="account.remove",
            resource="account",
            action="remove",
            target_command_id="account.delete",
            implemented=True,
            reason="Совместимое имя для account delete.",
        ),
    )
    return tuple(sorted(records, key=lambda record: record.alias_id))


def kebab_case(value: str) -> str:
    """Преобразовать имя SDK в lowercase kebab-case."""

    normalized = _NON_ALNUM_RE.sub("-", value.replace("_", "-").lower()).strip("-")
    if not normalized or _KEBAB_RE.fullmatch(normalized) is None:
        raise ValueError(f"Невозможно построить kebab-case имя: {value}")
    return normalized


__all__ = (
    "AliasRecord",
    "ApiCommandRecord",
    "CliParameterRecord",
    "CliRegistry",
    "ExclusionRecord",
    "HelperCommandRecord",
    "LocalCommandRecord",
    "build_cli_registry",
    "kebab_case",
)
