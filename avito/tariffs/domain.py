"""Доменные объекты пакета tariffs."""

from __future__ import annotations

from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride
from avito.core.domain import DomainObject
from avito.core.swagger import swagger_operation
from avito.tariffs.models import TariffInfo
from avito.tariffs.operations import GET_TARIFF_INFO


@dataclass(slots=True, frozen=True)
class Tariff(DomainObject):
    """Доменный объект тарифа."""

    __swagger_domain__ = "tariffs"
    __sdk_factory__ = "tariff"
    __sdk_factory_args__ = {"tariff_id": "path.tariff_id"}

    tariff_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/tariff/info/1",
        spec="Тарифы.json",
        operation_id="getTariffInfo",
    )
    def get_tariff_info(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> TariffInfo:
        """Получает информацию о тарифе аккаунта.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `TariffInfo` с типизированными данными ответа.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(GET_TARIFF_INFO, timeout=timeout, retry=retry)


__all__ = ("Tariff",)
