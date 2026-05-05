"""Доменные объекты пакета realty."""

from __future__ import annotations

from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.domain import DomainObject
from avito.core.swagger import swagger_operation
from avito.core.validation import DateInput, serialize_iso_date
from avito.realty.models import (
    RealtyActionResult,
    RealtyAnalyticsInfo,
    RealtyBaseParamsUpdateRequest,
    RealtyBookingsQuery,
    RealtyBookingsResult,
    RealtyBookingsUpdateRequest,
    RealtyInterval,
    RealtyIntervalsRequest,
    RealtyMarketPriceInfo,
    RealtyPricePeriod,
    RealtyPricesUpdateRequest,
)
from avito.realty.operations import (
    GET_INTERVALS,
    GET_MARKET_PRICE_CORRESPONDENCE,
    GET_REPORT_FOR_CLASSIFIED,
    LIST_REALTY_BOOKINGS,
    UPDATE_BASE_PARAMS,
    UPDATE_BOOKINGS_INFO,
    UPDATE_REALTY_PRICES,
)


@dataclass(slots=True, frozen=True)
class RealtyListing(DomainObject):
    """Доменный объект объявления краткосрочной аренды."""

    __swagger_domain__ = "realty"
    __sdk_factory__ = "realty_listing"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/realty/v1/items/intervals",
        spec="Краткосрочнаяаренда.json",
        operation_id="putIntervals",
        method_args={"intervals": "body.intervals", "item_id": "body.item_id"},
    )
    def get_intervals(
        self,
        *,
        intervals: list[RealtyInterval],
        item_id: int | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyActionResult:
        """Возвращает intervals для посутчной аренды.

        Аргументы:
            intervals: передает интервалы доступности объявления.
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            GET_INTERVALS,
            request=RealtyIntervalsRequest(
                item_id=item_id or int(self._require_item_id()),
                intervals=intervals,
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/realty/v1/items/{item_id}/base",
        spec="Краткосрочнаяаренда.json",
        operation_id="postBaseParams",
        method_args={"min_stay_days": "body.minimal_duration"},
    )
    def update_base_params(
        self,
        *,
        min_stay_days: int,
        item_id: int | str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyActionResult:
        """Обновляет base params для посутчной аренды.

        Аргументы:
            min_stay_days: задает минимальное число дней проживания.
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            UPDATE_BASE_PARAMS,
            path_params={"item_id": item_id or self._require_item_id()},
            request=RealtyBaseParamsUpdateRequest(min_stay_days=min_stay_days),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_item_id(self) -> str:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return str(self.item_id)


@dataclass(slots=True, frozen=True)
class RealtyBooking(DomainObject):
    """Доменный объект бронирований недвижимости."""

    __swagger_domain__ = "realty"
    __sdk_factory__ = "realty_booking"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/core/v1/accounts/{user_id}/items/{item_id}/bookings",
        spec="Краткосрочнаяаренда.json",
        operation_id="putBookingsInfo",
        method_args={"blocked_dates": "body.bookings"},
    )
    def update_bookings_info(
        self,
        *,
        blocked_dates: list[DateInput],
        user_id: int | str | None = None,
        item_id: int | str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyActionResult:
        """Обновляет информацию о бронированиях недвижимости.

        Аргументы:
            blocked_dates: передает заблокированные даты бронирования.
            user_id: идентифицирует пользователя или аккаунт Авито.
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            UPDATE_BOOKINGS_INFO,
            path_params={
                "user_id": user_id or self._require_user_id(),
                "item_id": item_id or self._require_item_id(),
            },
            request=RealtyBookingsUpdateRequest(
                blocked_dates=[
                    serialize_iso_date(f"blocked_dates[{index}]", blocked_date)
                    for index, blocked_date in enumerate(blocked_dates)
                ]
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "GET",
        "/realty/v1/accounts/{user_id}/items/{item_id}/bookings",
        spec="Краткосрочнаяаренда.json",
        operation_id="getRealtyBookings",
        method_args={"date_start": "query.date_start", "date_end": "query.date_end"},
    )
    def list_realty_bookings(
        self,
        *,
        date_start: DateInput,
        date_end: DateInput,
        with_unpaid: bool | None = None,
        user_id: int | str | None = None,
        item_id: int | str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyBookingsResult:
        """Возвращает список realty bookings для бронирований недвижимости.

        Аргументы:
            date_start: задает начальную дату периода бронирований.
            date_end: задает конечную дату периода бронирований.
            with_unpaid: включает неоплаченные бронирования в результат.
            user_id: идентифицирует пользователя или аккаунт Авито.
            item_id: идентифицирует объявление Авито.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyBookingsResult` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            LIST_REALTY_BOOKINGS,
            path_params={
                "user_id": user_id or self._require_user_id(),
                "item_id": item_id or self._require_item_id(),
            },
            query=RealtyBookingsQuery(
                date_start=serialize_iso_date("date_start", date_start),
                date_end=serialize_iso_date("date_end", date_end),
                with_unpaid=with_unpaid,
            ),
            timeout=timeout,
            retry=retry,
        )

    def _require_item_id(self) -> str:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return str(self.item_id)

    def _require_user_id(self) -> str:
        if self.user_id is None:
            raise ValidationError("Для операции требуется `user_id`.")
        return str(self.user_id)


@dataclass(slots=True, frozen=True)
class RealtyPricing(DomainObject):
    """Доменный объект цен краткосрочной аренды."""

    __swagger_domain__ = "realty"
    __sdk_factory__ = "realty_pricing"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/realty/v1/accounts/{user_id}/items/{item_id}/prices",
        spec="Краткосрочнаяаренда.json",
        operation_id="postRealtyPrices",
        method_args={"periods": "body.prices"},
    )
    def update_realty_prices(
        self,
        *,
        periods: list[RealtyPricePeriod],
        user_id: int | str | None = None,
        item_id: int | str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyActionResult:
        """Обновляет realty prices для цен недвижимости.

        Аргументы:
            periods: передает периоды цен.
            user_id: идентифицирует пользователя или аккаунт Авито.
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyActionResult` со статусом выполнения операции.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            UPDATE_REALTY_PRICES,
            path_params={
                "user_id": user_id or self._require_user_id(),
                "item_id": item_id or self._require_item_id(),
            },
            request=RealtyPricesUpdateRequest(periods=periods),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_item_id(self) -> str:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return str(self.item_id)

    def _require_user_id(self) -> str:
        if self.user_id is None:
            raise ValidationError("Для операции требуется `user_id`.")
        return str(self.user_id)


@dataclass(slots=True, frozen=True)
class RealtyAnalyticsReport(DomainObject):
    """Доменный объект аналитики по недвижимости."""

    __swagger_domain__ = "realty"
    __sdk_factory__ = "realty_analytics_report"
    __sdk_factory_args__ = {"item_id": "path.item_id", "user_id": "path.user_id"}

    item_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/realty/v1/marketPriceCorrespondence/{itemId}/{price}",
        spec="Аналитикапонедвижимости.json",
        operation_id="market_price_correspondence_v1",
        method_args={"price": "path.price"},
    )
    def get_market_price_correspondence(
        self,
        *,
        item_id: int | str | None = None,
        price: int | str,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyMarketPriceInfo:
        """Возвращает соответствие цены объявления рынку недвижимости.

        Аргументы:
            item_id: идентифицирует объявление Авито.
            price: передает цену для аналитического расчета.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyMarketPriceInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            GET_MARKET_PRICE_CORRESPONDENCE,
            path_params={
                "itemId": item_id or self._require_item_id(),
                "price": price,
            },
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "POST",
        "/realty/v1/report/create/{itemId}",
        spec="Аналитикапонедвижимости.json",
        operation_id="CreateReportForClassified",
    )
    def get_report_for_classified(
        self,
        *,
        item_id: int | str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> RealtyAnalyticsInfo:
        """Возвращает аналитический отчет по объявлению недвижимости.

        Аргументы:
            item_id: идентифицирует объявление Авито.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RealtyAnalyticsInfo` с типизированными данными ответа API.

        Поведение:
            Без `idempotency_key` write-вызов не повторяется при сетевых ошибках.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            GET_REPORT_FOR_CLASSIFIED,
            path_params={"itemId": item_id or self._require_item_id()},
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_item_id(self) -> str:
        if self.item_id is None:
            raise ValidationError("Для операции требуется `item_id`.")
        return str(self.item_id)


__all__ = (
    "RealtyAnalyticsReport",
    "RealtyBooking",
    "RealtyListing",
    "RealtyPricing",
)
