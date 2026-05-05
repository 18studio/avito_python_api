"""Operation specs for tariffs domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.tariffs.models import TariffInfo

GET_TARIFF_INFO = OperationSpec(
    name="tariffs.info.get",
    method="GET",
    path="/tariff/info/1",
    response_model=TariffInfo,
)

__all__ = ("GET_TARIFF_INFO",)
