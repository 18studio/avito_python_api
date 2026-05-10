# Task Plan: Add CLI Mode to avito-py

## Developer Context and Execution Instructions

This plan is intended for a developer who opens the task for the first time and must bring CLI mode to a stable, tested state without violating the SDK architecture.

Core idea: the CLI is a thin wrapper over the public SDK. It does not know how HTTP requests, authorization, retries, Swagger operation specs, transport, response mapping, or pagination internals work. For Avito API commands, the CLI always goes through `AvitoClient` -> public factory -> public domain method -> public SDK model serialization.

How to work with this plan:

1. Before making any changes, read this section, `Goal`, `Normative Rules`, `Current Baseline Findings`, `CLI Architecture`, `SDK Reuse Strategy`, and `Registry and Coverage`.
2. Then read the required documents:
   - `.ai/STYLEGUIDE.md`
   - `.ai/cli-guidelines.md`
   - `.ai/python-guidelines.md`
   - `docs/site/explanations/domain-architecture-v2.md`
   - `docs/site/explanations/swagger-binding-subsystem.md`
3. Execute stages strictly in order. Do not start the next stage until the current stage has passed its tests, verification commands, and stage checklist.
4. Make small changes. One stage should be a separate reviewable increment: minimal new functionality, tests, checks, and an updated checklist.
5. If a stage is too large, split it into sub-stages inside the same stage, but do not skip ahead to the next architectural area.
6. After each stage, leave the repository in a working state: stage tests pass, mypy/ruff verification passes, and there are no temporary workarounds or dead code.
7. When implementation convenience conflicts with the guides, follow the guides. If a guide blocks the task, first record the architectural decision in the plan or documentation instead of silently bypassing the rule.

The preliminary baseline audit has already been completed and recorded in
`Completed Pre-Coding Audit`. Before starting Stage 1, the developer must use
these results as the initial state:

- Current `AvitoClient`: which public factory methods exist, which ones are helper/workflow methods, and which ones must not become API commands.
- Current Swagger discovery: sync binding count and presence of `factory`, `factory_args`, `method_args`, and `operation_key`.
- Public domain methods: which methods are sync, async, legacy/deprecated, and helper methods without a Swagger binding.
- Current serialization models: where `model_dump()` / `to_dict()` exist, and how `PaginatedList`, enums, dates, and datetimes work.
- Current fake transport/testing helpers: what tests may use and what production CLI code must not import.
- Current `Makefile` and script linters: where `cli-lint` must be integrated and which commands already run in `make check`.
- Current `avito/__main__.py`: its smoke behavior must be replaced with CLI handoff in Stage 1.

Stage execution rules:

- Each stage must put production code only in the required files, include tests for new logic, and pass verification.
- Each stage checklist must be filled only after actual verification, not in advance.
- If a verification command fails for a reason unrelated to the stage change, record it next to the stage result with the exact command and error.
- If an exclusion is needed, it must include a reason, impact area, and follow-up. Silent exclusions are forbidden.
- If a new public command appears, it must have a kebab-case name, stable flags, localized help/error text according to the styleguide, JSON behavior, secret masking, and tests.
- If a command can modify state or trigger an expensive operation, classify the safety policy first, then add `--dry-run`, `--yes`, and `--confirm` only according to this plan.

Definition of done for the whole plan:

- All stage checklists are complete.
- `avito` and `python -m avito` work through one CLI app.
- All sync Swagger-bound domain methods are covered by a canonical CLI command or an explicit documented exclusion.
- In this plan, "100% CLI coverage" means that each sync Swagger-bound domain method has exactly one canonical CLI command, and each non-domain Swagger binding, deprecated/compatibility path, or unsupported helper has a documented exclusion with a reason. Direct coverage of auth-token internals through the CLI is outside the first release and is not a coverage defect.
- All supported helper workflows are covered by a command or documented exclusion.
- The coverage linter passes and is included in `make check`.
- The CLI does not duplicate SDK contracts and does not bypass the public `AvitoClient` surface.
- Secrets do not appear in any output mode.
- The final gate from Stage 14 passes.

## Goal

Build a convenient, stable, scriptable CLI for `avito-py` that covers every supported sync SDK domain method with maximum reuse of the existing SDK surface.

The CLI must be a thin product interface over the SDK, not a second SDK implementation. API commands must construct `AvitoClient`, call its public factories, call public domain methods, serialize public SDK models, and leave HTTP/auth/retry/pagination/mapping behavior inside the existing SDK layers.

Target outcome:

- `avito` console command and `python -m avito` expose the same CLI.
- Local account/profile/config commands work without Avito network calls.
- Every sync Swagger-bound public SDK method has exactly one canonical CLI command, unless it has a documented intentional exclusion.
- The first release coverage target is strict for sync domain API methods discovered through `AvitoClient` factory metadata. Non-domain auth-token bindings and compatibility-only wrappers are intentionally excluded unless a separate public SDK facade is designed for them.
- Every supported public non-Swagger helper has a CLI command or a documented exclusion.
- CLI coverage is checked automatically against Swagger binding discovery.
- Human output is useful by default; JSON output is stable for automation.
- Secrets are never printed in human, JSON, verbose, debug, error, coverage, or diagnostic output.
- Implementation is delivered in small reviewable stages, each with tests and verification commands.

## Normative Rules

Mandatory documents:

- `.ai/STYLEGUIDE.md`
- `.ai/cli-guidelines.md`
- `.ai/python-guidelines.md`, through `.ai/STYLEGUIDE.md`
- `docs/site/explanations/domain-architecture-v2.md`
- `docs/site/explanations/swagger-binding-subsystem.md`

Repository contracts:

- Package name: `avito-py`.
- Import package: `avito`.
- Public sync facade: `avito.client.AvitoClient`.
- Swagger/OpenAPI specs in `docs/avito/api/` are the API contract source.
- Swagger bindings discovered by `avito.core.swagger_discovery.discover_swagger_bindings()` are the canonical SDK coverage source.

Hard constraints:

- CLI code belongs under `avito/cli/`.
- Keep SDK core/domain/transport/auth layers free of Click and CLI behavior.
- Production CLI code must not import domain `operations.py`, transport implementations, auth provider internals, or testing fake transports.
- Production CLI code must not import from `tests`, `avito.testing`, `tests/fake_transport.py`, or `avito.core.operations`.
- Production CLI code must not import private SDK modules or private names unless the import is explicitly documented as a CLI-only compatibility exception in this plan and covered by an architecture lint rule.
- API commands must not call `OperationSpec`, `OperationExecutor`, `Transport`, or `AuthProvider` directly.
- API commands must not instantiate domain objects directly.
- Do not duplicate Swagger contract data in CLI metadata. CLI metadata may store command names, examples, aliases, safety policy, output hints, and documented exclusions only.
- Do not add or change public Avito API SDK methods as part of CLI work unless the normal SDK rules are followed: typed model, operation spec, docstring, and `@swagger_operation(...)`.
- Human-facing CLI text is Russian only: help descriptions, prompts, warnings, errors, and success output. Stable error codes remain uppercase English identifiers.
- No `setattr`, `globals()`, monkey-patching, generated Python source, or dynamic SDK method injection. Deterministic Click command registration from typed registry records is allowed.
- No dead code, unused aliases, unused `TypeVar`s, broad `Any`, or layer mixing.
- No dynamic imports for optional CLI dependencies. Runtime dependency failures must fail at import/install time and be fixed in `pyproject.toml`.
- No broad `except Exception` in CLI command flow unless the handler sanitizes output and immediately re-raises or converts to a typed `CliError`.

Non-goals for the first complete release:

- Async CLI surface.
- OS keychain integration. First release stores plaintext JSON files protected by permissions and documents that clearly.
- Reimplementing SDK validation in CLI. CLI only coerces shell strings into typed public method arguments and reports invalid CLI syntax early.
- A second public command alias such as `avito-cli`, unless there is a separate product requirement.

## Current Baseline Findings

Recorded and re-verified on 2026-05-10 while preparing this plan:

```text
sync Swagger bindings: 204
sync Swagger canonical map entries: 204
AvitoClient public callable methods, excluding close/from_env/auth/debug_info: 56
sync Swagger binding factories with factory metadata: 48
sync bindings without factory metadata: 4
```

Reproducible verification commands:

```bash
poetry run python -c "from avito.core.swagger_discovery import discover_swagger_bindings; d=discover_swagger_bindings(); sync=[b for b in d.bindings if b.variant == 'sync' and b.operation_key is not None]; print(len(sync)); print(len(d.canonical_map)); print(len([b for b in sync if b.factory is None]))"
poetry run python -c "import inspect; from avito.client import AvitoClient; excluded={'close','from_env','auth','debug_info'}; print(len([name for name, value in inspect.getmembers(AvitoClient) if not name.startswith('_') and callable(value) and name not in excluded]))"
poetry run pytest tests/core/test_swagger_linter.py tests/contracts/test_swagger_contracts.py
```

Verification result:

```text
tests/core/test_swagger_linter.py tests/contracts/test_swagger_contracts.py:
1913 passed
```

Do not use Swagger tag/domain labels as canonical CLI coverage buckets. Current
Swagger labels are human-facing and may be localized. CLI coverage and wave
planning must use discovered `factory` metadata as the stable grouping key.

Sync binding count by discovered factory:

```text
<none>: 4
account: 3
account_hierarchy: 5
ad: 3
ad_promotion: 4
ad_stats: 4
application: 5
autoload_archive: 4
autoload_profile: 5
autoload_report: 8
autostrategy_campaign: 7
autoteka_monitoring: 4
autoteka_report: 7
autoteka_scoring: 2
autoteka_valuation: 1
autoteka_vehicle: 12
bbip_promotion: 3
call_tracking_call: 3
chat: 4
chat_media: 2
chat_message: 4
chat_webhook: 3
cpa_archive: 3
cpa_auction: 2
cpa_call: 2
cpa_chat: 4
cpa_lead: 2
delivery_order: 5
delivery_task: 1
job_dictionary: 2
job_webhook: 4
order: 9
order_label: 3
promotion_order: 4
rating_profile: 1
realty_analytics_report: 2
realty_booking: 2
realty_listing: 2
realty_pricing: 1
resume: 3
review: 1
review_answer: 2
sandbox_delivery: 25
special_offer_campaign: 5
stock: 2
target_action_pricing: 5
tariff: 1
trx_promotion: 3
vacancy: 11
```

Bindings without factory metadata:

- `avito.auth.provider.AlternateTokenClient.request_client_credentials_token`
- `avito.auth.provider.AlternateTokenClient.request_refresh_token`
- `avito.auth.provider.TokenClient.request_autoteka_client_credentials_token`
- `avito.auth.provider.TokenClient.request_client_credentials_token`

Implementation impact:

- These 4 auth-token bindings are not normal domain commands through `AvitoClient` factories.
- Treat these 4 auth-token bindings as intentional non-domain API exclusions for the first CLI release.
- Expose user-facing credential/account readiness through local `account`, `status`, and `doctor` workflows, not by turning token client methods into generic API commands.
- If a future release exposes direct token exchange commands, it must be a separate SDK architecture change with explicit public facade design; CLI must not call `TokenClient` or `AlternateTokenClient` directly.
- The final coverage linter must count this decision explicitly, not silently treat missing factory metadata as success.

Current public non-Swagger helper/workflow candidates on `AvitoClient`:

- `account_health`
- `business_summary` compatibility wrapper for `account_health`
- `listing_health`
- `chat_summary`
- `order_summary`
- `review_summary`
- `promotion_summary`
- `capabilities`

Initial helper policy:

- Canonical CLI commands may cover `account_health`, `listing_health`, `chat_summary`, `order_summary`, `review_summary`, `promotion_summary`, and `capabilities`.
- `business_summary` is a compatibility helper and should not receive a second canonical command unless product requirements explicitly demand an alias. If exposed, it is an alias and does not count as helper coverage.
- `auth()` and `debug_info()` remain SDK support surfaces, not API coverage commands. Their CLI equivalents are `status` and `doctor`.

## Documentation Structure Findings

Current documentation uses MkDocs Material with `docs_dir: docs/site`.
Navigation is controlled by `awesome-pages` through `.pages` files:

- `docs/site/.pages` is the top-level nav: Home, `Tutorials`, `How-to`, `Reference`, `Explanations`, `Changelog`.
- `docs/site/tutorials/.pages` contains onboarding tutorials.
- `docs/site/how-to/.pages` contains task-oriented recipes.
- `docs/site/reference/.pages` contains stable public contracts and generated reference pages.
- `docs/site/explanations/.pages` contains architecture and rationale pages.

Generated reference pages are produced by `docs/site/assets/_gen_reference.py` during MkDocs builds:

- `reference/coverage.md`
- `reference/api-report.md`
- `reference/operations.md`
- `reference/domains/*.md`
- `reference/enums.md`

CLI documentation must follow this structure instead of adding an isolated page:

- README: short CLI quickstart only, with link to full docs.
- `docs/site/index.md`: add CLI as a first-class entry point after CLI release.
- `docs/site/tutorials/getting-started.md`: add the shortest first CLI call path, or a short cross-link if the page would become noisy.
- `docs/site/how-to/cli.md`: practical CLI setup and daily workflows.
- `docs/site/reference/cli.md`: stable CLI contract: grammar, global flags, output formats, exit codes, config files, environment variables, safety flags, command coverage policy.
- `docs/site/explanations/cli-architecture.md`: design rationale: thin wrapper over `AvitoClient`, registry/discovery, coverage linter phases, exclusions, secret masking, pagination policy.
- `docs/site/explanations/security-and-redaction.md`: add CLI secret-storage and output-redaction notes when account store lands.
- `docs/site/explanations/api-coverage-and-deprecations.md`: add CLI coverage guarantee and documented-exclusion policy after the coverage linter exists.
- `docs/site/how-to/auth-and-config.md`: link CLI profile/account setup to SDK env-based configuration without duplicating the whole config reference.

Navigation updates required:

- Add `cli.md` to `docs/site/how-to/.pages`.
- Add `cli.md` to `docs/site/reference/.pages`.
- Add `cli-architecture.md` to `docs/site/explanations/.pages`.
- If README/index/tutorial links are added before the CLI is usable, mark them clearly as planned only. Prefer adding public-facing docs after Stage 12 when commands exist.

## Plan Review Findings

Additional findings from reviewing this plan against `.ai/STYLEGUIDE.md`, `.ai/cli-guidelines.md`, and `.ai/python-guidelines.md`:

- The plan must treat CLI commands as public contracts. Renames, output schema changes, exit-code changes, and flag removals need deprecation, not silent replacement.
- The CLI must have static architecture enforcement, not only review discipline. Import boundaries for `avito/cli/` must be covered by `scripts/lint_architecture.py` or a dedicated CLI architecture linter before broad command generation starts.
- CLI coverage grouping must be based on discovered `factory` metadata, not localized Swagger tag/domain labels. Tags may be useful in reports, but they are not stable enough to drive command coverage gates.
- Python guideline compliance must be part of every stage that changes Python code. `ruff` and `mypy` are necessary but not sufficient.
- The write-command rollout is too large as a single stage. It is split into safety primitives, domain coverage waves, and strict coverage gate so each increment remains reviewable and testable.
- Coverage must distinguish three statuses: implemented canonical command, documented temporary exclusion, and documented intentional permanent exclusion. Temporary exclusions require an owner/follow-up and must fail after the configured target stage if still present.
- Generated command registration must be deterministic and inspectable by the CLI coverage linter without constructing `AvitoClient`, reading account files, or touching the network.
- Public docs must only describe implemented commands. Future commands stay in this plan until the implementation exists.
- The console entry point must be a stable callable, not a Click command object itself. Use `avito.cli.app:main` for packaging and keep `app` as the reusable Click root command/group for tests and `python -m avito`.
- Root-level global options are the canonical syntax for the first release: `avito --profile main account get-self`. Supporting trailing global options such as `avito account get-self --profile main` is optional and must be implemented deliberately, not assumed from Click behavior.
- The generated API command layer must use deterministic Click command objects attached to the Click root group. This keeps registration inspectable without generating Python source.
- `click` is the CLI framework for every stage and must be an explicit runtime dependency from Stage 1.
- Safety classification cannot rely on HTTP method alone. HTTP method may provide a default, but final command safety must come from explicit registry metadata and reviewed overrides for write, destructive, expensive, and local commands.
- CLI import-boundary checks should extend the existing `scripts/lint_architecture.py` unless there is a concrete reason to split them into a dedicated script. Avoid two overlapping architecture linters.
- The stable CLI contract should be documented as soon as the corresponding surface exists. Create or update `docs/site/reference/cli.md` from the first stage that introduces user-visible flags, output fields, exit codes, or command names; Stage 13 remains the full documentation pass.
- Every stage that adds or changes user-visible CLI behavior must update `CHANGELOG.md`. The SDK styleguide treats CLI commands, flags, output fields, and exit codes as public contracts.
- Dependency stages must update both `pyproject.toml` and `poetry.lock`. Verification must include a lock consistency check after adding `click` or changing CLI runtime dependencies.
- Representative smoke tests by factory are not enough for the final "all methods" claim. Before strict coverage, every canonical CLI command must be registered, render help, and execute at least once through a fake client or `SwaggerFakeTransport` when safe synthetic arguments exist. Commands that cannot be executed generically need a documented exclusion or a custom adapter with tests.
- Secret input must not force users to put `client_secret` in shell history. `--client-secret` remains supported for explicit automation, but `account add` must also support a hidden TTY prompt and at least one non-interactive alternative such as `--client-secret-stdin` or documented environment/config input.
- Some Swagger-bound methods may need command-specific adapters for file input, multipart data, binary responses, or complex public input models. These adapters are allowed only inside `avito/cli/` and must still call public `AvitoClient` factories and public domain methods.
- New CLI scripts must be type-checked explicitly when they are outside the configured `avito` mypy package scope. Stage verification should include `poetry run mypy scripts/lint_cli_coverage.py` once that script exists.

## Test and Lint Boundaries

`.ai/STYLEGUIDE.md` has a closed testing policy. CLI work must follow it from
Stage 1 instead of using pytest as a general policy checker.

Use pytest only for runtime behavior that a user or integration can observe:

- CLI command execution, exit codes, stdout/stderr routing, and output formats;
- profile/account/config persistence behavior through temporary directories;
- secret masking on success, error, verbose, debug, and JSON paths;
- generic invocation through public `AvitoClient` factories and public domain methods;
- fake-transport API smoke flows with request/response behavior;
- pagination materialization behavior and dry-run transport behavior.

Use linters/scripts, not pytest, for static or inventory checks:

- architecture/import boundaries for `avito/cli/`;
- generated command naming, kebab-case resources/actions/flags, and forbidden `resource-id`;
- duplicate canonical commands, local/API collisions, alias policy, and exclusion metadata completeness;
- coverage inventory: missing bindings, extra commands, expired temporary exclusions, and strict one-to-one mapping;
- report determinism and sanitized CLI coverage report content.

Do not add pytest tests whose only purpose is to exercise the CLI coverage linter
with synthetic broken inputs. The linter is verified by running it against the
real repository in each stage gate. If a linter rule needs implementation-level
confidence, keep its parser/checker simple and cover it through deterministic
real-code fixtures or move the check into an existing static lint script.

## CLI Architecture

Use a small hand-written CLI shell plus registry/discovery-driven API commands:

```text
avito/
  cli/
    __init__.py
    app.py              # root Click group and global context
    accounts.py         # local account/profile commands only
    client.py           # CLI-only AvitoClient construction
    commands.py         # generic invocation engine for SDK methods
    config.py           # CLI home, JSON persistence, account/config store
    coverage.py         # CLI coverage report and linter helpers
    errors.py           # CLI errors, exit-code mapping, secret sanitization
    help.py             # help command compatibility when Click defaults are insufficient
    registry.py         # command registry built from SDK metadata
    schemas.py          # CLI input coercion from signatures/type hints
    serialization.py    # model/pagination result serialization
    ui.py               # stdout/stderr, table/json/plain output
```

Do not add domain-specific CLI modules for every API package unless a command needs custom UX. The default path must be metadata-driven to avoid hand-copying 204 operations.

Command registration approach:

- Use Click for the root group, global options, local workflow commands, and help/version/status/doctor/config/account commands.
- Register generated API commands deterministically from registry records.
- Generated API commands are typed `click.Command` objects attached to Click groups from registry metadata. This is deterministic command registration, not SDK method injection.
- Do not generate Python source files for commands.
- Do not use `setattr`, `globals()`, monkey-patching, or modifying SDK/domain classes to create commands.
- Generated command callbacks must all delegate to one invocation engine; command-specific behavior belongs in registry metadata only when the generic path cannot infer it safely.

Package boundary:

- `avito/cli/*` may import `avito.client`, `avito.config`, public models, public exceptions, and Swagger discovery/reporting helpers.
- `avito/__main__.py` must contain only the CLI handoff after Stage 1.
- Tests may use `avito.testing.*`, `tests/fake_transport.py`, and public testing helpers; production CLI code must not.

Register only the canonical command:

```toml
[tool.poetry.scripts]
avito = "avito.cli.app:main"
```

## Command Model

Follow `.ai/cli-guidelines.md`:

```text
avito <resource> <action> [primary arguments] [flags]
```

Resource names are derived from `AvitoClient` factory names with kebab-case. Actions are derived from public SDK method names with kebab-case.

Default generated shape:

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

- Factory and method arguments become named flags by default.
- Positional arguments are allowed only for obvious single primary identifiers after explicit design review.
- Same SDK concept uses the same flag everywhere: `--user-id`, `--item-id`, `--order-id`, `--chat-id`, `--date-from`, `--date-to`, `--limit`, `--offset`.
- `resource_id` and `--resource-id` are forbidden.
- Generated commands preserve one obvious path per operation.
- Compatibility aliases delegate to canonical commands and do not count toward coverage.
- Local workflows may share a resource with API commands only when the action is unambiguous. `avito account add` is local profile management; `avito account get-self` is an Avito API call.
- Registry construction fails if a local command and generated API command claim the same canonical `resource action`.

## Global Flags

Supported from root and subcommands through one typed CLI context:

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

Canonical invocation syntax for global options:

```bash
avito --profile main account get-self
avito --json --no-input account get-self
```

The first release only guarantees root-level global options before the resource/action path.
If trailing global options are added later, they must be additive, tested, and documented.

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

Initial implementation may support only user config, but the resolver must reserve the full precedence contract without breaking users later.

Flag behavior:

- `--json` emits stable undecorated JSON for success output and JSON errors on stderr.
- JSON stdout must not contain progress, warnings, hints, colors, or prose.
- `--quiet` suppresses non-essential success output; combined with `--json`, commands returning data still emit JSON.
- `--plain`, `--table`, and `--wide` are mutually exclusive with `--json`; invalid combinations exit with code `2`.
- `--verbose` is user-facing extra detail and never overrides `--quiet`.
- `--debug` may include diagnostics but must never leak secrets.
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

Stable error codes include:

- `CONFIG_INVALID`
- `ACCOUNT_NOT_FOUND`
- `ACCOUNT_EXISTS`
- `AUTH_REQUIRED`
- `PERMISSION_DENIED`
- `VALIDATION_FAILED`
- `COMMAND_UNSUPPORTED`
- `SDK_METHOD_FAILED`

Errors, warnings, progress, and debug diagnostics go to stderr. Command results go to stdout. JSON errors are valid JSON on stderr.

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

- Create the CLI home lazily with `0700` permissions.
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

Active account belongs in config as one profile name. Do not store contradictory `active: bool` flags on each account.

Canonical flags:

- `--client-id`
- `--client-secret`
- `--client-secret-stdin`
- `--base-url`
- `--user-id`

Ticket-compatible aliases:

- `--api-key` as an alias for `--client-secret`
- `--endpoint` as an alias for `--base-url`

## SDK Reuse Strategy

Generic API invocation pipeline:

1. Resolve global flags and validate CLI mode.
2. Resolve profile/account and build `AvitoSettings`.
3. Create `AvitoClient(settings)` in a context manager.
4. Resolve CLI resource to an `AvitoClient` factory.
5. Coerce CLI strings into factory and method arguments using public signatures/type hints.
6. Call the SDK factory.
7. Call the public domain method.
8. Serialize the SDK return value through `model_dump()` / `to_dict()` / bounded pagination helpers.
9. Render as table, grouped text, plain value, or JSON.

Constraints:

- Build `AvitoClient` only after command syntax, config/profile resolution, and secret masking context are ready.
- Never instantiate domain objects directly in CLI.
- Never call operation specs directly from CLI commands.
- CLI may inspect public signatures and type hints, but not private domain object attributes.
- Dataclass serialization fallback is allowed only for CLI-local dataclasses, not SDK response models.

The coercion engine must support:

- `str`, `int`, `float`, `bool`
- `date` and `datetime` strings with validation
- enums by value/name with clear validation errors
- optional values
- list values from repeated flags or documented comma-separated values
- public dataclass input models only when they are already public SDK input models
- `PaginatedList[T]` with explicit materialization limits or streaming-safe iteration
- file inputs only for methods whose public signature already accepts file/path-like public inputs

Complex input policy:

- Do not expose raw Avito request bodies.
- Do not expose internal request DTOs.
- If a public SDK method already accepts a documented public input model, CLI may accept either explicit model-field flags or `--input-json <path>` that is parsed into that public model.
- `--input-json -` reads from stdin and is forbidden when stdin is not available or when another prompt would be required.
- JSON input errors are `VALIDATION_FAILED` with Russian messages and no echoed secrets.

If a method cannot be safely exposed by the generic engine, add it to a typed exclusion list with reason, owner, and follow-up. Final acceptance target is zero unsupported sync Swagger-bound methods unless intentionally excluded and documented.

## Registry and Coverage

Build a CLI registry from existing SDK metadata:

- `discover_swagger_bindings(registry=SwaggerRegistry.load(...))`
- `binding.factory`
- `binding.factory_args`
- `binding.method_name`
- `binding.method_args`
- public Python signatures and type hints

Registry records contain:

- stable canonical command id, for example `account.get-self`;
- resource and action in lowercase kebab-case;
- binding operation key for Swagger-bound API commands;
- SDK factory name and public method name;
- factory and method argument metadata from discovery/signatures;
- safety classification: read, write, destructive, expensive, local;
- output hint: object, collection, mutation result, plain value, unknown;
- examples and related commands for help;
- aliases stored separately from canonical records;
- exclusions stored separately with reason and follow-up.

Coverage invariant:

```text
each sync discovered Swagger binding -> exactly one canonical CLI command or documented intentional exclusion
each canonical API CLI command -> exactly one sync discovered Swagger binding
each supported public non-Swagger helper -> CLI command or documented exclusion
```

Coverage report fields:

- `api_bound_commands`
- `api_bound_missing_commands`
- `api_bound_exclusions`
- `helper_commands`
- `helper_exclusions`
- `local_cli_commands`
- `aliases`

Add a linter:

```bash
poetry run python scripts/lint_cli_coverage.py --strict
```

The linter fails when:

- a sync discovered Swagger binding has no canonical CLI command or explicit exclusion;
- a canonical API CLI command has no binding;
- two canonical CLI commands map to the same binding;
- a supported public helper has neither a command nor an exclusion;
- a local command conflicts with a generated API command;
- a command exposes `resource-id`;
- a command exposes a secret in an output schema;
- a command uses non-kebab-case resource/action/flag names;
- an exclusion lacks reason and follow-up.

Add `make cli-lint` and include it in `make check` after full CLI coverage is implemented.

## Output Contract

Default output:

- Human-readable Russian text.
- Tables for collections.
- Grouped key-value output for one object.
- Concise success text for writes.
- Next-step hints only when helpful and not noisy.

Machine output:

- `--json` emits stable, undecorated JSON.
- Top-level objects are stable and named by resource/action where useful.
- SDK models are serialized via their public serialization contract.
- Pagination output includes enough metadata when available.

Secret masking:

- Mask by key name and value pattern where practical.
- Use the same sanitizer for human output, JSON output, errors, verbose/debug output, and coverage/debug reports.
- Cover nested structures, lists, exception metadata, and debug mode in tests.
- Never print raw `client_secret`, `api_key`, `refresh_token`, `access_token`, `Authorization`, or token-like fields.

## Help and Completion

Help requirements:

```bash
avito --help
avito account --help
avito account get-self --help
avito help account
avito help account get-self
```

Help must include:

- Russian description;
- usage;
- at least one minimal example;
- one automation-friendly `--json --no-input` example where relevant;
- flags with stable names;
- related commands when useful.

Implementation requirement:

- `avito help` is a public compatibility command, not a private Click behavior assumption.
- `avito help <resource>` and `avito help <resource> <action>` must be tested no later than the stage that introduces nested generated commands.
- If Click's default help cannot provide this shape, implement a small `help.py` adapter that reads the same command registry metadata used for command registration.

Completion commands:

```bash
avito completion bash
avito completion zsh
avito completion fish
```

Completion can start with static command/flag completion and later add profile/account names.

## Completed Pre-Coding Audit

Baseline audit was completed before CLI implementation on 2026-05-10. This is
recorded here as pre-work, not as an implementation stage.

Verified repository state:

```text
sync Swagger canonical map entries: 204
sync Swagger bindings without factory metadata: 4
sync Swagger bindings: 204
sync binding factories with factory metadata: 48
AvitoClient public callable methods, excluding close/from_env/auth/debug_info: 56
python -m avito behavior: silent smoke entry point that constructs AvitoClient
CLI package/dependency state: no avito/cli package, no click dependency, no console script
Makefile state: no cli-lint target; quality currently runs typecheck, lint,
  python-guidelines-lint, swagger-lint, architecture-lint, async-parity-lint,
  docstring-lint, build
```

Verification commands run:

```bash
poetry run python -c "from avito.core.swagger_discovery import discover_swagger_bindings; print(len(discover_swagger_bindings().canonical_map))"
poetry run python -c "from avito.core.swagger_discovery import discover_swagger_bindings; d=discover_swagger_bindings(); print(len([b for b in d.bindings if b.variant == 'sync' and b.operation_key is not None and b.factory is None]))"
poetry run python -m avito
poetry run pytest tests/core/test_swagger_linter.py tests/contracts/test_swagger_contracts.py
```

Verification result:

```text
canonical map entries: 204
sync bindings without factory metadata: 4
python -m avito: exited 0 with no output
tests/core/test_swagger_linter.py tests/contracts/test_swagger_contracts.py:
1913 passed in 8.67s
```

The 4 bindings without factory metadata remain the planned first-release
auth-token exclusions:

- `avito.auth.provider.AlternateTokenClient.request_client_credentials_token`
- `avito.auth.provider.AlternateTokenClient.request_refresh_token`
- `avito.auth.provider.TokenClient.request_autoteka_client_credentials_token`
- `avito.auth.provider.TokenClient.request_client_credentials_token`

## Implementation Stages

Stage policy:

- Each stage must leave the branch in a releasable state.
- Every behavior stage includes tests in the same change.
- Stage deliverables are additive to this policy section. If a stage changes
  public CLI behavior but does not repeat `CHANGELOG.md` or CLI reference docs
  in its own deliverables, the policy here still requires those updates.
- After Stage 4C, CLI coverage report changes must be intentional in every CLI metadata change.
- After Stage 10C, `scripts/lint_cli_coverage.py --strict` is a required gate for all CLI changes.
- Do not broaden command coverage before the previous stage's verification passes.
- Keep each stage small enough for review. If a stage needs more than roughly 300-500 lines of production code or touches more than three production modules, split it into lettered sub-stages in this file before implementing.
- A sub-stage has its own deliverables, tests, verification commands, and checked-off exit criteria.
- If a coverage wave contains methods with file input, multipart payloads,
  binary responses, complex public input models, destructive operations, or
  expensive side effects, split that wave before coding. Do not absorb that
  complexity into a broad generated-command change.
- Do not mark a checklist item complete from inspection alone when a command or test can verify it.
- Every stage that changes Python code must run `poetry run python scripts/lint_python_guidelines.py`.
- Every stage that adds or changes CLI production imports must run `poetry run python scripts/lint_architecture.py` or the dedicated CLI architecture lint command introduced by that stage.
- Every stage that changes command metadata must run the current `scripts/lint_cli_coverage.py` phase, even before strict mode is enabled.
- Every stage that changes persisted config/account JSON shape must include migration/backward-compatibility tests or explicitly state why no existing persisted shape exists yet.
- Every stage that changes user-visible CLI text, flags, output fields, or exit codes must update `docs/site/reference/cli.md` once that reference page exists.
- Every stage that changes CLI public behavior must update `CHANGELOG.md` in the same change.
- Every stage that adds runtime dependencies must update `poetry.lock` and verify that dependency resolution is consistent.
- After `scripts/lint_cli_coverage.py` exists, every stage that touches CLI
  metadata, adapters, coverage, or registration must run
  `poetry run mypy scripts/lint_cli_coverage.py`.

Coverage linter phase policy:

- Stage 4C introduces `scripts/lint_cli_coverage.py` in report/partial mode. It must validate registry invariants that exist at that stage, but it must not require full all-domain command coverage yet.
- Stages 8-9 use the linter in read-coverage mode.
- Stage 10C switches the linter to strict mode and adds `make cli-lint` to `make check`.
- Strict mode fails on every missing sync Swagger-bound command unless there is a documented intentional exclusion.
- Linter output must be deterministic and sanitized so it can be committed as an audit artifact when needed.

Execution coverage policy:

- A command being registered and help-renderable is not enough for final
  coverage. Every canonical command must execute at least once through a fake
  client or fake transport unless it has a documented execution-smoke exclusion.
- Execution-smoke exclusions are separate from API coverage exclusions. They
  must include reason, owner, follow-up, and whether the command is still
  user-supported.
- Commands needing file input, stdin, binary output, multipart handling, or
  complex public input models should receive explicit CLI adapters rather than
  weakening the generic invocation path.

### Stage 1: CLI Dependency and Shell

Deliverables:

- Add `click` as an explicit runtime dependency.
- Update `poetry.lock` after dependency changes.
- Use Click test utilities only in tests; do not add a custom subprocess harness unless behavior specifically requires `python -m avito`.
- Add `avito/cli/` package skeleton.
- Add root `avito` Click group with typed global context.
- Add `avito --help`, `avito --version`, `avito version`.
- Add `avito help` as the user-facing help entry point. At Stage 1 it may delegate to root help only; nested help such as `avito help account get-self` becomes mandatory once nested commands exist.
- Route `python -m avito` to the same CLI app.
- Register Poetry script as `avito = "avito.cli.app:main"`; keep `app` as the reusable Click command/group object.
- Use Russian help text from the beginning.
- Add a `CHANGELOG.md` entry for the new CLI shell and public entry points.

Tests:

- `tests/cli/test_app.py`
- help output smoke tests;
- version command tests;
- global flag parsing tests.

Verification:

```bash
poetry run pytest tests/cli/test_app.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
poetry check --lock
poetry build
```

Exit criteria:

- Help/version commands do not touch network, config, or account files.
- `python -m avito --help` and `avito --help` exercise the same app.
- Importing `avito.cli.app` has no filesystem side effects and does not construct `AvitoClient`.
- Root-level global options are parsed in the canonical position before subcommands.

Stage checklist:

- [ ] `click` is added as a runtime dependency.
- [ ] `poetry.lock` is updated and lock consistency is verified.
- [ ] `avito/cli/` package exists with only the minimal shell files.
- [ ] `avito --help`, `avito help`, `avito --version`, `avito version`, and `python -m avito --help` work.
- [ ] Poetry script points to `avito.cli.app:main`, not directly to the Click command/group object.
- [ ] Canonical root-level global option syntax is covered by tests.
- [ ] No config directory or account file is created by help/version commands.
- [ ] `tests/cli/test_app.py` covers the shell behavior.
- [ ] Stage verification commands pass.

### Stage 2: Errors, UI, and Safe Output

Deliverables:

- Add `CliContext`.
- Add `CliError` hierarchy and exit-code mapping.
- Add stdout/stderr output helpers.
- Add JSON/human error rendering.
- Add one reusable sanitizer used by all renderers.
- Add color handling for `--no-color` and `NO_COLOR=1`.
- Add invalid global flag-combination validation.
- Create or update `docs/site/reference/cli.md` with the exit codes, global flags, output modes, stdout/stderr split, and current implemented commands.
- Add `cli.md` to `docs/site/reference/.pages` when the reference page is created.
- Update `CHANGELOG.md` with the first documented CLI contract: global flags, output modes, and exit codes.

Tests:

- human errors go to stderr;
- JSON errors are valid JSON on stderr;
- `--debug` does not reveal secrets;
- `--quiet` suppresses non-essential success output;
- invalid flag combinations exit with code `2`.

Verification:

```bash
poetry run pytest tests/cli/test_errors.py tests/cli/test_ui.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
poetry run mkdocs build --strict
```

Exit criteria:

- Every CLI error has a Russian message, stable uppercase code, and documented exit code.
- No traceback is printed by default; diagnostics are sanitized.
- The reference CLI contract documents only implemented behavior.

Stage checklist:

- [ ] `CliContext` is typed and shared by commands through one code path.
- [ ] `CliError` maps to documented exit codes.
- [ ] Human and JSON errors use the same sanitized error payload.
- [ ] Invalid output flag combinations exit with code `2`.
- [ ] `--quiet`, `--debug`, `--verbose`, `--no-color`, and `NO_COLOR=1` are covered by tests.
- [ ] `docs/site/reference/cli.md` documents implemented global flags, output modes, and exit codes.
- [ ] `docs/site/reference/.pages` includes `cli.md` once the page exists.
- [ ] Stage verification commands pass.

### Stage 3: Account Store and Profile Commands

Split Stage 3 into two reviewable sub-stages. Do not implement API invocation in
this stage; account/profile commands are local only.

#### Stage 3A: Account Store Primitives

Deliverables:

- Implement CLI home resolver and atomic JSON persistence.
- Implement account/config dataclasses and stores.
- Implement safe store loading: missing files, malformed JSON, permission
  failures, and schema-version handling.
- Implement conversion from stored account data to `AvitoSettings` without
  constructing `AvitoClient`.
- Store active account name in config, not per-account flags.

Tests:

- default home and environment override precedence;
- lazy directory creation;
- file permissions where platform supports it;
- atomic JSON writes through same-directory temporary files and `os.replace`;
- malformed JSON handling;
- account/config dataclass serialization masks secrets in JSON output helpers;
- conversion to `AvitoSettings` uses only SDK public settings types.

Verification:

```bash
poetry run pytest tests/cli/test_config.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Importing account/config modules creates no directories or files.
- Store code performs no Avito API network calls.
- Permission and malformed-file failures map to typed CLI errors.

Stage checklist:

- [ ] CLI home resolution follows `AVITO_PY_HOME`, `MY_SDK_HOME`, then `~/.avito-py`.
- [ ] Directory/file creation is lazy and uses required permissions where supported.
- [ ] JSON writes are atomic through same-directory temp files and `os.replace`.
- [ ] Active account is stored once in config, not as per-account boolean state.
- [ ] Store loading and malformed JSON behavior are tested.
- [ ] Stage 3A verification commands pass.

#### Stage 3B: Account Commands and Secret Input

Deliverables:

- Add account commands:
  - `avito account add`
  - `avito account list`
  - `avito account use <account-name>`
  - `avito account current`
  - `avito account delete <account-name>`
- Add optional `account remove` only as documented alias for `account delete`.
- Support safe secret entry for `client_secret`: hidden TTY prompt by default when input is allowed, plus a non-interactive path that does not require putting the secret directly in shell history.
- Add `--client-secret-stdin` for non-interactive secret input. It reads exactly
  one secret value from stdin, strips one trailing newline, refuses TTY stdin, and
  is mutually exclusive with `--client-secret` and `--api-key`.
- Keep `--client-secret` and ticket-compatible `--api-key` for explicit automation, but document the shell-history tradeoff.
- Ensure `--no-input` fails with `AUTH_REQUIRED`/`CONFIG_INVALID` instead of
  prompting when no secret was provided.
- Update `CHANGELOG.md` for account/profile commands and local plaintext secret storage behavior.

Tests:

- add/reload account;
- duplicate account conflict;
- active account set/get/clear;
- no-input behavior;
- ticket aliases `--api-key` and `--endpoint`;
- hidden prompt path;
- `--client-secret-stdin` path;
- mutually exclusive secret flags;
- JSON output contains no raw secrets.

Verification:

```bash
poetry run pytest tests/cli/test_accounts.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Account commands perform no Avito API network calls.
- Secret fields are masked in every output mode.
- Users have one interactive and one non-interactive way to provide secrets
  without putting them in shell history.

Stage checklist:

- [ ] Account add/list/use/current/delete commands work without network.
- [ ] `--api-key` and `--endpoint` aliases are tested.
- [ ] Hidden prompt secret input is tested.
- [ ] `--client-secret-stdin` is tested and refuses TTY stdin.
- [ ] `--client-secret`, `--api-key`, and `--client-secret-stdin` are mutually exclusive.
- [ ] Public docs or reference text clearly describe plaintext local storage and safe secret input.
- [ ] Stage 3B verification commands pass.

### Stage 4: CLI Registry From SDK Metadata

Split Stage 4 into three reviewable sub-stages. The goal is to introduce the
registry foundation, then help/alias behavior, then static coverage and
architecture enforcement. Do not start generic input coercion in Stage 5 until
all Stage 4 sub-stages pass.

#### Stage 4A: Typed Registry and Discovery Report

Deliverables:

- Build `avito/cli/registry.py`.
- Convert sync discovered Swagger bindings into canonical API command records.
- Preserve factory name, factory args, method name, method args, operation key,
  spec, path, HTTP method, domain, deprecated flag, and legacy flag.
- Derive canonical resource/action names from factory and method names using
  lowercase kebab-case.
- Register local commands and public non-Swagger helpers in separate categories,
  but do not implement nested registry-backed help yet.
- Add exclusion record types for API bindings, helper workflows, and execution
  smoke coverage.
- Add deterministic registry JSON/report data that can be produced without
  constructing `AvitoClient`, reading account files, or touching the network.
- Keep adapter references as stable string ids only; do not import adapter
  implementation modules during registry construction.

Tests:

- registry can be built without constructing `AvitoClient`, reading account
  files, or touching the network;
- sync discovered Swagger bindings are represented in report mode as command
  candidates or explicit exclusions;
- API, helper, local, alias placeholder, and exclusion records are separate typed
  categories;
- registry report output is deterministic.

Verification:

```bash
poetry run pytest tests/cli/test_registry.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Registry records are typed, deterministic, and serializable.
- Registry builds without creating `AvitoClient`.
- Registry pytest tests cover runtime behavior only.
- Full missing-command failures are deferred to later coverage-linter phases, not
  silently skipped.

Stage checklist:

- [ ] `avito/cli/registry.py` exists with typed API, helper, local, alias, and exclusion records.
- [ ] Sync Swagger bindings are converted into deterministic command candidates.
- [ ] Factory/method metadata and Swagger binding identifiers are preserved.
- [ ] Registry construction has no network, config, account-file, or `AvitoClient` side effects.
- [ ] Registry records can reference named adapters without importing adapter implementation modules.
- [ ] Stage 4A verification commands pass.

#### Stage 4B: Registry Help, Aliases, and Collisions

Deliverables:

- Add nested help support for registry-backed resources and actions:
  - `avito help <resource>`;
  - `avito help <resource> <action>`;
  - generated help must use registry metadata and must not instantiate
    `AvitoClient`.
- Add alias support separate from canonical command records.
- Ensure aliases delegate to canonical records and never count as command
  coverage.
- Add deterministic collision detection for `resource action` across local,
  helper, generated API, and alias records.
- Add local/API collision errors before command registration.
- Add help metadata fields needed by later generated commands: examples, related
  commands, safety summary, output hint, and adapter id.

Tests:

- `avito help <resource>` and `avito help <resource> <action>` render
  registry-backed help without constructing `AvitoClient`;
- local helper command metadata is visible to help/registration code separately
  from API command metadata;
- aliases delegate to canonical command records at runtime and do not produce
  duplicate callbacks;
- local/API command collisions fail during registry construction.

Verification:

```bash
poetry run pytest tests/cli/test_registry.py tests/cli/test_app.py
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Registry-backed help works for resources and actions.
- Alias behavior is deterministic and does not create duplicate canonical
  commands.
- Local/API command collisions fail before runtime command registration.

Stage checklist:

- [ ] Registry-backed `avito help <resource>` and `avito help <resource> <action>` are implemented and tested.
- [ ] API, helper, local, alias, and exclusion records remain separate categories.
- [ ] Compatibility aliases delegate to canonical commands and do not count as coverage.
- [ ] Local/API command collisions fail during registry construction.
- [ ] Stage 4B verification commands pass.

#### Stage 4C: CLI Coverage and Architecture Lint

Deliverables:

- Add `scripts/lint_cli_coverage.py`.
- Implement `scripts/lint_cli_coverage.py --phase registry`.
- In registry phase, verify that the registry includes all sync discovered
  bindings in report mode without requiring full all-domain command coverage yet.
- Verify lowercase kebab-case resource/action names, duplicate canonical
  commands, one-to-one binding ownership for records present at this stage,
  alias policy, local/API collisions, forbidden `resource-id`, and required
  exclusion metadata.
- Verify that adapter references, if present, point to an explicit adapter
  registry entry rather than ad hoc callback names.
- Extend `scripts/lint_architecture.py` with CLI import-boundary checks that
  forbid production `avito/cli/` imports from `tests`, `avito.testing`, domain
  operation modules, transport implementations, auth provider internals, and
  `avito.core.operations`. Add a dedicated CLI architecture linter only if the
  existing script becomes materially unsuitable.

Tests:

- runtime registry tests from Stage 4A and Stage 4B still pass;
- linter verification is performed by running the linter against the real
  repository, not by adding synthetic policy-only pytest cases.

Verification:

```bash
poetry run pytest tests/cli/test_registry.py tests/cli/test_app.py
poetry run python scripts/lint_cli_coverage.py --phase registry
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Exit criteria:

- CLI coverage linter fails on duplicate records, invalid names, local/API
  collisions, forbidden `resource-id`, invalid adapter references, or missing
  required exclusion metadata.
- Architecture lint statically enforces CLI production import boundaries.
- Full missing-command failures are deferred to read/full coverage phases, not
  silently skipped.

Stage checklist:

- [ ] `scripts/lint_cli_coverage.py` exists and exercises the registry in `--phase registry`.
- [ ] Canonical API commands present at this stage map one-to-one to sync Swagger bindings.
- [ ] CLI coverage linter checks kebab-case names, alias policy, local/API collisions, forbidden `resource-id`, and exclusion metadata.
- [ ] Existing `scripts/lint_architecture.py` statically checks CLI production import boundaries, unless a documented dedicated-linter exception exists.
- [ ] Stage 4C verification commands pass.

### Stage 5: Generic Input Coercion

Deliverables:

- Implement `avito/cli/schemas.py`.
- Implement typed CLI parameter metadata.
- Coerce CLI strings from signatures/type hints.
- Support repeated flags and documented comma-separated list parsing.
- Validate enum names/values and date/datetime formats with Russian errors.

Tests:

- coercion for primitives, bools, dates, datetimes, enums, optionals, and lists;
- missing required values fail without prompt in `--no-input`;
- invalid values produce `VALIDATION_FAILED`;
- supported repeated flags and comma-separated values coerce to the same typed list result.

Static lint responsibilities:

- generated flag names are lowercase kebab-case;
- generated flags never expose `--resource-id`.

Verification:

```bash
poetry run pytest tests/cli/test_schemas.py
poetry run python scripts/lint_cli_coverage.py --phase registry
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Input coercion is testable without constructing `AvitoClient` or invoking network code.

Stage checklist:

- [ ] CLI parameter metadata is typed and independent from Click internals where practical.
- [ ] Primitive, bool, date, datetime, enum, optional, and list coercion are tested.
- [ ] Repeated flags and documented comma-separated values behave consistently.
- [ ] Invalid values produce Russian `VALIDATION_FAILED` errors.
- [ ] Generated flag names are checked by the CLI coverage linter for kebab-case and absence of `--resource-id`.
- [ ] Stage verification commands pass.

### Stage 6: Generic Invocation Engine

Deliverables:

- Implement `avito/cli/commands.py`.
- Build and call `AvitoClient` through active account/profile.
- Invoke public SDK factory and method.
- Map SDK exceptions to CLI errors.
- Add explicit unsupported-method registry only for documented exclusions.
- Add a typed client factory protocol for tests so invocation behavior can be verified without real HTTP.
- Production code must default to constructing `AvitoClient`; tests may inject a fake client through the protocol.

Tests:

- active profile is used by default;
- `--profile` overrides active profile;
- CLI invokes expected factory and public method with expected arguments;
- SDK `AuthenticationError`, `AuthorizationError`, `ValidationError`, `ConflictError`, and not-found equivalents map to documented exit codes.

Static lint responsibilities:

- CLI production code does not import or call operation specs, operation executor, transport implementations, auth provider internals, or testing fake transports.

Verification:

```bash
poetry run pytest tests/cli/test_commands.py
poetry run python scripts/lint_cli_coverage.py --phase registry
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- API invocation path is a thin adapter over `AvitoClient` factories and public domain methods.

Stage checklist:

- [ ] API command invocation resolves profile/config before constructing `AvitoClient`.
- [ ] `AvitoClient` is always used as a context manager.
- [ ] Invocation calls factory method, then public domain method.
- [ ] Test-only fake clients are injected through typed protocols and are not imported by production CLI modules.
- [ ] Architecture lint proves operation specs and transport are not called directly by CLI production code.
- [ ] SDK exceptions map to documented CLI exit codes and sanitized messages.
- [ ] Stage verification commands pass.

### Stage 6B: Command Adapter Extension Point

Deliverables:

- Add `avito/cli/adapters.py` with a typed adapter protocol for commands whose
  public SDK signature is valid but cannot be exposed safely by the fully generic
  path.
- Restrict adapters to CLI input/output concerns: file opening, stdin handling,
  multipart-friendly path arguments, binary result rendering, and public input
  model construction.
- Require every adapter to call the same invocation engine or public
  `AvitoClient` factory/domain method path. Adapters must not call operation
  specs, operation executor, transport, auth provider internals, or domain object
  constructors directly.
- Add adapter metadata to registry records by stable adapter id. Do not store raw
  callables in metadata that must be serialized by the coverage report.
- Add linter checks that every adapter id referenced by a command exists, is
  used by at least one command, and has an owner/reason note.

Tests:

- a simple adapter can transform CLI-only input and still invokes a public SDK
  method through the shared path;
- adapter errors are sanitized and mapped to documented CLI exit codes;
- adapter registry rejects unknown adapter ids and duplicate adapter ids;
- an adapter-backed command still renders help and appears in coverage reports.

Verification:

```bash
poetry run pytest tests/cli/test_adapters.py tests/cli/test_commands.py
poetry run python scripts/lint_cli_coverage.py --phase registry
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- Adapter support exists before any all-domain command wave needs it.
- Adapter-backed commands remain auditable by the coverage linter.

Stage checklist:

- [ ] Adapter protocol is typed and documented in code.
- [ ] Adapter metadata is stable and serializable in registry/coverage reports.
- [ ] Adapter-backed invocation still uses public SDK factories and methods only.
- [ ] Architecture lint prevents adapters from importing forbidden internal layers.
- [ ] Unknown, duplicate, or unused adapter ids fail lint.
- [ ] Stage 6B verification commands pass.

### Stage 7: Result Serialization and Pagination

Deliverables:

- Implement `avito/cli/serialization.py`.
- Serialize SDK models through `model_dump()` / `to_dict()`.
- Serialize CLI-local dataclasses, enums, dates, datetimes, lists, and primitive values safely.
- Handle `PaginatedList[T]` with documented bounded defaults.
- Add `--limit`, `--page-limit`, and `--all` consistently for paginated commands when needed to avoid unbounded materialization.
- Default paginated output must be bounded. Conservative default: first page only or at most the SDK/default page size when the operation exposes a page size.
- `--all` must require an explicit opt-in and should show progress on stderr for long materialization.
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
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- JSON output schema is stable for object, collection, primitive, and paginated values.
- Default pagination cannot accidentally materialize an unbounded result set.

Stage checklist:

- [ ] SDK models serialize through `model_dump()` or `to_dict()`.
- [ ] CLI-local dataclasses, enums, dates, datetimes, lists, and primitives serialize safely.
- [ ] Pagination defaults are bounded and documented in command help.
- [ ] Human table/grouped output and JSON output are both tested.
- [ ] Secret sanitizer is applied after serialization and before rendering.
- [ ] Stage verification commands pass.

### Stage 8: First Vertical API Slice

Deliverables:

- Expose and test a small read-only slice:
  - `avito account get-self`
  - `avito account get-balance`
  - one paginated/list command if available.
- Use `SwaggerFakeTransport` or existing fake transport infrastructure in tests only.
- Do not make real network calls in tests.

Tests:

- command invokes expected SDK method;
- request path/query/body match fake transport expectations;
- human output works;
- JSON output works;
- errors map correctly.

Verification:

```bash
poetry run pytest tests/cli/test_account_api_commands.py
poetry run pytest tests/contracts/test_swagger_contracts.py
poetry run python scripts/lint_cli_coverage.py --phase read
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli
```

Exit criteria:

- At least one registry-bound API command runs end to end through generic path and fake transport.

Stage checklist:

- [ ] `account get-self` runs through registry, coercion, invocation, serialization, and UI layers.
- [ ] `account get-balance` runs through the same generic path.
- [ ] At least one list/paginated command is covered if an account-domain candidate exists.
- [ ] Tests use fake transport only and make no real network calls.
- [ ] Human output and `--json` output are both covered.
- [ ] Stage verification commands pass.

### Stage 9: Read-Only All-Domain API Coverage

Deliverables:

- Register generated read/list/get commands for every sync Swagger-bound read method supported by the generic engine.
- Add domain/resource help pages for read-only commands.
- Add generated examples where safe and meaningful.
- Add command metadata for methods needing custom list/file/enum parsing.
- Document every temporarily unsupported read-only sync binding.
- Before registering a whole factory group, classify each read-only method as
  generic, adapter-backed, or excluded. Methods requiring file/stdin/binary
  handling or complex public input models must not be forced through the generic
  path just to satisfy coverage.

Required coverage groups:

- Use discovered `factory` names as the canonical grouping key.
- Keep smoke-test grouping human-sized by clustering related factories only for
  test organization, not for coverage accounting.
- Every factory that owns at least one read-only sync binding must have either a
  smoke invocation in this stage or an explicit temporary exclusion with follow-up.

Tests:

- one read-only smoke invocation per completed factory group with fake transport;
- every canonical read-only command is registered, renders help, and has either a successful fake execution test or a documented temporary exclusion from execution smoke with reason and follow-up;
- human and JSON output for representative object and collection commands;
- fake-transport behavior proves no real network calls are made.

Static lint responsibilities:

- every discovered read-only sync binding has a canonical command or explicit temporary exclusion;
- generated read-only commands do not expose forbidden names or secret fields;
- local/API command collisions and alias policy remain valid.

Verification:

```bash
poetry run pytest tests/cli/test_domain_smoke_commands.py
poetry run python scripts/lint_cli_coverage.py --phase read
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Exit criteria:

- All sync Swagger-bound read-only methods are exposed or documented with temporary exclusions.
- Coverage report separates complete read coverage from pending write/destructive coverage.

Stage checklist:

- [ ] Every completed factory group has at least one read-only smoke command test.
- [ ] Every canonical read-only command has registration/help coverage and execution coverage or a documented temporary execution-smoke exclusion.
- [ ] CLI coverage linter covers every discovered read-only sync binding.
- [ ] Unsupported read-only bindings have explicit temporary exclusions with follow-up.
- [ ] Domain/resource help exists for generated read-only commands.
- [ ] Coverage linter distinguishes read coverage from pending write coverage.
- [ ] Stage verification commands pass.

### Stage 10A: Write Safety Primitives

Deliverables:

- Classify write/destructive commands from explicit registry safety metadata. HTTP method may provide defaults, but reviewed metadata is the source of truth.
- Require confirmation for destructive commands unless `--yes` or exact `--confirm` is supplied.
- Support `--dry-run` only when the SDK public method already supports `dry_run` or when CLI can safely preview without changing SDK behavior.
- Do not fake dry-run for SDK methods that would still execute transport.
- Ensure write commands build the same SDK call in dry-run and apply modes where `dry_run` exists.
- Add write/destructive command metadata fields without broadening all-domain write coverage yet.
- Add safety help text and examples for commands that can modify state or trigger expensive operations.

Tests:

- delete/reset-like commands require confirmation;
- `--no-input` fails instead of prompting;
- `--yes` and `--confirm` behave deterministically;
- dry-run methods do not call transport when SDK contract says they should not;
- non-dry-run write commands call transport exactly once.

Static lint responsibilities:

- safety metadata cannot be absent for write/destructive/expensive records;
- HTTP-method-derived safety defaults must be reviewed into explicit registry metadata before a command is exposed;
- destructive/expensive command help includes required safety flags and examples.

Verification:

```bash
poetry run pytest tests/cli/test_write_safety.py
poetry run python scripts/lint_cli_coverage.py --phase write-safety
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Exit criteria:

- No destructive command can run accidentally in non-interactive mode.
- `--dry-run` is exposed only where the SDK method can actually avoid transport or apply mode can be proven equivalent by tests.

Stage checklist:

- [ ] Write/destructive/expensive classification is deterministic and tested.
- [ ] Exposed write/destructive/expensive commands have explicit reviewed safety metadata.
- [ ] Destructive commands require prompt, `--yes`, or exact `--confirm`.
- [ ] `--no-input` never hangs and fails safely when confirmation is required.
- [ ] `--dry-run` is exposed only for SDK methods that safely support it.
- [ ] Safety behavior is reflected in command help.
- [ ] Stage verification commands pass.

### Stage 10B: Write Command Coverage by Domain Waves

Deliverables:

- Register generated commands for remaining write sync Swagger-bound methods in small domain waves.
- Treat the suggested waves as planning defaults, not mandatory commit size. If
  a wave exceeds the stage size policy, split it into smaller sub-waves in this
  file before implementation and give each sub-wave its own tests,
  verification, and checklist.
- Use discovered `factory` names as the wave unit. Suggested waves, based on the 2026-05-10 baseline:
  - Wave 1: low-count/low-risk factories: `rating_profile`, `review`, `review_answer`, `realty_analytics_report`, `realty_booking`, `realty_listing`, `realty_pricing`, `tariff`, `account`, `account_hierarchy`.
  - Wave 2: medium factories: `ad`, `ad_promotion`, `ad_stats`, `cpa_archive`, `cpa_auction`, `cpa_call`, `cpa_chat`, `cpa_lead`, `chat`, `chat_media`, `chat_message`, `chat_webhook`, `special_offer_campaign`.
  - Wave 3: jobs and autoload factories: `application`, `resume`, `vacancy`, `job_dictionary`, `job_webhook`, `autoload_archive`, `autoload_profile`, `autoload_report`.
  - Wave 4: large/high-risk commerce and promotion factories: `order`, `order_label`, `delivery_order`, `delivery_task`, `sandbox_delivery`, `stock`, `promotion_order`, `autostrategy_campaign`, `bbip_promotion`, `trx_promotion`, `target_action_pricing`.
  - Wave 5: Autoteka factories: `autoteka_vehicle`, `autoteka_report`, `autoteka_monitoring`, `autoteka_scoring`, `autoteka_valuation`.
- Each wave must update command metadata, smoke tests, exclusions, and coverage report together.
- Eliminate or document every unsupported sync binding in the wave before moving to the next wave.
- Temporary exclusions are allowed only inside a wave and must include owner, reason, target stage, and follow-up.
- Before exposing a write command, record its safety classification explicitly
  in registry metadata. HTTP method defaults can propose a classification, but
  reviewed metadata is required before the command becomes public.

Tests:

- one write smoke invocation per write-capable factory group in the current wave with fake transport;
- every canonical write command in the current wave is registered, renders help, and has either a successful fake execution test or a documented temporary execution-smoke exclusion with reason and follow-up;
- safety tests run for at least one destructive or expensive command when the wave contains one.

Static lint responsibilities:

- coverage linter fails on missing write commands for completed waves;
- coverage linter covers every write sync binding in completed waves;
- coverage linter verifies command naming, alias policy, and exclusion metadata for completed waves.

Verification for each wave:

```bash
poetry run pytest tests/cli/test_write_safety.py
poetry run pytest tests/cli/test_domain_smoke_commands.py
poetry run python scripts/lint_cli_coverage.py --phase write --domain <domain-or-wave>
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Exit criteria:

- Every write sync binding in completed waves has a canonical command or explicit temporary/intentional exclusion.
- Domain smoke tests use fake transport only and make no real network calls.
- No broad write coverage change lands without matching tests.

Stage checklist:

- [ ] Wave 1 write commands are covered or explicitly excluded.
- [ ] Wave 2 write commands are covered or explicitly excluded.
- [ ] Wave 3 write commands are covered or explicitly excluded.
- [ ] Wave 4 write commands are covered or explicitly excluded.
- [ ] Wave 5 write commands are covered or explicitly excluded.
- [ ] Every completed wave has fake-transport smoke tests.
- [ ] Every canonical write command in completed waves has registration/help coverage and execution coverage or a documented temporary execution-smoke exclusion.
- [ ] Temporary exclusions have owner, reason, target stage, and follow-up.
- [ ] Stage verification commands pass for each wave.

### Stage 10C: Strict CLI Coverage Gate

Deliverables:

- Switch `scripts/lint_cli_coverage.py --strict` to fail on every missing sync Swagger-bound command unless it has a documented intentional exclusion.
- Fail strict mode on expired temporary exclusions.
- Add `make cli-lint` and include it in `quality` after `swagger-lint` and before `architecture-lint`.
- Ensure the strict report is deterministic, sanitized, and suitable for CI output.
- Enforce that every canonical API command is registered and help-renderable.
- Enforce that every canonical API command has execution-smoke coverage or an intentional documented execution exclusion.

Tests:

- smoke command suite still passes for every completed factory group;
- representative strict-covered commands still run through fake transport with human and JSON output.

Static lint responsibilities:

- strict linter enforces that the real registry has no missing sync binding without an intentional exclusion;
- strict linter enforces that the real registry has no duplicate canonical command for one binding;
- strict linter enforces that the real registry has no canonical API command without a binding;
- strict linter enforces that the real registry has no expired temporary exclusions;
- strict linter passes with only implemented commands and intentional exclusions.

Verification:

```bash
poetry run pytest tests/cli/test_domain_smoke_commands.py
poetry run python scripts/lint_cli_coverage.py --strict
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
make cli-lint
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Exit criteria:

- Every sync discovered Swagger binding has exactly one canonical CLI command or documented intentional exclusion.
- `make cli-lint` is part of `make check` through `quality`.
- Every canonical CLI command is registered, help-renderable, and covered by execution smoke or explicit execution exclusion.

Makefile integration:

- Add `cli-lint` as `poetry run python scripts/lint_cli_coverage.py --strict`.
- Include `cli-lint` in `quality` after `swagger-lint` and before `architecture-lint`.
- Do not add strict `cli-lint` to `make check` before Stage 10C; earlier stages use explicit phase commands only.

Stage checklist:

- [ ] Remaining sync Swagger bindings are covered or intentionally excluded.
- [ ] All canonical API commands have registration/help coverage.
- [ ] All canonical API commands have execution-smoke coverage or documented intentional execution exclusions.
- [ ] `make cli-lint` is added to `make check`.
- [ ] Stage verification commands pass.

### Stage 11: Public Helper Workflows

Deliverables:

- Expose supported non-Swagger helper workflows or document exclusions:
  - account health/business summary;
  - chat summary;
  - order summary;
  - review summary;
  - promotion summary;
  - capability discovery.
- Keep helper commands out of the Swagger one-to-one coverage count.
- Ensure helper commands use public `AvitoClient`/SDK methods only.

Tests:

- helper command metadata or explicit exclusions are covered;
- helper commands do not conflict with API-bound commands;
- helper outputs are sanitized and support `--json`.

Verification:

```bash
poetry run pytest tests/cli/test_helper_workflows.py
poetry run python scripts/lint_cli_coverage.py --strict
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check avito/cli tests/cli scripts/lint_cli_coverage.py
```

Stage checklist:

- [ ] Each supported helper workflow has a command or explicit exclusion.
- [ ] Helper commands are excluded from Swagger one-to-one coverage counts.
- [ ] Helper commands use only public `AvitoClient`/SDK methods.
- [ ] Helper commands do not collide with generated API commands.
- [ ] Helper outputs support human and JSON modes and are sanitized.
- [ ] Stage verification commands pass.

### Stage 12: Config, Status, Doctor, and Completion

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
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run mypy avito
poetry run ruff check avito/cli tests/cli
```

Stage checklist:

- [ ] `config get/set/unset/list/list --show-source` work and are tested.
- [ ] Config source precedence is visible in debug/source output.
- [ ] `status` reports local readiness without leaking secrets.
- [ ] `doctor` reports malformed config and permission problems.
- [ ] Completion commands exist for bash, zsh, and fish.
- [ ] Stage verification commands pass.

### Stage 13: Documentation

Deliverables:

- Update `README.md` with a short CLI quickstart and links to docs.
- Update `docs/site/index.md` so CLI is visible as a first-class usage mode.
- Update `docs/site/tutorials/getting-started.md` with the shortest first CLI call path or a concise link to the CLI how-to.
- Add `docs/site/how-to/cli.md` for practical account/profile setup and daily CLI workflows:
  - install and verify `avito --version`;
  - add/use/list/delete local accounts;
  - run read-only API commands;
- run JSON automation commands with `--json --no-input`;
- use `status`, `doctor`, and completion commands;
- explain safe handling of local plaintext secrets.
- show safe secret input examples with hidden prompt and `--client-secret-stdin`;
- Complete `docs/site/reference/cli.md` for stable CLI contracts:
  - command grammar `avito <resource> <action>`;
  - global flags;
  - output modes and stdout/stderr split;
  - exit codes and stable error codes;
  - config files, CLI home resolution, environment variables, and profile precedence;
  - safety flags `--dry-run`, `--yes`, and `--confirm`;
  - generated command naming algorithm and compatibility alias policy;
  - sync Swagger-bound coverage guarantee and documented exclusion policy.
- Add `docs/site/explanations/cli-architecture.md` for design rationale:
  - CLI as a thin wrapper over `AvitoClient`;
  - registry/discovery-driven command generation;
  - coverage linter phases and strict gate;
  - auth-token binding exclusions;
  - secret masking and no raw SDK internals in CLI;
  - bounded pagination and `--all` policy.
- Update `docs/site/how-to/auth-and-config.md` with a short cross-link to CLI account/profile setup.
- Update `docs/site/explanations/security-and-redaction.md` with CLI secret-storage and output-redaction notes.
- Update `docs/site/explanations/api-coverage-and-deprecations.md` with CLI coverage and exclusion policy.
- Update navigation files:
  - add `cli.md` to `docs/site/how-to/.pages`;
  - add `cli.md` to `docs/site/reference/.pages`;
  - add `cli-architecture.md` to `docs/site/explanations/.pages`.
- Do not add generated CLI reference pages to `docs/site/assets/_gen_reference.py` unless the implementation has a stable CLI registry JSON/report that can be generated deterministically during MkDocs builds.
- If CLI docs mention commands that are not implemented yet, keep them in this plan only. Public docs must describe only implemented commands by the time Stage 13 is complete.

Documentation style requirements:

- Keep docs in Russian, with command names/flags/error codes unchanged.
- Keep how-to pages task-oriented; do not duplicate the entire reference contract there.
- Keep reference pages exhaustive and stable; avoid marketing language.
- Link to existing config, security, pagination, and API coverage pages instead of copying large sections.
- Include both human output and JSON automation examples.
- Never show real-looking secrets; examples must use placeholders such as `client-secret`.

Verification:

```bash
poetry run mkdocs build --strict
make docs-check
rg -n "client_secret|access_token|Authorization: Bearer|api_key" README.md docs/site
```

Stage checklist:

- [ ] README includes a CLI quickstart.
- [ ] `CHANGELOG.md` summarizes the CLI feature and points to the stable reference docs.
- [ ] `docs/site/index.md` links to the CLI docs.
- [ ] `docs/site/tutorials/getting-started.md` has a first CLI path or a clear CLI how-to link.
- [ ] `docs/site/how-to/cli.md` explains account/profile setup, daily workflows, automation, status/doctor, completion, and local plaintext secret storage.
- [ ] `docs/site/reference/cli.md` lists global flags, output modes, exit codes, config files, environment variables, safety flags, command grammar, naming, alias, and coverage contracts.
- [ ] `docs/site/explanations/cli-architecture.md` explains SDK reuse, registry/discovery, coverage linter phases, exclusions, secret masking, and pagination policy.
- [ ] Existing auth/config, security/redaction, and API coverage/deprecation pages link to or describe relevant CLI behavior.
- [ ] `.pages` navigation files include the new CLI pages in the correct sections.
- [ ] Docs examples do not contain real-looking secrets or bearer tokens.
- [ ] Stage verification commands pass.

### Stage 14: Final Gate

Run the full gate before completing the branch:

```bash
poetry run pytest tests/cli
poetry run pytest tests/core/test_swagger*.py tests/contracts/test_swagger_contracts.py
poetry run mypy avito
poetry run mypy scripts/lint_cli_coverage.py
poetry run ruff check .
poetry run python scripts/lint_python_guidelines.py
poetry run python scripts/lint_architecture.py
poetry run python scripts/lint_cli_coverage.py --strict
poetry build
make check
```

If generated docs, snippets, coverage pages, or reference output changed:

```bash
make docs-strict
```

Stage checklist:

- [ ] `poetry run pytest tests/cli` passes.
- [ ] Swagger registry/contract tests pass.
- [ ] `poetry run mypy avito` passes.
- [ ] `poetry run ruff check .` passes.
- [ ] Python guidelines, architecture, and CLI coverage linters pass.
- [ ] `poetry build` passes.
- [ ] `make check` passes.
- [ ] `make docs-strict` passes when docs/reference output changed.

## Acceptance Checklist

- [ ] `click` dependency added.
- [ ] `avito/cli/` exists and is isolated from SDK core/domain/transport/auth layers.
- [ ] Console command `avito` is registered in `pyproject.toml`.
- [ ] Console command entry point is `avito.cli.app:main`.
- [ ] `python -m avito` exposes the same CLI.
- [ ] `avito --help`, `avito --version`, and `avito version` work.
- [ ] Root-level global flags work in the documented canonical syntax, for example `avito --profile main account get-self`.
- [ ] Trailing/subcommand global flags are either deliberately implemented, tested, and documented as additive behavior, or explicitly documented as unsupported in the first release.
- [ ] CLI home defaults to `~/.avito-py/`.
- [ ] `AVITO_PY_HOME` and `MY_SDK_HOME` override CLI home with documented precedence.
- [ ] CLI home directory is created lazily with `0700` permissions.
- [ ] `accounts.json` and `config.json` are written atomically with `0600` permissions.
- [ ] Account commands add/list/use/current/delete accounts.
- [ ] `account remove` is omitted or implemented only as documented alias for `account delete`.
- [ ] `account add` supports `--client-id`, `--client-secret`, `--base-url`, `--api-key`, and `--endpoint`.
- [ ] `account add` supports `--client-secret-stdin` and hidden prompt input so secrets do not have to appear in shell history.
- [ ] No CLI output leaks raw secrets.
- [ ] CLI errors use stable error codes and documented exit codes.
- [ ] Results go to stdout; errors, warnings, progress, and debug diagnostics go to stderr.
- [ ] `--json` emits stable JSON for success and errors.
- [ ] CLI registry is built from SDK Swagger binding metadata.
- [ ] Every sync discovered Swagger binding has exactly one canonical CLI command or documented intentional exclusion.
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
- [ ] Every completed factory group has at least one representative smoke command tested through fake transport.
- [ ] CLI coverage linter exists, passes, and is included in `make check` after full coverage.
- [ ] README and docs include CLI usage, config, output, and exit-code contracts.
- [ ] Minimum stage verification commands pass during implementation.
- [ ] Final `make check` passes before completion.

## Resolved Defaults

- `avito cli coverage` is hidden/internal for the first release. The supported public surface is the script `scripts/lint_cli_coverage.py --strict` and documented coverage guarantees.
- Paginated commands default to bounded output: first page only or the SDK/default page size when applicable. Full materialization requires explicit `--all`.
- Generated API commands use named flags only in the first release. Positional primary IDs can be added later as additive aliases after command stability is proven.
- The 4 auth-token Swagger bindings are documented intentional exclusions for the first release and are represented by local account/status/doctor workflows instead of direct token-client commands.
- Click is the only planned CLI framework for the first release and is an
  explicit runtime dependency from Stage 1.
- Command coverage and execution-smoke coverage are separate gates: a command
  may satisfy Swagger coverage only when it is canonical and registered, but it
  still needs execution-smoke coverage or a documented execution exclusion
  before the final strict gate.
