"""Провайдеры аутентификации и token-flow для SDK Avito."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx

from avito.auth.models import (
    AccessToken,
    ClientCredentialsRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.exceptions import (
    AuthenticationError,
    AvitoError,
    ConfigurationError,
    ResponseMappingError,
)
from avito.core.swagger import swagger_operation
from avito.core.transport import Transport
from avito.core.types import RequestContext

CLIENT_CREDENTIALS_GRANT = "client_credentials"
REFRESH_TOKEN_GRANT = "refresh_token"

_UNSET = object()


def _map_token_response(payload: object, *, now: datetime | None = None) -> TokenResponse:
    if not isinstance(payload, dict):
        raise ResponseMappingError("OAuth-ответ должен быть JSON-объектом.", payload=payload)

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ResponseMappingError("В OAuth-ответе отсутствует `access_token`.", payload=payload)

    raw_expires_in = payload.get("expires_in", 0)
    if not isinstance(raw_expires_in, int | float) or isinstance(raw_expires_in, bool):
        raise ResponseMappingError("Поле `expires_in` должно быть числом.", payload=payload)

    refresh_token = payload.get("refresh_token")
    if refresh_token is not None and not isinstance(refresh_token, str):
        raise ResponseMappingError("Поле `refresh_token` должно быть строкой.", payload=payload)

    token_type = payload.get("token_type", "Bearer")
    if not isinstance(token_type, str):
        raise ResponseMappingError("Поле `token_type` должно быть строкой.", payload=payload)

    issued_at = now or datetime.now(UTC)
    return TokenResponse(
        access_token=AccessToken(
            value=access_token,
            expires_at=issued_at + timedelta(seconds=raw_expires_in),
            token_type=token_type,
        ),
        refresh_token=refresh_token,
        scope=payload.get("scope") if isinstance(payload.get("scope"), str) else None,
    )


class TokenFetcher(Protocol):
    """Контракт получения нового access token из внешнего источника."""

    def __call__(self, settings: AuthSettings) -> TokenResponse: ...


@dataclass(slots=True)
class AuthProvider:
    """Поставляет и кэширует токен доступа для transport-слоя."""

    settings: AuthSettings
    token_client: TokenClient | None = None
    alternate_token_client: AlternateTokenClient | None = None
    autoteka_token_client: TokenClient | None = None
    token_fetcher: TokenFetcher | None = None
    _access_token: AccessToken | None = field(default=None, init=False, repr=False)
    _refresh_token: str | None = field(default=None, init=False, repr=False)
    _autoteka_access_token: AccessToken | None = field(default=None, init=False, repr=False)

    def get_access_token(self) -> str:
        """Возвращает валидный access token, обновляя кэш при необходимости."""

        token = self._access_token
        now = datetime.now(UTC)
        if token is None or token.is_expired(now):
            token = self.refresh_access_token().access_token
        return token.value

    def refresh_access_token(self) -> TokenResponse:
        """Принудительно обновляет токен через refresh token или client credentials."""

        token_response = self._fetch_token_response()
        self._update_tokens(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
        )
        return token_response

    def invalidate_token(self) -> None:
        """Сбрасывает закэшированный токен после `401 Unauthorized`."""

        self._update_tokens(access_token=None)

    def close(self) -> None:
        """Закрывает внутренние HTTP-клиенты provider-а."""

        for client in (self.token_client, self.alternate_token_client, self.autoteka_token_client):
            if client is not None:
                client.close()

    def get_autoteka_access_token(self) -> str:
        """Возвращает отдельный access token для flow Автотеки."""

        token = self._autoteka_access_token
        now = datetime.now(UTC)
        if token is None or token.is_expired(now):
            token_response = (
                self._get_autoteka_token_client().request_autoteka_client_credentials_token(
                    ClientCredentialsRequest(
                        client_id=self.settings.autoteka_client_id or self.settings.client_id or "",
                        client_secret=self.settings.autoteka_client_secret
                        or self.settings.client_secret
                        or "",
                        scope=self.settings.autoteka_scope,
                    )
                )
            )
            self._update_tokens(autoteka_access_token=token_response.access_token)
            token = token_response.access_token
        return token.value

    def token_flow(self) -> TokenClient:
        """Возвращает canonical token client для low-level OAuth операций."""

        return self._get_token_client()

    def alternate_token_flow(self) -> AlternateTokenClient:
        """Возвращает дополнительный token client для альтернативного `/token` flow."""

        return self._get_alternate_token_client()

    def _fetch_token_response(self) -> TokenResponse:
        if self.token_fetcher is not None:
            token_response = self.token_fetcher(self.settings)
            if isinstance(token_response, AccessToken):
                return TokenResponse(access_token=token_response)
            return token_response
        if self._refresh_token:
            return self._get_token_client().request_refresh_token(
                RefreshTokenRequest(
                    client_id=self._require_client_id(),
                    client_secret=self._require_client_secret(),
                    refresh_token=self._refresh_token,
                    scope=self.settings.scope,
                )
            )
        if self.settings.refresh_token:
            return self._get_token_client().request_refresh_token(
                RefreshTokenRequest(
                    client_id=self._require_client_id(),
                    client_secret=self._require_client_secret(),
                    refresh_token=self.settings.refresh_token,
                    scope=self.settings.scope,
                )
            )
        return self._get_token_client().request_client_credentials_token(
            ClientCredentialsRequest(
                client_id=self._require_client_id(),
                client_secret=self._require_client_secret(),
                scope=self.settings.scope,
            )
        )

    def _update_tokens(
        self,
        *,
        access_token: AccessToken | None | object = _UNSET,
        refresh_token: str | None | object = _UNSET,
        autoteka_access_token: AccessToken | None | object = _UNSET,
    ) -> None:
        if access_token is not _UNSET:
            self._access_token = access_token if isinstance(access_token, AccessToken) else None
        if refresh_token is not _UNSET:
            if isinstance(refresh_token, str):
                self._refresh_token = refresh_token
        if autoteka_access_token is not _UNSET:
            self._autoteka_access_token = (
                autoteka_access_token if isinstance(autoteka_access_token, AccessToken) else None
            )

    def _get_token_client(self) -> TokenClient:
        if self.token_client is None:
            self.token_client = TokenClient(self.settings)
        token_client = self.token_client
        if token_client is None:
            raise ConfigurationError("Не удалось инициализировать OAuth token client.")
        return token_client

    def _get_alternate_token_client(self) -> AlternateTokenClient:
        if self.alternate_token_client is None:
            self.alternate_token_client = AlternateTokenClient(self.settings)
        alternate_token_client = self.alternate_token_client
        if alternate_token_client is None:
            raise ConfigurationError("Не удалось инициализировать alternate OAuth token client.")
        return alternate_token_client

    def _get_autoteka_token_client(self) -> TokenClient:
        if self.autoteka_token_client is None:
            self.autoteka_token_client = TokenClient(
                self.settings,
                token_url=self.settings.autoteka_token_url,
            )
        autoteka_token_client = self.autoteka_token_client
        if autoteka_token_client is None:
            raise ConfigurationError("Не удалось инициализировать OAuth token client для Автотеки.")
        return autoteka_token_client

    def _require_client_id(self) -> str:
        if self.settings.client_id is None:
            raise AuthenticationError("Для OAuth flow не задан `client_id`.")
        return self.settings.client_id

    def _require_client_secret(self) -> str:
        if self.settings.client_secret is None:
            raise AuthenticationError("Для OAuth flow не задан `client_secret`.")
        return self.settings.client_secret


@dataclass(slots=True, frozen=True)
class TokenClient:
    """Служебный клиент для canonical OAuth token endpoint."""

    __swagger_domain__ = "auth"

    settings: AuthSettings
    token_url: str | None = None
    client: httpx.Client | None = None
    sdk_settings: AvitoSettings | None = None

    def close(self) -> None:
        """Закрывает выделенный HTTP-клиент, если он был передан снаружи."""

        if self.client is not None:
            self.client.close()

    @swagger_operation(
        "POST",
        "/token",
        spec="Авторизация.json",
        operation_id="getAccessToken",
        method_args={"request": "body"},
    )
    def request_client_credentials_token(
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
        return self._request_token(payload)

    @swagger_operation(
        "POST",
        "/token",
        spec="Автотека.json",
        operation_id="getAccessToken",
        method_args={"request": "query.grant_type"},
    )
    def request_autoteka_client_credentials_token(
        self,
        request: ClientCredentialsRequest,
    ) -> TokenResponse:
        """Запрашивает access token по отдельному flow Автотеки."""

        return self.request_client_credentials_token(request)

    def request_refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """Запрашивает новый access token по flow `refresh_token`."""

        payload: dict[str, str] = {
            "grant_type": REFRESH_TOKEN_GRANT,
            "client_id": request.client_id,
            "client_secret": request.client_secret,
            "refresh_token": request.refresh_token,
        }
        if request.scope is not None:
            payload["scope"] = request.scope
        return self._request_token(payload)

    def _request_token(self, payload: dict[str, str]) -> TokenResponse:
        transport = self._build_transport()
        try:
            response = transport.request(
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
                transport.close()

        try:
            payload_object = response.json()
        except ValueError as exc:
            raise AuthenticationError(
                "OAuth-сервер вернул некорректный JSON.",
                status_code=response.status_code,
                payload=response.text,
                headers=dict(response.headers),
            ) from exc
        return _map_token_response(payload_object)

    def _build_transport(self) -> Transport:
        return Transport(
            self.sdk_settings or AvitoSettings(auth=self.settings),
            auth_provider=None,
            client=self.client,
        )


@dataclass(slots=True, frozen=True)
class AlternateTokenClient:
    """Служебный клиент для альтернативного token endpoint из swagger."""

    __swagger_domain__ = "auth"

    settings: AuthSettings
    client: httpx.Client | None = None
    sdk_settings: AvitoSettings | None = None

    def close(self) -> None:
        """Закрывает выделенный HTTP-клиент альтернативного token flow."""

        if self.client is not None:
            self.client.close()

    @swagger_operation(
        "POST",
        "/token\u200e",
        spec="Авторизация.json",
        operation_id="getAccessTokenAuthorizationCode",
        method_args={"request": "body"},
    )
    def request_client_credentials_token(
        self,
        request: ClientCredentialsRequest,
    ) -> TokenResponse:
        """Запрашивает токен через альтернативный canonical `/token`."""

        return TokenClient(
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
    )
    def request_refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """Обновляет токен через альтернативный canonical `/token`."""

        return TokenClient(
            self.settings,
            token_url=self.settings.alternate_token_url,
            client=self.client,
            sdk_settings=self.sdk_settings,
        ).request_refresh_token(request)


__all__ = ("AlternateTokenClient", "AuthProvider", "TokenClient", "TokenFetcher")
