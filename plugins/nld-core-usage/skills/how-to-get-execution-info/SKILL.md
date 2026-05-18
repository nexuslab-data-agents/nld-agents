---
name: how-to-get-execution-info
description: >
  Inspect the persisted execution state of an `nld` flow from the
  shell using the `nld flow state execution` subcommand group. Use when
  the user asks "did this flow run?", "when did it last succeed?", "why
  did it fail?", or wants the step-by-step breakdown of a specific
  execution. Covers `get-state` (latest header), `get-history` (newest
  first, optionally limited), and `get-steps` (per-execution step list,
  selected via `--latest` or `--flow-uid`). All commands emit JSON to
  stdout by default and accept `--output` to write to a file.
user-invocable: true
---

# How to Get Execution Info for a Flow

**Classification**: Atomic Skill | Flow State Inspection

---

## Definition

- **What**: Read the persisted execution state of a flow (header, full
  history, step detail) via the `nld flow state execution` subcommand
  group.
- **When**: The user asks about a flow's last run, its history, the
  status of a specific execution, or why a step failed. Also use as a
  troubleshooting first step before diving into raw SQL.
- **Why**: These commands resolve the flow definition, target the
  **primary** state backend connector automatically, and emit
  schema-stable JSON. Reaching for raw SQL works as a fallback but
  bypasses the namespace + connector resolution the CLI does for you.

For the underlying state model (`FlowExecutionInfo`,
`FlowExecutionState`, `FlowExecutionHistory`, dual state backend
semantics), see the `guide-flows` and `guide-incremental` skills.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- The flow must have a `state_backend_connector` configured (either
  inline on the flow YAML, or via the project-level default in
  `config/flow.yaml`). If neither is set, the CLI raises a clear
  RuntimeError.
- The connection referenced by `state_backend_connector.primary` must
  resolve to a backend that implements the read accessors. **PostgreSQL
  and S3 blob storage are supported today**; BigQuery, Snowflake, and
  DuckDB inherit a `NotImplementedError` default and need follow-up work.
- The resolver lazy-loads state-backend connectors from
  `connection_configs`, so the CLI works even when the executor has
  not yet loaded the connector for a regular run.

---

## The commands

```
nld flow state execution get-state    --name <flow> [--namespace <ns>]
                                      [--output] [--override-output-folder-path <dir>]

nld flow state execution get-history  --name <flow> [--namespace <ns>]
                                      [--limit <N>]
                                      [--output] [--override-output-folder-path <dir>]

nld flow state execution get-steps    --name <flow> [--namespace <ns>]
                                      (--flow-uid <UID> | --latest)
                                      [--output] [--override-output-folder-path <dir>]
```

### Common flags

| Flag | Purpose |
|------|---------|
| `--name <flow>` | Flow name (required). |
| `--namespace <ns>` | Namespace of the flow. Optional — the registry resolves it from the project layout when omitted. **Use this to read historical rows persisted under a previous namespace if the flow was relocated.** |
| `--output` | Boolean flag. Write the JSON to a fixed file under `output/<timestamp>/`. |
| `--override-output-folder-path <dir>` | Write into `<dir>` instead of the timestamped folder; implies `--output`. |

### Per-command flags

| Command | Flag | Purpose |
|---------|------|---------|
| `get-history` | `--limit <N>` | Cap to the most recent N executions. Default: no limit. |
| `get-steps` | `--flow-uid <UID>` | Steps for a specific execution. Mutually exclusive with `--latest`. |
| `get-steps` | `--latest` | Steps for the most recent execution. Mutually exclusive with `--flow-uid`. |

The `get-steps` selector is a true mutually-exclusive group: passing
neither flag, or both, raises a Click `UsageError` before any backend
call.

### Output shapes

| Command | Payload |
|---------|---------|
| `get-state` | `FlowExecutionInfo` header (no `steps`). `{}` when no execution exists. |
| `get-history` | `{"executions": [...]}` — each entry includes its `steps`, newest first. |
| `get-steps` | `[FlowStepExecutionInfo, ...]`. `[]` when the UID is unknown or no execution exists. |

`null` fields are stripped from every payload (`exclude_none=True`).

---

## Recipes

### 1. Was this flow's last run successful?

```
nld flow state execution get-state --name daily_sales_refresh
```

Inspect `execution_status` (`SUCCEEDED` / `FAILED` /
`SUCCEEDED_WITH_WARNING`), `started_at`, `ended_at`, and
`execution_error`. Empty `{}` means the flow has never been recorded.

### 2. Show the last 10 executions

```
nld flow state execution get-history --name daily_sales_refresh --limit 10
```

Useful for trend questions: "is this flow flaky?", "how often did it
backfill?", or for surfacing the `flow_uid` of an old failed run.

### 3. Find the first failure in recent history

```
nld flow state execution get-history --name daily_sales_refresh --limit 50 \
  | jq '.executions[] | select(.execution_status == "FAILED") | {flow_uid, started_at, execution_error}'
```

### 4. Step-by-step breakdown of the latest run

```
nld flow state execution get-steps --name daily_sales_refresh --latest
```

Returns the ordered step list with `step_name`, `started_at`,
`duration_seconds`, `step_status`, `step_error`, `query`,
`source_entries_in_*`, `target_entries_*_in_*`, `metadata`,
`custom_kpis`. Use this when a flow ran but a specific step misbehaved.

### 5. Re-investigate a specific historical execution

Once you have a UID from step 3:

```
nld flow state execution get-steps --name daily_sales_refresh \
  --flow-uid 0654d17d-6a47-473e-92a2-999d8edd6705
```

### 6. Capture for downstream analysis

```
nld flow state execution get-history --name daily_sales_refresh --limit 100 \
  --override-output-folder-path ./out
```

Writes `flow_state_execution_get_history.json` into `./out/`. Prefer
this over redirecting stdout when composing with other commands — the
CLI prints a log line about the destination, which would otherwise
pollute a redirected file.

### 7. Flow was relocated; old rows live under a previous namespace

```
nld flow state execution get-history --name wttj_companies_extraction \
  --namespace source_web_hr
```

The registry currently resolves the flow at its new location (e.g.
`wttj.extraction`), but rows written before the move carry the old
`flow_namespace`. Pass `--namespace` to read the historical rows
directly.

---

## Backend-specific access

The CLI is the canonical reader, but knowing the underlying tables
helps when the CLI is unavailable or when you need joins beyond what
the JSON exposes.

### PostgreSQL (fully supported)

Tables live under the connection's configured schema (or `public`
when no schema is set):

| Table | Holds |
|-------|-------|
| `_nld_execution_state` | One row per `(flow_namespace, flow_name)` — the latest execution. Source for `get-state`. |
| `_nld_execution_history` | One row per execution. Source for `get-history`. |
| `_nld_execution_step_history` | One row per (execution, step). Joined back into `get-state` and `get-history` via `flow_uid`. |

Read-only SQL fallback:

```sql
select *
from _nld_execution_history
where flow_namespace = 'source.raw'
  and flow_name = 'daily_sales_refresh'
order by started_at desc
limit 10;
```

### S3 blob storage (fully supported for execution reads)

The S3 backend implements `get_latest_execution_info` and
`get_execution_history`, so `get-state` and `get-history` work directly
against an S3 state backend (and via the dual-state primary when an S3
backend is declared as primary). State lives as JSON artifacts under
the backend's `s3_root_path`, derived from the flow's `S3Structure`
target by `determine_parameters_for_flow_definition` (composed
`s3_root_prefix` + `s3_folder_path`):

- per-execution info: `<s3_root_path>/state/execution_info/<flow_uid>.json`
- consolidated history: `<s3_root_path>/state/execution_history.json`

`get-steps` is served from the same `FlowExecutionInfo` payload, so the
step list is available too.

### BigQuery / Snowflake / DuckDB

The shared abstract accessors are in place but the concrete read
implementations have not been wired yet. The CLI raises
`NotImplementedError` for these backends. Read via the connector's
native CLI (`bq query`, `snowsql`, `duckdb`) against the same
`_nld_execution_*` table names until that work lands.

### Local file backend

Read implementations are pending. State lives as JSON artifacts on the
connector's root path under the same `state/` layout as S3.

---

## Dual state backend

When `state_backend_connector` declares both `primary` and `secondary`
(see `guide-flows` §8.3), **all reads target the `primary` only**. The
`secondary` backend is a write-only mirror of per-run artifacts —
asking it for history would miss the consolidated history file, which
is primary-only by design.

If a flow is configured with a secondary and you specifically want to
inspect what landed there, use that connector's own CLI (psql / bq /
duckdb / s3 ls) against the documented table or path layout.

---

## Guidelines for agents

- **Start with the CLI**, not raw SQL. The CLI handles namespace
  resolution, the dual-state primary selection, and the step-history
  join for you.
- **Don't run `get-history` without `--limit`** on a long-lived flow
  unless you actually need the full history — payloads can be megabytes.
- **`get-steps` without `--latest` or `--flow-uid` is a usage error**;
  pick one. Use `get-history` first to find a UID, then drill into
  `get-steps --flow-uid`.
- **Empty `{}` from `get-state` is a signal**, not a failure: the flow
  has no recorded execution under the current `(namespace, name)`. If
  you expected rows, check whether the flow was relocated and re-run
  with `--namespace <previous>`.
- **`--output` writes a deterministic file name**
  (`flow_state_execution_get_state.json`,
  `flow_state_execution_get_history.json`,
  `flow_state_execution_get_steps.json`). Use
  `--override-output-folder-path` to control the directory; the file
  name itself is fixed.

---

## Cross-references

- Architectural reference: `guide-flows` (`FlowExecutionInfo` /
  `FlowExecutionState` / `FlowExecutionHistory`, save vs read paths,
  step tracking decorator).
- For the dual state backend semantics (which writes mirror to
  secondary, which stay primary-only): `guide-incremental` §4.4 "Dual
  State Backend".
- For incremental processing state (separate from execution state):
  `how-to-get-incremental-info`.
