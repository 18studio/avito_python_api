# CLI UX Style Guide

Design a CLI as both a product interface and a scriptable API. Commands, flags,
output schemas, and exit codes are long-term contracts.

## Core Rules

1. Prefer additive changes. Document deprecations before removing commands,
   flags, fields, or exit codes.
2. Default output is human-readable. Provide machine-readable output explicitly:
   `--json`, `--plain`, `--quiet`, and `--no-input`.
3. Make successful commands answer: what happened, what changed, and what to do
   next.
4. Use a consistent command grammar: `tool <resource> <action>`.
5. Resources are nouns; actions are verbs: `tool model deploy`,
   `tool endpoint delete`, `tool registry sync`.
6. Command names and flags use lowercase kebab-case.
7. Prefer explicit names over unclear abbreviations. Short aliases may exist
   only beside clear long flags: `-o, --output`, `-f, --file`, `-h, --help`.

## Arguments and Flags

Use positional arguments only for obvious primary inputs:

```bash
tool model inspect llama-3-8b
tool endpoint delete production-chat
```

Use named flags when argument order is ambiguous or the command is complex:

```bash
tool model copy --from llama-3-8b --to llama-3-8b-prod
tool model deploy --model llama-3-8b --namespace production --gpu a100 --replicas 2
```

Boolean flags should be positive: `--enable-cache`, `--verify-checksum`,
`--wait`. `--no-*` is acceptable only for disabling default behavior:
`--no-color`, `--no-input`, `--no-cache`.

Use the same flag name for the same concept everywhere:

```text
--namespace
--output
--format
--quiet
--json
--yes
--no-input
--dry-run
```

## Safety

Every destructive command must support explicit confirmation.

Interactive confirmation:

```text
This will delete endpoint "production-chat".
Type "production-chat" to confirm:
```

Automation confirmation:

```bash
tool endpoint delete production-chat --confirm production-chat
tool cache clear --yes
```

Complex write operations should support `--dry-run` and build the same planned
change without applying it:

```text
Dry run: no changes will be applied.

Would create:
  Deployment: llama-3-70b
  Replicas: 2
  GPU type: a100-80gb
```

Dangerous commands must be hard to run accidentally: delete, reset, destroy,
force deploy, overwrite, production changes, and expensive operations. Use
`--force` only to bypass explicit safety checks. Show cost or resource impact
before infrastructure-heavy operations. Never print secrets by default; mask
them unless a deliberate reveal command is used.

## Help

Every command must support:

```bash
tool --help
tool model --help
tool model deploy --help
tool help model deploy
```

Help output should follow this shape:

```text
Description:
  Deploy a model and expose it through an OpenAI-compatible endpoint.

Usage:
  tool model deploy <model> [flags]

Examples:
  tool model deploy llama-3-8b
  tool model deploy llama-3-70b --gpu a100 --replicas 2
  tool model deploy llama-3-8b --namespace production --json

Flags:
  --gpu string          GPU type to use
  --replicas int        Number of replicas
  --namespace string    Target namespace
  --json                Output result as JSON
  --dry-run             Preview changes without applying them
  -h, --help            Show help

Related commands:
  tool model list
  tool endpoint test
  tool logs
```

Put examples before exhaustive reference. Include at least one minimal example,
one realistic production example, and one automation-friendly example. For
recoverable usage errors, show the problem, usage, and examples.

## Output

Default output should be concise and useful:

```text
Endpoint created: production-chat

URL:
  https://api.example.com/v1/chat/completions

Next:
  tool endpoint test production-chat
```

Use aligned tables for lists and keep columns stable:

```text
NAME              STATUS    MODEL        GPU        REPLICAS
production-chat   ready     llama-3-8b   a10g       2
staging-chat      pending   mistral-7b   l4         1
```

Use grouped key-value output for one resource:

```text
Endpoint: production-chat

Status:      ready
Model:       llama-3-8b
GPU:         a10g
Replicas:    2
URL:         https://api.example.com/v1/chat/completions
Created:     2026-05-09 12:30:00
```

Machine-readable output must be stable and undecorated. Do not include spinners,
warnings, progress, or human instructions in JSON.

Use stdout for command results. Use stderr for errors, warnings, progress,
debug logs, spinners, and deprecation notices. This must work:

```bash
tool model list --json | jq '.models[]'
```

Support output formatting with a documented primary convention:

```text
--json
--plain
--table
--wide
--quiet
--output <format>
```

## Errors

Errors must explain the problem, cause, fix, command to try, and stable error
code when useful:

```text
Error: model "llama-3-70b" requires more GPU memory.

Required:
  80GB GPU memory

Available:
  40GB GPU memory

Try:
  tool model deploy llama-3-8b
  tool nodepool add --gpu a100-80gb

Error code:
  MODEL_GPU_MEMORY_INSUFFICIENT
```

Use stable machine-readable error codes such as `MODEL_NOT_FOUND`,
`AUTH_REQUIRED`, `PERMISSION_DENIED`, `REGISTRY_UNAVAILABLE`,
`GPU_MEMORY_INSUFFICIENT`, `CHECKSUM_FAILED`, and `CONFIG_INVALID`.

Suggest close matches for mistyped commands or invalid values. Do not expose
internal stack traces by default; reserve diagnostic detail for `--verbose` or
`--debug`, and never expose secrets in either mode.

## Progress

For operations longer than a few seconds, show progress on stderr:

```text
Deploying model: llama-3-8b

OK Validated model license
OK Checked GPU compatibility
OK Downloaded model weights
OK Verified checksum
.. Creating runtime artifact
   Starting endpoint
```

Use a spinner for unknown duration, step counters for workflows, progress bars
for measurable transfers, and live status for deployments. Clean up progress
output after completion so the final result is readable.

## Interactivity

Interactive prompts are allowed only when stdin is a TTY. Commands must never
hang in CI, scripts, or piped usage:

```bash
tool model deploy llama-3-8b --json > result.json
```

Every prompt needs a non-interactive equivalent using flags and `--no-input`.
Prompts must be specific, safe, and show defaults:

```text
Namespace [default: default]:
Replicas [default: 1]:
GPU type [default: auto]:
```

## Automation and Exit Codes

Automation-friendly commands should support `--json`, `--quiet`, `--no-input`,
`--yes`, and `--dry-run` where relevant.

Baseline exit codes:

```text
0   Success
1   General error
2   Invalid usage
3   Not found
4   Permission denied
5   Authentication required
6   Conflict
7   Validation failed
8   External dependency unavailable
```

Document all public exit codes. `--quiet` should suppress non-essential output
and emit only the final value or nothing on success. Keep `--verbose`
user-facing and `--debug` diagnostic.

## Configuration

Use and document this precedence order:

```text
1. CLI flags
2. Environment variables
3. Project config
4. User config
5. System config
6. Built-in defaults
```

Flags must override environment variables. Config commands should be explicit:

```bash
tool config get
tool config set registry s3://company-models
tool config unset registry
tool config list
tool config list --show-source
```

Show config source when debugging:

```text
KEY          VALUE                  SOURCE
registry     s3://company-models     project config
namespace    production              environment
gpu          auto                    default
```

## Color and Accessibility

Color must never be the only source of meaning; pair it with text or symbols.
Respect `--no-color` and `NO_COLOR=1`. Enable color only in TTY output and use
it sparingly:

```text
Green    success
Yellow   warning
Red      error
Blue     links or neutral emphasis
Gray     secondary metadata
```

## Naming

Use consistent action verbs:

```text
create
list
get
inspect
update
delete
deploy
start
stop
restart
sync
test
logs
status
doctor
```

Use `list` for collections and choose one of `get` or `inspect` for one item.
Prefer `delete` over `remove`; reserve `remove` for detaching something rather
than destroying it. Use `status` for quick system state and `doctor` for
diagnostics.

## Resilience

Commands should be safe to retry and should not create duplicate resources after
partial failure. Long operations should resume where possible: model downloads,
artifact builds, image pushes, deployments, and registry syncs.

Partial failure must be explicit:

```text
Deployment partially completed.

Completed:
  OK Model downloaded
  OK Checksum verified

Failed:
  ERR Endpoint creation

Reason:
  Namespace "production" does not exist.

Try:
  tool namespace create production
  tool model deploy llama-3-8b --namespace production
```

## Versioning and Deprecation

Support `tool version` and `tool --version`. Include CLI version, build commit,
API version, and server compatibility when available.

Deprecation warnings must include removal timing and replacement guidance:

```text
Warning: "tool deploy" is deprecated and will be removed in v2.0.

Use:
  tool model deploy
```

## Completion and Logs

Provide shell completion:

```bash
tool completion bash
tool completion zsh
tool completion fish
```

Completion should include commands, flags, models, endpoints, namespaces,
registries, and config keys where possible.

Logs should be easy to follow but should not replace structured status:

```bash
tool logs endpoint production-chat --follow --tail 100
tool logs scheduler --since 1h --level warn
tool status
tool endpoint status production-chat
```

## Recommended Global Flags

```text
-h, --help
--version
--verbose
--debug
--quiet
--json
--no-color
--no-input
--config <path>
--profile <name>
--namespace <name>
--context <name>
--dry-run
--yes
--confirm <value>
--timeout <duration>
```

## Recommended Command Set

```bash
tool init
tool status
tool doctor
tool config get
tool config set
tool config list

tool auth login
tool auth logout
tool auth status

tool model list
tool model inspect
tool model deploy
tool model delete

tool registry list
tool registry add
tool registry sync
tool registry inspect

tool endpoint list
tool endpoint inspect
tool endpoint test
tool endpoint delete

tool logs
tool version
tool completion
```

## Review Checklist

```text
[ ] Follows tool <resource> <action>
[ ] Uses lowercase kebab-case
[ ] Supports --help with examples
[ ] Has actionable errors and stable error codes
[ ] Separates stdout and stderr
[ ] Provides JSON output where useful
[ ] Works in CI without prompts
[ ] Protects destructive actions
[ ] Supports --dry-run for complex writes
[ ] Documents exit codes
[ ] Makes color optional
[ ] Is safe to retry
[ ] Handles deprecated flags gracefully
[ ] Produces useful success output
[ ] Suggests next steps where relevant
```

## Opinionated Defaults

```text
Command style:      tool <resource> <action>
Case style:         lowercase kebab-case
Default output:     human-readable
Machine output:     --json
Help:               --help and help command
Progress:           stderr
Result data:        stdout
Errors:             stderr
Color:              enabled only in TTY
No color:           --no-color and NO_COLOR
Automation:         --quiet, --no-input, --yes
Safety:             confirmation for destructive actions
Preview:            --dry-run for write operations
Diagnostics:        doctor and status commands
```
