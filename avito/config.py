"""Конфигурация SDK Avito и параметры transport-слоя."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from avito._env import parse_env_int, resolve_env_aliases
from avito.auth.settings import AuthSettings
from avito.core.exceptions import ConfigurationError
from avito.core.retries import RetryPolicy
from avito.core.types import ApiTimeouts

_FORBIDDEN_USER_AGENT_SUFFIX_FRAGMENTS = (
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "client_secret",
    "secret",
    "password",
    "bearer",
)


@dataclass(slots=True, frozen=True)
class AvitoSettings:
    """Единственный публичный контракт конфигурации SDK."""

    ENV_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "base_url": ("AVITO_BASE_URL",),
        "user_id": ("AVITO_USER_ID",),
        "user_agent_suffix": ("AVITO_USER_AGENT_SUFFIX",),
    }

    base_url: str = "https://api.avito.ru"
    user_id: int | None = None
    user_agent_suffix: str | None = None
    auth: AuthSettings = field(default_factory=AuthSettings)
    timeouts: ApiTimeouts = field(default_factory=ApiTimeouts)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> AvitoSettings:
        """Загружает конфигурацию из окружения и optional `.env` файла."""

        resolved_values = resolve_env_aliases(cls.ENV_ALIASES, env_file=env_file)
        user_id = resolved_values.get("user_id")
        auth_settings = AuthSettings.from_env(env_file=env_file)
        return cls(
            base_url=resolved_values.get("base_url", "https://api.avito.ru"),
            user_id=parse_env_int(user_id, field_name="user_id") if user_id is not None else None,
            user_agent_suffix=resolved_values.get("user_agent_suffix"),
            auth=auth_settings,
            timeouts=ApiTimeouts.from_env(env_file=env_file),
            retry_policy=RetryPolicy.from_env(env_file=env_file),
        ).validate_required()

    @classmethod
    def supported_env_vars(cls) -> dict[str, tuple[str, ...]]:
        """Возвращает документированный набор env-переменных SDK."""

        env_vars = dict(cls.ENV_ALIASES)
        env_vars.update(
            {
                f"auth.{field_name}": aliases
                for field_name, aliases in AuthSettings.supported_env_vars().items()
            }
        )
        return env_vars

    def validate_required(self) -> AvitoSettings:
        """Проверяет обязательные части публичной конфигурации SDK."""

        self._validate_user_agent_suffix()
        self.auth.validate_required()
        return self

    def _validate_user_agent_suffix(self) -> None:
        suffix = self.user_agent_suffix
        if suffix is None:
            return
        if not suffix.strip():
            raise ConfigurationError("Поле `user_agent_suffix` не должно быть пустым.")
        if "\r" in suffix or "\n" in suffix:
            raise ConfigurationError(
                "Поле `user_agent_suffix` не должно содержать переводы строки."
            )
        lowered = suffix.lower()
        if any(fragment in lowered for fragment in _FORBIDDEN_USER_AGENT_SUFFIX_FRAGMENTS):
            raise ConfigurationError(
                "Поле `user_agent_suffix` не должно содержать секреты или auth-данные."
            )


__all__ = ("AvitoSettings",)
