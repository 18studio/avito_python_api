# CLI

`avito` is the command-line entry point for `avito-py`. The current CLI surface
exposes the shell, global flags, account/profile commands, version commands,
registry-backed help, account API commands, and generated read-only API commands
for supported sync Swagger-bound GET/HEAD methods.

## Commands

| Command | Description |
|---|---|
| `avito --help` | Prints root help and exits without reading account files or touching the network. |
| `avito help` | Prints the same root help as `avito --help`. |
| `avito help <resource>` | Prints registry-backed help for local commands, aliases, helper workflows, and API command candidates without constructing `AvitoClient`. |
| `avito help <resource> <action>` | Prints registry-backed command help, including selected flags from Swagger binding metadata where available. |
| `avito --version` | Prints the installed package version. |
| `avito version` | Prints the installed package version. With `--json`, prints `{"version": "..."}`. |
| `python -m avito --help` | Uses the same CLI application as `avito --help`. |
| `avito <resource> <read-action> [flags]` | Calls a supported sync Swagger-bound GET/HEAD SDK method through `AvitoClient` and public domain methods. |
| `avito account get-self` | Calls `AvitoClient.account().get_self()` through the public SDK and prints the authorized profile. |
| `avito account get-balance --user-id USER_ID` | Calls `AvitoClient.account(user_id=...).get_balance()` through the public SDK and prints the account balance. |
| `avito config get active-profile` | Prints the effective active profile. |
| `avito config set active-profile NAME` | Stores the active profile in the local config file. |
| `avito config unset active-profile` | Clears the stored active profile. |
| `avito config list --show-source` | Prints supported config keys with their value sources. |
| `avito status` | Checks local profile/account readiness without touching the network. |
| `avito doctor` | Checks local CLI files and reports malformed JSON or permission problems. |
| `avito completion bash\|zsh\|fish` | Prints shell-specific completion setup instructions. |

Compatibility aliases are documented separately from canonical commands. For
example, `avito account remove` delegates to `avito account delete` and does not
count as a separate canonical command in CLI coverage.

## Global Flags

Global flags are parsed before the subcommand:

```bash
avito --json version
avito --profile main --config ./config.json --timeout 3.5 version
```

| Flag | Current behavior |
|---|---|
| `--profile NAME` | Selects the local account profile used for API commands. |
| `--config PATH` | Selects an alternate config file for local profile resolution. |
| `--json` | Selects JSON output for commands and JSON error rendering. |
| `--plain` | Accepted as an output mode selector. |
| `--table` | Accepted as an output mode selector. |
| `--wide` | Accepted as an output mode selector. |
| `--quiet` | Suppresses non-essential success output. Errors still go to stderr. |
| `--no-input` | Accepted for future non-interactive commands. |
| `--no-color` | Disables colored human diagnostics. |
| `--verbose` | Accepted for future diagnostic output. |
| `--debug` | Adds sanitized debug details to CLI errors. Secrets are redacted. |
| `--timeout SECONDS` | Passed to API commands whose public SDK method accepts a timeout override. |

`--json`, `--plain`, `--table`, and `--wide` are mutually exclusive. Combining
more than one exits with code `2`.

The `NO_COLOR=1` environment variable also disables colored human diagnostics.

## Local Config and Diagnostics

The first CLI release stores one local config key: `active-profile`. The
effective value follows the documented precedence: the root `--profile` flag
wins over the value stored in `config.json`; if neither exists, the value is
empty.

```bash
avito config set active-profile main
avito config get active-profile
avito config list --show-source
avito config unset active-profile
```

With `--json`, config commands emit a stable `config` object. `--show-source`
adds the source name (`cli`, `config`, or `default`) and the local config path
when the value came from a file.

`avito status` is a local readiness check. It loads the selected profile and
account store, reports whether the CLI can construct SDK settings, and records
`network_checked: false` because it never calls Avito API.

`avito doctor` validates the local config and account files. It reports
malformed JSON and permission failures as sanitized diagnostics; if errors are
found, the command prints the diagnostic report and exits with `CONFIG_INVALID`.

Shell completion commands print setup instructions:

```bash
avito completion bash
avito completion zsh
avito completion fish
```

## Safety Flags

Write-like generated API commands use reviewed safety metadata from the CLI
registry. HTTP method can provide an initial default, but the command record is
the contract used by command registration, help, and the coverage linter.

Destructive or expensive commands require confirmation before the SDK client is
constructed:

```bash
avito --profile main <resource> <action> --confirm <command-id>
avito --profile main <resource> <action> --yes
```

In non-interactive mode, a command that requires confirmation fails instead of
prompting. `--yes` and `--confirm` are mutually exclusive.

`--dry-run` is shown only when the public SDK method accepts `dry_run`. The CLI
does not fake dry-run for methods that would still call transport.

## Implemented API Commands

API commands are registry-backed and call only public SDK factories and public
domain methods. Read-only commands are generated from sync Swagger binding
metadata for GET/HEAD operations when all required CLI inputs are represented by
`factory_args` and `method_args`.

```bash
avito --profile main account get-self
avito --json --profile main account get-balance --user-id 123
avito --profile main ad get --user-id 123 --item-id 456
avito --json --profile main vacancy list
```

The command output uses the same result renderer as local commands. Human output
uses grouped key/value lines for single SDK models, and `--json` emits the
serialized public SDK model without extra prose.

The current read phase intentionally excludes these temporary command candidates
because their Swagger binding metadata does not yet expose a required domain
identifier as a stable CLI flag:

- `autoteka-vehicle.get-preview`
- `autoteka-vehicle.get-specification-by-id`
- `autoteka-vehicle.get-teaser`
- `cpa-chat.get`
- `order-label.download`
- `realty-analytics-report.get-market-price-correspondence`
- `target-action-pricing.get-bids`

Each exclusion is represented in the CLI registry with owner, reason, follow-up,
and target stage metadata.

## Output Contract

Command results go to stdout. Human errors, warnings, progress, and debug
diagnostics go to stderr. JSON errors are valid JSON on stderr.

The result renderer used by API commands serializes SDK models only through their
public `model_dump()` / `to_dict()` contract. Local CLI dataclasses, enum values,
dates, datetimes, lists, primitives, and binary values are converted to
JSON-compatible values before rendering. Secret redaction is applied after
serialization and before human or JSON output is printed.

Lazy SDK pagination is bounded by default. A `PaginatedList` result is serialized
as an object with `items` and `pagination` metadata; the default snapshot loads at
most one page unless a later command explicitly opts into a higher page limit or
full materialization.

Human error shape:

```text
INVALID_FLAG_COMBINATION: Флаги --json, --plain, --table и --wide нельзя использовать вместе.
```

JSON error shape:

```json
{
  "code": "INVALID_FLAG_COMBINATION",
  "exit_code": 2,
  "message": "Флаги --json, --plain, --table и --wide нельзя использовать вместе."
}
```

With `--debug`, error renderers may include sanitized `details`. The same
sanitizer is used for human and JSON renderers, so values such as tokens,
authorization headers, and `client_secret` are replaced with `***`.

## Exit Codes

| Exit code | Stable code | Meaning |
|---:|---|---|
| `0` | — | Command completed successfully. |
| `2` | `CLI_USAGE_ERROR`, `INVALID_FLAG_COMBINATION` | Invalid command usage or incompatible flags. |
| `3` | `CLI_CONFIGURATION_ERROR` | Reserved for local configuration errors. |
| `4` | `CLI_AUTHENTICATION_ERROR` | Reserved for authentication failures. |
| `5` | `CLI_AUTHORIZATION_ERROR` | Reserved for authorization failures. |
| `6` | `CLI_RATE_LIMIT_ERROR` | Reserved for upstream rate-limit failures. |
| `7` | `CLI_UPSTREAM_ERROR` | Reserved for upstream API errors. |
| `8` | `CLI_TRANSPORT_ERROR` | Reserved for transport failures. |
| `70` | `CLI_INTERNAL_ERROR` | Reserved for unexpected internal failures. |
