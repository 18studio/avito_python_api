"""Async rate limiter for the transport layer."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping

from avito.core._transport_shared import RateLimitState
from avito.core.retries import RetryPolicy


class AsyncRateLimiter:
    """Async token bucket over shared `RateLimitState`."""

    def __init__(
        self,
        policy: RetryPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._state = RateLimitState.from_policy(policy, now=clock())
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Wait until a request may be sent and return the total delay."""

        total_delay = 0.0
        async with self._lock:
            while True:
                delay = self._state.compute_delay(self._clock())
                if delay <= 0.0:
                    return total_delay
                await self._sleep(delay)
                total_delay += delay

    def observe_response(self, *, headers: Mapping[str, str]) -> None:
        """Update cooldown from response headers."""

        self._state.observe_response(now=self._clock(), headers=headers)


__all__ = ("AsyncRateLimiter",)
