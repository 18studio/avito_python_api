"""Локальный rate limiter transport-слоя."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping

from avito.core._transport_shared import RateLimitState
from avito.core.retries import RetryPolicy


class RateLimiter:
    """Token bucket для превентивного ограничения частоты запросов."""

    def __init__(
        self,
        policy: RetryPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._state = RateLimitState.from_policy(policy, now=clock())
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Ждёт, пока запрос можно безопасно отправить, и возвращает задержку."""

        total_delay = 0.0
        while True:
            delay = self._reserve_or_delay()
            if delay <= 0.0:
                return total_delay
            self._sleep(delay)
            total_delay += delay

    def observe_response(self, *, headers: Mapping[str, str]) -> None:
        """Обновляет локальный cooldown по rate-limit headers upstream API."""

        with self._lock:
            self._state.observe_response(now=self._clock(), headers=headers)

    def _reserve_or_delay(self) -> float:
        with self._lock:
            return self._state.compute_delay(self._clock())


__all__ = ("RateLimiter",)
