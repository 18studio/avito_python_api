from __future__ import annotations

import httpx
import pytest

from avito import AuthSettings, AvitoClient, AvitoSettings
from avito.auth import AuthProvider
from avito.core import ClientClosedError, Transport


def test_closed_client_raises_lifecycle_error_without_http_request() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={})

    settings = AvitoSettings(
        auth=AuthSettings(client_id="client-id", client_secret="client-secret")
    )
    client = AvitoClient._from_transport(
        settings,
        transport=Transport(
            settings,
            auth_provider=None,
            client=httpx.Client(
                transport=httpx.MockTransport(handler),
                base_url="https://api.avito.ru",
            ),
        ),
        auth_provider=AuthProvider(settings.auth),
    )

    client.close()

    with pytest.raises(ClientClosedError, match="Клиент закрыт"):
        client.account().get_self()

    assert calls["count"] == 0
