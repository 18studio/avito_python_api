"""Типизированные модели раздела tariffs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from avito.core import ApiModel, JsonReader


class TariffLevel(str, Enum):
    """Уровень тарифного контракта."""

    UNKNOWN = "__unknown__"
    MAX = "Тариф Максимальный"
    BASE = "Тариф Базовый"


@dataclass(slots=True, frozen=True)
class TariffContractInfo(ApiModel):
    """Информация о текущем или запланированном тарифном контракте."""

    level: TariffLevel | None
    is_active: bool | None
    start_time: int | None
    close_time: int | None
    bonus: int | None
    price: float | None
    original_price: float | None
    packages_count: int | None

    @classmethod
    def from_payload(cls, payload: object) -> TariffContractInfo:
        """Преобразует JSON-объект контракта тарифа в SDK-модель."""

        reader = JsonReader(payload)
        price = reader.mapping("price") or {}
        packages = reader.list("packages")
        price_reader = JsonReader(price)
        return cls(
            level=reader.enum(TariffLevel, "level", unknown=TariffLevel.UNKNOWN),
            is_active=reader.optional_bool("isActive"),
            start_time=reader.optional_int("startTime"),
            close_time=reader.optional_int("closeTime"),
            bonus=reader.optional_int("bonus"),
            price=price_reader.optional_float("price"),
            original_price=price_reader.optional_float("originalPrice"),
            packages_count=len(packages) if packages else None,
        )


@dataclass(slots=True, frozen=True)
class TariffInfo(ApiModel):
    """Информация по текущему и запланированному тарифу."""

    current: TariffContractInfo | None = None
    scheduled: TariffContractInfo | None = None

    @classmethod
    def from_payload(cls, payload: object) -> TariffInfo:
        """Преобразует ответ API с информацией о тарифе в SDK-модель."""

        reader = JsonReader(payload)
        return cls(
            current=_contract_from_mapping(reader.mapping("current")),
            scheduled=_contract_from_mapping(reader.mapping("scheduled")),
        )


def _contract_from_mapping(payload: Mapping[str, object] | None) -> TariffContractInfo | None:
    if not payload:
        return None
    return TariffContractInfo.from_payload(cast(object, payload))


__all__ = ("TariffContractInfo", "TariffInfo", "TariffLevel")
