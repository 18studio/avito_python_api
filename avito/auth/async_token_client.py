"""Async OAuth token-flow clients."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from avito.auth._cache import map_token_response
from avito.auth.models import ClientCredentialsRequest, RefreshTokenRequest, TokenResponse
from avito.auth.provider import CLIENT_CREDENTIALS_GRANT, REFRESH_TOKEN_GRANT
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.async_transport import AsyncTransport
from avito.core.exceptions import AuthenticationError, AvitoError
from avito.core.swagger import swagger_operation
from avito.core.types import RequestContext


@dataclass(slots=True, frozen=True)
class AsyncTokenClient:
    """Служебный async-клиент для canonical OAuth token endpoint."""

    __swagger_domain__ = "auth"

    settings: AuthSettings
    token_url: str | None = None
    client: httpx.AsyncClient | None = None
    sdk_settings: AvitoSettings | None = None

    async def aclose(self) -> None:
        """Закрывает выделенный HTTP-клиент, если он был передан снаружи."""

        if self.client is not None:
            await self.client.aclose()

    @swagger_operation(
        "POST",
        "/token",
        spec="Авторизация.json",
        operation_id="getAccessToken",
        method_args={"request": "body"},
        variant="async",
    )
    async def request_client_credentials_token(
        self,
        request: ClientCredentialsRequest,
    ) -> TokenResponse:
        """Запрашивает access token по flow `client_credentials`."""

        payload: dict[str, str] = {
            "grant_type": CLIENT_CREDENTIALS_GRANT,
            "client_id": request.client_id,
            "client_secret": request.client_secret,
        }
        if request.scope is not None:
            payload["scope"] = request.scope
        return await self._request_token(payload)

    @swagger_operation(
        "POST",
        "/token",
        spec="Автотека.json",
        operation_id="getAccessToken",
        method_args={"request": "query.grant_type"},
        variant="async",
    )
    async def request_autoteka_client_credentials_token(
        self,
        request: ClientCredentialsRequest,
    ) -> TokenResponse:
        """Запрашивает access token по отдельному flow Автотеки."""

        return await self.request_client_credentials_token(request)

    async def request_refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """Запрашивает новый access token по flow `refresh_token`."""

        payload: dict[str, str] = {
            "grant_type": REFRESH_TOKEN_GRANT,
            "client_id": request.client_id,
            "client_secret": request.client_secret,
            "refresh_token": request.refresh_token,
        }
        if request.scope is not None:
            payload["scope"] = request.scope
        return await self._request_token(payload)

    async def _request_token(self, payload: dict[str, str]) -> TokenResponse:
        """Run the request token helper."""
        transport = AsyncTransport(
            self.sdk_settings or AvitoSettings(auth=self.settings),
            auth_provider=None,
            client=self.client,
        )
        try:
            response = await transport.request(
                "POST",
                self.token_url or self.settings.token_url,
                context=RequestContext("auth.oauth_token", requires_auth=False),
                data=payload,
                headers={"Accept": "application/json"},
            )
        except AuthenticationError:
            raise
        except AvitoError as exc:
            raise AuthenticationError(
                exc.message,
                status_code=exc.status_code,
                error_code=exc.error_code,
                operation=exc.operation,
                attempt=exc.attempt,
                method=exc.method,
                endpoint=exc.endpoint,
                details=exc.details,
                retry_after=exc.retry_after,
                request_id=exc.request_id,
                metadata=exc.metadata,
                payload=exc.payload,
                headers=exc.headers,
            ) from exc
        finally:
            if self.client is None:
                await transport.aclose()

        try:
            payload_object = response.json()
        except ValueError as exc:
            raise AuthenticationError(
                "OAuth-сервер вернул некорректный JSON.",
                status_code=response.status_code,
                payload=response.text,
                headers=dict(response.headers),
            ) from exc
        return map_token_response(payload_object)


@dataclass(slots=True, frozen=True)
class AsyncAlternateTokenClient:
    """Служебный async-клиент для альтернативного token endpoint из swagger."""

    __swagger_domain__ = "auth"

    settings: AuthSettings
    client: httpx.AsyncClient | None = None
    sdk_settings: AvitoSettings | None = None

    async def aclose(self) -> None:
        """Закрывает выделенный HTTP-клиент альтернативного token flow."""

        if self.client is not None:
            await self.client.aclose()

    @swagger_operation(
        "POST",
        "/token\u200e",
        spec="Авторизация.json",
        operation_id="getAccessTokenAuthorizationCode",
        method_args={"request": "body"},
        variant="async",
    )
    async def request_client_credentials_token(
        self,
        request: ClientCredentialsRequest,
    ) -> TokenResponse:
        """Запрашивает токен через альтернативный canonical `/token`."""

        return await AsyncTokenClient(
            self.settings,
            token_url=self.settings.alternate_token_url,
            client=self.client,
            sdk_settings=self.sdk_settings,
        ).request_client_credentials_token(request)

    @swagger_operation(
        "POST",
        "/token\u200e\u200e",
        spec="Авторизация.json",
        operation_id="refreshAccessTokenAuthorizationCode",
        method_args={"request": "body"},
        variant="async",
    )
    async def request_refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """Обновляет токен через альтернативный canonical `/token`."""

        return await AsyncTokenClient(
            self.settings,
            token_url=self.settings.alternate_token_url,
            client=self.client,
            sdk_settings=self.sdk_settings,
        ).request_refresh_token(request)


__all__ = ("AsyncAlternateTokenClient", "AsyncTokenClient")
