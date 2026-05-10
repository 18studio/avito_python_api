# Task Plan: Add CLI Mode to avito-py

## Project Context

- Package name: `avito-py`.
- Import package: `avito`.
- Current public facade: `avito.client.AvitoClient`.
- Current config contract: `avito.config.AvitoSettings`.
- Current auth config contract: `avito.auth.settings.AuthSettings`.
- Packaging: Poetry-style `[tool.poetry]` in `pyproject.toml`; no console script is currently registered.
- Existing module entry point: `avito/__main__.py` is only a smoke check that creates `AvitoClient`.
- Architecture rule: CLI code must stay outside SDK core/domain/transport/auth layers.
- Styleguide constraints:
  - do not return raw `dict` or `Any` from public SDK methods;
  - do not mix CLI, transport, auth, parsing, or domain logic;
  - error messages in SDK code are Russian only;
  - avoid dead code and unused aliases;
  - keep core SDK free of Typer imports.

## Proposed CLI Shape

Use `avito/cli/` instead of the ticket's generic `sdk/cli/`:

```text
avito/
  cli/
    __init__.py
    app.py
    accounts.py
    config.py
    ui.py
```

Register the console command as `avito` unless product naming requires another command:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:app"
```

Also consider registering `avito-cli` as a compatibility alias if product naming wants a CLI-specific command:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:app"
avito-cli = "avito.cli.app:app"
```

Keep `avito/__main__.py` compatible. A later implementation can either leave it as the existing smoke check or route `python -m avito` to the Typer app if that is desired.

## Data Model

Persist CLI-local account records under an Avito-specific home directory:

```text
~/.avito-py/
  config.json
  accounts.json
```

Support override:

```bash
MY_SDK_HOME=/custom/path avito account list
```

`MY_SDK_HOME` is required because the ticket names it explicitly. Also support `AVITO_PY_HOME` as the project-specific alias, with this precedence:

1. `AVITO_PY_HOME`
2. `MY_SDK_HOME`
3. `Path.home() / ".avito-py"`

Document both variables, but make clear that `MY_SDK_HOME` exists for ticket compatibility and `AVITO_PY_HOME` is the Avito-specific name.

Suggested stored account fields:

- `name: str`
- `client_id: str`
- `client_secret: str`
- `base_url: str` stored internally, exposed in CLI as both `--base-url` and ticket-compatible `--endpoint`
- `user_id: int | None`
- optional OAuth fields already supported by `AuthSettings`: `scope`, `refresh_token`, `token_url`, `alternate_token_url`, `autoteka_token_url`, `autoteka_client_id`, `autoteka_client_secret`, `autoteka_scope`

The generic ticket example uses `--api-key`. Avito uses OAuth `client_id` and `client_secret`, so the canonical Avito flags should be `--client-id` and `--client-secret`. To satisfy the ticket's CLI shape without weakening the SDK contract, support `--api-key` as an alias for `--client-secret` and still require `--client-id` unless a future Avito auth mode removes that requirement.

Do not print full secret values. Mask values such as `client_secret`, `api_key`, refresh tokens, and API-like tokens in CLI output.

## Implementation Plan

1. Add Typer dependency
   - Add `typer` to `[tool.poetry.dependencies]`.
   - Do not add `rich` unless Typer pulls it in or it is explicitly approved.
   - Update the lock file through Poetry if dependency locking is part of the branch workflow.

2. Add CLI package skeleton
   - Create `avito/cli/__init__.py`.
   - Create `avito/cli/app.py` with the root Typer app.
   - Create `avito/cli/accounts.py` with an `account` subcommand app.
   - Create `avito/cli/config.py` for CLI home resolution and JSON persistence.
   - Create `avito/cli/ui.py` for shared output helpers.

3. Add config/home resolver
   - Implement `get_cli_home(env: Mapping[str, str] | None = None) -> Path`.
   - Default to `Path.home() / ".avito-py"`.
   - Respect `MY_SDK_HOME` for ticket compatibility.
   - Respect `AVITO_PY_HOME` as a project-specific alias with higher precedence.
   - Keep this logic independent from Typer so tests can call it directly.
   - Create directories lazily when saving data, not on import.

4. Add account storage layer
   - Use frozen dataclasses for CLI account records where practical.
   - Implement load/save functions or an `AccountStore` class in `avito/cli/config.py`.
   - Store `accounts.json` and `config.json` separately:
     - `accounts.json` contains named account records.
     - `config.json` contains the active account name.
   - Validate duplicate account names, missing active accounts, and malformed JSON.
   - Keep messages and exceptions consistent with repository conventions.

5. Add account commands
   - `avito account add`
     - Accept canonical flags: `--name`, `--client-id`, `--client-secret`, `--base-url`, and optional `--user-id`.
     - Accept ticket-compatible aliases: `--api-key` for `--client-secret` and `--endpoint` for `--base-url`.
     - Prompt interactively for missing required fields.
     - Default base URL to `https://api.avito.ru`.
   - `avito account list`
     - Display all accounts with base URL and active marker.
     - Mask sensitive fields if shown.
   - `avito account use <account-name>`
     - Set the active account in `config.json`.
   - `avito account current`
     - Display the currently active account.
   - `avito account remove <account-name>`
     - Confirm removal unless a `--yes` flag is supplied.
     - If removing the active account, clear the active account.

6. Add SDK client factory helper for future CLI commands
   - Add a CLI-only helper that converts the active account record to `AvitoSettings`.
   - This helper belongs in `avito/cli/config.py` or a future `avito/cli/client.py`, not in `avito/config.py`.
   - Use `AvitoClient(settings)` from the CLI; do not duplicate SDK behavior.
   - Any future CLI command that calls Avito API must use the active account automatically unless the command provides an explicit account override.

7. Add UI helpers
   - Implement:
     - `success(message: str) -> None`
     - `error(message: str) -> None`
     - `warning(message: str) -> None`
     - `info(message: str) -> None`
     - `print_table(rows: list[dict[str, object]]) -> None`
     - `confirm(message: str) -> bool`
   - Prefer `typer.echo`, `typer.secho`, `typer.confirm`, and `typer.prompt`.
   - Avoid raw `print()` in command modules.

8. Register console command
   - Add Poetry script entry:

     ```toml
     [tool.poetry.scripts]
     avito = "avito.cli.app:app"
     ```

   - Optionally add the alias if desired:

     ```toml
     avito-cli = "avito.cli.app:app"
     ```

   - Verify:

     ```bash
     poetry run avito --help
     poetry run avito account --help
     ```

9. Add tests
   - Add focused tests under `tests/cli/`.
   - Cover config home resolution:
     - default home;
     - `MY_SDK_HOME` override;
     - `AVITO_PY_HOME` override;
     - precedence when both variables are present.
   - Cover account storage:
     - add and reload account;
     - set/get active account;
     - remove inactive account;
     - remove active account clears active config;
     - sensitive value masking does not reveal full secrets.
   - Cover CLI command surface with Typer's `CliRunner`:
     - `avito --help`;
     - `avito account --help`;
     - non-interactive `account add --name dev --client-id ... --client-secret ... --endpoint ...`;
     - non-interactive ticket-compatible `account add --name dev --client-id ... --api-key ... --endpoint ...`;
     - `account use`, `account current`, `account list`, and `account remove --yes`.
   - Prefer direct tests of the config/account storage layer for persistence edge cases.

10. Update README
    - Add a short CLI section:

      ```bash
      avito account add --name dev --client-id ... --client-secret ...
      avito account add --name dev --client-id ... --api-key ... --endpoint https://api.avito.ru
      avito account use dev
      avito account list
      ```

    - Document `MY_SDK_HOME` and `AVITO_PY_HOME`.
    - Mention that secrets are stored locally and masked in output.

11. Verification
    - Minimum for this non-API-surface change:

      ```bash
      poetry run pytest tests/cli
      poetry run mypy avito
      poetry run ruff check .
      ```

    - Before completing the branch, run:

      ```bash
      make check
      ```

## Acceptance Checklist

- [ ] Typer dependency added.
- [ ] `avito/cli/` package exists and is isolated from SDK core.
- [ ] Console command is registered in `pyproject.toml`.
- [ ] `avito --help` works.
- [ ] `avito account --help` shows account commands.
- [ ] `account add` stores account data.
- [ ] `account list` lists accounts without exposing secrets.
- [ ] `account use` switches active account.
- [ ] `account current` displays active account.
- [ ] `account remove` deletes accounts and handles active account removal.
- [ ] Config is stored under `~/.avito-py/` by default.
- [ ] Config directory can be overridden with `MY_SDK_HOME`.
- [ ] Config directory can be overridden with `AVITO_PY_HOME`.
- [ ] `account add` supports ticket-compatible `--api-key` and `--endpoint` aliases.
- [ ] CLI output uses `avito/cli/ui.py` helpers.
- [ ] Existing SDK import and runtime behavior remain unchanged.
- [ ] Basic tests cover config/account storage logic.
- [ ] Basic CLI tests cover help output and account command flow.
- [ ] README contains CLI usage examples.
