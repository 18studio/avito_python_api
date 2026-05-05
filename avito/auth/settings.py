"""Настройки аутентификации SDK Avito."""

from __future__ import annotations

import os
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from avito._env import read_dotenv, resolve_env_aliases
from avito.core.exceptions import ConfigurationError


@dataclass(slots=True, frozen=True)
class AuthSettings:
    """Единственный публичный контракт OAuth-конфигурации SDK."""

    ENV_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "client_id": ("AVITO_CLIENT_ID",),
        "client_secret": ("AVITO_CLIENT_SECRET",),
        "scope": ("AVITO_SCOPE",),
        "refresh_token": ("AVITO_REFRESH_TOKEN",),
        "token_url": ("AVITO_TOKEN_URL",),
        "alternate_token_url": ("AVITO_ALTERNATE_TOKEN_URL",),
        "autoteka_token_url": ("AVITO_AUTOTEKA_TOKEN_URL",),
        "autoteka_client_id": ("AVITO_AUTOTEKA_CLIENT_ID",),
        "autoteka_client_secret": ("AVITO_AUTOTEKA_CLIENT_SECRET",),
        "autoteka_scope": ("AVITO_AUTOTEKA_SCOPE",),
    }
    DEPRECATED_ENV_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "client_secret": ("AVITO_SECRET",),
    }

    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None
    refresh_token: str | None = None
    token_url: str = "/token"
    alternate_token_url: str = "/token"
    autoteka_token_url: str = "/autoteka/token"
    autoteka_client_id: str | None = None
    autoteka_client_secret: str | None = None
    autoteka_scope: str | None = None

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> AuthSettings:
        """Загружает auth-настройки из процесса и optional `.env` файла."""

        aliases = cls._env_aliases_with_deprecated()
        resolved_values = resolve_env_aliases(aliases, env_file=env_file)
        if cls._uses_deprecated_client_secret_alias(env_file=env_file):
            warnings.warn(
                "`AVITO_SECRET` устарел; используйте `AVITO_CLIENT_SECRET`.",
                DeprecationWarning,
                stacklevel=2,
            )
        return cls(**resolved_values).validate_required()

    @classmethod
    def supported_env_vars(cls) -> dict[str, tuple[str, ...]]:
        """Возвращает документированный набор env-переменных."""

        return dict(cls.ENV_ALIASES)

    @classmethod
    def _env_aliases_with_deprecated(cls) -> dict[str, tuple[str, ...]]:
        aliases = dict(cls.ENV_ALIASES)
        for field_name, deprecated_aliases in cls.DEPRECATED_ENV_ALIASES.items():
            aliases[field_name] = aliases.get(field_name, ()) + deprecated_aliases
        return aliases

    @classmethod
    def _uses_deprecated_client_secret_alias(
        cls, *, env_file: str | Path | None
    ) -> bool:
        canonical_aliases = cls.ENV_ALIASES["client_secret"]
        deprecated_aliases = cls.DEPRECATED_ENV_ALIASES["client_secret"]
        file_values = read_dotenv(env_file)
        for source in (os.environ, file_values):
            if _has_env_value(source, canonical_aliases):
                return False
            if _has_env_value(source, deprecated_aliases):
                return True
        return False

    def validate_required(self) -> AuthSettings:
        """Проверяет обязательные поля OAuth-конфигурации."""

        missing_fields: list[str] = []
        if not self.client_id:
            missing_fields.append("client_id: " + ", ".join(self.ENV_ALIASES["client_id"]))
        if not self.client_secret:
            missing_fields.append("client_secret: " + ", ".join(self.ENV_ALIASES["client_secret"]))
        if missing_fields:
            raise ConfigurationError(
                "Не заданы обязательные настройки OAuth. Ожидаются "
                + "; ".join(missing_fields)
                + "."
            )
        return self


def _has_env_value(source: Mapping[str, str], aliases: tuple[str, ...]) -> bool:
    return any(source.get(alias) not in {None, ""} for alias in aliases)


__all__ = ("AuthSettings",)
