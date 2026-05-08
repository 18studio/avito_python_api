"""Внутренние утилиты детерминированного чтения env и `.env`."""

from __future__ import annotations

import os
from collections.abc import Mapping
from json import JSONDecodeError, loads
from pathlib import Path

from avito.core.exceptions import ConfigurationError


def read_dotenv(env_file: str | Path | None) -> dict[str, str]:
    """Читает простой `.env` файл без побочных эффектов."""

    if env_file is None:
        return {}

    path = Path(env_file)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_value = value.strip()
        if len(cleaned_value) >= 2 and cleaned_value[0] == cleaned_value[-1]:
            if cleaned_value[0] in {"'", '"'}:
                cleaned_value = cleaned_value[1:-1]
        values[key.strip()] = cleaned_value
    return values


def resolve_env_aliases(
    aliases_by_field: Mapping[str, tuple[str, ...]],
    *,
    env_file: str | Path | None,
) -> dict[str, str]:
    """Разрешает env alias-имена с приоритетом process environment над `.env`."""

    file_values = read_dotenv(env_file)
    resolved: dict[str, str] = {}

    for field_name, aliases in aliases_by_field.items():
        for source in (os.environ, file_values):
            value = _first_present(source, aliases)
            if value is not None:
                resolved[field_name] = value
                break

    return resolved


def _first_present(source: Mapping[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = source.get(alias)
        if value is not None and value != "":
            return value
    return None


def parse_env_int(value: str, *, field_name: str) -> int:
    """Преобразует env-значение в `int` с typed-ошибкой."""

    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Некорректное значение `{field_name}`: ожидается int, получено {value!r}."
        ) from exc


def parse_env_float(value: str, *, field_name: str) -> float:
    """Преобразует env-значение в `float` с typed-ошибкой."""

    try:
        return float(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Некорректное значение `{field_name}`: ожидается float, получено {value!r}."
        ) from exc


def parse_env_bool(value: str, *, field_name: str) -> bool:
    """Преобразует env-значение в `bool` с typed-ошибкой."""

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(
        f"Некорректное значение `{field_name}`: ожидается bool, получено {value!r}."
    )


def parse_env_str_tuple(value: str, *, field_name: str) -> tuple[str, ...]:
    """Преобразует env-значение в кортеж строк."""

    stripped = value.strip()
    if not stripped:
        return ()
    if stripped.startswith("["):
        try:
            parsed = loads(stripped)
        except JSONDecodeError as exc:
            raise ConfigurationError(
                f"Некорректное значение `{field_name}`: ожидается JSON-массив строк."
            ) from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ConfigurationError(
                f"Некорректное значение `{field_name}`: ожидается список строк."
            )
        return tuple(parsed)
    parts = tuple(part.strip() for part in stripped.split(",") if part.strip())
    if not parts:
        raise ConfigurationError(
            f"Некорректное значение `{field_name}`: ожидается непустой список строк."
        )
    return parts
