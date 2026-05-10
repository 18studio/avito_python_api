# Task Plan: Add CLI Mode to avito-py

## Goal

Build a convenient, stable, scriptable CLI for `avito-py` that covers every supported SDK domain method with maximum reuse of the existing SDK surface.

The CLI must not become a second SDK implementation. It must call `AvitoClient` factories and public domain methods, reuse existing models and serialization, and keep all HTTP/auth/retry/mapping behavior inside the current SDK layers.

Target outcome:

- `avito` console command and `python -m avito` expose the same CLI.
- Account/profile management works without network calls.
- Every sync Swagger-bound public SDK method has a discoverable CLI route.
- Every supported non-Swagger helper workflow has either a CLI route or a documented intentional exclusion.
- CLI coverage is checked automatically against Swagger binding discovery.
- Human output is useful by default; JSON output is stable for automation.
- Secrets are never printed in normal, JSON, verbose, debug, or error output.
- Implementation is delivered in small stages with tests and verification gates after each stage.

## Source Rules

Normative documents:

- `.ai/STYLEGUIDE.md`
- `.ai/cli-guidelines.md`
- `docs/site/explanations/domain-architecture-v2.md`
- `docs/site/explanations/swagger-binding-subsystem.md`

Repository contracts:

- Package name: `avito-py`.
- Import package: `avito`.
- Public facade: `avito.client.AvitoClient`.
- Sync domain methods are the first CLI coverage target.
- Swagger/OpenAPI specs in `docs/avito/api/` are the API contract source.
- Swagger bindings discovered by `avito.core.swagger_discovery.discover_swagger_bindings()` are the canonical SDK coverage source.

Important style constraints:

- CLI code belongs under `avito/cli/`; do not put CLI behavior into core/domain/transport/auth layers.
- Keep core SDK free of Typer imports.
- Do not duplicate transport, auth, retry, request mapping, response mapping, pagination, or validation logic in CLI code.
- Do not return raw `dict` or `Any` from public SDK methods.
- Do not add public Avito API methods without `@swagger_operation(...)`.
- Error messages in SDK and CLI user-facing text are Russian only. Stable error codes remain uppercase English identifiers.
- Avoid dead code, unused aliases, and dynamic method injection.

## CLI Architecture

Use a small hand-written CLI shell plus generated/discovered command metadata.

```text
avito/
  cli/
    __init__.py
    app.py              # root Typer app and global context
    accounts.py         # local account/profile commands
    client.py           # CLI-only AvitoClient construction
    commands.py         # generic invocation engine for SDK methods
    config.py           # CLI home, JSON persistence, account store
    coverage.py         # CLI coverage report and linter helpers
    errors.py           # CLI errors, exit-code mapping, secret sanitization
    help.py             # optional help command compatibility
    registry.py         # command registry built from SDK metadata
    schemas.py          # CLI input coercion from signatures/type hints
    serialization.py    # model/pagination result serialization
    ui.py               # stdout/stderr, table/json/plain output
```

Do not add domain-specific CLI modules for every API package unless a command needs custom UX. The default path must be metadata-driven to avoid hand-copying 204 operations.

Register only the canonical command unless product naming explicitly requires an alias:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:app"
```

Route `python -m avito` to the same Typer app.

## Command Model

Use the `.ai/cli-guidelines.md` grammar:

```text
avito <resource> <action> [primary arguments] [flags]
```

Resource names should be derived from SDK factory names with kebab-case:

- `account`
- `account-hierarchy`
- `ad`
- `ad-stats`
- `autoload-profile`
- `chat`
- `promotion-order`
- `target-action-pricing`
- `delivery-order`
- `realty-listing`

Actions should be derived from public SDK method names with kebab-case:

- `get-self` from `get_self`
- `list-services` from `list_services`
- `create-order` from `create_order`

Default generated command shape:

```bash
avito <factory-name> <method-name> [factory args] [method args]
```

Examples:

```bash
avito account get-self
avito account get-balance --user-id 123
avito ad get --item-id 456 --user-id 123
avito ad-stats get-item-stats --user-id 123 --item-ids 456,789 --date-from 2026-05-01
avito promotion-order list-services --item-id 456 --json
```

Rules:

- Factory arguments and method arguments become named flags by default.
- Positional arguments are allowed only for obvious single primary identifiers after explicit design review.
- Same SDK concept must use the same CLI flag everywhere: `--user-id`, `--item-id`, `--order-id`, `--chat-id`, `--date-from`, `--date-to`, `--limit`, `--offset`.
- `resource_id` must never appear.
- Generated commands must preserve one obvious path per operation. Compatibility aliases must delegate to the canonical command and be documented as aliases.

## Global Flags

Supported from the root command and all subcommands through one typed CLI context:

```text
-h, --help
--version
--profile <name>
--config <path>
--json
--plain
--table
--wide
--quiet
--no-input
--no-color
--verbose
--debug
--timeout <seconds>
```

Write/destructive commands additionally support:

```text
--dry-run
--yes
--confirm <value>
```

Precedence:

1. CLI flags
2. Environment variables
3. Project config
4. User config
5. System config
6. Built-in defaults

Initial implementation may support only user config, but the precedence contract must be documented and the config resolver must leave room for project/system config without breaking users.

Flag behavior:

- `--json` makes success output and CLI errors machine-readable JSON.
- `--quiet` suppresses non-essential success output; when combined with `--json`, commands returning data still emit their JSON result.
- `--plain`, `--table`, and `--wide` are mutually exclusive with `--json`; invalid combinations fail with exit code `2`.
- `--verbose` is user-facing extra detail and never overrides `--quiet`.
- `--debug` may include diagnostic fields but must never leak secrets.
- `--no-color` and `NO_COLOR=1` disable color everywhere.
- Commands must not prompt when `--no-input` is set or stdin is not a TTY.

## Exit Codes

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

Every CLI error includes a stable code such as:

- `CONFIG_INVALID`
- `ACCOUNT_NOT_FOUND`
- `ACCOUNT_EXISTS`
- `AUTH_REQUIRED`
- `PERMISSION_DENIED`
- `VALIDATION_FAILED`
- `COMMAND_UNSUPPORTED`
- `SDK_METHOD_FAILED`

Errors and warnings go to stderr. Command results go to stdout. JSON errors are valid JSON on stderr.

## Account and Config Model

Persist CLI-local data under:

```text
~/.avito-py/
  config.json
  accounts.json
```

Home override precedence:

1. `AVITO_PY_HOME`
2. `MY_SDK_HOME`
3. `Path.home() / ".avito-py"`

`MY_SDK_HOME` is ticket compatibility. `AVITO_PY_HOME` is the project-specific name.

File-system requirements:

- Create the CLI home directory lazily with `0700` permissions.
- Write `accounts.json` and `config.json` with `0600` permissions.
- Save JSON atomically through a temporary file in the same directory and `os.replace`.
- Never create files or directories on import.
- Map permission failures to exit code `4` with `PERMISSION_DENIED`.
- Map malformed JSON to exit code `7` or `5` depending on whether the command can continue without config.

Stored account fields:

- `name: str`
- `client_id: str`
- `client_secret: str`
- `base_url: str`
- `user_id: int | None`
- OAuth fields already supported by `AuthSettings`: `scope`, `refresh_token`, `token_url`, `alternate_token_url`, `autoteka_token_url`, `autoteka_client_id`, `autoteka_client_secret`, `autoteka_scope`

Canonical flags:

- `--client-id`
- `--client-secret`
- `--base-url`
- `--user-id`

Ticket-compatible aliases:

- `--api-key` as an alias for `--client-secret`
- `--endpoint` as an alias for `--base-url`

Secrets must be omitted or masked in every output format, including JSON and debug diagnostics.

## SDK Reuse Strategy

The CLI invokes SDK methods through a generic pipeline:

1. Resolve profile/account and build `AvitoSettings`.
2. Create `AvitoClient(settings)` in a context manager.
3. Resolve the CLI resource to an `AvitoClient` factory.
4. Coerce CLI strings into the factory arguments and method arguments using public signatures/type hints.
5. Call the SDK factory.
6. Call the public domain method.
7. Serialize the SDK return value through existing `model_dump()` / `to_dict()` / pagination materialization helpers.
8. Render as table, grouped text, plain value, or JSON.

Do not use `OperationSpec` directly from CLI commands. Operation specs remain internal SDK metadata.

The generic invocation engine must support:

- primitive values: `str`, `int`, `float`, `bool`
- `date` and `datetime` strings with validation
- enums by value/name with clear validation errors
- optional values
- list values from repeated flags or comma-separated values where documented
- public dataclass input models only when they are already public SDK input models
- `PaginatedList[T]` with explicit materialization limits or streaming-safe iteration
- file inputs only for methods whose public signature already accepts file/path-like public inputs

If a method cannot be safely exposed by the generic engine, add it to a typed exception list with a reason and a tracked follow-up. The acceptance target for final completion is zero unsupported sync Swagger-bound methods unless an operation is intentionally not usable from CLI and documented.

## Registry and Coverage

Build a CLI registry from existing SDK metadata:

- `discover_swagger_bindings(registry=SwaggerRegistry.load(...))`
- `binding.factory`
- `binding.factory_args`
- `binding.method_name`
- `binding.method_args`
- public Python signatures and type hints

Coverage invariant:

```text
each sync discovered Swagger binding -> exactly one canonical CLI command
each canonical API CLI command -> exactly one sync discovered Swagger binding
each supported public non-Swagger helper -> CLI command or documented exclusion
```

Compatibility aliases are allowed but must not count as separate canonical coverage.

Non-Swagger public helpers are not part of the Swagger one-to-one invariant, but they are part of the user-facing SDK. Track them separately:

- `AvitoClient` summary/workflow helpers such as account health, chat/order/review/promotion summaries, and capability discovery;
- public domain helper methods without Swagger bindings, if any exist;
- local CLI-only workflows such as `account`, `config`, `status`, `doctor`, and `completion`.

The coverage report must show separate counts:

- `api_bound_commands`
- `api_bound_missing_commands`
- `helper_commands`
- `helper_exclusions`
- `local_cli_commands`

Add a CLI coverage linter:

```bash
poetry run python scripts/lint_cli_coverage.py
```

The linter must fail when:

- a sync discovered Swagger binding has no canonical CLI command;
- a canonical API CLI command has no binding;
- two canonical CLI commands map to the same binding;
- a public supported helper has neither a command nor an explicit exclusion;
- a command exposes a forbidden `resource-id` flag;
- a command exposes a secret in an output schema;
- a command uses a non-kebab-case resource/action/flag name.

Add `make cli-lint` and include it in `make check` after the CLI reaches full coverage.

## Output Contract

Default output:

- Human-readable.
- Tables for collections.
- Grouped key-value output for one object.
- Concise success text for writes.
- Next-step hints only when helpful and not noisy.

Machine output:

- `--json` emits stable, undecorated JSON.
- Top-level objects are stable and named by resource/action.
- SDK models are serialized via their public serialization contract.
- Pagination output includes enough metadata when available.

Examples:

```json
{"accounts": [{"name": "dev", "base_url": "https://api.avito.ru", "active": true}]}
```

```json
{"result": {"operation": "account.get_self", "data": {"id": 123}}}
```

Avoid raw secrets in all output:

- `client_secret`
- `api_key`
- `refresh_token`
- `access_token`
- `Authorization`
- token-like fields

## Help and Completion

Help requirements:

```bash
avito --help
avito account --help
avito account get-self --help
avito help account
avito help account get-self
```

If Typer makes `avito help account` impractical, implement a small `help` command that delegates to the registry metadata instead of relying only on Typer internals.

Help must include:

- description in Russian;
- usage;
- at least one minimal example;
- one automation-friendly `--json --no-input` example where relevant;
- flags with stable names;
- related commands when useful.

Completion commands:

```bash
avito completion bash
avito completion zsh
avito completion fish
```

Completion can start with static command/flag completion and later add profile/account names.

## Implementation Stages

Each stage must be small enough to review independently and must end with tests and verification.

### Stage 0: Baseline Audit

Deliverables:

- Record current sync Swagger binding count.
- Record current `AvitoClient` factory mapping count.
- Confirm which factory names exist in `AvitoClient` but not in bindings.
- Confirm whether every sync binding has `factory` metadata.
- Record public non-Swagger helper methods and decide command vs exclusion.

Verification:

```bash
poetry run python -c "from avito.core.swagger_discovery import discover_swagger_bindings; print(len(discover_swagger_bindings().canonical_map))"
poetry run pytest tests/core/test_swagger_linter.py tests/contracts/test_swagger_contracts.py
```

Exit criteria:

- A short audit note is added to this plan or a linked implementation note.
- Any missing factory metadata is tracked before CLI generation starts.

### Stage 1: CLI Dependency and Shell

Deliverables:

- Add `typer` dependency.
- Add `avito/cli/` package skeleton.
- Add root `avito` app with global context.
- Add `avito --help`, `avito --version`, `avito version`.
- Route `python -m avito` to the CLI.
- Register Poetry script.

Tests:

- `tests/cli/test_app.py`
- help output smoke tests;
- version command tests;
- global flag parsing tests.

Verification:

```bash
poetry run pytest tests/cli/test_app.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
poetry build
```

### Stage 2: Errors, UI, and Safe Output

Deliverables:

- Add `CliContext`.
- Add `CliError` hierarchy and exit-code mapping.
- Add stdout/stderr output helpers.
- Add JSON/human error rendering.
- Add secret masking/sanitization.
- Add color handling for `--no-color` and `NO_COLOR=1`.

Tests:

- human errors go to stderr;
- JSON errors are valid JSON on stderr;
- `--debug` does not reveal secrets;
- `--quiet` suppresses non-essential success output;
- invalid flag combinations exit with code `2`.

Verification:

```bash
poetry run pytest tests/cli/test_errors.py tests/cli/test_ui.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 3: Account Store and Profile Commands

Deliverables:

- Implement CLI home resolver and atomic JSON persistence.
- Implement account dataclasses and `AccountStore`.
- Add account commands:
  - `avito account add`
  - `avito account list`
  - `avito account use <account-name>`
  - `avito account current`
  - `avito account delete <account-name>`
- Add optional `account remove` only as a documented alias for `account delete`.
- Add CLI-only helper that converts the active account to `AvitoSettings`.

Tests:

- default home and environment override precedence;
- lazy directory creation;
- file permissions where the platform supports it;
- add/reload account;
- duplicate account conflict;
- active account set/get/clear;
- malformed JSON handling;
- no-input behavior;
- ticket aliases `--api-key` and `--endpoint`;
- JSON output contains no raw secrets.

Verification:

```bash
poetry run pytest tests/cli/test_config.py tests/cli/test_accounts.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 4: CLI Registry From SDK Metadata

Deliverables:

- Build `avito/cli/registry.py`.
- Convert sync discovered Swagger bindings into canonical resource/action commands.
- Preserve mapping to factory name, factory args, method name, method args, operation key, and domain.
- Register public non-Swagger helper commands in a separate helper registry.
- Add explicit alias support separate from canonical command records.
- Add registry JSON/debug report command:
  - `avito cli coverage --json`
  - or hidden internal command if public exposure is not desired.

Tests:

- registry includes all sync discovered bindings;
- registry accounts for public helper methods separately from API bindings;
- resource/action names are kebab-case;
- every command maps to exactly one binding;
- no duplicate canonical commands;
- aliases do not affect canonical coverage.

Verification:

```bash
poetry run pytest tests/cli/test_registry.py
poetry run python scripts/lint_cli_coverage.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

### Stage 5: Generic Input Coercion and Invocation

Deliverables:

- Implement `avito/cli/schemas.py`.
- Implement `avito/cli/commands.py`.
- Coerce CLI flags from signatures/type hints.
- Build and call `AvitoClient` through active account/profile.
- Invoke public SDK factory and method.
- Map SDK exceptions to CLI errors.
- Add explicit unsupported-method registry only for cases with documented reasons.

Tests:

- coercion for primitives, bools, dates, datetimes, enums, optionals, lists;
- missing required values fail without prompt in `--no-input`;
- invalid values produce `VALIDATION_FAILED`;
- active profile is used by default;
- `--profile` overrides active profile;
- SDK `AuthenticationError`, `AuthorizationError`, `ValidationError`, `ConflictError`, and not-found equivalents map to documented exit codes.

Verification:

```bash
poetry run pytest tests/cli/test_schemas.py tests/cli/test_commands.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 6: Result Serialization and Pagination

Deliverables:

- Implement `avito/cli/serialization.py`.
- Serialize SDK models through `model_dump()` / `to_dict()`.
- Serialize dataclasses, enums, dates, datetimes, lists, and primitive values safely.
- Handle `PaginatedList[T]` with documented defaults.
- Add `--limit` or `--page-limit` only when needed to avoid accidentally materializing unbounded result sets.
- Render default tables for collections and grouped output for single models.

Tests:

- model serialization uses public model contract;
- paginated results do not fetch unbounded pages by default;
- JSON output is stable;
- tables have stable columns for repeated models;
- no secrets appear in serialized output.

Verification:

```bash
poetry run pytest tests/cli/test_serialization.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 7: First Vertical API Slice

Deliverables:

- Expose and test a small read-only vertical slice:
  - `avito account get-self`
  - `avito account get-balance`
  - one paginated/list command if available.
- Use `SwaggerFakeTransport` or existing fake transport infrastructure.
- Do not make real network calls in tests.

Tests:

- command invokes the expected SDK method;
- request path/query/body match Swagger fake transport expectations;
- human output works;
- JSON output works;
- errors are mapped correctly.

Verification:

```bash
poetry run pytest tests/cli/test_account_api_commands.py
poetry run pytest tests/contracts/test_swagger_contracts.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 8: All-Domain Generated API Commands

Deliverables:

- Register generated commands for every sync Swagger-bound method.
- Add domain/resource help pages.
- Add generated examples where safe and meaningful.
- Add explicit command metadata for methods needing custom list/file/enum parsing.
- Eliminate or document every unsupported sync binding.

Required domains:

- `accounts`
- `ads`
- `autoteka`
- `cpa`
- `jobs`
- `messenger`
- `orders`
- `promotion`
- `ratings`
- `realty`
- `tariffs`

Required helper workflows:

- account health/business summary;
- chat summary;
- order summary;
- review summary;
- promotion summary;
- capability discovery.

Tests:

- one smoke invocation per domain with fake transport;
- one command metadata assertion per discovered sync binding;
- generic coverage test that fails on missing commands;
- helper command metadata or explicit exclusions are covered;
- no generated command exposes forbidden names or secret fields.

Verification:

```bash
poetry run pytest tests/cli/test_all_domains_metadata.py
poetry run pytest tests/cli/test_domain_smoke_commands.py
poetry run python scripts/lint_cli_coverage.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

### Stage 9: Write Commands, Safety, and Dry Run

Deliverables:

- Classify write/destructive commands from HTTP method and/or SDK metadata.
- Require confirmation for destructive commands unless `--yes` or exact `--confirm` is supplied.
- Support `--dry-run` only when the SDK public method already supports `dry_run` or when the CLI can safely preview without changing SDK behavior.
- Do not fake dry-run for SDK methods that would still execute transport.
- Ensure write commands build the same SDK call in dry-run and apply modes where `dry_run` exists.

Tests:

- delete/reset-like commands require confirmation;
- `--no-input` fails instead of prompting;
- `--yes` and `--confirm` behave deterministically;
- dry-run methods do not call transport when SDK contract says they should not;
- non-dry-run write commands call transport exactly once.

Verification:

```bash
poetry run pytest tests/cli/test_write_safety.py
poetry run pytest tests/domains/promotion tests/domains/orders
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 10: Config, Status, Doctor, and Completion

Deliverables:

- Add explicit config commands:
  - `avito config get`
  - `avito config set`
  - `avito config unset`
  - `avito config list`
  - `avito config list --show-source`
- Add `avito status` for profile/config/auth readiness without leaking secrets.
- Add `avito doctor` for local diagnostics.
- Add shell completion commands for bash, zsh, and fish.

Tests:

- config precedence and source display;
- status works without network where possible;
- doctor reports malformed config and permission issues;
- completion commands render scripts or clear instructions.

Verification:

```bash
poetry run pytest tests/cli/test_config_commands.py tests/cli/test_status_doctor.py tests/cli/test_completion.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

### Stage 11: Documentation

Deliverables:

- README CLI quickstart.
- Docs how-to page for CLI account/profile setup.
- Docs reference for global flags, output formats, exit codes, config files, environment variables, and secret storage.
- Docs page explaining generated all-domain command grammar.
- Examples for human and JSON automation usage.
- Document that secrets are stored locally in plaintext JSON protected with `0600` permissions.

Verification:

```bash
poetry run mkdocs build --strict
make docs-check
```

### Stage 12: Final Gate

Run the full gate before completing the branch:

```bash
poetry run pytest tests/cli
poetry run pytest tests/core/test_swagger*.py tests/contracts/test_swagger_contracts.py
poetry run mypy avito
poetry run ruff check .
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run python scripts/lint_cli_coverage.py
poetry build
make check
```

If generated docs, snippets, coverage pages, or reference output changed:

```bash
make docs-strict
```

## Acceptance Checklist

- [ ] `typer` dependency added.
- [ ] `avito/cli/` exists and is isolated from SDK core/domain/transport/auth layers.
- [ ] Console command `avito` is registered in `pyproject.toml`.
- [ ] `python -m avito` exposes the same CLI.
- [ ] `avito --help`, `avito --version`, and `avito version` work.
- [ ] Global flags work consistently at root and subcommand levels.
- [ ] CLI home defaults to `~/.avito-py/`.
- [ ] `AVITO_PY_HOME` and `MY_SDK_HOME` override CLI home with documented precedence.
- [ ] CLI home directory is created lazily with `0700` permissions.
- [ ] `accounts.json` and `config.json` are written atomically with `0600` permissions.
- [ ] Account commands add/list/use/current/delete accounts.
- [ ] `account remove` is omitted or implemented only as a documented alias for `account delete`.
- [ ] `account add` supports `--client-id`, `--client-secret`, `--base-url`, `--api-key`, and `--endpoint`.
- [ ] No CLI output leaks raw secrets.
- [ ] CLI errors use stable error codes and documented exit codes.
- [ ] Results go to stdout; errors, warnings, progress, and debug diagnostics go to stderr.
- [ ] `--json` emits stable JSON for success and errors.
- [ ] `--quiet`, `--plain`, `--table`, `--wide`, `--no-input`, `--no-color`, `--verbose`, and `--debug` are documented and tested.
- [ ] CLI registry is built from SDK Swagger binding metadata.
- [ ] Every sync discovered Swagger binding has exactly one canonical CLI command.
- [ ] Every canonical API CLI command maps to exactly one sync discovered Swagger binding.
- [ ] Every supported public non-Swagger helper has a CLI command or documented exclusion.
- [ ] Compatibility aliases do not count as canonical coverage.
- [ ] Generated command names and flags are lowercase kebab-case.
- [ ] No command exposes `resource-id`.
- [ ] Generic invocation uses `AvitoClient` factories and public domain methods.
- [ ] CLI does not call `OperationSpec` or transport directly for API commands.
- [ ] Input coercion covers primitives, booleans, dates, datetimes, enums, optionals, and lists.
- [ ] Pagination behavior is bounded and documented.
- [ ] Destructive commands require confirmation unless `--yes` or `--confirm` is supplied.
- [ ] `--dry-run` is exposed only for SDK methods that safely support it.
- [ ] One smoke command per domain is tested through fake transport.
- [ ] CLI coverage linter exists and passes.
- [ ] README and docs include CLI usage, config, output, and exit-code contracts.
- [ ] Minimum stage verification commands pass during implementation.
- [ ] Final `make check` passes before completion.

## Open Decisions

- Whether to expose async SDK methods in CLI. Initial plan targets sync methods only because CLI processes are synchronous command executions and sync Swagger coverage is the canonical first product surface.
- Whether `avito cli coverage` should be public or hidden. The linter/report is required either way.
- Whether generated commands should materialize all pagination by default or require an explicit `--all`. Conservative default: bounded output with explicit opt-in for full materialization.
- Whether to add `avito-cli` as an alias. Conservative default: do not add it without a product requirement.
