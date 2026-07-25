---
name: determine-incremental-strategy
description: Determine the correct incremental type (no_increment, by_source_tst, by_key) for a data flow, whether SQL-based or not. Walks through source characteristics, retry semantics, and deletion handling to recommend an incremental type, loading strategy, and IncrementalConfig.
user-invocable: true
---

# Analysis: Determine Incremental Type

Recommend the correct incremental type for a data flow.

The repository supports three incremental types (`no_increment`,
`by_source_tst`, `by_key`) and four loading strategies (`FULL`, `DELTA`,
`BACKFILL`, `BACKFILL_DELTA`). Choosing the wrong combination leads to
either reprocessing the whole dataset on every run or silently missing
records. This skill walks the analysis end-to-end and produces a concrete
recommendation.

## Architectural Context

Before starting the analysis, load the relevant nld-core guide skills for
architectural context:

- **`guide-incremental`** — incremental types, state management, backend
  implementations. Read sections 2.4 (Loading Strategies), 2.5 (Incremental
  Types), and 2.7 (Backend and Engine Implementations) when in doubt.
- **`guide-flows`** — SQLFlowTask vs DataFlowTask lifecycle, write strategies,
  and how incremental filtering integrates with flow execution.
- **`guide-structures`** — structure definitions and field characterisations,
  relevant when evaluating source/target schema for timestamp columns or
  partition keys.

The nld-core plugin (required dependency) provides the full architectural
reference via its guide skills.

## Instructions

Follow these steps strictly and in order.

### Step 1: Identify the target flow

The user provides one of the following as argument:

1. A path to a flow YAML definition (e.g. `flows/my_namespace/my_flow.yml`)
2. A flow namespace + name (e.g. `my_namespace.my_flow`)
3. A free-form description of a new flow they intend to create

If a YAML path or namespace is given, locate and read the flow definition
and any referenced source/target structures. If only a description is
given, ask the user a single consolidated question to gather the missing
facts listed in Step 2.

Also detect whether the flow is **SQL-based** or **not**:

- SQL flow: definition uses `nld.flow.sql.sql_flow_task.SQLFlowTask` (or a
  subclass), the YAML references a SQL query file, or the user explicitly
  says "SQL flow".
- Non-SQL flow: a Python `DataFlowTask` subclass, file-based ingest,
  HTTP API pull, etc.

This distinction matters because `by_source_tst` requires the processing
step to actually filter source data with the computed `pull_from` /
`pull_to` window. SQL flows do that natively by injecting the timestamps
as query parameters; non-SQL flows must do it explicitly in their
`run_flow()` implementation.

### Step 2: Gather source characteristics

Collect the following facts. If any are missing from the YAML or
surrounding code, ask the user in **one** consolidated question:

| Fact | Why it matters |
|------|----------------|
| Does the source expose a monotonic, reliable update timestamp column (e.g. `updated_at`, `last_modified_at`)? | Required for `by_source_tst`. |
| Is the source naturally partitioned into discrete keys (date partitions, file batches, tenant IDs, S3 prefixes)? | Required for `by_key`. |
| Approximate volume per run and total dataset size | Decides whether full reload is acceptable. |
| Does the source ever logically delete records, and must deletions propagate downstream? | Only `by_key` tracks logical deletion (`tracks_logical_deletion`). |
| Are per-item retries needed (one bad key should not block the others)? | Argues for `by_key`. |
| Does the user need backfill semantics (re-run a specific date / key range)? | `by_key` supports `BACKFILL` and `BACKFILL_DELTA`; `by_source_tst` supports only `FULL` / `DELTA`. |
| Backend in use (s3_blob_storage, postgresql, local) and engine (pydantic, duckdb) | Not all incremental + backend + engine combinations exist. See `guide-incremental` section 2.7. |

### Step 3: Apply the decision tree

Walk the following decision tree in order. Stop at the first matching rule.

1. **Pick `no_increment` if any of:**
   - The source is a small static lookup / reference table that is cheap
     to fully reload every run.
   - The source has no usable timestamp **and** no usable partitioning key.
   - The flow is intentionally a full-refresh materialization (e.g. a
     downstream aggregate that must be rebuilt from scratch).

   This sets `tracks_state=False` so no state read/write/logging happens.
   Confirm with the user that full reload cost is acceptable.

2. **Pick `by_key` if any of:**
   - The source is partitioned into discrete keys you can enumerate
     cheaply (date partitions, file names, S3 prefixes, tenant IDs).
   - You need per-key retry semantics (failed keys retry next run while
     succeeded ones are skipped).
   - The source has logical deletions that must be detected and
     propagated (`tracks_logical_deletion=True`).
   - The user needs to backfill specific keys via `--keys` or a `--limit`.

   Verify the chosen `(backend, engine)` combination is supported in the
   support matrix (see `guide-incremental` section 2.7).

3. **Pick `by_source_tst` if all of:**
   - The source has a single, monotonic, reliable timestamp column.
   - The flow can filter source rows by `[pull_from, pull_to)` — for SQL
     flows this means the query template accepts the timestamp params;
     for non-SQL flows the `run_flow()` must use them.
   - Per-key retry and logical deletion are **not** required.

   Note: `by_source_tst` only supports `FULL` and `DELTA` strategies.

4. **Otherwise, escalate to the user.** Do not pick a strategy if the
   facts in Step 2 are inconsistent (e.g. a SQL flow over a source with
   no timestamp and no enumerable keys). Explain the contradiction and
   ask which constraint they prefer to relax.

### Step 4: Pick the loading strategy

Recommend the default loading strategy for normal scheduled runs based on
the chosen incremental type:

| Incremental type | Default strategy | Notes |
|------------------|------------------|-------|
| `no_increment`   | `FULL`           | Only strategy that makes sense. |
| `by_source_tst`  | `DELTA`          | Use `FULL` only for the very first run or full refresh. |
| `by_key`         | `DELTA`          | `BACKFILL` / `BACKFILL_DELTA` are operator-triggered for replays. |

If the user already mentioned needing backfills, also call out the
relevant CLI flags (`--full`, `--keys`, `--limit`).

### Step 5: Recommend `IncrementalConfig` settings

Suggest concrete YAML values for the per-flow `IncrementalConfig`. The
defaults are usually right; only diverge when there is a clear reason.

| Property | Default | Recommend changing when |
|----------|---------|--------------------------|
| `type` | (required) | Must match the type chosen in Step 3. `strategy` is accepted as a deprecated alias. |
| `persist_initial_processing_state` | `True` | Disable only for very small / very fast flows where the extra write is wasteful. |
| `immediate_step_persistence` | `True` | Disable when the flow has many short steps and the per-step write cost dominates; accept that intermediate progress is lost on crash. |

### Step 6: Verify backend + engine support

Cross-check the chosen `(incremental_type, backend, engine)` against the
support matrix in `guide-incremental` section 2.7. If the combination is
not implemented, either:

- Recommend a supported alternative backend/engine, or
- Tell the user which backend module they would need to add and point at
  `nld/flow/incremental/{type}/backend/` for the file naming convention.

### Step 7: Report the recommendation

Produce a short report with these sections, in this order:

1. **Flow under analysis** — path / name, SQL or non-SQL.
2. **Key facts collected** — bulleted list of the answers from Step 2.
3. **Recommended incremental type** — one of `no_increment`,
   `by_source_tst`, `by_key`, with a one-sentence justification tied to
   the facts.
4. **Recommended loading strategy** — default + any backfill flags the
   operator should know about.
5. **Recommended `IncrementalConfig` YAML snippet** — copy-pasteable.
6. **Backend + engine compatibility** — confirmation that the combination
   exists, or the alternative if not.
7. **Open risks / follow-ups** — anything the user must verify (e.g.
   "confirm `updated_at` is never updated retroactively", "confirm the
   SQL query uses the `pull_from` / `pull_to` parameters").

Keep the report focused on decisions and their justification. Do not
restate the architecture doc.
