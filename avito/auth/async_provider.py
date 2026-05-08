"""Async authentication provider for the SDK."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from avito.auth._cache import TokenCache
from avito.auth.async_token_client import AsyncAlternateTokenClient, AsyncTokenClient
from avito.auth.models import (
    AccessToken,
    ClientCredentialsRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from avito.auth.settings import AuthSettings
from avito.core.exceptions import AuthenticationError, ConfigurationError


class AsyncTokenFetcher(Protocol):
    """Контракт async-получения нового access token из внешнего источника."""

    async def __call__(self, settings: AuthSettings) -> TokenResponse:
        """Fetch a token payload."""
        ...


@dataclass(slots=True)
class AsyncAuthProvider:
    """Поставляет и кэширует токен доступа для async transport-слоя."""

    settings: AuthSettings
    token_client: AsyncTokenClient | None = None
    alternate_token_client: AsyncAlternateTokenClient | None = None
    autoteka_token_client: AsyncTokenClient | None = None
    token_fetcher: AsyncTokenFetcher | None = None
    _cache: TokenCache = field(default_factory=TokenCache, init=False, repr=False)
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _autoteka_refresh_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    async def get_access_token(self) -> str:
        """Возвращает валидный access token, обновляя кэш при необходимости."""

        now = datetime.now(UTC)
        if not self._cache.access_is_fresh(now):
            async with self._refresh_lock:
                now = datetime.now(UTC)
                if not self._cache.access_is_fresh(now):
                    token_response = await self.refresh_access_token()
                    return token_response.access_token.value
        access_token = self._cache.access_token
        if access_token is None:
            raise AuthenticationError("Не удалось получить OAuth access token.")
        return access_token.value

    async def refresh_access_token(self) -> TokenResponse:
        """Принудительно обновляет токен через refresh token или client credentials."""

        token_response = await self._fetch_token_response()
        self._cache.access_token = token_response.access_token
        if token_response.refresh_token is not None:
            self._cache.refresh_token = token_response.refresh_token
        return token_response

    def invalidate_token(self) -> None:
        """Сбрасывает закэшированный токен после `401 Unauthorized`."""

        self._cache.reset_access()

    async def aclose(self) -> None:
        """Закрывает внутренние HTTP-клиенты provider-а."""

        for client in (self.token_client, self.alternate_token_client, self.autoteka_token_client):
            if client is not None:
                await client.aclose()

    async def get_autoteka_access_token(self) -> str:
        """Возвращает отдельный access token для flow Автотеки."""

        now = datetime.now(UTC)
        if not self._cache.autoteka_is_fresh(now):
            async with self._autoteka_refresh_lock:
                now = datetime.now(UTC)
                if not self._cache.autoteka_is_fresh(now):
                    token_response = (
                        await self._get_autoteka_token_client().request_autoteka_client_credentials_token(
                            ClientCredentialsRequest(
                                client_id=self.settings.autoteka_client_id
                                or self.settings.client_id
                                or "",
                                client_secret=self.settings.autoteka_client_secret
                                or self.settings.client_secret
                                or "",
                                scope=self.settings.autoteka_scope,
                            )
                        )
                    )
                    self._cache.autoteka_access_token = token_response.access_token
        token = self._cache.autoteka_access_token
        if token is None:
            raise AuthenticationError("Не удалось получить OAuth access token для Автотеки.")
        return token.value

    def token_flow(self) -> AsyncTokenClient:
        """Возвращает canonical async token client для low-level OAuth операций."""

        return self._get_token_client()

    def alternate_token_flow(self) -> AsyncAlternateTokenClient:
        """Возвращает дополнительный async token client для альтернативного `/token` flow."""

        return self._get_alternate_token_client()

    async def _fetch_token_response(self) -> TokenResponse:
        """Fetch token response."""
        if self.token_fetcher is not None:
            token_response = await self.token_fetcher(self.settings)
            if isinstance(token_response, AccessToken):
                return TokenResponse(access_token=token_response)
            return token_response
        if self._cache.refresh_token:
            return await self._get_token_client().request_refresh_token(
                RefreshTokenRequest(
                    client_id=self._require_client_id(),
                    client_secret=self._require_client_secret(),
                    refresh_token=self._cache.refresh_token,
                    scope=self.settings.scope,
                )
            )
        if self.settings.refresh_token:
            return await self._get_token_client().request_refresh_token(
                RefreshTokenRequest(
                    client_id=self._require_client_id(),
                    client_secret=self._require_client_secret(),
                    refresh_token=self.settings.refresh_token,
                    scope=self.settings.scope,
                )
            )
        return await self._get_token_client().request_client_credentials_token(
            ClientCredentialsRequest(
                client_id=self._require_client_id(),
                client_secret=self._require_client_secret(),
                scope=self.settings.scope,
            )
        )

    def _get_token_client(self) -> AsyncTokenClient:
        """Return token client."""
        if self.token_client is None:
            self.token_client = AsyncTokenClient(self.settings)
        if self.token_client is None:
            raise ConfigurationError("Не удалось инициализировать OAuth token client.")
        return self.token_client

    def _get_alternate_token_client(self) -> AsyncAlternateTokenClient:
        """Return alternate token client."""
        if self.alternate_token_client is None:
            self.alternate_token_client = AsyncAlternateTokenClient(self.settings)
        if self.alternate_token_client is None:
            raise ConfigurationError("Не удалось инициализировать alternate OAuth token client.")
        return self.alternate_token_client

    def _get_autoteka_token_client(self) -> AsyncTokenClient:
        """Return autoteka token client."""
        if self.autoteka_token_client is None:
            self.autoteka_token_client = AsyncTokenClient(
                self.settings,
                token_url=self.settings.autoteka_token_url,
            )
        if self.autoteka_token_client is None:
            raise ConfigurationError("Не удалось инициализировать OAuth token client для Автотеки.")
        return self.autoteka_token_client

    def _require_client_id(self) -> str:
        """Validate required client id."""
        if self.settings.client_id is None:
            raise AuthenticationError("Для OAuth flow не задан `client_id`.")
        return self.settings.client_id

    def _require_client_secret(self) -> str:
        """Validate required client secret."""
        if self.settings.client_secret is None:
            raise AuthenticationError("Для OAuth flow не задан `client_secret`.")
        return self.settings.client_secret


__all__ = ("AsyncAuthProvider", "AsyncTokenFetcher")
