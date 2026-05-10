# CLI

`avito` is the command-line entry point for `avito-py`. The current CLI surface is
intentionally small: it exposes the shell, global flags, help, and version
commands. API-calling commands are not implemented yet.

## Commands

| Command | Description |
|---|---|
| `avito --help` | Prints root help and exits without reading account files or touching the network. |
| `avito help` | Prints the same root help as `avito --help`. |
| `avito --version` | Prints the installed package version. |
| `avito version` | Prints the installed package version. With `--json`, prints `{"version": "..."}`. |
| `python -m avito --help` | Uses the same CLI application as `avito --help`. |

## Global Flags

Global flags are parsed before the subcommand:

```bash
avito --json version
avito --profile main --config ./config.json --timeout 3.5 version
```

| Flag | Current behavior |
|---|---|
| `--profile NAME` | Accepted and stored in the typed CLI context. Account loading is not implemented yet. |
| `--config PATH` | Accepted and stored in the typed CLI context. Config loading is not implemented yet. |
| `--json` | Selects JSON output for commands and JSON error rendering. |
| `--plain` | Accepted as an output mode selector. |
| `--table` | Accepted as an output mode selector. |
| `--wide` | Accepted as an output mode selector. |
| `--quiet` | Suppresses non-essential success output. Errors still go to stderr. |
| `--no-input` | Accepted for future non-interactive commands. |
| `--no-color` | Disables colored human diagnostics. |
| `--verbose` | Accepted for future diagnostic output. |
| `--debug` | Adds sanitized debug details to CLI errors. Secrets are redacted. |
| `--timeout SECONDS` | Accepted and stored in the typed CLI context. API calls are not implemented yet. |

`--json`, `--plain`, `--table`, and `--wide` are mutually exclusive. Combining
more than one exits with code `2`.

The `NO_COLOR=1` environment variable also disables colored human diagnostics.

## Output Contract

Command results go to stdout. Human errors, warnings, progress, and debug
diagnostics go to stderr. JSON errors are valid JSON on stderr.

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
