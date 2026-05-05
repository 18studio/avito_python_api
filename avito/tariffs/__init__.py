"""Пакет tariffs."""

from avito.tariffs.domain import Tariff
from avito.tariffs.models import TariffContractInfo, TariffInfo, TariffLevel

__all__ = ("Tariff", "TariffContractInfo", "TariffInfo", "TariffLevel")
