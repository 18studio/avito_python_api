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
    errors.py
    ui.py
```

Register the console command as `avito` unless product naming requires another command:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:app"
```

Do not register `avito-cli` unless product naming explicitly requires a CLI-specific compatibility alias:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:app"
avito-cli = "avito.cli.app:app"
```

Route `python -m avito` to the Typer app so the module entry point and console script expose the same CLI behavior.

Add version commands:

```bash
avito --version
avito version
```

The version output should include the installed SDK version. Build commit and Avito API compatibility can be omitted until the project has those values.

## CLI Contract

CLI commands are public product surface. They must follow `.ai/cli-guidelines.md`:

- default output is human-readable;
- machine-readable output is available through `--json`;
- quiet automation output is available through `--quiet`;
- prompts are disabled by `--no-input`;
- command results go to stdout;
- errors, warnings, progress, and deprecation notices go to stderr;
- no command exposes secrets in normal, JSON, verbose, debug, or error output;
- color must not be the only source of meaning;
- `NO_COLOR=1` and `--no-color` disable colored output.

Supported global flags:

```text
--json
--quiet
--no-input
--no-color
--verbose
--debug
--version
```

Baseline exit codes:

```text
0   success
1   general error
2   invalid usage
3   not found
4   permission denied
5   authentication/config required
6   conflict
7   validation failed
8   external dependency unavailable
```

Every CLI error should include a stable error code such as `CONFIG_INVALID`, `ACCOUNT_NOT_FOUND`, `ACCOUNT_EXISTS`, `AUTH_REQUIRED`, or `VALIDATION_FAILED`.
User-facing CLI error messages must be written in Russian only, matching the SDK styleguide. Do not mix Russian and English in one error message. Stable error codes remain uppercase English identifiers.

Global flags must have deterministic precedence and conflict behavior:

- `--json` makes successful command output and CLI errors machine-readable JSON.
- `--quiet` suppresses non-essential success output; when combined with `--json`, JSON output remains the contract for commands that return data.
- `--debug` may include diagnostic details for human errors, but must not leak secrets; in `--json` mode diagnostics must be placed in stable JSON fields.
- `--verbose` is user-facing detail and must not override `--quiet`.
- `--no-color` and `NO_COLOR=1` disable color everywhere.
- Global options should work consistently at the root command level and for subcommands through shared CLI context.

The root CLI must support help in both common forms:

```bash
avito --help
avito account --help
avito help account
```

If Typer's built-in help behavior makes `avito help account` impractical, document the explicit exception and cover `--help` behavior instead.

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

File-system requirements:

- create the CLI home directory lazily with `0700` permissions;
- write `accounts.json` and `config.json` with `0600` permissions;
- save JSON atomically through a temporary file and replace;
- never create files or directories on import;
- report permission and malformed JSON errors as CLI errors without stack traces by default.

Suggested stored account fields:

- `name: str`
- `client_id: str`
- `client_secret: str`
- `base_url: str` stored internally, exposed in CLI as both `--base-url` and ticket-compatible `--endpoint`
- `user_id: int | None`
- optional OAuth fields already supported by `AuthSettings`: `scope`, `refresh_token`, `token_url`, `alternate_token_url`, `autoteka_token_url`, `autoteka_client_id`, `autoteka_client_secret`, `autoteka_scope`

The generic ticket example uses `--api-key`. Avito uses OAuth `client_id` and `client_secret`, so the canonical Avito flags should be `--client-id` and `--client-secret`. To satisfy the ticket's CLI shape without weakening the SDK contract, support `--api-key` as an alias for `--client-secret` and still require `--client-id` unless a future Avito auth mode removes that requirement.

Do not print full secret values. Mask values such as `client_secret`, `api_key`, refresh tokens, and API-like tokens in CLI output.

Human output uses stable tables or grouped key-value output. JSON output must use stable top-level object shapes, for example:

```json
{"accounts": [{"name": "dev", "base_url": "https://api.avito.ru", "active": true}]}
```

```json
{"account": {"name": "dev", "base_url": "https://api.avito.ru", "active": true}}
```

Secret fields must be omitted or masked in JSON output; do not emit raw stored credentials.

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
   - Create `avito/cli/errors.py` for CLI error types, stable error codes, and exit-code mapping.
   - Create `avito/cli/ui.py` for shared output helpers.

3. Add config/home resolver
   - Implement `get_cli_home(env: Mapping[str, str] | None = None) -> Path`.
   - Default to `Path.home() / ".avito-py"`.
   - Respect `MY_SDK_HOME` for ticket compatibility.
   - Respect `AVITO_PY_HOME` as a project-specific alias with higher precedence.
   - Keep this logic independent from Typer so tests can call it directly.
   - Create directories lazily when saving data, not on import.
   - Create directories with `0700` and config files with `0600`.
   - Persist JSON atomically:
     - create the temporary file in the same directory as the target file;
     - ensure the temporary file is not world-readable;
     - write and flush the full JSON document before replacement;
     - replace the target with `os.replace`;
     - remove leftover temporary files on write failures where practical.
   - Map permission failures to CLI errors with exit code `4` and stable error code `PERMISSION_DENIED`.

4. Add account storage layer
   - Use frozen dataclasses for CLI account records where practical.
   - Implement load/save functions or an `AccountStore` class in `avito/cli/config.py`.
   - Store `accounts.json` and `config.json` separately:
     - `accounts.json` contains named account records.
     - `config.json` contains the active account name.
   - Validate duplicate account names, missing active accounts, and malformed JSON.
   - `account add` must fail with a conflict error when the account already exists.
   - Do not add overwrite behavior unless a separate `account update` command is introduced.
   - Keep messages and exceptions consistent with repository conventions.

5. Add account commands
   - `avito account add`
     - Accept canonical flags: `--name`, `--client-id`, `--client-secret`, `--base-url`, and optional `--user-id`.
     - Accept ticket-compatible aliases: `--api-key` for `--client-secret` and `--endpoint` for `--base-url`.
     - Prompt interactively for missing required fields.
     - Never prompt when `--no-input` is supplied or stdin is not a TTY; fail with a validation error instead.
     - Default base URL to `https://api.avito.ru`.
   - `avito account list`
     - Display all accounts with base URL and active marker.
     - Mask sensitive fields if shown.
   - `avito account use <account-name>`
     - Set the active account in `config.json`.
   - `avito account current`
     - Display the currently active account.
   - `avito account delete <account-name>`
     - Confirm removal unless a `--yes` flag is supplied.
     - If removing the active account, clear the active account.
   - `avito account remove <account-name>`
     - Keep as a ticket-compatible alias for `account delete` only if the ticket requires the exact verb.
     - If implemented, document it as an alias and keep all behavior delegated to `account delete`.

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
     - `print_table(rows: Sequence[Mapping[str, object]]) -> None`
     - `print_json(payload: Mapping[str, object]) -> None`
     - `confirm(message: str, *, expected: str | None = None) -> bool`
     - `mask_secret(value: str | None) -> str | None`
   - Prefer `typer.echo`, `typer.secho`, `typer.confirm`, and `typer.prompt`.
   - Avoid raw `print()` in command modules.
   - Use stdout for command results and stderr for errors/warnings.
   - Support `--no-color` and `NO_COLOR=1`.
   - Centralize global CLI state in a typed context object so command modules do not parse flags independently.

8. Add CLI error handling
   - Map CLI-specific errors to documented exit codes.
   - Hide stack traces unless `--debug` is enabled.
   - Emit stable error codes in human and JSON output.
   - Keep user-facing SDK/CLI error text in Russian only; do not mix languages.
   - Ensure `--json` errors are valid JSON and still go to stderr.
   - Ensure `--debug` never exposes `client_secret`, `api_key`, refresh tokens, access tokens, authorization headers, or token-like values.

9. Register console command
   - Add Poetry script entry:

     ```toml
     [tool.poetry.scripts]
     avito = "avito.cli.app:app"
     ```

   - Do not add the alias unless explicitly required:

     ```toml
     avito-cli = "avito.cli.app:app"
     ```

   - Verify:

     ```bash
     poetry run avito --help
     poetry run avito account --help
     poetry run avito --version
     poetry run python -m avito --help
     ```

10. Add tests
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
     - duplicate account names fail with conflict;
     - malformed JSON fails with a CLI configuration error;
     - atomic save does not leave partial config on write failure where practical;
     - sensitive value masking does not reveal full secrets.
   - Cover CLI command surface with Typer's `CliRunner`:
     - `avito --help`;
     - `avito account --help`;
     - `avito help account` or the documented exception if this form is intentionally unsupported;
     - `avito --version`;
     - `python -m avito --help` behavior through the module entry point;
     - non-interactive `account add --name dev --client-id ... --client-secret ... --endpoint ...`;
     - non-interactive ticket-compatible `account add --name dev --client-id ... --api-key ... --endpoint ...`;
     - `account add --no-input` fails instead of prompting when required values are missing;
     - `account use`, `account current`, `account list`, and `account delete --yes`;
     - `account remove --yes` only if the compatibility alias is implemented;
     - `--json` output is valid JSON and contains no raw secrets;
     - `--quiet` suppresses non-essential success output.
     - `--json` errors are valid JSON on stderr;
     - `--debug` does not reveal secrets;
     - `--verbose` does not override `--quiet`;
     - `--no-color` and `NO_COLOR=1` disable color output.
   - Prefer direct tests of the config/account storage layer for persistence edge cases.

11. Update documentation
    - Add a short CLI section:

      ```bash
      avito account add --name dev --client-id ... --client-secret ...
      avito account add --name dev --client-id ... --api-key ... --endpoint https://api.avito.ru
      avito account use dev
      avito account list
      avito account current --json
      avito account delete dev --yes
      ```

    - Document `MY_SDK_HOME` and `AVITO_PY_HOME`.
    - Mention that secrets are stored locally in plaintext JSON files protected with `0600` permissions and masked in output.
    - Document `--json`, `--quiet`, `--no-input`, `--no-color`, `--version`, and public exit codes.
    - Add or update a docs how-to page if CLI is considered part of public user workflow, not just README examples.

12. Verification
    - Minimum for this non-API-surface change:

      ```bash
      poetry run pytest tests/cli
      poetry run mypy avito
      poetry run ruff check .
      poetry run python scripts/lint_python_guidelines.py
      poetry run python scripts/lint_architecture.py
      poetry build
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
- [ ] `avito --version` works.
- [ ] `avito version` works.
- [ ] `python -m avito --help` exposes the same CLI entry point.
- [ ] `avito account --help` shows account commands.
- [ ] `account add` stores account data.
- [ ] `account add --no-input` never prompts and fails on missing required values.
- [ ] `account add` rejects duplicate names with a conflict error.
- [ ] `account list` lists accounts without exposing secrets.
- [ ] `account list --json` emits valid JSON without exposing secrets.
- [ ] `account use` switches active account.
- [ ] `account current` displays active account.
- [ ] `account current --json` emits valid JSON without exposing secrets.
- [ ] `account delete` deletes accounts and handles active account removal.
- [ ] `account remove` is either omitted or implemented only as a documented alias for `account delete`.
- [ ] Config is stored under `~/.avito-py/` by default.
- [ ] Config directory can be overridden with `MY_SDK_HOME`.
- [ ] Config directory can be overridden with `AVITO_PY_HOME`.
- [ ] CLI home directory is created lazily with `0700` permissions.
- [ ] `accounts.json` and `config.json` are written with `0600` permissions.
- [ ] Config writes are atomic.
- [ ] `account add` supports ticket-compatible `--api-key` and `--endpoint` aliases.
- [ ] CLI output uses `avito/cli/ui.py` helpers.
- [ ] CLI errors use stable error codes and documented exit codes.
- [ ] CLI results use stdout; errors and warnings use stderr.
- [ ] `--quiet`, `--json`, `--no-input`, `--no-color`, `--verbose`, and `--debug` behavior is documented.
- [ ] Existing SDK import and runtime behavior remain unchanged.
- [ ] Basic tests cover config/account storage logic.
- [ ] Basic CLI tests cover help output and account command flow.
- [ ] Tests cover JSON output, quiet output, no-input behavior, duplicate names, malformed JSON, and secret masking.
- [ ] README contains CLI usage examples.
- [ ] Public docs mention CLI usage if the CLI is part of public workflow.
- [ ] Minimum verification commands pass.
- [ ] `make check` passes before completing the branch.
