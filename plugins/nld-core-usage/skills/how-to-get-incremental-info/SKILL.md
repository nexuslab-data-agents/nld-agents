---
name: how-to-get-incremental-info
description: >
  Inspect the persisted incremental state of an `nld` flow from the
  shell using `nld flow state incremental get-state`. Use when the user
  asks "where did the last delta stop?", "which keys still need
  processing?", or "what watermark will the next run resume from?".
  Returns the current processing state by default; `--include-post-processing`
  bundles in the authoritative post-processing state. Stdout renders a
  concise text summary by default; pass `--format json` for the full
  machine-readable payload, or `--output` to write JSON to a file.
user-invocable: true
---

# How to Get Incremental Info for a Flow

**Classification**: Atomic Skill | Flow State Inspection

---

## Definition

- **What**: Read the persisted incremental state of a flow (current
  processing state, optionally also the authoritative post-processing
  state) via `nld flow state incremental get-state`.
- **When**: The user asks where the next delta will resume, which keys
  are pending or failed for a `by_key` flow, or what the
  `by_source_tst` watermark currently is. Also use as a first step
  when debugging "why did the flow not pick up X?".
- **Why**: The CLI resolves the flow's incremental strategy
  automatically (`by_source_tst` / `by_key` / `no_increment`), targets
  the **primary** state backend, and emits schema-stable JSON. Reading
  the underlying tables/files directly works as a fallback but
  bypasses that resolution.

For the architecture (state classes, processing lifecycle, dual state
backend semantics), see the `guide-incremental` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- The flow must have a `state_backend_connector` configured (inline or
  via the project-level default in `config/flow.yaml`); otherwise the
  CLI raises a clear RuntimeError.
- The connection referenced by `state_backend_connector.primary` must
  resolve to a backend that implements the read accessors. **PostgreSQL
  is the only fully-supported backend today**; other backends inherit
  a `NotImplementedError` default.

---

## The command

```
nld flow state incremental get-state --name <flow> [--namespace <ns>]
                                     [--include-post-processing]
                                     [--format text|json]
                                     [--output] [--override-output-folder-path <dir>]
```

### Flags

| Flag | Purpose |
|------|---------|
| `--name <flow>` | Flow name (required). |
| `--namespace <ns>` | Namespace of the flow. Optional — the registry resolves it from the project layout when omitted. Pass explicitly when the flow was relocated and you want to read state under a previous namespace. |
| `--include-post-processing` | Also include the authoritative post-processing state in the payload (the value the next run will read as its starting point). |
| `--format text\|json` | Stdout rendering. `text` (default) prints a concise human-friendly summary; `json` prints the full machine-readable payload. |
| `--output` | Write JSON to a fixed file under `output/<timestamp>/`. File output is always JSON, independent of `--format`. |
| `--override-output-folder-path <dir>` | Write into `<dir>` instead; implies `--output`. |

### Output shapes

| Invocation | Payload |
|------------|---------|
| `get-state` (default) | The current `FlowProcessingState` for the flow's incremental strategy. `{}` when none exists. |
| `get-state --include-post-processing` | `{"processing_state": ..., "post_processing_state": ...}`. Each wrapper key is omitted entirely when its underlying state is absent. |

`null` fields are stripped from every payload (`exclude_none=True`).

The shape of the inner state depends on the flow's incremental strategy:

- **`by_source_tst`** — `BySourceTstProcessingState`:
  `flow_uid`, `strategy`, `pull_from_timestamp`, `pull_to_timestamp`,
  `processing_status`, `process_error_message`,
  `processing_completed_at`. Post-processing is `BySourceTstState`:
  `last_pull_to_timestamp` (the watermark the next run resumes from).
- **`by_key`** — `ByKeyProcessingState`: `flow_uid`, `strategy`, and
  `keys: dict[str, ByKeySingleKeyProcessingState]` keyed by source
  identifier; each per-key entry carries `processing_status`,
  `process_error_message`, `processing_completed_at`, `parameters`.
  Post-processing is `ByKeyState`: `keys: dict[str, ByKeySingleKeyState]`
  with `status`, `last_successfully_processed_at`,
  `last_processed_at`, `last_process_status`,
  `last_process_error_message`, `first_processed_at`,
  `source_deleted_at`, `parameters`.
- **`no_increment`** — typically empty. The flow has no incremental
  state to inspect.

---

## Recipes

### 1. `by_source_tst`: where will the next delta resume?

```
nld flow state incremental get-state --name daily_sales_refresh --include-post-processing
```

Read `post_processing_state.last_pull_to_timestamp` — that is the
exact value `pull_from_timestamp` will take on the next DELTA run.
`processing_state.pull_from_timestamp` and `pull_to_timestamp` show
the range the most recent run covered.

### 2. `by_key`: which keys still need processing?

```
nld flow state incremental get-state --name customer_enrichment --include-post-processing --format json \
  | jq '.post_processing_state.keys
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
nld flow state incremental get-state --name customer_enrichment
```

Without `--include-post-processing`, you see only the current
`ByKeyProcessingState` — the keys the most recent run planned to
process and their per-key outcomes. Compare against (2) to see what
moved during that run.

### 4. `by_key`: count of pending vs failed vs succeeded keys

```
nld flow state incremental get-state --name customer_enrichment --include-post-processing --format json \
  | jq '.post_processing_state.keys
        | [.[].status]
        | group_by(.)
        | map({status: .[0], count: length})'
```

### 5. `by_source_tst`: was the latest run a backfill or a delta?

```
nld flow state incremental get-state --name daily_sales_refresh --format json \
  | jq '{flow_uid, strategy, processing_status,
         range: [.pull_from_timestamp, .pull_to_timestamp]}'
```

`strategy` distinguishes `FULL` / `DELTA` / `BACKFILL` /
`BACKFILL_DELTA` for the most recent run.

### 6. Capture for downstream analysis

```
nld flow state incremental get-state --name daily_sales_refresh \
  --include-post-processing \
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

## Backend-specific access

The CLI is the canonical reader. Knowing the underlying tables helps
when the CLI is unavailable.

### PostgreSQL (fully supported)

Each incremental strategy stores both a current processing state and a
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

### BigQuery / Snowflake / DuckDB

The shared abstract accessors are in place but the concrete read
implementations have not been wired yet. The CLI raises
`NotImplementedError` for these backends. Read via the connector's
native CLI against the same table names until that work lands.

### S3 blob / local file

State lives as JSON artifacts on the connector's root path (for S3,
`<root>` is the backend's `s3_root_path`, derived from the flow's
`S3Structure` target by `determine_parameters_for_flow_definition` —
composed `s3_root_prefix` + `s3_folder_path`):

- processing state:
  `<root>/state/<flow_uid>/processed_state.json`
- post-processing state:
  `<root>/state/<incremental_type>_state.json`

---

## Dual state backend

When `state_backend_connector` declares both `primary` and `secondary`
(see `guide-flows` §8.3), **the post-processing state lives only on
the primary**. The secondary mirrors per-run processing state but
never the authoritative post-processing state — by design, so the
primary stays the single source of truth for "where the next run
resumes from".

`get-state --include-post-processing` always reads the primary, so the
distinction is transparent at the CLI layer. Direct reads against the
secondary's tables/files would only show processing-state mirrors and
miss the post-processing state entirely. See `guide-incremental` §4.4
"Dual State Backend" for the full read/write semantics table.

---

## Guidelines for agents

- **Use `--include-post-processing` whenever the user asks about
  "next run", "watermark", or "what's pending"** — the post-processing
  state is the authoritative answer; the processing state alone is
  about what the *most recent* run did.
- **For `by_key` flows, always inspect `keys` per-status** rather than
  reading the top-level `flow_uid`. The interesting signal is per-key.
- **Empty `{}` is a signal**, not a failure: the flow has no recorded
  state under the current `(namespace, name)`. If you expected rows,
  check whether the flow was relocated and re-run with `--namespace
  <previous>`.
- **Don't read the secondary backend for incremental state.** It only
  carries processing-state mirrors, never the post-processing state.
  Reads via the CLI already enforce this.
- **`--output` writes a deterministic file name**
  (`flow_state_incremental_get_state.json`). Use
  `--override-output-folder-path` to control the directory; the file
  name itself is fixed.

---

## Cross-references

- Architectural reference: `guide-incremental` (state classes, processing
  lifecycle, factory pattern, backend implementations). Section 4.4
  "Dual State Backend (Primary + Optional Secondary)" covers what
  mirrors and what doesn't.
- For execution state (separate from incremental state):
  `how-to-get-execution-info`.
- For choosing or configuring an incremental type for a *new* flow:
  `how-to-determine-incremental-strategy`.
