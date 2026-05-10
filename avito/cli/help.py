"""Registry-backed справка CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from avito.cli.registry import (
    AliasRecord,
    ApiCommandRecord,
    CliRegistry,
    HelperCommandRecord,
    LocalCommandRecord,
    OutputHint,
    build_cli_registry,
)

RegistryCommandRecord = ApiCommandRecord | HelperCommandRecord | LocalCommandRecord


@dataclass(frozen=True, slots=True)
class RegistryHelpRenderer:
    """Рендерит справку из registry без создания AvitoClient."""

    registry: CliRegistry

    def render(self, topic: tuple[str, ...]) -> str | None:
        """Вернуть registry-backed справку или None, если topic не найден."""

        if len(topic) == 1:
            return self.render_resource(topic[0])
        if len(topic) == 2:
            return self.render_action(topic[0], topic[1])
        return None

    def render_resource(self, resource: str) -> str | None:
        """Вернуть справку по resource."""

        commands = self._commands_for_resource(resource)
        aliases = self._aliases_for_resource(resource)
        if not commands and not aliases:
            return None

        lines = [
            f"Справка: avito {resource}",
            "",
            "Использование:",
            f"  avito {resource} <action> [flags]",
            "",
            "Команды:",
        ]
        lines.extend(_format_command_line(record) for record in commands)
        if aliases:
            lines.append("")
            lines.append("Совместимые команды:")
            lines.extend(_format_alias_line(alias) for alias in aliases)
        return "\n".join(lines)

    def render_action(self, resource: str, action: str) -> str | None:
        """Вернуть справку по конкретному resource/action."""

        command = self._command_for_action(resource, action)
        if command is not None:
            return _render_command_help(command)

        alias = self._alias_for_action(resource, action)
        if alias is not None:
            return _render_alias_help(alias)
        return None

    def _commands_for_resource(self, resource: str) -> tuple[RegistryCommandRecord, ...]:
        records: list[RegistryCommandRecord] = []
        records.extend(
            record for record in self.registry.api_commands if record.resource == resource
        )
        records.extend(
            record for record in self.registry.helper_commands if record.resource == resource
        )
        records.extend(
            record for record in self.registry.local_commands if record.resource == resource
        )
        return tuple(sorted(records, key=lambda record: record.action))

    def _aliases_for_resource(self, resource: str) -> tuple[AliasRecord, ...]:
        aliases = tuple(alias for alias in self.registry.aliases if alias.resource == resource)
        return tuple(sorted(aliases, key=lambda alias: alias.action))

    def _command_for_action(self, resource: str, action: str) -> RegistryCommandRecord | None:
        matches = [
            record
            for record in self._commands_for_resource(resource)
            if record.action == action
        ]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Registry содержит несколько команд для avito {resource} {action}.")
        return matches[0]

    def _alias_for_action(self, resource: str, action: str) -> AliasRecord | None:
        matches = [
            alias
            for alias in self._aliases_for_resource(resource)
            if alias.action == action
        ]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Registry содержит несколько alias для avito {resource} {action}.")
        return matches[0]


def render_registry_help(
    topic: tuple[str, ...],
    *,
    registry: CliRegistry | None = None,
) -> str | None:
    """Вернуть registry-backed справку для `avito help ...`."""

    resolved_registry = registry or build_cli_registry()
    return RegistryHelpRenderer(resolved_registry).render(topic)


def _format_command_line(record: RegistryCommandRecord) -> str:
    status = "готова" if record.implemented else "запланирована"
    return f"  {record.action:<24} {record.description} ({status})"


def _format_alias_line(alias: AliasRecord) -> str:
    return f"  {alias.action:<24} совместимое имя для {alias.target_command_id}: {alias.reason}"


def _render_command_help(record: RegistryCommandRecord) -> str:
    lines = [
        f"Справка: avito {record.resource} {record.action}",
        "",
        record.description,
        "",
        "Использование:",
        f"  avito {record.resource} {record.action} [flags]",
        "",
        f"Безопасность: {record.safety_summary}",
        f"Вывод: {_format_output_hint(record.output_hint)}",
    ]
    parameters = _parameter_lines(record)
    if parameters:
        lines.append("")
        lines.append("Флаги:")
        lines.extend(parameters)
    if not record.implemented:
        lines.append("")
        lines.append("Статус: команда описана в реестре, исполнение будет подключено позже.")
    if record.examples:
        lines.append("")
        lines.append("Примеры:")
        lines.extend(f"  {example}" for example in record.examples)
    if record.related_commands:
        lines.append("")
        lines.append("Связанные команды:")
        lines.extend(f"  {command_id}" for command_id in record.related_commands)
    return "\n".join(lines)


def _render_alias_help(alias: AliasRecord) -> str:
    target_resource, target_action = alias.target_command_id.split(".", maxsplit=1)
    return "\n".join(
        (
            f"Справка: avito {alias.resource} {alias.action}",
            "",
            f"Совместимое имя для `avito {target_resource} {target_action}`.",
            alias.reason,
            "",
            "Использование:",
            f"  avito {alias.resource} {alias.action} [flags]",
        )
    )


def _parameter_lines(record: RegistryCommandRecord) -> tuple[str, ...]:
    if not isinstance(record, ApiCommandRecord):
        return ()
    return tuple(
        f"  {parameter.flag:<24} {_format_parameter_source(parameter.source)}: "
        f"{parameter.binding_expression}"
        for parameter in record.parameters
    )


def _format_output_hint(output_hint: OutputHint) -> str:
    labels: dict[OutputHint, str] = {
        "object": "объект",
        "collection": "коллекция",
        "mutation": "изменение",
        "plain": "простое значение",
        "unknown": "будет уточнен при подключении исполнения",
    }
    return labels[output_hint]


def _format_parameter_source(source: Literal["factory", "method"]) -> str:
    labels: dict[Literal["factory", "method"], str] = {
        "factory": "аргумент ресурса",
        "method": "аргумент действия",
    }
    return labels[source]


__all__ = ("RegistryHelpRenderer", "render_registry_help")
