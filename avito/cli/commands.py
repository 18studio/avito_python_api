"""Generic API command invocation through the public SDK facade."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence

from avito.cli.adapters import (
    ClientContext,
    ClientFactory,
    get_command_adapter_registry,
    invoke_adapter_command,
)
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
    CliUsageError,
    CliValidationError,
)
from avito.cli.registry import ApiCommandRecord, HelperCommandRecord
from avito.cli.safety import SafetyOptions, validate_safety_options
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


def invoke_api_command(
    ctx: CliContext,
    command: ApiCommandRecord,
    raw_values: Mapping[str, Sequence[str]],
    *,
    safety_options: SafetyOptions | None = None,
    client_factory: ClientFactory | None = None,
) -> object:
    """Invoke one registry-backed API command through `AvitoClient`."""

    if command.adapter_id is not None:
        return invoke_adapter_command(
            get_command_adapter_registry(),
            ctx,
            command,
            raw_values,
            engine=_invoke_api_command_generic,
            safety_options=safety_options,
            client_factory=client_factory,
        )
    return _invoke_api_command_generic(
        ctx,
        command,
        raw_values,
        safety_options=safety_options,
        client_factory=client_factory,
    )


def invoke_helper_command(
    ctx: CliContext,
    command: HelperCommandRecord,
    raw_values: Mapping[str, Sequence[str]],
    *,
    client_factory: ClientFactory | None = None,
) -> object:
    """Invoke one public helper workflow through `AvitoClient`."""

    values = coerce_cli_values(command.parameters, raw_values, no_input=ctx.no_input)
    settings = resolve_avito_settings(ctx)
    resolved_factory = client_factory or _default_client_factory

    try:
        with resolved_factory(settings) as client:
            method = getattr(client, command.sdk_method_name, None)
            if not callable(method):
                raise CliSdkMethodError(
                    "Публичный helper-метод SDK для команды не найден.",
                    details={
                        "method": command.sdk_method_name,
                        "command_id": command.command_id,
                    },
                )
            return method(**values)
    except CliError:
        raise
    except AvitoError as exc:
        raise map_sdk_error(exc, command=command) from exc


def _invoke_api_command_generic(
    ctx: CliContext,
    command: ApiCommandRecord,
    raw_values: Mapping[str, Sequence[str]],
    *,
    safety_options: SafetyOptions | None = None,
    client_factory: ClientFactory | None = None,
) -> object:
    """Invoke one command through the generic public SDK path."""

    resolved_safety_options = safety_options or SafetyOptions()
    validate_safety_options(ctx, command, resolved_safety_options)
    values = coerce_cli_values(command.parameters, raw_values, no_input=ctx.no_input)
    factory_kwargs = _kwargs_for_source(command, values, source="factory")
    method_kwargs = _kwargs_for_source(command, values, source="method")
    settings = resolve_avito_settings(ctx)
    resolved_factory = client_factory or _default_client_factory

    try:
        with resolved_factory(settings) as client:
            domain = _call_public_factory(client, command, factory_kwargs)
            method_kwargs = _with_timeout_if_supported(ctx, domain, command, method_kwargs)
            method_kwargs = _with_dry_run_if_supported(
                resolved_safety_options,
                domain,
                command,
                method_kwargs,
            )
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


def map_sdk_error(
    error: AvitoError,
    *,
    command: ApiCommandRecord | HelperCommandRecord,
) -> CliError:
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


def _with_dry_run_if_supported(
    options: SafetyOptions,
    domain: object,
    command: ApiCommandRecord,
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    resolved = dict(kwargs)
    if not options.dry_run:
        return resolved
    method = getattr(domain, command.sdk_method_name, None)
    if callable(method) and "dry_run" in inspect.signature(method).parameters:
        resolved["dry_run"] = True
        return resolved
    raise CliUsageError(
        "SDK-метод команды не поддерживает dry_run.",
        details={"command_id": command.command_id, "method": command.sdk_method},
    )


def _find_account(accounts: Sequence[StoredAccount], profile: str) -> StoredAccount | None:
    for account in accounts:
        if account.name == profile:
            return account
    return None


def _sdk_error_details(
    error: AvitoError,
    *,
    command: ApiCommandRecord | HelperCommandRecord,
) -> dict[str, object]:
    details: dict[str, object] = {
        "command_id": command.command_id,
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
    if isinstance(command, ApiCommandRecord):
        details["operation_key"] = command.operation_key
    return details


__all__ = (
    "ClientContext",
    "ClientFactory",
    "SafetyOptions",
    "invoke_helper_command",
    "invoke_api_command",
    "map_sdk_error",
    "resolve_avito_settings",
)
