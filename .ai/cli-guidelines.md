# CLI UX Style Guide

## 1. Core Principles

### Rule 1. Treat the CLI as a product interface and an API

A CLI is used both by humans and by scripts. Design every command, flag, output format, and exit code as a long-term contract.

**Guidelines:**

* Avoid breaking command names, flags, output schemas, and exit codes after release.
* Document deprecations before removing anything.
* Prefer additive changes over breaking changes.
* Assume users will automate every command.

---

### Rule 2. Be human-first by default, machine-readable on demand

The default experience should be pleasant for humans. Automation should be supported through explicit flags.

**Use:**

```bash
tool models list
```

For human-readable output.

```bash
tool models list --json
```

For automation.

**Required flags:**

```bash
--json
--plain
--quiet
--no-input
```

---

### Rule 3. Make the happy path obvious

A new user should understand what to do next after every major command.

**Good output:**

```text
✓ Model deployed: llama-3-8b

Endpoint:
  https://api.example.com/v1/chat/completions

Next steps:
  tool endpoint test llama-3-8b
  tool logs llama-3-8b
```

**Avoid:**

```text
Done.
```

---

## 2. Command Structure

### Rule 4. Use a consistent command grammar

Use a predictable hierarchy:

```bash
tool <resource> <action>
```

**Examples:**

```bash
tool model list
tool model deploy
tool model delete

tool endpoint create
tool endpoint list
tool endpoint test

tool registry sync
tool registry inspect
```

Avoid mixing naming styles:

```bash
tool deploy-model
tool modelRemove
tool start_inference
tool runModel
```

---

### Rule 5. Resources should be nouns, actions should be verbs

Resources describe the object. Actions describe what happens to the object.

**Good:**

```bash
tool model deploy
tool endpoint delete
tool registry sync
```

**Bad:**

```bash
tool deploy model
tool delete-endpoint
tool syncing-registry
```

---

### Rule 6. Use lowercase kebab-case

All command names and flags should use lowercase kebab-case.

**Good:**

```bash
tool model deploy --model-name llama-3 --gpu-count 2
```

**Bad:**

```bash
tool Model Deploy --modelName llama-3 --GPUCount 2
tool model deploy --model_name llama-3
```

---

### Rule 7. Prefer explicit names over unclear abbreviations

Use short names only when they are obvious and standard.

**Good:**

```bash
--namespace
--registry
--gpu-count
--model
--output
```

**Acceptable:**

```bash
--cpu
--gpu
--ram
--url
```

**Bad:**

```bash
--ns
--reg
--gc
--mdl
--outp
```

Short aliases may exist, but they must not replace clear long names.

```bash
-o, --output
-f, --file
-h, --help
```

---

## 3. Arguments and Flags

### Rule 8. Use positional arguments only for obvious primary inputs

Use positional arguments when there is only one natural value.

**Good:**

```bash
tool model inspect llama-3-8b
tool endpoint delete production-chat
```

Use flags when values may be confused.

**Good:**

```bash
tool model copy --from llama-3-8b --to llama-3-8b-prod
```

**Bad:**

```bash
tool model copy llama-3-8b llama-3-8b-prod
```

The second version forces users to remember argument order.

---

### Rule 9. Required values should usually be flags in complex commands

For complex operations, prefer named flags.

**Good:**

```bash
tool model deploy \
  --model llama-3-8b \
  --namespace production \
  --gpu a100 \
  --replicas 2
```

**Bad:**

```bash
tool model deploy llama-3-8b production a100 2
```

---

### Rule 10. Boolean flags should be positive and explicit

Prefer positive names.

**Good:**

```bash
--enable-cache
--verify-checksum
--wait
```

Avoid confusing negatives.

```bash
--no-disable-cache
--dont-wait
```

For disabling default behavior, `--no-*` is acceptable.

```bash
--no-color
--no-input
--no-cache
```

---

### Rule 11. Use consistent flag names across commands

The same concept must have the same flag name everywhere.

Use consistently:

```bash
--namespace
--output
--format
--quiet
--json
--yes
--no-input
--dry-run
```

Do not mix:

```bash
--namespace
--ns
--project
--workspace
```

unless they represent genuinely different concepts.

---

### Rule 12. Every destructive command must support explicit confirmation

Interactive confirmation:

```bash
tool endpoint delete production-chat
```

```text
This will delete endpoint "production-chat".
Type "production-chat" to confirm:
```

Automation confirmation:

```bash
tool endpoint delete production-chat --confirm production-chat
```

For less dangerous operations, `--yes` is acceptable:

```bash
tool cache clear --yes
```

---

### Rule 13. Every complex write operation should support `--dry-run`

Use `--dry-run` to preview changes without applying them.

```bash
tool model deploy llama-3-70b --dry-run
```

Example output:

```text
Dry run: no changes will be applied.

Would create:
  Deployment: llama-3-70b
  Replicas: 2
  GPU type: a100-80gb
  Endpoint: /v1/chat/completions

Estimated resources:
  GPU memory: 160GB
  Storage: 140GB
```

---

## 4. Help and Documentation

### Rule 14. Every command must support `--help`

These should work:

```bash
tool --help
tool model --help
tool model deploy --help
tool help model deploy
```

---

### Rule 15. Help output must follow a standard structure

Recommended format:

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

---

### Rule 16. Put examples before exhaustive reference

Users copy examples more often than they read full flag descriptions.

Each command should include at least:

* One minimal example.
* One realistic production example.
* One automation-friendly example.

---

### Rule 17. Show help when the user makes a recoverable mistake

When required input is missing, show the problem, usage, and examples.

**Good:**

```text
Missing required argument: <model>

Usage:
  tool model deploy <model> [flags]

Examples:
  tool model deploy llama-3-8b
  tool model deploy llama-3-70b --gpu a100 --replicas 2
```

**Bad:**

```text
Error: invalid args
```

---

## 5. Output Style

### Rule 18. Default output should be concise and useful

Default output should answer:

1. What happened?
2. What changed?
3. What should I do next?

**Good:**

```text
✓ Endpoint created: production-chat

URL:
  https://api.example.com/v1/chat/completions

Next:
  tool endpoint test production-chat
```

---

### Rule 19. Use tables for lists

Use aligned tables for human-readable lists.

```text
NAME              STATUS    MODEL        GPU        REPLICAS
production-chat   ready     llama-3-8b   a10g       2
staging-chat      pending   mistral-7b   l4         1
```

Keep table columns stable across releases.

---

### Rule 20. Use detailed views for single resources

For one resource, use grouped key-value output.

```text
Endpoint: production-chat

Status:      ready
Model:       llama-3-8b
GPU:         a10g
Replicas:    2
URL:         https://api.example.com/v1/chat/completions
Created:     2026-05-09 12:30:00
```

---

### Rule 21. Machine-readable output must be stable

For `--json`, use predictable field names and avoid decorative content.

```json
{
  "name": "production-chat",
  "status": "ready",
  "model": "llama-3-8b",
  "gpu": "a10g",
  "replicas": 2,
  "url": "https://api.example.com/v1/chat/completions"
}
```

Do not include spinners, warnings, progress, or human instructions in JSON output.

---

### Rule 22. Separate stdout and stderr

Use `stdout` for command results.

Use `stderr` for:

* Errors.
* Warnings.
* Progress.
* Debug logs.
* Spinners.
* Deprecation notices.

This must work cleanly:

```bash
tool model list --json | jq '.models[]'
```

---

### Rule 23. Support output formatting

Recommended flags:

```bash
--json
--plain
--table
--wide
--quiet
```

Example:

```bash
tool endpoint list --output json
tool endpoint list --output table
tool endpoint list --quiet
```

Pick either `--json` or `--output json` as the primary convention. Supporting both is acceptable, but the documentation should prefer one.

---

## 6. Error Design

### Rule 24. Errors must explain what happened and how to fix it

A good error includes:

1. Problem.
2. Cause.
3. Fix.
4. Command to try.
5. Optional error code.

**Good:**

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

**Bad:**

```text
Error: failed
```

---

### Rule 25. Use stable error codes

Every important error should have a stable machine-readable code.

Examples:

```text
MODEL_NOT_FOUND
AUTH_REQUIRED
PERMISSION_DENIED
REGISTRY_UNAVAILABLE
GPU_MEMORY_INSUFFICIENT
CHECKSUM_FAILED
CONFIG_INVALID
```

These are useful for support, docs, telemetry, and automation.

---

### Rule 26. Suggest the closest valid command or value

When the user mistypes something, suggest a correction.

```text
Unknown command: modle

Did you mean?
  tool model
```

For invalid values:

```text
Unknown GPU type: a1000

Available GPU types:
  a10g
  l4
  a100
  h100
```

---

### Rule 27. Do not expose internal stack traces by default

Default errors should be user-facing.

**Bad:**

```text
thread 'main' panicked at src/scheduler.rs:194
```

**Good:**

```text
Error: scheduler is unavailable.

The API gateway could not connect to the scheduler service.

Try:
  tool status
  tool logs scheduler
```

Expose debug details only with:

```bash
--debug
--verbose
```

---

## 7. Progress and Long-Running Operations

### Rule 28. Never leave users staring at a blank terminal

For operations longer than a few seconds, show progress.

Use:

* Spinner for unknown duration.
* Step counter for multi-step workflows.
* Progress bar for measurable downloads or uploads.
* Live status for deployments.

---

### Rule 29. Use step-based progress for workflows

Example:

```text
Deploying model: llama-3-8b

✓ Validated model license
✓ Checked GPU compatibility
✓ Downloaded model weights
✓ Verified checksum
→ Creating runtime artifact
  Starting endpoint
```

---

### Rule 30. Show measurable progress when possible

For downloads:

```text
Downloading model weights... 12.4GB / 32.0GB
```

For parallel tasks:

```text
Preparing shards... 6 / 16
```

For deployment:

```text
Starting replicas... 1 / 2 ready
```

---

### Rule 31. Clean up progress output after completion

Final output should be readable and not contain dozens of spinner redraws.

**Good final output:**

```text
✓ Downloaded model weights
✓ Verified checksum
✓ Created runtime artifact
✓ Endpoint is ready
```

---

## 8. Interactivity

### Rule 32. Interactive prompts are allowed only when stdin is a TTY

Do not prompt in CI, scripts, or piped commands.

This should never hang:

```bash
tool model deploy llama-3-8b --json > result.json
```

---

### Rule 33. Every prompt must have a non-interactive equivalent

Interactive:

```bash
tool init
```

Non-interactive:

```bash
tool init \
  --project production \
  --registry s3://company-models \
  --namespace llm-prod \
  --no-input
```

---

### Rule 34. Prompts should be specific and safe

**Good:**

```text
Select a registry:

  1. Hugging Face
  2. S3
  3. OCI registry
  4. Internal registry

Registry:
```

**Bad:**

```text
Input:
```

---

### Rule 35. Defaults should be visible

Show default values in prompts.

```text
Namespace [default: default]:
Replicas [default: 1]:
GPU type [default: auto]:
```

---

## 9. Automation and CI/CD

### Rule 36. Commands must be scriptable

Every command used in automation should support:

```bash
--json
--quiet
--no-input
--yes
--dry-run
```

Where relevant.

---

### Rule 37. Exit codes must be meaningful

Recommended baseline:

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

Document all public exit codes.

---

### Rule 38. `--quiet` should suppress non-essential output

`--quiet` should show only the final result or nothing on success.

Example:

```bash
tool model deploy llama-3-8b --quiet
```

Acceptable output:

```text
production-chat
```

Or no output, depending on command semantics.

---

### Rule 39. `--verbose` and `--debug` should be separate

Use:

```bash
--verbose
```

For more user-facing detail.

Use:

```bash
--debug
```

For diagnostic information useful to engineers and support.

Do not expose secrets in either mode.

---

## 10. Configuration

### Rule 40. Use a clear configuration precedence order

Recommended order:

```text
1. CLI flags
2. Environment variables
3. Project config
4. User config
5. System config
6. Built-in defaults
```

Document this clearly.

---

### Rule 41. Flags must override environment variables

Example:

```bash
TOOL_NAMESPACE=staging tool model deploy llama-3-8b --namespace production
```

The command should use:

```text
production
```

not:

```text
staging
```

---

### Rule 42. Config commands should be explicit

Use:

```bash
tool config get
tool config set registry s3://company-models
tool config unset registry
tool config list
```

Avoid hidden magic.

---

### Rule 43. Show config source when helpful

For debugging:

```bash
tool config list --show-source
```

Example output:

```text
KEY          VALUE                  SOURCE
registry     s3://company-models     project config
namespace    production              environment
gpu          auto                    default
```

---

## 11. Color and Accessibility

### Rule 44. Color must never be the only source of meaning

Do not rely only on red, green, or yellow. Use symbols and text too.

**Good:**

```text
✓ Ready
⚠ Warning
✗ Failed
```

**Bad:**

```text
Ready
Warning
Failed
```

with meaning expressed only through color.

---

### Rule 45. Support `--no-color`

Every command should respect:

```bash
--no-color
```

And the environment variable:

```bash
NO_COLOR=1
```

---

### Rule 46. Use color sparingly

Recommended color semantics:

```text
Green    success
Yellow   warning
Red      error
Blue     links or neutral emphasis
Gray     secondary metadata
```

Avoid colorful output that competes with the content.

---

## 12. Naming Conventions

### Rule 47. Use consistent action verbs

Recommended verbs:

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

Avoid synonyms for the same action.

Do not mix:

```text
list
show-all
print
display
```

Pick one.

---

### Rule 48. Use `list` for collections and `get` or `inspect` for one item

Collections:

```bash
tool model list
tool endpoint list
```

Single resource:

```bash
tool model inspect llama-3-8b
tool endpoint get production-chat
```

Choose either `get` or `inspect` as the preferred single-resource verb.

For developer tools, `inspect` is often more descriptive.

---

### Rule 49. Use `delete`, not `remove`, unless there is a semantic difference

Recommended:

```bash
tool endpoint delete production-chat
```

Use `remove` only when detaching something rather than destroying it.

Example:

```bash
tool endpoint remove-label production-chat stable
```

---

### Rule 50. Use `status` for system state

```bash
tool status
tool model status llama-3-8b
tool endpoint status production-chat
```

`status` should be quick, readable, and safe.

---

### Rule 51. Use `doctor` for diagnostics

```bash
tool doctor
```

Should check:

```text
✓ CLI version
✓ Authentication
✓ Cluster access
✓ Registry access
✓ GPU nodes
✓ Scheduler status
✓ API gateway status
```

---

## 13. Safety and Trust

### Rule 52. Dangerous commands must be hard to run accidentally

Use confirmation for:

* Delete.
* Reset.
* Destroy.
* Force deploy.
* Overwrite.
* Production changes.
* Expensive operations.

---

### Rule 53. Use `--force` only for bypassing safety checks

`--force` should mean: “I know this is risky.”

Do not use `--force` as a generic fix for validation problems.

Bad:

```bash
tool model deploy llama-3 --force
```

when the user simply forgot a namespace.

Good:

```bash
tool endpoint delete production-chat --force --confirm production-chat
```

---

### Rule 54. Show cost or resource impact before expensive operations

For infrastructure-heavy commands, show estimates.

```text
This deployment may allocate:

  GPUs:       2 × a100-80gb
  Memory:     160GB
  Storage:    140GB
  Replicas:   2

Continue? [y/N]
```

---

### Rule 55. Never print secrets by default

Mask secrets:

```text
API key: sk-...x92a
```

Provide explicit reveal commands only when necessary:

```bash
tool auth token show --reveal
```

---

## 14. Resilience and Idempotency

### Rule 56. Commands should be safe to retry

If a command fails midway, running it again should not create duplicate resources.

Example:

```bash
tool model deploy llama-3-8b
```

If the model was already downloaded, the command should reuse it.

```text
✓ Model weights already downloaded
✓ Checksum verified
→ Resuming deployment
```

---

### Rule 57. Long operations should resume when possible

Especially for:

* Model downloads.
* Artifact builds.
* Image pushes.
* Deployments.
* Registry syncs.

---

### Rule 58. Partial failure should be explicit

```text
Deployment partially completed.

Completed:
  ✓ Model downloaded
  ✓ Checksum verified

Failed:
  ✗ Endpoint creation

Reason:
  Namespace "production" does not exist.

Try:
  tool namespace create production
  tool model deploy llama-3-8b --namespace production
```

---

## 15. Versioning and Deprecation

### Rule 59. Show CLI version

Support:

```bash
tool version
tool --version
```

Output should include:

```text
CLI version
Build commit
API version
Server compatibility
```

Example:

```text
tool version 1.4.2
API version: v1
Build: 9f3a12c
```

---

### Rule 60. Warn before removing commands or flags

Deprecation warning:

```text
Warning: --model-id is deprecated and will be removed in v2.0.
Use --model instead.
```

---

### Rule 61. Deprecation messages must include replacement guidance

Bad:

```text
Warning: deprecated.
```

Good:

```text
Warning: "tool deploy" is deprecated and will be removed in v2.0.

Use:
  tool model deploy
```

---

## 16. Autocomplete

### Rule 62. Provide shell completion

Support:

```bash
tool completion bash
tool completion zsh
tool completion fish
```

---

### Rule 63. Completion should include dynamic resources where possible

Autocomplete should suggest:

* Commands.
* Flags.
* Models.
* Endpoints.
* Namespaces.
* Registries.
* Config keys.

Example:

```bash
tool endpoint inspect <TAB>
```

Should suggest existing endpoints.

---

## 17. Logging

### Rule 64. Logs should be easy to follow

Use:

```bash
tool logs endpoint production-chat
tool logs scheduler
tool logs gateway
```

Support:

```bash
--follow
--since
--tail
--level
```

Example:

```bash
tool logs endpoint production-chat --follow --tail 100
```

---

### Rule 65. Logs should not replace structured status

Do not force users to inspect logs to understand normal state.

Use:

```bash
tool status
tool endpoint status production-chat
```

for state.

Use:

```bash
tool logs
```

for investigation.

---

## 18. Recommended Global Flags

Every CLI should consider these global flags:

```bash
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
```

For infrastructure tools:

```bash
--namespace <name>
--context <name>
--dry-run
--yes
--confirm <value>
--timeout <duration>
```

---

## 19. Recommended Command Set

For an infrastructure or AI platform CLI, a strong baseline is:

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

---

## 20. Output Examples

### Success

```text
✓ Model deployed: llama-3-8b

Endpoint:
  https://api.example.com/v1/chat/completions

Next:
  tool endpoint test llama-3-8b
```

---

### Warning

```text
Warning: GPU type was not specified.

Using automatic selection:
  GPU: a10g

To choose manually:
  tool model deploy llama-3-8b --gpu a100
```

---

### Error

```text
Error: registry is unavailable.

The CLI could not connect to:
  s3://company-models

Try:
  tool registry inspect company-models
  tool doctor

Error code:
  REGISTRY_UNAVAILABLE
```

---

### Dry run

```text
Dry run: no changes will be applied.

Would create:
  Model deployment: llama-3-8b
  Endpoint: production-chat
  Replicas: 2
  GPU: a10g

Would modify:
  Namespace: production
```

---

### JSON

```json
{
  "status": "ready",
  "endpoint": {
    "name": "production-chat",
    "url": "https://api.example.com/v1/chat/completions"
  },
  "model": {
    "name": "llama-3-8b"
  }
}
```

---

## 21. CLI Review Checklist

Before releasing a command, check:

```text
[ ] Does the command follow tool <resource> <action>?
[ ] Are names lowercase and kebab-case?
[ ] Does it support --help?
[ ] Does help include examples?
[ ] Are errors actionable?
[ ] Are stdout and stderr separated?
[ ] Is JSON output available where useful?
[ ] Does it work in CI without prompts?
[ ] Are destructive actions protected?
[ ] Is --dry-run available for complex write operations?
[ ] Are exit codes documented?
[ ] Are colors optional?
[ ] Is the command safe to retry?
[ ] Are deprecated flags handled gracefully?
[ ] Is the output useful after success?
[ ] Does the command suggest the next step?
```

---

## 22. Opinionated Defaults

Use these defaults unless there is a strong reason not to:

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

This can serve as the baseline style guide for designing a professional CLI with strong developer experience and enterprise readiness.
