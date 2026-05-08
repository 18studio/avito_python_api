"""Пакет tariffs."""

from avito.tariffs.async_domain import AsyncTariff
from avito.tariffs.domain import Tariff
from avito.tariffs.models import TariffContractInfo, TariffInfo, TariffLevel

__all__ = ("AsyncTariff", "Tariff", "TariffContractInfo", "TariffInfo", "TariffLevel")
