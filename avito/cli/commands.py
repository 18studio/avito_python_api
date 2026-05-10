"""Generic API command invocation through the public SDK facade."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Protocol

from avito.cli.config import AccountStore, ConfigStore, StoredAccount, resolve_cli_home
from avito.cli.context import CliContext
from avito.cli.errors import (
    CliAuthorizationError,
    CliAuthRequiredError,
    CliConflictError,
    CliError,
    CliRateLimitError,
    CliSdkMethodError,
    CliTransportError,
    CliValidationError,
)
from avito.cli.registry import ApiCommandRecord
from avito.cli.schemas import coerce_cli_values
from avito.client import AvitoClient
from avito.config import AvitoSettings
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AvitoError,
    ConflictError,
    RateLimitError,
    TransportError,
    ValidationError,
)
from avito.core.types import ApiTimeouts


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
    """Factory used by production code and tests to build SDK clients."""

    def __call__(self, settings: AvitoSettings) -> ClientContext:
        """Build a context-managed SDK client."""


def invoke_api_command(
    ctx: CliContext,
    command: ApiCommandRecord,
    raw_values: Mapping[str, Sequence[str]],
    *,
    client_factory: ClientFactory | None = None,
) -> object:
    """Invoke one registry-backed API command through `AvitoClient`."""

    values = coerce_cli_values(command.parameters, raw_values, no_input=ctx.no_input)
    factory_kwargs = _kwargs_for_source(command, values, source="factory")
    method_kwargs = _kwargs_for_source(command, values, source="method")
    settings = resolve_avito_settings(ctx)
    resolved_factory = client_factory or _default_client_factory

    try:
        with resolved_factory(settings) as client:
            domain = _call_public_factory(client, command, factory_kwargs)
            method_kwargs = _with_timeout_if_supported(ctx, domain, command, method_kwargs)
            return _call_public_method(domain, command, method_kwargs)
    except CliError:
        raise
    except AvitoError as exc:
        raise map_sdk_error(exc, command=command) from exc


def resolve_avito_settings(ctx: CliContext) -> AvitoSettings:
    """Resolve active CLI profile into public SDK settings."""

    home = resolve_cli_home()
    config = ConfigStore(home, path=ctx.config).load()
    profile = ctx.profile or config.active_profile
    if profile is None:
        raise CliAuthRequiredError("Активная учетная запись не выбрана.")

    account = _find_account(AccountStore(home).load().accounts, profile)
    if account is None:
        raise CliAuthRequiredError(
            "Учетная запись не найдена в локальном хранилище.",
            details={"profile": profile},
        )
    return account.to_avito_settings()


def map_sdk_error(error: AvitoError, *, command: ApiCommandRecord) -> CliError:
    """Convert SDK exceptions into documented CLI errors."""

    details = _sdk_error_details(error, command=command)
    if isinstance(error, AuthenticationError):
        return CliAuthRequiredError(error.message, details=details)
    if isinstance(error, AuthorizationError):
        return CliAuthorizationError(error.message, details=details)
    if isinstance(error, ValidationError):
        return CliValidationError(error.message, details=details)
    if isinstance(error, ConflictError):
        return CliConflictError(error.message, details=details)
    if isinstance(error, RateLimitError):
        return CliRateLimitError(error.message, details=details)
    if isinstance(error, TransportError):
        return CliTransportError(error.message, details=details)
    return CliSdkMethodError(error.message, details=details)


def _default_client_factory(settings: AvitoSettings) -> ClientContext:
    return AvitoClient(settings)


def _kwargs_for_source(
    command: ApiCommandRecord,
    values: Mapping[str, object],
    *,
    source: str,
) -> dict[str, object]:
    return {
        parameter.name: values[parameter.name]
        for parameter in command.parameters
        if parameter.source == source and parameter.name in values
    }


def _call_public_factory(
    client: object,
    command: ApiCommandRecord,
    kwargs: Mapping[str, object],
) -> object:
    factory = getattr(client, command.factory, None)
    if not callable(factory):
        raise CliSdkMethodError(
            "Публичная SDK factory для команды не найдена.",
            details={"factory": command.factory, "command_id": command.command_id},
        )
    return factory(**kwargs)


def _call_public_method(
    domain: object,
    command: ApiCommandRecord,
    kwargs: Mapping[str, object],
) -> object:
    method = getattr(domain, command.sdk_method_name, None)
    if not callable(method):
        raise CliSdkMethodError(
            "Публичный SDK-метод для команды не найден.",
            details={"method": command.sdk_method_name, "command_id": command.command_id},
        )
    return method(**kwargs)


def _with_timeout_if_supported(
    ctx: CliContext,
    domain: object,
    command: ApiCommandRecord,
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    resolved = dict(kwargs)
    if ctx.timeout is None:
        return resolved
    method = getattr(domain, command.sdk_method_name, None)
    if not callable(method):
        return resolved
    if "timeout" in inspect.signature(method).parameters:
        resolved["timeout"] = ApiTimeouts(
            connect=ctx.timeout,
            read=ctx.timeout,
            write=ctx.timeout,
            pool=ctx.timeout,
        )
    return resolved


def _find_account(accounts: Sequence[StoredAccount], profile: str) -> StoredAccount | None:
    for account in accounts:
        if account.name == profile:
            return account
    return None


def _sdk_error_details(error: AvitoError, *, command: ApiCommandRecord) -> dict[str, object]:
    return {
        "command_id": command.command_id,
        "operation_key": command.operation_key,
        "sdk_method": command.sdk_method,
        "status_code": error.status_code,
        "error_code": error.error_code,
        "operation": error.operation,
        "method": error.method,
        "endpoint": error.endpoint,
        "request_id": error.request_id,
        "metadata": dict(error.metadata),
        "details": error.details,
    }


__all__ = (
    "ClientContext",
    "ClientFactory",
    "invoke_api_command",
    "map_sdk_error",
    "resolve_avito_settings",
)
