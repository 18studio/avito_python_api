"""Tests for local CLI account and config stores."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from avito.auth.settings import AuthSettings
from avito.cli.config import (
    ACCOUNTS_FILENAME,
    CLI_HOME_ENV,
    CONFIG_FILENAME,
    TICKET_HOME_ENV,
    AccountsDocument,
    AccountStore,
    CliConfigDocument,
    ConfigStore,
    StoredAccount,
    resolve_cli_home,
)
from avito.cli.errors import CliConfigFileError, CliPermissionError
from avito.config import AvitoSettings


def test_resolve_cli_home_prefers_project_environment_variable(tmp_path: Path) -> None:
    avito_home = tmp_path / "avito"
    ticket_home = tmp_path / "ticket"

    home = resolve_cli_home(
        {
            CLI_HOME_ENV: str(avito_home),
            TICKET_HOME_ENV: str(ticket_home),
        }
    )

    assert home == avito_home


def test_resolve_cli_home_uses_ticket_compatibility_environment_variable(
    tmp_path: Path,
) -> None:
    ticket_home = tmp_path / "ticket"

    home = resolve_cli_home({TICKET_HOME_ENV: str(ticket_home)})

    assert home == ticket_home


def test_resolve_cli_home_defaults_to_user_home(monkeypatch: pytest.MonkeyPatch) -> None:
    user_home = Path("/tmp/example-user")
    monkeypatch.setattr(Path, "home", lambda: user_home)

    home = resolve_cli_home({})

    assert home == user_home / ".avito-py"


def test_import_and_store_construction_do_not_create_files(tmp_path: Path) -> None:
    home = tmp_path / "home"

    AccountStore(home)
    ConfigStore(home)

    assert not home.exists()


def test_missing_files_load_empty_documents_without_creating_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    accounts = AccountStore(home).load()
    config = ConfigStore(home).load()

    assert accounts == AccountsDocument()
    assert config == CliConfigDocument()
    assert not home.exists()


def test_save_creates_home_and_files_with_restricted_permissions(tmp_path: Path) -> None:
    home = tmp_path / "home"
    account_store = AccountStore(home)
    config_store = ConfigStore(home)

    account_store.save(
        AccountsDocument(
            accounts=(
                StoredAccount(
                    name="main",
                    client_id="client-id",
                    client_secret="client-secret",
                ),
            )
        )
    )
    config_store.save(CliConfigDocument(active_profile="main"))

    assert _mode(home) == 0o700
    assert _mode(home / ACCOUNTS_FILENAME) == 0o600
    assert _mode(home / CONFIG_FILENAME) == 0o600


def test_account_store_round_trip_preserves_account_data(tmp_path: Path) -> None:
    home = tmp_path / "home"
    store = AccountStore(home)
    document = AccountsDocument(
        accounts=(
            StoredAccount(
                name="main",
                client_id="client-id",
                client_secret="client-secret",
                base_url="https://example.test",
                user_id=123,
                refresh_token="refresh-token",
                autoteka_client_secret="autoteka-secret",
            ),
        )
    )

    store.save(document)
    loaded = store.load()

    assert loaded == document


def test_config_stores_active_profile_once(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ConfigStore(home).save(CliConfigDocument(active_profile="main"))

    config_payload = json.loads((home / CONFIG_FILENAME).read_text(encoding="utf-8"))

    assert config_payload["active_profile"] == "main"
    assert "active" not in config_payload


def test_atomic_write_uses_same_directory_temporary_file_and_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    replaced_paths: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        source_path = Path(source)
        target_path = Path(target)
        replaced_paths.append((source_path, target_path))
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)

    ConfigStore(home).save(CliConfigDocument(active_profile="main"))

    assert len(replaced_paths) == 1
    source_path, target_path = replaced_paths[0]
    assert source_path.parent == home
    assert target_path == home / CONFIG_FILENAME
    assert not source_path.exists()


def test_malformed_json_maps_to_typed_config_error(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / CONFIG_FILENAME).write_text("{invalid", encoding="utf-8")

    with pytest.raises(CliConfigFileError) as exc_info:
        ConfigStore(home).load()

    assert exc_info.value.code == "CONFIG_INVALID"
    assert exc_info.value.exit_code == 7


def test_unsupported_schema_version_maps_to_typed_config_error(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ACCOUNTS_FILENAME).write_text(
        json.dumps({"schema_version": 999, "accounts": []}),
        encoding="utf-8",
    )

    with pytest.raises(CliConfigFileError):
        AccountStore(home).load()


def test_permission_error_maps_to_typed_permission_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    def denied_mkdir(
        self: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "mkdir", denied_mkdir)

    with pytest.raises(CliPermissionError) as exc_info:
        ConfigStore(home).save(CliConfigDocument(active_profile="main"))

    assert exc_info.value.code == "PERMISSION_DENIED"
    assert exc_info.value.exit_code == 4


def test_account_json_masks_secrets_for_output_helpers() -> None:
    account = StoredAccount(
        name="main",
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        autoteka_client_secret="autoteka-secret",
    )

    payload = account.to_json(mask_secrets=True)

    assert payload["client_id"] == "client-id"
    assert payload["client_secret"] == "***"
    assert payload["refresh_token"] == "***"
    assert payload["autoteka_client_secret"] == "***"


def test_accounts_document_masks_nested_account_secrets() -> None:
    document = AccountsDocument(
        accounts=(
            StoredAccount(
                name="main",
                client_id="client-id",
                client_secret="client-secret",
            ),
        )
    )

    payload = document.to_json(mask_secrets=True)

    accounts = payload["accounts"]
    assert isinstance(accounts, list)
    first_account = accounts[0]
    assert isinstance(first_account, dict)
    assert first_account["client_secret"] == "***"


def test_stored_account_converts_to_public_avito_settings() -> None:
    account = StoredAccount(
        name="main",
        client_id="client-id",
        client_secret="client-secret",
        base_url="https://example.test",
        user_id=123,
        scope="messenger",
        refresh_token="refresh-token",
        token_url="/custom-token",
        alternate_token_url="/alternate-token",
        autoteka_token_url="/autoteka-token",
        autoteka_client_id="autoteka-client",
        autoteka_client_secret="autoteka-secret",
        autoteka_scope="autoteka",
    )

    settings = account.to_avito_settings()

    assert isinstance(settings, AvitoSettings)
    assert isinstance(settings.auth, AuthSettings)
    assert settings.base_url == "https://example.test"
    assert settings.user_id == 123
    assert settings.auth.client_id == "client-id"
    assert settings.auth.client_secret == "client-secret"
    assert settings.auth.scope == "messenger"
    assert settings.auth.refresh_token == "refresh-token"
    assert settings.auth.token_url == "/custom-token"
    assert settings.auth.alternate_token_url == "/alternate-token"
    assert settings.auth.autoteka_token_url == "/autoteka-token"
    assert settings.auth.autoteka_client_id == "autoteka-client"
    assert settings.auth.autoteka_client_secret == "autoteka-secret"
    assert settings.auth.autoteka_scope == "autoteka"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)
