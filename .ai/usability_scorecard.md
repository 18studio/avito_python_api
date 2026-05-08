# Python SDK UX Evaluation Methodology

A reproducible methodology for diagnosing the developer experience (DX) of any Python SDK built on top of an HTTP API. The goal is not a binary pass/fail check, but finding weak spots in the user experience and prioritizing improvements.

The methodology is universal: it is not tied to specific classes, files, or method names. All criteria are formulated through **roles**, **contracts**, and **behavior**, not code identifiers.

---

## 1. What the Methodology Evaluates

- **Integration experience.** The path from "installed the package" to "made the first successful request".
- **Day-to-day development experience.** Speed of finding the right method, predictability of behavior, cost of debugging, cost of testing one's own code on top of the SDK.
- **Maintenance experience.** Behavior on upgrade, on upstream API changes, on environment changes, on network failures.

The methodology does **not** evaluate:

- performance (latency, throughput, memory);
- architectural cleanliness for its own sake;
- upstream API feature completeness (this is a separate "coverage" metric, only partially included).

## 2. Goals, Constraints, and Assumptions

**Goals:**

1. Produce a quantitative score `Score ∈ [0, 100]`, comparable across releases and across different SDKs.
2. Localize weak spots down to the behavior/contract level (without binding to a specific file).
3. Produce a prioritized improvement backlog (via the `Pain` index, see §6).

**Constraints:**

- The methodology is designed for SDK wrappers on top of HTTP/REST APIs. For gRPC, WebSocket, or low-level libraries, some criteria are not applicable and are explicitly disabled.
- Minimum evaluation: one evaluator in ~1 working day. Reference evaluation: two independent evaluators with cross-check.
- Some criteria require user participation (persona sessions); if access to real users is unavailable, a simulation mode is used (the evaluator plays the persona role).

**Assumptions:**

- The SDK has a public repository or source code access.
- The SDK is distributed via PyPI/similar index, installable in one step.
- At least minimal documentation exists (README, docstrings).

---

## 3. Personas

Each sub-criterion is evaluated from the perspective of three personas. The final score for a sub-criterion = **minimum** of the three scores (the weakest link determines DX).

- **P1. Newcomer integrator.** Using the SDK for the first time. Relies on README, quickstart, and IDE hints. Reads source code only as a last resort.
- **P2. Experienced developer.** Writes production code, uses `mypy`, debugs incidents, writes their own tests on top of the SDK.
- **P3. Maintainer.** Updates the SDK version in their project, monitors releases, maintains backward compatibility of their own code, collects bug reports.

---

## 4. Data Collection Methods

A single set of methods — each criterion explicitly states which apply.

| Code | Method | Description |
|---|---|---|
| **AC** | Auditing Code | Manual reading of the public API without diving into implementation. The evaluator's role is "smart reader", not author |
| **SA** | Static Analysis | Applying static analyzers: types, style, docstrings, dead code, security lint |
| **FI** | Fault Injection | Controlled error injection (5xx, 401, timeout, malformed JSON) via mocks and proxies |
| **TT** | Timed Task | Time-based task: measuring how long it takes a persona to reach the result |
| **TAL** | Think-Aloud Lab | User session with a "think aloud" protocol: recording moments of getting stuck |
| **HE** | Heuristic Evaluation | Heuristic analysis using 10 DX heuristics (see §5.5) |
| **CB** | Comparative Benchmark | Comparing specific behavior against reference SDKs (Stripe, Azure, Google Cloud, boto3, OpenAI) |
| **DA** | Document Audit | Verifying public documentation against actual SDK behavior |
| **LA** | Log Analysis | Analyzing SDK logs: what is written, at what levels, whether secrets leak |
| **AM** | Automated Metric | Any machine-extractable metric: test coverage, number of public symbols with docstrings, number of `TODO`/`FIXME`, etc. |

Each sub-criterion must have **≥1 method from {SA, FI, DA, AM, CB}** — at least one source independent of subjective judgment. Manual methods (AC, TT, TAL, HE) are applied in addition, but not as the sole source.

---

## 5. Tools

### 5.1 Python Static Analysis

- **ruff** — style violations, basic anti-patterns, dead code, subset of `flake8` rules.
- **mypy** in `--strict` mode — completeness of type annotations, `Any` leaks, annotation/runtime mismatches.
- **pyright** (alternative) — faster and stricter static type analyzer.
- **bandit** — security lint (hardcoded secrets, unsafe patterns).
- **vulture** — dead code detection: unused imports, functions, classes.
- **radon** / **xenon** — cyclomatic complexity of public methods.
- **interrogate** — docstring coverage of public API.
- **pydocstyle** — docstring format.

### 5.2 Dynamic Tests and Fault Injection

- **pytest** — base for contract, integration, and error-mapping tests.
- **respx** / **httpx-mock** — HTTP layer mock for `httpx`-based clients.
- **vcrpy** / **pytest-recording** — recording and replaying real HTTP sessions for regression.
- **pytest-httpserver** — spin up a test HTTP server capable of simulating 4xx/5xx/medleys.
- **toxiproxy** / **mitmproxy** — simulating network anomalies: jitter, drops, rate limiting.
- **hypothesis** — property-based tests for edge cases in serialization and mappers.
- **freezegun** — time freezing for checking retry-after and backoff behavior.

### 5.3 Documentation Measurement Tools

- **vale** — prose linter for documentation style and terminology.
- **markdownlint** — Markdown quality.
- **sphinx-build -W** — reference build without warnings.
- **link-checker** (e.g., `lychee`) — dead link detection.
- **Diátaxis matrix** — manual categorization of existing materials (see §9.15).

### 5.4 UX Research Tools

- **Time-to-First-Call (TTFC)** — metric in seconds from `pip install` to first successful real request, measured with a stopwatch.
- **Task Success Rate (TSR)** — share of users who solved the test task without assistance.
- **System Usability Scale (SUS)** in **DevSUS** variant — 10-question questionnaire adapted for SDKs. Result from 0 to 100, reference threshold ≥80.
- **Think-aloud protocol** — user narrates their progress; evaluator records points of getting stuck.
- **Diary study** (for P3) — collecting a maintainer's notes over 1–2 sprints of use.

### 5.5 DX Heuristics for Python SDK (HE)

Adapted Nielsen checklist for SDKs:

1. **Visibility of state.** The user understands where a network call happens and where it does not.
2. **Match to domain language.** Method names reflect domain operations, not HTTP.
3. **Freedom and control.** Per-operation overrides exist, and there is an "escape hatch" to low-level primitives when needed.
4. **Consistency and standards.** The SDK follows Python conventions (snake_case, PEP 8) and internal conventions throughout the surface.
5. **Error prevention.** Incorrect input is caught before the network call (fail-fast).
6. **Recognition over recall.** IDE autocomplete provides everything needed without consulting documentation.
7. **Flexibility and efficiency.** A newcomer completes the happy path in minutes; an experienced user has access to fine-tuning.
8. **Minimalism.** The public API contains only what is needed; everything else is hidden.
9. **Language of errors.** Messages help diagnose and act, not merely state a fact.
10. **Help and documentation.** All four Diátaxis modes are covered: tutorials, how-to, reference, explanations.

### 5.6 Reference SDKs for Comparative Benchmark (CB)

Behavior comparisons are made against reference Python SDKs:

- **Stripe** (`stripe-python`) — idempotency, auto-pagination, error mapping.
- **Azure SDK for Python** — client constructor, long-running operations, `ItemPaged`.
- **Google Cloud Python** — ADC, transparent pagination.
- **boto3** — configuration, retries, sessions.
- **OpenAI Python SDK** — async/sync parity, streaming responses.

For each behavior, the methodology requires formulating an answer: "in the reference it is implemented via X, in the evaluated SDK via Y; the DX difference is Z".

---

## 6. Scale, Formula, and Prioritization

### 6.1 Sub-criterion Scoring Scale

| Level | Score | Indicator |
|---|---|---|
| Absent | 0% | Requirement not met; defect visible in the first minutes |
| Partial | 25% | Met in some places, violated elsewhere |
| Basic | 50% | Met in most cases, with systematic exceptions |
| Good | 75% | Met everywhere, rare minor deviations |
| Reference | 100% | Met, no signs of weakness, comparable to best SDKs |

Intermediate values are allowed with justification.

### 6.2 Integral Score Formula

```
Score = Σ ( weight_criterion_i × Σ ( weight_subcriterion_ij × grade_ij ) )
```

where `grade_ij ∈ [0, 1]`, `Σ weight_criterion = 100%`, and within each criterion `Σ weight_subcriterion = weight_criterion`.

### 6.3 Interpretation

- **≥ 90%** — reference DX, comparable to industry-leading SDKs.
- **75–89%** — working tool, noticeable rough edges in 1–2 criteria.
- **60–74%** — DX debt, planned refactoring needed.
- **< 60%** — architectural revision required before wide publication.

### 6.4 Pain Index (Pain-ranking)

For each sub-criterion with `grade < 0.75`:

```
Pain = weight_subcriterion × (1 - grade) × persona_multiplier × cadence_multiplier
```

where:

- `persona_multiplier = 1.5` if the deficiency affects persona P1 (newcomer), otherwise 1.0 — newcomers leave an SDK fastest;
- `cadence_multiplier = 1.3` if the weakness manifests in everyday scenarios (written/read in every other line of user code), 1.0 otherwise.

The backlog is sorted by descending `Pain`. The top quartile is the target for the nearest sprint.

---

## 7. Criteria

Sum of weights = 100%.

| # | Criterion | Weight |
|---|---|---|
| 1 | Onboarding and Time-to-First-Call | 10% |
| 2 | Public API Discoverability | 8% |
| 3 | Naming and Consistency | 4% |
| 4 | Typing and IDE-friendliness | 10% |
| 5 | Data Modeling and Return Types | 6% |
| 6 | Error Handling and Actionability | 8% |
| 7 | Safety of Use | 6% |
| 8 | Reliability Under Unstable Network | 7% |
| 9 | Idempotency of Write Operations | 3% |
| 10 | Pagination and Collection Handling | 4% |
| 11 | Per-operation Overrides | 3% |
| 12 | Async/Sync Parity | 3% |
| 13 | Configuration and Fail-fast | 4% |
| 14 | API Contract Coverage | 4% |
| 15 | Documentation (Diátaxis) | 7% |
| 16 | Testability by User Code | 5% |
| 17 | Observability and Logging | 3% |
| 18 | Compatibility and Deprecation Policy | 5% |

Detailed descriptions of each criterion follow.

---

### 8. Criterion 1. Onboarding and Time-to-First-Call — 10%

**Goal.** Measure the path from "learned about the SDK" to "saw the first result".

**Key metric.** TTFC (minutes).

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 1.1 | Installation with one command, no system dependencies | 1% | TT, DA | `pip install` in a clean venv, measure time and errors |
| 1.2 | README quickstart reproducible via copy-paste | 2% | TT, DA | Clean venv, run README examples, count manual edits |
| 1.3 | First successful call requires ≤5 lines of code | 2% | AC, TT | LoC count for the canonical scenario |
| 1.4 | Environment variables are documented, priority resolution is described | 1% | DA | Verify documentation against behavior when `env` vs `.env` conflict |
| 1.5 | Fail-fast on invalid configuration | 2% | FI | Remove required fields, verify: error before network, clear exception class, no secrets |
| 1.6 | Canonical TTFC ≤ 15 minutes for P1 | 2% | TT, TAL | Video recording of newcomer session, stopwatch |

**Procedure.**

1. Spin up a clean venv, record exact time.
2. Run `pip install <sdk>`; record installation time and warnings.
3. Copy quickstart to a file, run it. Each manual edit reduces score 1.2 by 25%.
4. Measure TTFC until the first real network response.
5. Intentionally remove one required config field, catch the exception, evaluate the message quality.

**Symptoms of weak spots.**

- README leads through a "full example" before a "minimal example".
- Required fields require creating intermediate objects.
- Configuration error masquerades as a network exception.
- `pip install` requires system packages without warning.

**Recording template:** "Canonical scenario — N lines, TTFC — M minutes, manual edits — K, first configuration error message — `<quote>`".

---

### 9. Criterion 2. Public API Discoverability — 8%

**Goal.** Measure how much effort is needed to find the right method without reading source code.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 2.1 | Single entry point (facade) | 2% | AC, HE-2, CB | Comparison with Stripe/Azure: all scenarios from one root |
| 2.2 | Factory methods by domain area | 2% | AC | IDE autocomplete on the root client shows all domains |
| 2.3 | One obvious path for each operation | 2% | AC, DA | Search for duplicates in documentation and public names |
| 2.4 | Package structure navigation is predictable | 1% | AC, HE-4 | Sub-package names match API sections |
| 2.5 | Method names reflect business actions | 1% | AC, HE-2 | Absence of `post_*`/`do_*` style names |

**Procedure.**

1. Give P1 a task formulated in domain language (e.g., "send message X to user Y"). Measure time to the correct method.
2. Open the root SDK object in IDE, verify all domains appear in autocomplete.
3. Collect list of public methods and check for duplicates: two access points to the same data — deduct score 2.3.

**Symptoms.**

- Two equivalent paths exist for one action without a deprecation marker.
- Sub-package names don't match familiar operation names.
- `find . -name "utils*.py"` finds files containing significant business logic.

---

### 10. Criterion 3. Naming and Consistency — 4%

**Goal.** Consistent naming style = less time to learn.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 3.1 | Follows PEP 8 and Python conventions | 1% | SA | `ruff`, `pep8-naming` |
| 3.2 | Consistent operation prefixes (`get_`, `list_`, `create_`, ...) | 1% | AC, AM | Script grouping public methods by prefix |
| 3.3 | Domain-specific identifiers (no `resource_id`, `entity_id`) | 1% | AM | grep for abstract names in public signatures |
| 3.4 | Consistent parameter order in similar methods | 1% | AC | Visual comparison of signatures in the same family |

**Procedure.** Run `ruff` and `pep8-naming`; export list of public methods to CSV with columns `prefix`, `nouns`, `params`; analyze visually.

---

### 11. Criterion 4. Typing and IDE-friendliness — 10%

**Goal.** Protect the user at the static layer; provide maximum hints in the IDE.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 4.1 | Public API is fully typed | 3% | SA | `mypy --strict`, `pyright --strict` |
| 4.2 | No `Any`/`dict[str, Any]`/`object` in public signatures | 2% | SA, AM | grep signatures + mypy report |
| 4.3 | Runtime type matches annotation | 1% | AC, FI | Compare declared vs actual on collections (iterators, lazy) |
| 4.4 | Closed value sets expressed as enums | 2% | AC, DA | Cross-check with OpenAPI: fields with `enum` must be typed |
| 4.5 | IDE shows argument types, return types, and exceptions | 2% | HE-6, AC | Open 10 random public methods in IDE |

**Procedure.** Run `mypy --strict` and `pyright --strict` in CI, export error list; grep `": Any"`, `-> Any`, `-> dict`; sample 10 methods — manual IDE hover check.

**Effect ranking tools:** sub-criterion 4.1 — `exit_code` from mypy; 4.2 — grep hit count divided by total public signatures; 4.5 — assessed via HE.

---

### 12. Criterion 5. Data Modeling and Return Types — 6%

**Goal.** Users work with domain objects, not "raw" structures.

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 5.1 | Public methods return typed models, not dictionaries | 2% | AC, SA |
| 5.2 | Model fields have concrete domain names | 1% | AC |
| 5.3 | `required` and `Optional` are expressed explicitly and match the spec | 1% | DA |
| 5.4 | Uniform serialization (`to_dict`/`model_dump`) for all public models | 1% | AC, AM |
| 5.5 | Transport fields are hidden from public models | 1% | AC |

**Procedure.** Sample 20 public models; for each: serialize to JSON using a standard function, verify absence of internal fields, cross-check nullability against the specification.

---

### 13. Criterion 6. Error Handling and Actionability — 8%

**Goal.** Errors help diagnose and act.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 6.1 | Domain exception hierarchy covers significant HTTP statuses | 2% | FI | `pytest-httpserver` with sequence 400/401/403/404/409/422/429/5xx |
| 6.2 | Semantically distinct errors are not related by inheritance | 1% | AC | Exception graph analysis |
| 6.3 | Error messages contain operation, status, request-id, attempt | 2% | FI, AC | Capture exception, check attributes |
| 6.4 | Messages are actionable (what happened + what to do) | 1% | HE-9 | Sample 20 errors, evaluate against actionability checklist |
| 6.5 | Parse errors and transport errors are distinguishable by type | 1% | FI | Submit malformed JSON vs network drop |
| 6.6 | Probe methods return `bool`, don't throw | 1% | FI, AC | Check `exists`-style behavior on 404 |

**Procedure.** Build a matrix `(status × failure type) → expected exception class`. Submit each case through `pytest-httpserver` or `respx`. Record mismatches. For 6.4, apply the actionability checklist: (a) what happened, (b) where, (c) what to do, (d) where to get help.

---

### 14. Criterion 7. Safety of Use — 6%

**Goal.** Users must not leak secrets through the SDK.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 7.1 | Secrets do not appear in logs at any level | 2% | LA | Intercept `logging`, regex check against markers `Bearer`, `client_secret=`, `Authorization` |
| 7.2 | Secrets do not appear in exception messages | 1% | FI | Provoke an error with a known secret value in a parameter |
| 7.3 | Client diagnostic snapshot is safe by default | 1% | AC, FI | Call a "diagnostic" function, check content |
| 7.4 | Serialization of public models does not expose internal fields | 1% | AC | `json.dumps(model.to_dict())` on a model sample |
| 7.5 | `bandit` reports no high-severity findings in public modules | 1% | SA | `bandit -r <package>` |

**Procedure.** Set up a test that intercepts `logging` at `DEBUG` level, run 10 typical scenarios, grep output against secret regexes. For 7.5 — CI integration of `bandit`.

---

### 15. Criterion 8. Reliability Under Unstable Network — 7%

**Goal.** The SDK survives network failures without user intervention.

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 8.1 | Retries only on safe scenarios | 2% | FI | Sequences `[500, 500, 200]`, `[429, 200]`, `[timeout, 200]`, `[POST, 500]` |
| 8.2 | Exponential backoff with jitter | 1% | FI, AM | `freezegun` + measure delays between attempts, check variance |
| 8.3 | `Retry-After` is respected on `429` | 1% | FI | Server returns `429 Retry-After: 3`, check actual delay |
| 8.4 | After retries exhausted — domain exception, not transport exception | 1% | FI | `[500, 500, 500, 500]` → not `httpx.*`, but a domain type |
| 8.5 | Connect/read/write timeouts are configured explicitly | 1% | AC | Read transport constructor |
| 8.6 | Retry/timeout policy is configurable | 1% | AC, CB | Compare with `stripe-python` and Azure SDK |

**Procedure.** Connect `toxiproxy` or a mock server with programmable delay; for 8.2 — ≥5 attempts, measure `stdev(delays) > 0`; for 8.3 — compare actual delay with `Retry-After ± 20%`.

---

### 16. Criterion 9. Idempotency of Write Operations — 3%

**Goal.** A safe repeat of a write call does not create duplicates.

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 9.1 | Public write methods accept `idempotency_key` | 1% | AC, CB (reference — Stripe) |
| 9.2 | The same key is used throughout the entire retry chain | 1% | FI |
| 9.3 | Absence of key = no retry on non-idempotent statuses | 1% | FI |

**Procedure.** Scenario `[transport_error, 200]` for POST: with key — two requests with the same header; without key — one attempt and exception.

---

### 17. Criterion 10. Pagination and Collection Handling — 4%

**Goal.** Large collections don't require manual page stitching.

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 10.1 | Lazy container returned by default | 1% | AC, FI |
| 10.2 | Iterating first N elements → `ceil(N/page)` requests | 1% | FI, AM |
| 10.3 | Explicit full materialization without repeated requests | 1% | FI |
| 10.4 | Empty collection makes no extra requests; page N error propagates when reading N | 1% | FI |

**Procedure.** Mock server with N pages: count HTTP calls for a slice `[:k]`, for full materialization, for empty response, for error on page 3.

---

### 18. Criterion 11. Per-operation Overrides — 3%

**Goal.** Flexibility at the individual call level without mutating the client.

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 11.1 | `timeout` can be overridden at the method level | 1% | AC, FI |
| 11.2 | Retry policy can be disabled/strengthened for a single call | 1% | AC, FI |
| 11.3 | Override does not mutate the client and does not leak between calls | 1% | FI |

**Procedure.** Pass `timeout=0.001` to one call, verify that a neighboring call with the default timeout is not affected.

---

### 19. Criterion 12. Async/Sync Parity — 3%

Applicable only if the SDK declares an async surface; otherwise the criterion is disabled and the weight is redistributed proportionally.

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 12.1 | Async and sync live in separate namespaces | 1% | AC, CB |
| 12.2 | Signatures are identical (differ only by `async`/`await`) | 1% | AC, AM |
| 12.3 | Feature parity within a single release | 1% | DA |

---

### 20. Criterion 13. Configuration and Fail-fast — 4%

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 13.1 | Configuration from environment, explicit object, and direct arguments — all three paths work | 1% | AC, TT |
| 13.2 | Priority resolution (`env > .env > defaults`) is deterministic and documented | 1% | FI, DA |
| 13.3 | Missing required fields are caught before the first HTTP call | 1% | FI |
| 13.4 | Generic env names (`TOKEN`, `SECRET`) are not official aliases | 1% | DA |

---

### 21. Criterion 14. API Contract Coverage — 4%

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 14.1 | All operations in the upstream spec have a public method | 2% | AM, DA |
| 14.2 | Field names, nullability, and enums match the spec | 1% | DA |
| 14.3 | Deprecated operations are explicitly marked with deprecation | 1% | AC, DA |

**Procedure.** Extract the list of `operationId` from OpenAPI/Swagger; map to public methods via a correspondence table; cross-check fields against schema on a sample of 20 models.

---

### 22. Criterion 15. Documentation (Diátaxis) — 7%

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 15.1 | Tutorial (step-by-step from zero to first success) is present | 1.5% | DA, TT | Run P1 persona through the tutorial |
| 15.2 | How-to guides for typical tasks | 1.5% | DA | Inventory of ready-made recipes |
| 15.3 | Reference covers the public API | 1.5% | AM | `interrogate` — docstring coverage |
| 15.4 | Explanations for key concepts (transport, retry, pagination) | 1% | DA |
| 15.5 | CHANGELOG is maintained, linked to releases | 0.5% | DA |
| 15.6 | Documentation examples are executable | 1% | TT | Copy-paste all snippets into a venv |

**Procedure.** Build a Diátaxis matrix (4 columns, documentation sections as rows). Each section belongs to exactly one cell. Empty columns = failure.

---

### 23. Criterion 16. Testability by User Code — 5%

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 16.1 | Public fake/mock transport is available from a documented namespace | 2% | AC, DA |
| 16.2 | Mock contract is documented: response script, call inspection, error injection | 1% | DA |
| 16.3 | Public models serialize stably via `json.dumps` without custom encoders | 1% | AM |
| 16.4 | Context manager closes resources; calling after close gives a clear error | 1% | FI |

**Procedure.** Write a "canonical consumer test": create a client with the public mock, run 3 scenarios, serialize results to JSON, close the client, attempt to call a method — record behavior.

---

### 24. Criterion 17. Observability and Logging — 3%

| # | Sub-criterion | Weight | Methods | Tools |
|---|---|---|---|---|
| 17.1 | SDK uses standard `logging` under a named logger | 1% | AC, LA |
| 17.2 | Structured fields: operation, endpoint, status, attempt, latency | 1% | LA |
| 17.3 | Every network call leaves at least one record at `DEBUG` | 1% | LA |

**Procedure.** Enable `logging` at `DEBUG`, run 5 typical scenarios, export records as JSON lines, verify field presence and absence of secrets.

---

### 25. Criterion 18. Compatibility and Deprecation Policy — 5%

| # | Sub-criterion | Weight | Methods |
|---|---|---|---|
| 18.1 | Semver is followed (breaking → major, additive → minor, fix → patch) | 1% | DA |
| 18.2 | Deprecation period is explicit, at least two minor releases | 1% | DA |
| 18.3 | Deprecated symbols emit `DeprecationWarning` with a link to the replacement | 1% | AC, FI |
| 18.4 | CHANGELOG contains sections `Added`/`Changed`/`Deprecated`/`Removed`/`Fixed` | 1% | DA |
| 18.5 | Public renames always go through an alias with a warning | 1% | AC, DA |

**Procedure.** Take the last 3–5 releases; for each — match the nature of changes against the versioning. Import deprecated symbols, verify `DeprecationWarning`.

---

## 26. Evaluation Process

Recommended duration for a full cycle — 1–2 days per evaluator; 3–4 days with user participation.

### 26.1 Preparation (30 min)

- Clean venv, fix SDK SHA/version.
- Install tools from §5.
- Create working folder `evaluation/<sha>/` for artifacts.

### 26.2 Automated Layer (1–2 hours)

Run sequentially and save output:

- `ruff check`, `ruff format --check`
- `mypy --strict` or `pyright --strict`
- `bandit -r`
- `vulture`
- `interrogate`
- custom script comparing upstream spec with public API

Fill all sub-criteria with `SA`/`AM` method.

### 26.3 Document Audit (1–2 hours)

- Build the Diátaxis matrix.
- Cross-check the list of env variables in documentation against actual behavior.
- Review CHANGELOG for recent releases.
- Verify executability of all documentation snippets.

### 26.4 Fault Injection (2–3 hours)

- Spin up `pytest-httpserver` or `respx`.
- Run matrices: `(status × scenario) → expected behavior`.
- Record results in a table.

### 26.5 Persona Sessions (2×30 min, optionally 3×30)

- P1 receives the canonical onboarding task.
- P2 receives the task "write a test on top of the SDK".
- P3 (if available — optional via diary study) records version upgrade incidents.
- Screen recording, think-aloud protocol.

### 26.6 Heuristic Pass (1 hour)

Using 10 DX heuristics (§5.5). Each heuristic produces a short observation + reference to affected sub-criteria.

### 26.7 Comparative Benchmark (1 hour)

Select 2–3 reference SDKs from §5.6. Record divergences on the same scenarios.

### 26.8 Synthesis and Report (1–2 hours)

- Fill the summary table `criterion × subcriterion × grade × evidence`.
- Calculate `Score`.
- Calculate `Pain` for each sub-criterion with `grade < 0.75`.
- Sort backlog.
- Format report following the template in §27.

---

## 27. Report Template

Fixed structure to make results comparable across releases.

### 27.1 Summary

- **Score**: `XX%` (category: reference / working / debt / refactoring).
- **Evaluation date**, **SDK version**, **evaluator name**.
- Top 3 findings in 1–2 sentences.

### 27.2 Criteria Summary Table

Columns: `#`, criterion, weight, weighted-average score, contribution to `Score`, trend (`↑/↓/→` relative to previous evaluation).

### 27.3 Detailed Observations by Criterion

For each criterion:

- Sub-criterion scores with brief justification.
- Evidence — link to log, screenshot, quoted message, session recording. **Without specifying concrete filenames from source code** — behavior is described, not location.
- What will earn +25% in the next evaluation.

### 27.4 Top-10 by Pain Index

Table: `#`, observation, sub-criterion, `Pain`, estimated fix effort, recommendation.

### 27.5 Appendices

- Raw tool output (`ruff.txt`, `mypy.txt`, `bandit.json`).
- FI matrix with requested/received reactions.
- Persona session transcripts (de-identified).
- DevSUS questionnaires.

---

## 28. Methodology Validation

The methodology is considered valid if:

1. **Reproducibility.** Two independent evaluators produce `Score` within ±5% on the same revision.
2. **Pain-ranking stability.** The top-10 sub-criteria by `Pain` agree between sessions ≥80%.
3. **Automation.** Each sub-criterion has at least one objective data source (SA/FI/DA/AM/CB). No purely subjective sub-criteria.
4. **Predictability.** Implementing all backlog recommendations produces a `Score` increase no less than the sum of weights of the corresponding sub-criteria.
5. **Portability.** The methodology applies to any Python SDK without changes, except for disabling criterion 12 (async/sync parity) for synchronous SDKs.

---

## 29. Application Schedule

- **Quarterly** for stable SDKs.
- **Before every major release** as a release gate.
- **After any architectural rework** of the public API.
- **After negative user feedback appears** — targeted evaluation of the criteria indicated by the feedback.

Results — `Score`, delta, Pain-top — are published in release notes as part of the release quality description.
