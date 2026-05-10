"""Локальное хранилище профилей CLI."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from avito.auth.settings import AuthSettings
from avito.cli.errors import CliConfigFileError, CliPermissionError
from avito.config import AvitoSettings

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

CLI_HOME_ENV = "AVITO_PY_HOME"
TICKET_HOME_ENV = "MY_SDK_HOME"
DEFAULT_HOME_NAME = ".avito-py"
CONFIG_FILENAME = "config.json"
ACCOUNTS_FILENAME = "accounts.json"
SCHEMA_VERSION = 1
SECRET_MASK = "***"


@dataclass(frozen=True, slots=True)
class StoredAccount:
    """Сохраненная учетная запись CLI."""

    name: str
    client_id: str
    client_secret: str
    base_url: str = "https://api.avito.ru"
    user_id: int | None = None
    scope: str | None = None
    refresh_token: str | None = None
    token_url: str = "/token"
    alternate_token_url: str = "/token"
    autoteka_token_url: str = "/autoteka/token"
    autoteka_client_id: str | None = None
    autoteka_client_secret: str | None = None
    autoteka_scope: str | None = None

    @classmethod
    def from_json(cls, value: object) -> StoredAccount:
        """Создает учетную запись из JSON-модели."""

        payload = _require_mapping(value, label="account")
        name = _require_str(payload, "name")
        client_id = _require_str(payload, "client_id")
        client_secret = _require_str(payload, "client_secret")
        base_url = _optional_str(payload, "base_url") or "https://api.avito.ru"
        user_id = _optional_int(payload, "user_id")
        return cls(
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
            user_id=user_id,
            scope=_optional_str(payload, "scope"),
            refresh_token=_optional_str(payload, "refresh_token"),
            token_url=_optional_str(payload, "token_url") or "/token",
            alternate_token_url=_optional_str(payload, "alternate_token_url") or "/token",
            autoteka_token_url=_optional_str(payload, "autoteka_token_url") or "/autoteka/token",
            autoteka_client_id=_optional_str(payload, "autoteka_client_id"),
            autoteka_client_secret=_optional_str(payload, "autoteka_client_secret"),
            autoteka_scope=_optional_str(payload, "autoteka_scope"),
        )

    def to_json(self, *, mask_secrets: bool = False) -> dict[str, JsonValue]:
        """Возвращает JSON-модель учетной записи."""

        return {
            "name": self.name,
            "client_id": self.client_id,
            "client_secret": _mask(self.client_secret, enabled=mask_secrets),
            "base_url": self.base_url,
            "user_id": self.user_id,
            "scope": self.scope,
            "refresh_token": _mask(self.refresh_token, enabled=mask_secrets),
            "token_url": self.token_url,
            "alternate_token_url": self.alternate_token_url,
            "autoteka_token_url": self.autoteka_token_url,
            "autoteka_client_id": self.autoteka_client_id,
            "autoteka_client_secret": _mask(
                self.autoteka_client_secret,
                enabled=mask_secrets,
            ),
            "autoteka_scope": self.autoteka_scope,
        }

    def to_avito_settings(self) -> AvitoSettings:
        """Создает публичные настройки SDK без сетевых вызовов."""

        auth = AuthSettings(
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
            refresh_token=self.refresh_token,
            token_url=self.token_url,
            alternate_token_url=self.alternate_token_url,
            autoteka_token_url=self.autoteka_token_url,
            autoteka_client_id=self.autoteka_client_id,
            autoteka_client_secret=self.autoteka_client_secret,
            autoteka_scope=self.autoteka_scope,
        )
        return AvitoSettings(base_url=self.base_url, user_id=self.user_id, auth=auth)


@dataclass(frozen=True, slots=True)
class AccountsDocument:
    """Файл сохраненных учетных записей CLI."""

    schema_version: int = SCHEMA_VERSION
    accounts: tuple[StoredAccount, ...] = ()

    @classmethod
    def from_json(cls, value: object) -> AccountsDocument:
        """Создает документ учетных записей из JSON-модели."""

        payload = _require_mapping(value, label=ACCOUNTS_FILENAME)
        schema_version = _optional_int(payload, "schema_version") or SCHEMA_VERSION
        _validate_schema_version(schema_version, filename=ACCOUNTS_FILENAME)
        accounts_value = payload.get("accounts", [])
        if not isinstance(accounts_value, list):
            raise CliConfigFileError("Поле `accounts` должно быть списком.")
        accounts = tuple(StoredAccount.from_json(item) for item in accounts_value)
        names = [account.name for account in accounts]
        if len(names) != len(set(names)):
            raise CliConfigFileError("Имена учетных записей в `accounts.json` должны быть уникальны.")
        return cls(schema_version=schema_version, accounts=accounts)

    def to_json(self, *, mask_secrets: bool = False) -> dict[str, JsonValue]:
        """Возвращает JSON-модель файла учетных записей."""

        return {
            "schema_version": self.schema_version,
            "accounts": [account.to_json(mask_secrets=mask_secrets) for account in self.accounts],
        }


@dataclass(frozen=True, slots=True)
class CliConfigDocument:
    """Файл локальной конфигурации CLI."""

    schema_version: int = SCHEMA_VERSION
    active_profile: str | None = None

    @classmethod
    def from_json(cls, value: object) -> CliConfigDocument:
        """Создает документ конфигурации из JSON-модели."""

        payload = _require_mapping(value, label=CONFIG_FILENAME)
        schema_version = _optional_int(payload, "schema_version") or SCHEMA_VERSION
        _validate_schema_version(schema_version, filename=CONFIG_FILENAME)
        return cls(
            schema_version=schema_version,
            active_profile=_optional_str(payload, "active_profile"),
        )

    def to_json(self, *, mask_secrets: bool = False) -> dict[str, JsonValue]:
        """Возвращает JSON-модель файла конфигурации."""

        return {
            "schema_version": self.schema_version,
            "active_profile": self.active_profile,
        }


class AccountStore:
    """Хранилище локальных учетных записей CLI."""

    def __init__(self, home: Path) -> None:
        """Создать store для accounts.json внутри CLI home."""

        self._home = home
        self._path = home / ACCOUNTS_FILENAME

    @property
    def path(self) -> Path:
        """Возвращает путь к файлу учетных записей."""

        return self._path

    def load(self) -> AccountsDocument:
        """Загружает учетные записи или возвращает пустой документ."""

        if not self._path.exists():
            return AccountsDocument()
        return AccountsDocument.from_json(_read_json_file(self._path))

    def save(self, document: AccountsDocument) -> None:
        """Атомарно сохраняет учетные записи."""

        _ensure_cli_home(self._home)
        _write_json_file(self._path, document.to_json(mask_secrets=False))


class ConfigStore:
    """Хранилище локальной конфигурации CLI."""

    def __init__(self, home: Path, *, path: Path | None = None) -> None:
        """Создать store для config.json или пользовательского пути."""

        self._home = home
        self._uses_default_path = path is None
        self._path = path if path is not None else home / CONFIG_FILENAME

    @property
    def path(self) -> Path:
        """Возвращает путь к файлу конфигурации."""

        return self._path

    def load(self) -> CliConfigDocument:
        """Загружает конфигурацию или возвращает пустой документ."""

        if not self._path.exists():
            return CliConfigDocument()
        return CliConfigDocument.from_json(_read_json_file(self._path))

    def save(self, document: CliConfigDocument) -> None:
        """Атомарно сохраняет конфигурацию."""

        if self._uses_default_path:
            _ensure_cli_home(self._home)
        else:
            _ensure_config_parent(self._path.parent)
        _write_json_file(self._path, document.to_json(mask_secrets=False))


def resolve_cli_home(env: Mapping[str, str] | None = None) -> Path:
    """Возвращает каталог CLI без создания файлов."""

    source = os.environ if env is None else env
    avito_home = source.get(CLI_HOME_ENV)
    if avito_home:
        return Path(avito_home).expanduser()
    ticket_home = source.get(TICKET_HOME_ENV)
    if ticket_home:
        return Path(ticket_home).expanduser()
    return Path.home() / DEFAULT_HOME_NAME


def _ensure_cli_home(path: Path) -> None:
    """Создать CLI home с закрытыми правами доступа."""

    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path, 0o700)
    except PermissionError as exc:
        raise CliPermissionError(
            "Нет прав на создание или изменение каталога CLI.",
            details={"path": str(path)},
        ) from exc


def _ensure_config_parent(path: Path) -> None:
    """Создать родительский каталог пользовательского config path."""

    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise CliPermissionError(
            "Нет прав на создание или изменение каталога CLI.",
            details={"path": str(path)},
        ) from exc


def _read_json_file(path: Path) -> JsonValue:
    """Прочитать JSON-файл и преобразовать ошибки в CLI errors."""

    try:
        with path.open("r", encoding="utf-8") as file_obj:
            # JSON is the boundary where Python cannot know the concrete shape.
            return cast(JsonValue, json.load(file_obj))
    except PermissionError as exc:
        raise CliPermissionError(
            "Нет прав на чтение локального файла CLI.",
            details={"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise CliConfigFileError(
            "Локальный файл CLI содержит некорректный JSON.",
            details={"path": str(path), "line": exc.lineno, "column": exc.colno},
        ) from exc


def _write_json_file(path: Path, payload: Mapping[str, JsonValue]) -> None:
    """Атомарно записать JSON-файл с закрытыми правами доступа."""

    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary_name: str | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            file_obj.write(text)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except PermissionError as exc:
        raise CliPermissionError(
            "Нет прав на запись локального файла CLI.",
            details={"path": str(path)},
        ) from exc
    finally:
        if temporary_name is not None and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    """Проверить, что JSON value является объектом."""

    if not isinstance(value, dict):
        raise CliConfigFileError(f"`{label}` должен содержать JSON-объект.")
    return value


def _require_str(payload: Mapping[str, object], field_name: str) -> str:
    """Прочитать обязательную непустую строку из JSON object."""

    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise CliConfigFileError(f"Поле `{field_name}` должно быть непустой строкой.")
    return value


def _optional_str(payload: Mapping[str, object], field_name: str) -> str | None:
    """Прочитать optional строку из JSON object."""

    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CliConfigFileError(f"Поле `{field_name}` должно быть строкой.")
    return value


def _optional_int(payload: Mapping[str, object], field_name: str) -> int | None:
    """Прочитать optional integer из JSON object."""

    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise CliConfigFileError(f"Поле `{field_name}` должно быть целым числом.")
    return value


def _validate_schema_version(schema_version: int, *, filename: str) -> None:
    """Проверить поддерживаемую версию локального JSON-файла."""

    if schema_version != SCHEMA_VERSION:
        raise CliConfigFileError(
            "Версия локального файла CLI не поддерживается.",
            details={"filename": filename, "schema_version": schema_version},
        )


def _mask(value: str | None, *, enabled: bool) -> str | None:
    """Замаскировать secret value при безопасном выводе."""

    if value is None:
        return None
    if enabled:
        return SECRET_MASK
    return value


__all__ = (
    "ACCOUNTS_FILENAME",
    "CLI_HOME_ENV",
    "CONFIG_FILENAME",
    "DEFAULT_HOME_NAME",
    "SCHEMA_VERSION",
    "TICKET_HOME_ENV",
    "AccountStore",
    "AccountsDocument",
    "CliConfigDocument",
    "ConfigStore",
    "StoredAccount",
    "resolve_cli_home",
)
