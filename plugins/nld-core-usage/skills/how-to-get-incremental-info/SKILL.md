---
name: how-to-get-incremental-info
description: >
  Inspect the incremental state of an `nld` flow from the shell using
  the `nld flow state incremental` subcommand group: `get-state` returns
  the current authoritative state the next run resumes from (or, with
  `--processing-only`, the transient state the most recent run left
  behind), and `compute` resolves the processing state the next run
  would build — optionally persisting it as a PLANNED plan, which
  `get-planned` then lists. Use when the user asks "where did the last
  delta stop?", "which keys still need processing?", "what watermark
  will the next run resume from?", or "what would the next run actually
  decide to do?". Stdout renders a concise text
  summary by default; pass `--format json` for the full machine-readable
  payload, or `--output` to write JSON to a file.
user-invocable: true
---

# How to Get Incremental Info for a Flow

**Classification**: Atomic Skill | Flow State Inspection

---

## Definition

- **What**: Read or compute the incremental state of a flow via the
  `nld flow state incremental` subcommand group:
  - `get-state` — read the current authoritative state (the
    post-processing state the next run resumes from); with
    `--processing-only`, read the transient processing state the most
    recent run left behind instead.
  - `compute` — resolve the processing state the next run would build,
    without starting the run; with `--persist`, store the result as a
    PLANNED plan in the planned-state slot.
  - `get-planned` — list the flow's PLANNED plans (lifecycle metadata,
    newest first).
- **When**: The user asks where the next delta will resume, which keys
  are pending or failed for a `by_key` flow, what the `by_source_tst`
  watermark holds, or what the next run *would* process if launched
  against the live source. Also use as a first step when debugging
  "why did the flow not pick up X?".
- **Why**: The CLI resolves the flow's incremental type
  automatically (`by_source_tst` / `by_key` / `no_increment`), targets
  the **primary** state backend, and emits schema-stable JSON. Reading
  the underlying tables/files directly works as a fallback but
  bypasses that resolution.

For the architecture (state classes, processing lifecycle, dual state
backend semantics, planned-state slot), see the `guide-incremental`
skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- The flow must have a `state_backend_connector` configured (inline or
  via the project-level default in `config/flow.yaml`); otherwise the
  CLI raises a clear RuntimeError.
- `get-state` (default) and `--processing-only` need
  `read_post_processing_state` / `read_processing_state` on the primary
  backend. PostgreSQL implements both; the other backends inherit a
  `NotImplementedError` default on the live-state read accessors.
- `compute` (read-only) runs wherever the flow runs — it resolves the
  next processing state in memory from `retrieve_current_state`. The
  CLI prints "not supported" for `no_increment` flows because the
  strategy has no processing state to compute.
- `compute --persist` and `get-planned` require both layers of
  planned-state support: the strategy's
  `FlowIncrementalDefinition.supports_planned_state` (set on `by_key`
  and `by_source_tst`) **and** the backend's
  `IncrementalBackendStateManager.supports_planned_state` (set on
  PostgreSQL and S3). When either layer is off the CLI emits a "not
  supported" notice and `--persist` returns `persisted=False` instead
  of letting the backend read raise.

---

## The command

```
nld flow state incremental get-state --name <flow> [--namespace <ns>]
                                     [--processing-only]
                                     [--format text|json]
                                     [--output] [--override-output-folder-path <dir>]
```

### Flags

| Flag | Purpose |
|------|---------|
| `--name <flow>` | Flow name (required). |
| `--namespace <ns>` | Namespace of the flow. Optional — the registry resolves it from the project layout when omitted. Pass explicitly when the flow was relocated and you want to read state under a previous namespace. |
| `--profile-name <profile>` | Optional. Select the credential profile of the state backend connection to read from. |
| `--processing-only` | Return the transient processing state the most recent run left behind, instead of the current authoritative state. |
| `--format text\|json` | Stdout rendering. `text` (default) prints a concise human-friendly summary; `json` prints the full machine-readable payload. |
| `--output` | Write JSON to a fixed file under `output/<timestamp>/`. File output is always JSON, independent of `--format`. |
| `--override-output-folder-path <dir>` | Write into `<dir>` instead; implies `--output`. |

### Output shapes

| Invocation | Payload |
|------------|---------|
| `get-state` (default) | The current authoritative `FlowState` (post-processing state) for the flow's incremental type — the value the next run reads as its starting point. `{}` when none exists. |
| `get-state --processing-only` | The transient `FlowProcessingState` the most recent run left behind. `{}` when none exists. |

`null` fields are stripped from every payload (`exclude_none=True`).

> **Breaking change (nld-core ≥ the release carrying this flip).** The
> default `get-state` now returns the **authoritative current state**
> (previously it returned the processing state). The old
> `--include-post-processing` flag is gone; use `--processing-only` for
> the previous default behaviour. The default JSON payload is now the
> state object itself, not a `{"processing_state", "post_processing_state"}`
> wrapper.

The shape of the state depends on the flow's incremental type:

- **`by_source_tst`** — current state is `BySourceTstState`:
  `last_pull_to_timestamp` (the watermark the next run resumes from).
  With `--processing-only`, `BySourceTstProcessingState`: `flow_uid`,
  `strategy`, `pull_from_timestamp`, `pull_to_timestamp`,
  `processing_status`, `process_error_message`,
  `processing_completed_at`.
- **`by_key`** — current state is `ByKeyState`:
  `keys: dict[str, ByKeySingleKeyState]` with `status`,
  `last_successfully_processed_at`, `last_processed_at`,
  `last_process_status`, `last_process_error_message`,
  `first_processed_at`, `source_deleted_at`, `parameters`. With
  `--processing-only`, `ByKeyProcessingState`: `flow_uid`, `strategy`,
  and `keys: dict[str, ByKeySingleKeyProcessingState]` keyed by source
  identifier; each per-key entry carries `processing_status`,
  `process_error_message`, `processing_completed_at`, `parameters`.
- **`no_increment`** — typically empty. The flow has no incremental
  state to inspect.

The text rendering (default `--format text`) labels the default view
`Current state:` and the `--processing-only` view `Processing state:`.
For `by_key` flows both views append a **`Sample of last retrieved`**
section listing the most recently retrieved keys (ordered by their
last-retrieved timestamp), so you can spot-check what was pulled
without dumping every key.

---

## Recipes

### 1. `by_source_tst`: where will the next delta resume?

```
nld flow state incremental get-state --name daily_sales_refresh
```

Read `last_pull_to_timestamp` — that is the exact value
`pull_from_timestamp` will take on the next DELTA run. To see the range
the most recent run covered, add `--processing-only` and read
`pull_from_timestamp` / `pull_to_timestamp`.

### 2. `by_key`: which keys still need processing?

```
nld flow state incremental get-state --name customer_enrichment --format json \
  | jq '.keys
        | to_entries
        | map(select(.value.status != "SUCCEEDED"))
        | map({key: .key, status: .value.status, last_error: .value.last_process_error_message})'
```

Pass `--format json` whenever piping into `jq` — without it stdout is
the text summary, not the machine payload.

Returns every key that hasn't reached `SUCCEEDED` — typically
`NOT_PROCESSED`, `FAILED`, or `DELETED`. Use this before manually
re-triggering work or filing an incident.

### 3. `by_key`: what did the most recent run intend to process?

```
nld flow state incremental get-state --name customer_enrichment --processing-only
```

With `--processing-only`, you see the transient `ByKeyProcessingState`
— the keys the most recent run planned to process and their per-key
outcomes. Compare against (2) (the default current state) to see what
moved during that run.

### 4. `by_key`: count of pending vs failed vs succeeded keys

```
nld flow state incremental get-state --name customer_enrichment --format json \
  | jq '.keys
        | [.[].status]
        | group_by(.)
        | map({status: .[0], count: length})'
```

### 5. `by_source_tst`: was the latest run a backfill or a delta?

```
nld flow state incremental get-state --name daily_sales_refresh --processing-only --format json \
  | jq '{flow_uid, strategy, processing_status,
         range: [.pull_from_timestamp, .pull_to_timestamp]}'
```

`strategy` distinguishes `FULL` / `DELTA` / `BACKFILL` /
`BACKFILL_DELTA` for the most recent run. This is a property of the
transient processing state, so `--processing-only` is required.

### 6. Capture for downstream analysis

```
nld flow state incremental get-state --name daily_sales_refresh \
  --override-output-folder-path ./out
```

Writes `flow_state_incremental_get_state.json` into `./out/`. Prefer
this over redirecting stdout — the CLI prints a log line about the
destination, which would otherwise pollute a redirected file.

### 7. Flow was relocated; old state lives under a previous namespace

```
nld flow state incremental get-state --name wttj_companies_extraction \
  --namespace source_web_hr
```

The registry resolves the flow at its current namespace by default;
state written under a previous namespace remains under that
namespace. Pass `--namespace` explicitly to read it.

---

## Computing the next processing state (`compute`)

`get-state` reads what the most recent run left behind. `compute`
resolves what the **next** run would do: it runs the flow's own
pre-processing-for-state slice (retrieve latest incremental state →
retrieve source state → determine logically deleted entries →
determine processing state) and returns the resulting
`FlowProcessingState`, without starting a run.

```
nld flow state incremental compute --name <flow> [--namespace <ns>]
                                   [--persist] [--requestor <user>]
                                   [--source-request-authorized]
                                   [--format text|json]
                                   [--output] [--override-output-folder-path <dir>]
                                   [<extra-incremental-options>]
```

`compute` never writes the live processing-state slot and never records
execution-history rows. It builds a fully-initialised `DataFlowTask`
through the same executor a real run uses, so per-flow connectors and
state-manager wiring are identical to execution.

Unknown options (e.g. `--limit`, `--keys`, `--full`) pass through to
the underlying `DataFlowTask` the same way `nld flow execute` accepts
them, so the computed plan reflects the parameters the next execution
would resolve.

### Flags

| Flag | Purpose |
|------|---------|
| `--name <flow>` / `--namespace <ns>` | Flow selection, as for `get-state`. |
| `--persist` | Persist the computed processing state to the state backend as a `PLANNED` plan, cancelling any prior `PLANNED` plan for the same flow. Without it, `compute` is read-only. |
| `--requestor <user>` | Identifier recorded on the persisted plan. Defaults to the current OS user (`getpass.getuser()`, falling back to `"unknown"`). Only meaningful with `--persist`. |
| `--source-request-authorized` | Pre-authorize the source-side queries that `retrieve_source_state` issues. When omitted and the flow's incremental definition declares `requires_source_state_retrieval` (only `by_key` today), the CLI prompts for confirmation before touching the source. |
| `--format text\|json`, `--output`, `--override-output-folder-path <dir>` | Same rendering / file-output convention as `get-state`. The fixed file name is `flow_state_incremental_compute.json`. |

### Output shape

```json
{
  "processing_state": { ... },   // the FlowProcessingState the next run would build
  "persisted": true,              // false when --persist is not set
  "plan_state_uid": "…",          // present only when persisted
  "requestor": "…"                // present only when persisted
}
```

`processing_state` is omitted when the strategy produces no processing
state (e.g. `no_increment`). `null` fields are stripped
(`exclude_none=True`). The shape of `processing_state` matches the
per-strategy shape documented for `get-state` above.

### Source-side cost

For `by_key` flows, `compute` calls the flow's `retrieve_source_state`,
which can issue real queries against third-party APIs or listings. The
command gates that step: pass `--source-request-authorized` to proceed
non-interactively, or answer the confirmation prompt. `by_source_tst`
and `no_increment` do not retrieve source state, so they never prompt.

### The planned-state slot

`--persist` writes to a slot that is **separate from the live
processing-state slot a running flow reads and writes**, on the
**primary** state backend only. A plan carries a lifecycle `status` of
`PLANNED`, `CANCELLED`, or `COMPLETED`; writing a new plan flips any
prior `PLANNED` plan for the same flow to `CANCELLED`, so at most one
`PLANNED` plan exists per flow at a time. Persisting requires both
`supports_planned_state=True` on the incremental definition
(strategies `by_key` and `by_source_tst`) and on the primary backend
(PostgreSQL and S3 mixins). When either layer is off, `--persist`
prints `persisted=False` and `get-planned` reports "Planned states are
not supported for this flow" instead of attempting a backend read. See
`execution-and-incremental-design.md` §4.5 "Planned-state slot" for the
storage layout, lifecycle, and per-strategy freshness rules.

List the plans recorded for a flow with `get-planned`:

```
nld flow state incremental get-planned --name daily_sales_refresh
```

It returns each `PLANNED` plan's lifecycle metadata (`plan_state_uid`,
`status`, `strategy`, `computed_at`, `requestor`, …), newest first —
the same backends that accept `--persist` back this listing.

### Consuming a plan from `nld flow execute`

`nld flow execute --planned-state-policy` selects how the next run
treats a `PLANNED` plan in the slot. Choices:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Adopt the plan when `is_planned_processing_state_fresh` returns `True`; recompute otherwise. |
| `recompute` | Ignore the planned-state slot entirely; always recompute. |
| `trust` | Adopt the plan as-is, without the freshness check. |
| `strict` | Require a fresh plan: raise `NoPlannedStateException` (code `42002`) when no plan exists, `StalePlannedStateException` (code `42003`) when the plan is stale. |

On a successful run, the consumed plan transitions to `COMPLETED` and
its `executed_by_flow_uid` is set to the run's `flow_uid`; a failed run
leaves the plan `PLANNED` so the next run can retry it. The strategy
flag has no effect when planned-state support is off on either layer.

`nld flow execute --state-compute-only` is the execute-side equivalent
of `nld flow state incremental compute --persist`: it computes and
persists a `PLANNED` plan without running the flow, requires `--name`,
and is incompatible with `--downstream` / `--upstream`. Source-side
queries (for strategies with `requires_source_state_retrieval`) are
pre-authorised because no target data is written.

### Recipes

#### `by_key`: preview which keys the next run will process

```
nld flow state incremental compute --name customer_enrichment \
  --source-request-authorized --format json \
  | jq '.processing_state.keys
        | to_entries
        | map(select(.value.processing_status == "TO_BE_PROCESSED"))
        | map(.key)'
```

Lists the keys the next run would mark `TO_BE_PROCESSED`, computed
against the current source and the persisted state — before committing
to a run.

#### Persist a plan for the record

```
nld flow state incremental compute --name daily_sales_refresh --persist
```

Computes and stores a `PLANNED` plan; the printed `plan_state_uid`
identifies it in the planned-state slot.

---

## Backend-specific access

The CLI is the canonical reader. Knowing the underlying tables helps
when the CLI is unavailable.

### PostgreSQL (fully supported)

Each incremental type stores both a current processing state and a
post-processing state in two separate tables:

| Strategy | Processing state table | Post-processing state table |
|----------|------------------------|----------------------------|
| `by_source_tst` | `_nld_incremental_by_source_tst_processing_state` | `_nld_incremental_by_source_tst_state` |
| `by_key` | `_nld_incremental_by_key_processing_state` | `_nld_incremental_by_key_state` |
| `no_increment` | n/a | n/a |

The processing-state table has one row per `(flow_uid, [key_name])` —
the latest run's planned/executed work. The post-processing (state)
table has one row per `(flow_namespace, flow_name, [key_name])` — the
authoritative state the next run reads.

Read-only SQL fallback for `by_source_tst`:

```sql
select last_pull_to_timestamp
from _nld_incremental_by_source_tst_state
where flow_namespace = 'source.raw'
  and flow_name = 'daily_sales_refresh';
```

### Snowflake

`by_source_tst` and `by_key` are fully supported: `read_processing_state` /
`read_post_processing_state` back `get-state`, and
`SnowflakeIncrementalBackendMixin` opts into `supports_planned_state`,
so `compute --persist` and `get-planned` work. The table names match
the PostgreSQL section above.

### BigQuery / DuckDB

The shared abstract accessors for the live processing-state and
post-processing-state tables are in place but the concrete read
overrides have not been wired, so `get-state` raises
`NotImplementedError` on these backends. Read via the connector's
native CLI against the same table names. `compute` (read-only) still
works through `retrieve_current_state`; `--persist` is unavailable
because these backends do not opt into `supports_planned_state`.

### S3 blob / local file

State lives as artifacts on the connector's root path. For S3,
`<state-root>` is `<s3_root_path>/state/`, with `s3_root_path` derived
from the flow's `S3Structure` target by
`determine_parameters_for_flow_definition` — composed `s3_root_prefix`
+ `s3_folder_path`.

- processing state:
  `<state-root>/<flow_uid>/processed_state.<json|parquet>`
- post-processing state:
  `<state-root>/<incremental_type>_state.<json|parquet>`
- state-plan index (all plans for the flow, keyed by `plan_state_uid`):
  `<state-root>/state_plans.<json|parquet>`
- per-plan processing-state payload (one folder per plan):
  `<state-root>/plans/<plan_state_uid>/<strategy>_planned_processing_state.<json|parquet>`

`file_format` on the connector's `params` controls the extension and
the encoding (JSON writes the full Pydantic envelope; parquet writes
rows against the schema returned by `get_state_plans_index_schema()` /
`get_<strategy>_processing_state_schema()`, with the envelope
`flow_uid` / `strategy` carried in PyArrow schema metadata). The S3
mixin assumes a single writer per flow on the index file.

---

## Dual state backend

When `state_backend_connector` declares both `primary` and `secondary`
(see `guide-flows` §8.3), **the post-processing state lives only on
the primary**. The secondary mirrors per-run processing state but
never the authoritative post-processing state — by design, so the
primary stays the single source of truth for "where the next run
resumes from".

`get-state` (default) always reads the post-processing state from the
primary, so the distinction is transparent at the CLI layer. Direct
reads against the secondary's tables/files would only show
processing-state mirrors and miss the post-processing state entirely.
See `guide-incremental` §4.4 "Dual State Backend" for the full
read/write semantics table.

---

## Guidelines for agents

- **Plain `get-state` already answers "next run", "watermark", or
  "what's pending"** — the default is the authoritative post-processing
  state. Reach for `--processing-only` only when the user specifically
  asks what the *most recent* run did (its planned/executed working
  set), which is transient.
- **For `by_key` flows, always inspect `keys` per-status** rather than
  reading the top-level `flow_uid`. The interesting signal is per-key.
- **Empty `{}` is a signal**, not a failure: the flow has no recorded
  state under the current `(namespace, name)`. If you expected rows,
  check whether the flow was relocated and re-run with `--namespace
  <previous>`.
- **Don't read the secondary backend for incremental state.** It only
  carries processing-state mirrors, never the post-processing state.
  Reads via the CLI already enforce this.
- **`--output` writes a deterministic file name** per subcommand
  (`flow_state_incremental_get_state.json` for `get-state`,
  `flow_state_incremental_compute.json` for `compute`). Use
  `--override-output-folder-path` to control the directory; the file
  name itself is fixed.
- **Reach for `compute` to answer "what would the next run do?"** —
  `get-state` describes the past; `compute` resolves the next run's
  decisions against the live source. On `by_key` flows it queries the
  source, so pass `--source-request-authorized` only when those queries
  are acceptable.
- **Default `compute` to read-only.** Add `--persist` only when you
  intend to record a `PLANNED` plan; it cancels any prior `PLANNED`
  plan for the flow.

---

## Cross-references

- Architectural reference: `guide-incremental` (state classes, processing
  lifecycle, factory pattern, backend implementations). The bundled
  `execution-and-incremental-design.md` covers §4.4 "Dual State
  Backend (Primary + Optional Secondary)" — what mirrors and what
  doesn't — and §4.5 "Planned-state slot" — strategy/backend opt-in,
  per-strategy freshness, storage layout, and the
  `--planned-state-policy` interaction.
- For execution state (separate from incremental state):
  `how-to-get-execution-info`.
- For choosing or configuring an incremental type for a *new* flow:
  `how-to-determine-incremental-strategy`.
- For authoring an external incremental type that opts into plans:
  `how-to-create-a-new-incremental-type`.
