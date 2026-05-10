"""Метаданные команд CLI, построенные из публичных SDK bindings."""

from __future__ import annotations

import importlib
import inspect
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from avito.cli.safety import CommandSafetyPolicy
from avito.cli.schemas import (
    CliParameterSchema,
    CliValueKind,
    build_parameter_schemas,
)
from avito.core.swagger_discovery import (
    DiscoveredSwaggerBinding,
    SwaggerBindingDiscovery,
    discover_swagger_bindings,
)
from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry, load_swagger_registry

CommandCategory = Literal["api", "helper", "local"]
ExclusionCategory = Literal["api", "helper", "execution_smoke"]
ExclusionStatus = Literal["intentional", "temporary"]
OutputHint = Literal["object", "collection", "mutation", "plain", "unknown"]
SafetyKind = Literal["read", "write", "destructive", "expensive", "local"]

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_IMPLEMENTED_API_COMMAND_IDS = frozenset({"account.get-balance", "account.get-self"})
_READ_METHODS = frozenset({"GET", "HEAD"})
_TEMPORARY_WRITE_EXCLUSION_COMMAND_IDS = frozenset(
    {
        "application.update",
        "autostrategy-campaign.get-stat",
        "bbip-promotion.create-order",
        "bbip-promotion.get-forecasts",
        "bbip-promotion.get-suggests",
        "call-tracking-call.get",
        "chat-media.upload-images",
        "cpa-auction.create-item-bids",
        "promotion-order.get-order-status",
        "realty-analytics-report.get-report-for-classified",
        "realty-listing.get-intervals",
        "realty-pricing.update-realty-prices",
        "sandbox-delivery.add-areas",
        "sandbox-delivery.add-sorting-center",
        "sandbox-delivery.add-tags-to-sorting-center",
        "sandbox-delivery.add-tariff",
        "sandbox-delivery.add-terminals",
        "sandbox-delivery.cancel-sandbox-announcement",
        "sandbox-delivery.create-sandbox-announcement",
        "sandbox-delivery.set-order-properties",
        "sandbox-delivery.set-order-real-address",
        "sandbox-delivery.update-custom-area-schedule",
        "sandbox-delivery.update-terms",
        "stock.update",
        "target-action-pricing.delete",
        "target-action-pricing.get-promotions-by-item-ids",
        "target-action-pricing.update-auto",
        "target-action-pricing.update-manual",
        "trx-promotion.apply",
        "vacancy.update",
        "vacancy.update-auto-renewal",
    }
)
_TEMPORARY_READ_EXCLUSION_COMMAND_IDS = frozenset(
    {
        "autoteka-vehicle.get-preview",
        "autoteka-vehicle.get-specification-by-id",
        "autoteka-vehicle.get-teaser",
        "cpa-chat.get",
        "order-label.download",
        "realty-analytics-report.get-market-price-correspondence",
        "target-action-pricing.get-bids",
    }
)


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
    parameters: tuple[CliParameterSchema, ...]
    spec: str
    http_method: str
    path: str
    operation_id: str | None
    domain: str | None
    deprecated: bool
    legacy: bool
    implemented: bool
    description: str
    examples: tuple[str, ...]
    related_commands: tuple[str, ...]
    safety: SafetyKind
    safety_summary: str
    safety_policy: CommandSafetyPolicy
    output_hint: OutputHint
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
            "implemented": self.implemented,
            "description": self.description,
            "examples": list(self.examples),
            "related_commands": list(self.related_commands),
            "safety": self.safety,
            "safety_summary": self.safety_summary,
            "safety_policy": self.safety_policy.to_dict(),
            "output_hint": self.output_hint,
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
    parameters: tuple[CliParameterSchema, ...]
    implemented: bool
    description: str
    examples: tuple[str, ...]
    related_commands: tuple[str, ...]
    safety: SafetyKind
    safety_summary: str
    safety_policy: CommandSafetyPolicy
    output_hint: OutputHint
    adapter_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные helper-команды."""

        return {
            "command_id": self.command_id,
            "resource": self.resource,
            "action": self.action,
            "sdk_method_name": self.sdk_method_name,
            "sdk_method": self.sdk_method,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "implemented": self.implemented,
            "description": self.description,
            "examples": list(self.examples),
            "related_commands": list(self.related_commands),
            "safety": self.safety,
            "safety_summary": self.safety_summary,
            "safety_policy": self.safety_policy.to_dict(),
            "output_hint": self.output_hint,
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
    examples: tuple[str, ...]
    related_commands: tuple[str, ...]
    safety: SafetyKind
    safety_summary: str
    safety_policy: CommandSafetyPolicy
    output_hint: OutputHint

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимые данные локальной команды."""

        return {
            "command_id": self.command_id,
            "resource": self.resource,
            "action": self.action,
            "implemented": self.implemented,
            "description": self.description,
            "examples": list(self.examples),
            "related_commands": list(self.related_commands),
            "safety": self.safety,
            "safety_summary": self.safety_summary,
            "safety_policy": self.safety_policy.to_dict(),
            "output_hint": self.output_hint,
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

    def command_ids(self) -> frozenset[str]:
        """Вернуть множество канонических command id без alias."""

        command_ids: set[str] = set()
        for _category, record in _canonical_records(self):
            command_ids.add(record.command_id)
        return frozenset(command_ids)


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
        command_record = _build_api_command_record(binding, operation)
        if command_record.command_id in _TEMPORARY_READ_EXCLUSION_COMMAND_IDS:
            exclusions.append(_build_temporary_read_exclusion(command_record))
            continue
        if command_record.command_id in _TEMPORARY_WRITE_EXCLUSION_COMMAND_IDS:
            exclusions.append(_build_temporary_write_exclusion(command_record))
            continue
        api_commands.append(command_record)

    helper_commands, helper_exclusions = _build_helper_records()
    exclusions.extend(helper_exclusions)
    registry = CliRegistry(
        api_commands=tuple(sorted(api_commands, key=lambda record: record.command_id)),
        helper_commands=helper_commands,
        local_commands=_build_local_command_records(),
        aliases=_build_alias_records(),
        exclusions=tuple(sorted(exclusions, key=lambda record: record.exclusion_id)),
    )
    validate_cli_registry(registry)
    return registry


def _sync_bindings(
    discovery: SwaggerBindingDiscovery,
) -> tuple[DiscoveredSwaggerBinding, ...]:
    """Вернуть sync Swagger bindings с operation key."""

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
    """Найти Swagger operation для discovered binding."""

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
    """Построить canonical API command record из SDK binding."""

    if binding.operation_key is None or binding.spec is None or binding.factory is None:
        raise ValueError("API-команда требует operation_key, spec и factory.")
    resource = kebab_case(binding.factory)
    action = kebab_case(binding.method_name)
    command_id = f"{resource}.{action}"
    return ApiCommandRecord(
        command_id=command_id,
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
        implemented=True,
        description=_api_description(binding, operation),
        examples=_api_examples(resource, action, binding),
        related_commands=(),
        safety=_safety_for_method(operation.method),
        safety_summary=_safety_summary_for_method(operation.method),
        safety_policy=_api_safety_policy(binding, operation),
        output_hint=_output_hint_for_command(command_id, operation.method),
    )


def _build_parameter_records(
    binding: DiscoveredSwaggerBinding,
) -> tuple[CliParameterSchema, ...]:
    """Построить CLI parameter records из binding metadata."""

    return build_parameter_schemas(binding)


def _build_auth_token_exclusion(binding: DiscoveredSwaggerBinding) -> ExclusionRecord:
    """Построить intentional exclusion для non-domain token binding."""

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


def _build_temporary_read_exclusion(command: ApiCommandRecord) -> ExclusionRecord:
    """Построить intentional exclusion для read command без safe generic input."""

    return ExclusionRecord(
        exclusion_id=f"api.{command.operation_key}",
        category="api",
        status="intentional",
        reason=(
            "Read-only binding намеренно исключен из первого CLI release: команда требует "
            "дополнительный идентификатор доменного объекта, который не представлен в "
            "factory_args/method_args metadata."
        ),
        follow_up=(
            "Уточнить Swagger binding metadata или добавить CLI adapter, чтобы команда "
            "могла принять обязательный идентификатор без обхода публичного SDK в "
            "следующем coverage increment."
        ),
        owner="cli",
        operation_key=command.operation_key,
        sdk_method=command.sdk_method,
        command_id=command.command_id,
    )


def _build_temporary_write_exclusion(command: ApiCommandRecord) -> ExclusionRecord:
    """Построить intentional exclusion для write command без safe generic input."""

    return ExclusionRecord(
        exclusion_id=f"api.{command.operation_key}",
        category="api",
        status="intentional",
        reason=(
            "Write binding намеренно исключен из первого CLI release: команда требует "
            "CLI adapter или уточнения binding metadata, потому что "
            "generic flags не могут безопасно построить обязательный публичный input "
            "model, file/stdin payload или отсутствующий идентификатор доменного объекта."
        ),
        follow_up=(
            "Добавить typed CLI adapter или исправить factory_args/method_args metadata, "
            "затем включить команду в canonical CLI coverage."
        ),
        owner="cli",
        operation_key=command.operation_key,
        sdk_method=command.sdk_method,
        command_id=command.command_id,
    )


def _build_helper_records() -> tuple[tuple[HelperCommandRecord, ...], tuple[ExclusionRecord, ...]]:
    """Построить helper commands и helper exclusions."""

    helper_commands = (
        _helper(
            "account-health",
            "show",
            "account_health",
            "Health-сводка аккаунта.",
            parameters=(
                _helper_parameter("user_id", "integer"),
                _helper_parameter("listing_limit", "integer"),
                _helper_parameter("listing_page_size", "integer"),
                _helper_parameter("date_from", "date"),
                _helper_parameter("date_to", "date"),
            ),
        ),
        _helper(
            "listing-health",
            "show",
            "listing_health",
            "Health-сводка объявлений.",
            parameters=(
                _helper_parameter("user_id", "integer"),
                _helper_parameter("limit", "integer"),
                _helper_parameter("page_size", "integer"),
                _helper_parameter("date_from", "date"),
                _helper_parameter("date_to", "date"),
            ),
        ),
        _helper(
            "chat-summary",
            "show",
            "chat_summary",
            "Сводка сообщений.",
            parameters=(_helper_parameter("user_id", "integer"),),
        ),
        _helper("order-summary", "show", "order_summary", "Сводка заказов."),
        _helper("review-summary", "show", "review_summary", "Сводка отзывов."),
        _helper(
            "promotion-summary",
            "show",
            "promotion_summary",
            "Сводка продвижения.",
            parameters=(
                _helper_parameter(
                    "item_ids",
                    "list",
                    multiple=True,
                    item_value_kind="integer",
                ),
            ),
        ),
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
    *,
    parameters: tuple[CliParameterSchema, ...] = (),
) -> HelperCommandRecord:
    """Создать helper command record."""

    return HelperCommandRecord(
        command_id=f"{resource}.{action}",
        resource=resource,
        action=action,
        sdk_method_name=method_name,
        sdk_method=f"avito.client.AvitoClient.{method_name}",
        parameters=parameters,
        implemented=True,
        description=description,
        examples=(f"avito {resource} {action}", f"avito --json --no-input {resource} {action}"),
        related_commands=(),
        safety="read",
        safety_summary="Локальная вспомогательная команда читает данные через публичный интерфейс SDK.",
        safety_policy=CommandSafetyPolicy(
            kind="read",
            confirmation_required=False,
            dry_run_supported=False,
            review_note="Helper-команда только читает данные через публичный интерфейс SDK.",
        ),
        output_hint="object",
    )


def _helper_parameter(
    name: str,
    value_kind: CliValueKind,
    *,
    multiple: bool = False,
    item_value_kind: CliValueKind | None = None,
) -> CliParameterSchema:
    """Создать optional helper parameter schema."""

    return CliParameterSchema(
        name=name,
        source="method",
        binding_expression=f"helper.{name}",
        flag=f"--{kebab_case(name)}",
        value_kind=value_kind,
        required=False,
        multiple=multiple,
        item_value_kind=item_value_kind,
        annotation=value_kind,
    )


def _build_local_command_records() -> tuple[LocalCommandRecord, ...]:
    """Построить registry records для local CLI commands."""

    records = (
        _local("account", "add", "Добавить учетную запись.", "mutation"),
        _local("account", "list", "Показать учетные записи.", "collection"),
        _local("account", "use", "Выбрать активную учетную запись.", "mutation"),
        _local("account", "current", "Показать активную учетную запись.", "object"),
        _local("account", "delete", "Удалить учетную запись.", "mutation", safety="destructive"),
        _local("completion", "bash", "Показать подключение completion для bash.", "plain"),
        _local("completion", "fish", "Показать подключение completion для fish.", "plain"),
        _local("completion", "zsh", "Показать подключение completion для zsh.", "plain"),
        _local("config", "get", "Показать значение локальной конфигурации.", "object"),
        _local("config", "list", "Показать локальную конфигурацию.", "collection"),
        _local("config", "set", "Сохранить значение локальной конфигурации.", "mutation"),
        _local("config", "unset", "Удалить значение локальной конфигурации.", "mutation"),
        _local("doctor", "show", "Проверить локальные файлы CLI.", "object"),
        _local("status", "show", "Показать локальную готовность CLI.", "object"),
        _local("version", "show", "Показать версию.", "plain"),
        _local("help", "show", "Показать справку.", "plain"),
    )
    return tuple(sorted(records, key=lambda record: record.command_id))


def _local(
    resource: str,
    action: str,
    description: str,
    output_hint: OutputHint,
    *,
    safety: SafetyKind = "local",
) -> LocalCommandRecord:
    """Создать local command record."""

    return LocalCommandRecord(
        command_id=f"{resource}.{action}",
        resource=resource,
        action=action,
        implemented=True,
        description=description,
        examples=(f"avito {resource} {action}",),
        related_commands=(),
        safety=safety,
        safety_summary="Локальная команда не вызывает Avito API.",
        safety_policy=_local_safety_policy(safety),
        output_hint=output_hint,
    )


def _build_alias_records() -> tuple[AliasRecord, ...]:
    """Построить compatibility alias records."""

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


def validate_cli_registry(registry: CliRegistry) -> None:
    """Проверить детерминированные collision-инварианты registry."""

    _validate_canonical_collisions(registry)
    _validate_aliases(registry)


def _validate_canonical_collisions(registry: CliRegistry) -> None:
    """Проверить отсутствие duplicate canonical resource/action."""

    seen: dict[tuple[str, str], str] = {}
    for category, record in _canonical_records(registry):
        key = (record.resource, record.action)
        existing = seen.get(key)
        if existing is not None:
            raise ValueError(
                "CLI registry содержит конфликт команд "
                f"{record.resource} {record.action}: {existing} и {category}:{record.command_id}"
            )
        seen[key] = f"{category}:{record.command_id}"


def _validate_aliases(registry: CliRegistry) -> None:
    """Проверить target и collision policy для aliases."""

    command_ids = registry.command_ids()
    canonical_keys = {
        (record.resource, record.action)
        for _category, record in _canonical_records(registry)
    }
    seen_alias_keys: dict[tuple[str, str], str] = {}
    for alias in registry.aliases:
        key = (alias.resource, alias.action)
        if alias.target_command_id not in command_ids:
            raise ValueError(
                f"CLI alias {alias.alias_id} ссылается на неизвестную команду "
                f"{alias.target_command_id}."
            )
        if key in canonical_keys:
            raise ValueError(
                f"CLI alias {alias.alias_id} конфликтует с canonical command "
                f"{alias.resource} {alias.action}."
            )
        existing = seen_alias_keys.get(key)
        if existing is not None:
            raise ValueError(
                f"CLI alias {alias.alias_id} конфликтует с alias {existing} "
                f"для {alias.resource} {alias.action}."
            )
        seen_alias_keys[key] = alias.alias_id


def _canonical_records(
    registry: CliRegistry,
) -> tuple[
    tuple[CommandCategory, ApiCommandRecord | HelperCommandRecord | LocalCommandRecord],
    ...,
]:
    """Вернуть все canonical records с category labels."""

    records: list[
        tuple[CommandCategory, ApiCommandRecord | HelperCommandRecord | LocalCommandRecord]
    ] = []
    records.extend(("api", record) for record in registry.api_commands)
    records.extend(("helper", record) for record in registry.helper_commands)
    records.extend(("local", record) for record in registry.local_commands)
    return tuple(records)


def _api_description(binding: DiscoveredSwaggerBinding, operation: SwaggerOperation) -> str:
    """Сформировать русское описание API command."""

    if binding.deprecated or operation.deprecated:
        return (
            "Устаревшая операция Avito API; политика CLI должна сохранять "
            "совместимость или явно исключать команду."
        )
    if binding.legacy:
        return (
            "Совместимая операция Avito API; политика CLI должна сохранять "
            "канонический путь или явно исключать команду."
        )
    if operation.operation_id is not None:
        return f"Вызвать операцию Avito API `{operation.operation_id}` через публичный SDK."
    return f"Вызвать SDK-метод {binding.sdk_method}."


def _api_examples(
    resource: str,
    action: str,
    binding: DiscoveredSwaggerBinding,
) -> tuple[str, ...]:
    """Сформировать базовые examples для API command."""

    flags = tuple(
        f"--{kebab_case(name)} <value>"
        for name in (*sorted(binding.factory_args), *sorted(binding.method_args))
    )
    command = " ".join(("avito", resource, action, *flags))
    return (command, f"avito --json --no-input {resource} {action}")


def _safety_for_method(method: str) -> SafetyKind:
    """Классифицировать safety kind по HTTP method."""

    if method in _READ_METHODS:
        return "read"
    if method == "DELETE":
        return "destructive"
    return "write"


def _safety_summary_for_method(method: str) -> str:
    """Вернуть русскую safety-сводку для HTTP method."""

    if method in _READ_METHODS:
        return "Команда только читает данные Avito API."
    if method == "DELETE":
        return "Команда удаляет или отменяет данные в Avito API и требует подтверждения."
    return "Команда может изменить состояние или запустить действие в Avito API."


def _api_safety_policy(
    binding: DiscoveredSwaggerBinding,
    operation: SwaggerOperation,
) -> CommandSafetyPolicy:
    """Построить reviewed safety policy для API command."""

    kind = _safety_for_method(operation.method)
    if kind == "read":
        return CommandSafetyPolicy(
            kind="read",
            confirmation_required=False,
            dry_run_supported=False,
            review_note="GET/HEAD operation проверена как read-only команда.",
        )
    return CommandSafetyPolicy(
        kind=kind,
        confirmation_required=kind in {"destructive", "expensive"},
        dry_run_supported=_sdk_method_accepts(binding, "dry_run"),
        review_note=(
            "Write operation получает явную CLI safety metadata перед публикацией; "
            "HTTP method используется только как исходная классификация."
        ),
    )


def _local_safety_policy(kind: SafetyKind) -> CommandSafetyPolicy:
    """Построить safety policy для local CLI command."""

    return CommandSafetyPolicy(
        kind=kind,
        confirmation_required=kind in {"destructive", "expensive"},
        dry_run_supported=False,
        review_note="Локальная CLI-команда проверена отдельно от Swagger coverage.",
    )


def _sdk_method_accepts(binding: DiscoveredSwaggerBinding, parameter_name: str) -> bool:
    """Проверить наличие параметра в публичном SDK method."""

    module = importlib.import_module(binding.module)
    domain_class = getattr(module, binding.class_name)
    method = getattr(domain_class, binding.method_name)
    return parameter_name in inspect.signature(method).parameters


def _output_hint_for_command(command_id: str, method: str) -> OutputHint:
    """Определить output hint для command record."""

    if command_id in _IMPLEMENTED_API_COMMAND_IDS:
        return "object"
    if method not in _READ_METHODS:
        return "mutation"
    return "unknown"


__all__ = (
    "AliasRecord",
    "ApiCommandRecord",
    "CliParameterSchema",
    "CliRegistry",
    "ExclusionRecord",
    "HelperCommandRecord",
    "LocalCommandRecord",
    "OutputHint",
    "SafetyKind",
    "build_cli_registry",
    "kebab_case",
    "validate_cli_registry",
)
