"""Async fake transport and helpers for SDK tests."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Mapping
from typing import cast

import httpx

from avito.async_client import AsyncAvitoClient
from avito.auth import AuthSettings
from avito.auth.async_provider import AsyncAuthProvider
from avito.auth.async_token_client import AsyncAlternateTokenClient, AsyncTokenClient
from avito.config import AvitoSettings
from avito.core.async_transport import AsyncTransport
from avito.core.retries import RetryPolicy
from avito.core.types import ApiTimeouts
from avito.testing.fake_transport import JsonValue, RecordedRequest, RouteResponder


class AsyncFakeTransport:
    """Deterministic async fake transport for SDK contract tests."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.avito.ru",
        fanout_recorder: FanoutPeakRecorder | None = None,
    ) -> None:
        """Initialize AsyncFakeTransport."""
        self.base_url = base_url.rstrip("/")
        self.requests: list[RecordedRequest] = []
        self._routes: dict[tuple[str, str], deque[RouteResponder]] = {}
        self._handle_lock = asyncio.Lock()
        self._fanout_recorder = fanout_recorder

    def add(self, method: str, path: str, *responses: RouteResponder) -> AsyncFakeTransport:
        """Регистрирует один или несколько ответов для HTTP-маршрута."""

        key = (method.upper(), path)
        bucket = self._routes.setdefault(key, deque())
        bucket.extend(responses)
        return self

    def add_json(
        self,
        method: str,
        path: str,
        payload: JsonValue,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncFakeTransport:
        """Регистрирует JSON-ответ для HTTP-маршрута."""

        return self.add(method, path, httpx.Response(status_code, json=payload, headers=headers))

    def build(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        user_id: int | None = None,
        authenticated: bool = False,
        auth_settings: AuthSettings | None = None,
    ) -> AsyncTransport:
        """Создаёт низкоуровневый AsyncTransport поверх fake transport."""

        settings, auth_provider, http_client = self._build_parts(
            retry_policy=retry_policy,
            user_id=user_id,
            authenticated=authenticated,
            auth_settings=auth_settings,
        )
        return AsyncTransport(
            settings,
            auth_provider=auth_provider,
            client=http_client,
            sleep=lambda _: asyncio.sleep(0),
        )

    def as_client(
        self,
        *,
        user_id: int | None = None,
        retry_policy: RetryPolicy | None = None,
        authenticated: bool = False,
        auth_settings: AuthSettings | None = None,
    ) -> AsyncAvitoClient:
        """Создает публичный `AsyncAvitoClient` поверх fake transport."""

        settings, auth_provider, http_client = self._build_parts(
            retry_policy=retry_policy,
            user_id=user_id,
            authenticated=authenticated,
            auth_settings=auth_settings,
        )
        transport = AsyncTransport(
            settings,
            auth_provider=auth_provider,
            client=http_client,
            sleep=lambda _: asyncio.sleep(0),
        )
        return AsyncAvitoClient._from_transport(
            settings,
            transport=transport,
            auth_provider=auth_provider or AsyncAuthProvider(settings.auth),
        )

    def count(self, *, method: str | None = None, path: str | None = None) -> int:
        """Возвращает число перехваченных запросов с опциональной фильтрацией."""

        return len(
            [
                request
                for request in self.requests
                if (method is None or request.method == method.upper())
                and (path is None or request.path == path)
            ]
        )

    def last(self, *, method: str | None = None, path: str | None = None) -> RecordedRequest:
        """Возвращает последний перехваченный запрос с опциональной фильтрацией."""

        matches = [
            request
            for request in self.requests
            if (method is None or request.method == method.upper())
            and (path is None or request.path == path)
        ]
        if not matches:
            raise AssertionError(f"No requests matched method={method!r} path={path!r}")
        return matches[-1]

    def _build_parts(
        self,
        *,
        retry_policy: RetryPolicy | None,
        user_id: int | None,
        authenticated: bool,
        auth_settings: AuthSettings | None,
    ) -> tuple[AvitoSettings, AsyncAuthProvider | None, httpx.AsyncClient]:
        """Build parts."""
        resolved_auth = auth_settings or AuthSettings(
            client_id="fake-client-id",
            client_secret="fake-client-secret",
        )
        settings = AvitoSettings(
            base_url=self.base_url,
            user_id=user_id,
            auth=resolved_auth,
            retry_policy=retry_policy or RetryPolicy(),
            timeouts=ApiTimeouts(),
        )
        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(self._handle),
            base_url=self.base_url,
        )
        auth_provider = None
        if authenticated:
            auth_provider = AsyncAuthProvider(
                resolved_auth,
                token_client=AsyncTokenClient(
                    resolved_auth,
                    client=http_client,
                    sdk_settings=settings,
                ),
                alternate_token_client=AsyncAlternateTokenClient(
                    resolved_auth,
                    client=http_client,
                    sdk_settings=settings,
                ),
                autoteka_token_client=AsyncTokenClient(
                    resolved_auth,
                    token_url=resolved_auth.autoteka_token_url,
                    client=http_client,
                    sdk_settings=settings,
                ),
            )
        return settings, auth_provider, http_client

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        """Handle handle."""
        if self._fanout_recorder is not None:
            await self._fanout_recorder.enter()
        try:
            return await self._handle_recorded(request)
        finally:
            if self._fanout_recorder is not None:
                await self._fanout_recorder.exit()

    async def _handle_recorded(self, request: httpx.Request) -> httpx.Response:
        """Handle recorded."""
        async with self._handle_lock:
            recorded = RecordedRequest(
                method=request.method.upper(),
                path=request.url.path,
                params=dict(request.url.params),
                headers=dict(request.headers),
                json_body=self._decode_json(request),
                content=request.content,
            )
            self.requests.append(recorded)
            key = (recorded.method, recorded.path)
            if key not in self._routes:
                available = ", ".join(f"{method} {path}" for method, path in sorted(self._routes))
                raise AssertionError(
                    "Маршрут не прописан в AsyncFakeTransport: "
                    f"{recorded.method} {recorded.path}. "
                    f"Добавьте route_sequence или add_json для этого пути. Доступные: {available}"
                )
            responders = self._routes[key]
            responder = responders[0] if len(responders) == 1 else responders.popleft()
            response = responder(recorded) if callable(responder) else responder
            response.request = request
            return response

    @staticmethod
    def _decode_json(request: httpx.Request) -> JsonValue:
        """Decode json."""
        if not request.content:
            return None
        try:
            return cast(JsonValue, json.loads(request.content.decode()))
        except json.JSONDecodeError:
            return None


class FanoutPeakRecorder:
    """Считает пик одновременно выполняющихся async fake-запросов."""

    def __init__(self) -> None:
        """Initialize FanoutPeakRecorder."""
        self._lock = asyncio.Lock()
        self._active = 0
        self.peak = 0

    async def enter(self) -> None:
        """Record fan-out enter event."""
        async with self._lock:
            self._active += 1
            self.peak = max(self.peak, self._active)

    async def exit(self) -> None:
        """Record fan-out exit event."""
        async with self._lock:
            self._active -= 1


__all__ = ("AsyncFakeTransport", "FanoutPeakRecorder")
