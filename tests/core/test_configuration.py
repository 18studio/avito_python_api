from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from avito import AvitoClient
from avito.auth import AuthSettings
from avito.config import AvitoSettings
from avito.core.exceptions import ConfigurationError

ENV_KEYS = (
    "AVITO_BASE_URL",
    "AVITO_USER_ID",
    "AVITO_USER_AGENT_SUFFIX",
    "AVITO_CLIENT_ID",
    "AVITO_CLIENT_SECRET",
    "AVITO_SECRET",
    "AVITO_REFRESH_TOKEN",
)


def clear_avito_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def write_env_file(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_avito_settings_from_env_reads_full_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_BASE_URL=https://sandbox.avito.ru",
                "AVITO_USER_ID=42",
                "AVITO_USER_AGENT_SUFFIX=ci/contract-tests",
                "AVITO_CLIENT_ID=client-id",
                "AVITO_CLIENT_SECRET=client-secret",
                "AVITO_REFRESH_TOKEN=refresh-token",
            )
        ),
    )

    settings = AvitoSettings.from_env(env_file=env_file)

    assert settings.base_url == "https://sandbox.avito.ru"
    assert settings.user_id == 42
    assert settings.user_agent_suffix == "ci/contract-tests"
    assert settings.auth.client_id == "client-id"
    assert settings.auth.client_secret == "client-secret"
    assert settings.auth.refresh_token == "refresh-token"


def test_avito_settings_from_env_reads_from_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_BASE_URL=https://file.avito.ru",
                "AVITO_USER_ID=77",
                "AVITO_CLIENT_ID=file-client-id",
                "AVITO_CLIENT_SECRET=file-client-secret",
            )
        ),
    )

    settings = AvitoSettings.from_env(env_file=env_file)

    assert settings.base_url == "https://file.avito.ru"
    assert settings.user_id == 77
    assert settings.auth.client_id == "file-client-id"
    assert settings.auth.client_secret == "file-client-secret"


def test_avito_settings_from_env_requires_explicit_auth_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)

    with pytest.raises(ConfigurationError, match="client_id"):
        AvitoSettings.from_env(env_file=write_env_file(tmp_path / ".env", "AVITO_CLIENT_SECRET=x"))

    clear_avito_env(monkeypatch)
    with pytest.raises(ConfigurationError, match="client_secret"):
        AvitoSettings.from_env(env_file=write_env_file(tmp_path / ".env", "AVITO_CLIENT_ID=x"))


def test_avito_settings_from_env_accepts_avito_secret_alias_with_deprecation_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_CLIENT_ID=client-id",
                "AVITO_SECRET=legacy-secret",
            )
        ),
    )

    with pytest.deprecated_call(match="AVITO_SECRET"):
        settings = AvitoSettings.from_env(env_file=env_file)

    assert settings.auth.client_secret == "legacy-secret"


def test_avito_settings_from_env_prefers_documented_client_secret_without_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_CLIENT_ID=client-id",
                "AVITO_CLIENT_SECRET=client-secret",
                "AVITO_SECRET=legacy-secret",
            )
        ),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        settings = AvitoSettings.from_env(env_file=env_file)

    assert settings.auth.client_secret == "client-secret"


def test_auth_settings_supported_env_vars_excludes_deprecated_secret_alias() -> None:
    supported = AuthSettings.supported_env_vars()

    assert supported["client_secret"] == ("AVITO_CLIENT_SECRET",)


def test_avito_settings_from_env_ignores_unsupported_generic_aliases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "BASE_URL=https://generic.avito.ru",
                "USER_ID=77",
                "CLIENT_ID=generic-client-id",
                "SECRET=generic-client-secret",
            )
        ),
    )

    with pytest.raises(ConfigurationError, match="client_id"):
        AvitoSettings.from_env(env_file=env_file)


def test_avito_client_from_env_initializes_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_BASE_URL=https://sandbox.avito.ru",
                "AVITO_USER_ID=512",
                "AVITO_CLIENT_ID=client-id",
                "AVITO_CLIENT_SECRET=client-secret",
            )
        ),
    )

    client = AvitoClient.from_env(env_file=env_file)
    try:
        assert client.settings.base_url == "https://sandbox.avito.ru"
        assert client.settings.user_id == 512
        assert client.settings.auth.client_id == "client-id"
        assert client.settings.auth.client_secret == "client-secret"
    finally:
        client.close()


def test_explicit_settings_do_not_implicitly_read_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "from-process-env")

    settings = AvitoSettings(auth=AuthSettings(client_id="client-id"))

    assert settings.auth.client_secret is None


def test_process_environment_overrides_dotenv_and_parses_retry_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_avito_env(monkeypatch)
    env_file = write_env_file(
        tmp_path / ".env",
        "\n".join(
            (
                "AVITO_BASE_URL=https://from-file.avito.ru",
                "AVITO_CLIENT_ID=file-client-id",
                "AVITO_CLIENT_SECRET=file-client-secret",
                "AVITO_TIMEOUT_CONNECT=2.5",
                "AVITO_TIMEOUT_READ=11",
                "AVITO_RETRY_MAX_ATTEMPTS=4",
                "AVITO_RETRY_BACKOFF_FACTOR=0.75",
                "AVITO_RETRY_MAX_DELAY=9.5",
                "AVITO_RETRY_RETRYABLE_METHODS=GET,POST,PATCH",
                "AVITO_RETRY_RETRY_ON_RATE_LIMIT=false",
                "AVITO_RETRY_MAX_RATE_LIMIT_WAIT_SECONDS=12.5",
                "AVITO_RATE_LIMIT_ENABLED=true",
                "AVITO_RATE_LIMIT_REQUESTS_PER_SECOND=3.5",
                "AVITO_RATE_LIMIT_BURST=7",
            )
        ),
    )
    monkeypatch.setenv("AVITO_BASE_URL", "https://from-env.avito.ru")
    monkeypatch.setenv("AVITO_CLIENT_ID", "env-client-id")
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "env-client-secret")

    settings = AvitoSettings.from_env(env_file=env_file)

    assert settings.base_url == "https://from-env.avito.ru"
    assert settings.auth.client_id == "env-client-id"
    assert settings.auth.client_secret == "env-client-secret"
    assert settings.timeouts.connect == 2.5
    assert settings.timeouts.read == 11.0
    assert settings.retry_policy.max_attempts == 4
    assert settings.retry_policy.backoff_factor == 0.75
    assert settings.retry_policy.max_delay == 9.5
    assert settings.retry_policy.retryable_methods == ("GET", "POST", "PATCH")
    assert settings.retry_policy.retry_on_rate_limit is False
    assert settings.retry_policy.max_rate_limit_wait_seconds == 12.5
    assert settings.retry_policy.rate_limit_enabled is True
    assert settings.retry_policy.rate_limit_requests_per_second == 3.5
    assert settings.retry_policy.rate_limit_burst == 7


def test_avito_settings_rejects_secret_like_user_agent_suffix() -> None:
    with pytest.raises(ConfigurationError, match="user_agent_suffix"):
        AvitoSettings(
            auth=AuthSettings(client_id="client-id", client_secret="client-secret"),
            user_agent_suffix="secret=abc",
        ).validate_required()
