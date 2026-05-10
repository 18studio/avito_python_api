"""Typed extension point for non-generic CLI command input handling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from avito.cli.context import CliContext
from avito.cli.errors import CliError, CliSdkMethodError, CliValidationError
from avito.cli.registry import ApiCommandRecord
from avito.config import AvitoSettings


class ClientContext(Protocol):
    """Context manager that yields a public SDK client object."""

    def __enter__(self) -> object:
        """Enter SDK client context."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit SDK client context."""


class ClientFactory(Protocol):
    """Factory used by adapters to build public SDK clients."""

    def __call__(self, settings: AvitoSettings) -> ClientContext:
        """Build a context-managed SDK client."""


class CommandInvocationEngine(Protocol):
    """Shared engine that invokes a command through `AvitoClient` public methods."""

    def __call__(
        self,
        ctx: CliContext,
        command: ApiCommandRecord,
        raw_values: Mapping[str, Sequence[str]],
        *,
        client_factory: ClientFactory | None = None,
    ) -> object:
        """Invoke a command after adapter-owned CLI input normalization."""


class CommandAdapter(Protocol):
    """Adapter for CLI-only concerns before the shared SDK invocation path.

    Implementations may normalize stdin, file paths, multipart-friendly CLI
    values, binary rendering options, or public input models. They must delegate
    the actual Avito API call to the supplied invocation engine or call
    `AvitoClient` factories and public domain methods directly.
    """

    def invoke(
        self,
        ctx: CliContext,
        command: ApiCommandRecord,
        raw_values: Mapping[str, Sequence[str]],
        *,
        engine: CommandInvocationEngine,
        client_factory: ClientFactory | None = None,
    ) -> object:
        """Invoke adapter-backed command."""


@dataclass(frozen=True, slots=True)
class AdapterMetadata:
    """Stable serializable metadata for a command adapter."""

    adapter_id: str
    owner: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible adapter metadata."""

        return {
            "adapter_id": self.adapter_id,
            "owner": self.owner,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RegisteredCommandAdapter:
    """A command adapter paired with stable metadata."""

    metadata: AdapterMetadata
    adapter: CommandAdapter

    @property
    def adapter_id(self) -> str:
        """Return stable adapter id."""

        return self.metadata.adapter_id


@dataclass(frozen=True, slots=True)
class CommandAdapterRegistry:
    """Explicit registry of CLI command adapters."""

    adapters: tuple[RegisteredCommandAdapter, ...]

    def get(self, adapter_id: str) -> RegisteredCommandAdapter | None:
        """Return registered adapter by id."""

        for adapter in self.adapters:
            if adapter.adapter_id == adapter_id:
                return adapter
        return None

    def ids(self) -> frozenset[str]:
        """Return registered adapter ids."""

        return frozenset(adapter.adapter_id for adapter in self.adapters)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible adapter registry metadata."""

        return {
            "adapters": [
                adapter.metadata.to_dict()
                for adapter in sorted(self.adapters, key=lambda item: item.adapter_id)
            ],
        }


def build_command_adapter_registry(
    adapters: Sequence[RegisteredCommandAdapter],
) -> CommandAdapterRegistry:
    """Build and validate a deterministic adapter registry."""

    registry = CommandAdapterRegistry(tuple(sorted(adapters, key=lambda item: item.adapter_id)))
    validate_command_adapter_registry(registry)
    return registry


def validate_command_adapter_registry(registry: CommandAdapterRegistry) -> None:
    """Validate adapter ids and required owner/reason metadata."""

    seen: set[str] = set()
    for adapter in registry.adapters:
        adapter_id = adapter.adapter_id
        if adapter_id in seen:
            raise ValueError(f"CLI adapter id повторяется: {adapter_id}")
        seen.add(adapter_id)
        if not adapter.metadata.owner:
            raise ValueError(f"CLI adapter {adapter_id} должен содержать owner.")
        if not adapter.metadata.reason:
            raise ValueError(f"CLI adapter {adapter_id} должен содержать reason.")


def get_command_adapter_registry() -> CommandAdapterRegistry:
    """Return production adapter registry.

    Stage 6B intentionally registers no production adapters yet. Later command
    waves can add concrete adapters here with stable ids and owner/reason notes.
    """

    return build_command_adapter_registry(())


def invoke_adapter_command(
    registry: CommandAdapterRegistry,
    ctx: CliContext,
    command: ApiCommandRecord,
    raw_values: Mapping[str, Sequence[str]],
    *,
    engine: CommandInvocationEngine,
    client_factory: ClientFactory | None = None,
) -> object:
    """Invoke an adapter-backed command with sanitized adapter errors."""

    if command.adapter_id is None:
        return engine(ctx, command, raw_values, client_factory=client_factory)

    registered_adapter = registry.get(command.adapter_id)
    if registered_adapter is None:
        raise CliSdkMethodError(
            "CLI adapter для команды не найден.",
            details={"adapter_id": command.adapter_id, "command_id": command.command_id},
        )
    try:
        return registered_adapter.adapter.invoke(
            ctx,
            command,
            raw_values,
            engine=engine,
            client_factory=client_factory,
        )
    except CliError:
        raise
    except (OSError, ValueError) as exc:
        raise CliValidationError(
            "Не удалось обработать входные данные CLI adapter.",
            details={
                "adapter_id": command.adapter_id,
                "command_id": command.command_id,
                "error_type": type(exc).__name__,
            },
        ) from exc


__all__ = (
    "AdapterMetadata",
    "ClientFactory",
    "CommandAdapter",
    "CommandAdapterRegistry",
    "CommandInvocationEngine",
    "RegisteredCommandAdapter",
    "build_command_adapter_registry",
    "get_command_adapter_registry",
    "invoke_adapter_command",
    "validate_command_adapter_registry",
)
