from __future__ import annotations

import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from inspect import iscoroutinefunction
from typing import ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

_WARNED_SYMBOLS: set[str] = set()


@dataclass(frozen=True, slots=True)
class DeprecatedSdkSymbol:
    """Metadata for public SDK symbols that emit runtime deprecation warnings."""

    symbol: str
    replacement: str
    removal_version: str
    deprecated_since: str


def warn_deprecated_once(
    *,
    symbol: str,
    replacement: str,
    removal_version: str,
    deprecated_since: str,
) -> None:
    if symbol in _WARNED_SYMBOLS:
        return
    _WARNED_SYMBOLS.add(symbol)
    warnings.warn(
        (
            f"`{symbol}` устарел с версии {deprecated_since}; "
            f"используйте `{replacement}`. "
            f"Удаление запланировано в версии {removal_version}."
        ),
        DeprecationWarning,
        stacklevel=3,
    )


def deprecated_method(
    *,
    symbol: str,
    replacement: str,
    removal_version: str,
    deprecated_since: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    metadata = DeprecatedSdkSymbol(
        symbol=symbol,
        replacement=replacement,
        removal_version=removal_version,
        deprecated_since=deprecated_since,
    )

    def decorate(method: Callable[P, R]) -> Callable[P, R]:
        if iscoroutinefunction(method):
            @wraps(method)
            async def async_wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                warn_deprecated_once(
                    symbol=symbol,
                    replacement=replacement,
                    removal_version=removal_version,
                    deprecated_since=deprecated_since,
                )
                async_method = cast(Callable[P, Awaitable[R]], method)
                return await async_method(*args, **kwargs)

            async_wrapped.__sdk_deprecation__ = metadata  # type: ignore[attr-defined]
            return async_wrapped  # type: ignore[return-value]

        @wraps(method)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            warn_deprecated_once(
                symbol=symbol,
                replacement=replacement,
                removal_version=removal_version,
                deprecated_since=deprecated_since,
            )
            return method(*args, **kwargs)

        wrapped.__sdk_deprecation__ = metadata  # type: ignore[attr-defined]
        return wrapped

    return decorate
