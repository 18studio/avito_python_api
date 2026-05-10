"""Иерархия ошибок CLI и безопасный рендеринг."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO, Any, ClassVar

import click

from avito.cli.context import CliContext
from avito.cli.ui import emit_json_stderr, emit_stderr, sanitize_cli_output

EXIT_USAGE = 2
EXIT_CONFIGURATION = 3
EXIT_AUTHENTICATION = 4
EXIT_AUTHORIZATION = 5
EXIT_RATE_LIMIT = 6
EXIT_UPSTREAM = 7
EXIT_TRANSPORT = 8
EXIT_INTERNAL = 70


def _current_cli_context() -> CliContext | None:
    """Вернуть текущий CliContext из Click context stack."""

    click_context = click.get_current_context(silent=True)
    if click_context is None:
        return None
    if isinstance(click_context.obj, CliContext):
        return click_context.obj
    parent = click_context.parent
    if parent is not None and isinstance(parent.obj, CliContext):
        return parent.obj
    return None


@dataclass(slots=True)
class CliError(click.ClickException):
    """Базовая ошибка CLI со стабильным кодом и exit code."""

    message: str
    code: str
    exit_code: int
    details: object | None = None
    _raw_message: str = field(init=False, repr=False)
    _ctx: CliContext | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Инициализировать ClickException и сохранить CLI context."""

        self._raw_message = self.message
        self._ctx = _current_cli_context()
        click.ClickException.__init__(self, self.message)

    def to_payload(self, *, debug: bool = False) -> dict[str, object]:
        """Возвращает безопасную JSON-совместимую модель ошибки."""

        payload: dict[str, object] = {
            "code": self.code,
            "exit_code": self.exit_code,
            "message": self.message,
        }
        if debug and self.details is not None:
            payload["details"] = sanitize_cli_output(self.details)
        return payload

    def show(self, file: IO[Any] | None = None) -> None:
        """Печатает ошибку в stderr в human или JSON-формате."""

        ctx = self._ctx
        payload = self.to_payload(debug=ctx.debug if ctx is not None else False)
        if ctx is not None and ctx.json_output:
            emit_json_stderr(payload)
            return

        emit_stderr(ctx, f"{self.code}: {payload['message']}", fg="red")
        if ctx is not None and ctx.debug and "details" in payload:
            emit_stderr(ctx, f"details={payload['details']}", fg="yellow")


class CliUsageError(CliError):
    """Ошибка использования команды."""

    DEFAULT_CODE: ClassVar[str] = "CLI_USAGE_ERROR"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку некорректного использования CLI."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_USAGE,
            details=details,
        )


class InvalidFlagCombinationError(CliUsageError):
    """Несовместимые глобальные флаги."""

    DEFAULT_CODE: ClassVar[str] = "INVALID_FLAG_COMBINATION"


class CliPermissionError(CliError):
    """Ошибка доступа к локальным файлам CLI."""

    DEFAULT_CODE: ClassVar[str] = "PERMISSION_DENIED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку доступа к локальному ресурсу."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_AUTHENTICATION,
            details=details,
        )


class CliConfigFileError(CliError):
    """Ошибка чтения или валидации локальной конфигурации CLI."""

    DEFAULT_CODE: ClassVar[str] = "CONFIG_INVALID"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку локальной конфигурации."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_UPSTREAM,
            details=details,
        )


class CliAuthRequiredError(CliError):
    """Ошибка отсутствующих учетных данных CLI."""

    DEFAULT_CODE: ClassVar[str] = "AUTH_REQUIRED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку отсутствующей авторизации."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_AUTHENTICATION,
            details=details,
        )


class CliAuthorizationError(CliError):
    """Ошибка прав доступа в Avito API."""

    DEFAULT_CODE: ClassVar[str] = "PERMISSION_DENIED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку недостаточных прав upstream API."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_AUTHORIZATION,
            details=details,
        )


class CliValidationError(CliError):
    """Ошибка валидации входных значений CLI."""

    DEFAULT_CODE: ClassVar[str] = "VALIDATION_FAILED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку валидации CLI input."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_UPSTREAM,
            details=details,
        )


class CliConflictError(CliError):
    """Конфликт состояния upstream-ресурса."""

    DEFAULT_CODE: ClassVar[str] = "CONFLICT"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку конфликта состояния."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_UPSTREAM,
            details=details,
        )


class CliRateLimitError(CliError):
    """Upstream API вернул ограничение частоты запросов."""

    DEFAULT_CODE: ClassVar[str] = "RATE_LIMITED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку rate limit."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_RATE_LIMIT,
            details=details,
        )


class CliTransportError(CliError):
    """Транспортный сбой до корректного ответа upstream API."""

    DEFAULT_CODE: ClassVar[str] = "TRANSPORT_FAILED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку транспорта."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_TRANSPORT,
            details=details,
        )


class CliSdkMethodError(CliError):
    """Ошибка выполнения публичного SDK-метода."""

    DEFAULT_CODE: ClassVar[str] = "SDK_METHOD_FAILED"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        """Создать ошибку публичного SDK method."""

        super().__init__(
            message=message,
            code=self.DEFAULT_CODE,
            exit_code=EXIT_UPSTREAM,
            details=details,
        )


__all__ = (
    "EXIT_AUTHENTICATION",
    "EXIT_AUTHORIZATION",
    "EXIT_CONFIGURATION",
    "EXIT_INTERNAL",
    "EXIT_RATE_LIMIT",
    "EXIT_TRANSPORT",
    "EXIT_UPSTREAM",
    "EXIT_USAGE",
    "CliAuthRequiredError",
    "CliAuthorizationError",
    "CliConflictError",
    "CliConfigFileError",
    "CliError",
    "CliPermissionError",
    "CliRateLimitError",
    "CliSdkMethodError",
    "CliTransportError",
    "CliUsageError",
    "CliValidationError",
    "InvalidFlagCombinationError",
)
