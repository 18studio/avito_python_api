"""Safe JSON payload readers for response model parsing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import TypeVar, cast

from avito.core.exceptions import ResponseMappingError

PayloadMapping = Mapping[str, object]
EnumT = TypeVar("EnumT", bound=Enum)


class JsonReader:
    """Typed helpers for reading upstream JSON payloads."""

    def __init__(self, payload: object) -> None:
        self._payload = self.expect_mapping(payload)

    @staticmethod
    def expect_mapping(payload: object) -> PayloadMapping:
        """Return payload as mapping or raise mapping error."""

        if not isinstance(payload, Mapping):
            raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
        return cast(PayloadMapping, payload)

    @staticmethod
    def expect_list(payload: object) -> list[object]:
        """Return payload as list or raise mapping error."""

        if not isinstance(payload, list):
            raise ResponseMappingError("Ожидался JSON-массив.", payload=payload)
        return payload

    def required_str(self, *keys: str) -> str:
        """Read required string field using fallback key order."""

        value = self.optional_str(*keys)
        if value is None:
            raise self._missing_required(keys)
        return value

    def optional_str(self, *keys: str) -> str | None:
        """Read optional string field using fallback key order."""

        value = self._first_present(keys)
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise self._wrong_type(keys, "строка")

    def required_int(self, *keys: str) -> int:
        """Read required integer field using fallback key order."""

        value = self.optional_int(*keys)
        if value is None:
            raise self._missing_required(keys)
        return value

    def optional_int(self, *keys: str) -> int | None:
        """Read optional integer field using fallback key order."""

        value = self._first_present(keys)
        if value is None:
            return None
        if isinstance(value, bool):
            raise self._wrong_type(keys, "целое число")
        if isinstance(value, int):
            return value
        raise self._wrong_type(keys, "целое число")

    def required_float(self, *keys: str) -> float:
        """Read required numeric field using fallback key order."""

        value = self.optional_float(*keys)
        if value is None:
            raise self._missing_required(keys)
        return value

    def optional_float(self, *keys: str) -> float | None:
        """Read optional numeric field using fallback key order."""

        value = self._first_present(keys)
        if value is None:
            return None
        if isinstance(value, bool):
            raise self._wrong_type(keys, "число")
        if isinstance(value, int | float):
            return float(value)
        raise self._wrong_type(keys, "число")

    def required_bool(self, *keys: str) -> bool:
        """Read required boolean field using fallback key order."""

        value = self.optional_bool(*keys)
        if value is None:
            raise self._missing_required(keys)
        return value

    def optional_bool(self, *keys: str) -> bool | None:
        """Read optional boolean field using fallback key order."""

        value = self._first_present(keys)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        raise self._wrong_type(keys, "boolean")

    def required_datetime(self, *keys: str) -> datetime:
        """Read required ISO datetime field using fallback key order."""

        value = self.optional_datetime(*keys)
        if value is None:
            raise self._missing_required(keys)
        return value

    def optional_datetime(self, *keys: str) -> datetime | None:
        """Read optional ISO datetime field using fallback key order."""

        raw_value = self.optional_str(*keys)
        if raw_value is None:
            return None
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ResponseMappingError(
                f"Поле `{_field_label(keys)}` содержит некорректную дату.",
                payload=self._payload,
            ) from exc

    def enum(
        self,
        enum_type: type[EnumT],
        *keys: str,
        unknown: EnumT | None = None,
    ) -> EnumT | None:
        """Read enum value; return unknown fallback when provided."""

        raw_value = self.optional_str(*keys)
        if raw_value is None:
            return None
        try:
            return enum_type(raw_value)
        except ValueError:
            if unknown is not None:
                return unknown
            raise ResponseMappingError(
                f"Поле `{_field_label(keys)}` содержит неизвестное значение enum.",
                payload=self._payload,
            ) from None

    def mapping(self, *keys: str) -> PayloadMapping | None:
        """Read optional nested mapping."""

        value = self._first_present(keys)
        if value is None:
            return None
        if isinstance(value, Mapping):
            return cast(PayloadMapping, value)
        raise self._wrong_type(keys, "JSON-объект")

    def list(self, *keys: str) -> list[object]:
        """Read optional list field and return an empty list when missing."""

        value = self._first_present(keys)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return list(value)
        raise self._wrong_type(keys, "JSON-массив")

    def _first_present(self, keys: tuple[str, ...]) -> object | None:
        for key in keys:
            if key in self._payload and self._payload[key] is not None:
                return self._payload[key]
        return None

    def _missing_required(self, keys: tuple[str, ...]) -> ResponseMappingError:
        return ResponseMappingError(
            f"В ответе API отсутствует обязательное поле `{_field_label(keys)}`.",
            payload=self._payload,
        )

    def _wrong_type(self, keys: tuple[str, ...], expected: str) -> ResponseMappingError:
        return ResponseMappingError(
            f"Поле `{_field_label(keys)}` должно иметь тип: {expected}.",
            payload=self._payload,
        )


def _field_label(keys: tuple[str, ...]) -> str:
    if not keys:
        return "<unknown>"
    return "`, `".join(keys)


__all__ = ("JsonReader", "PayloadMapping")
