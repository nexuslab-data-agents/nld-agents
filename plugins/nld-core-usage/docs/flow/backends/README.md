# Flow Backends

A flow's state is persisted through two backend families, both selected
by the flow's `state_backend_connector` and a processing engine:

- **Execution backend** (`core/nld/flow/execution/backend/`) — stores
  the execution header, execution state, execution history, and the
  per-step history.
- **Incremental (state) backend**
  (`core/nld/flow/incremental/impl/<strategy>/backend/`) — stores the
  incremental processing state and post-processing state for the flow's
  incremental strategy (`by_key`, `by_source_tst`, `no_increment`), and
  the planned-state slot.

This area documents, per connector, which commands each backend
supports. For the same matrix organised by incremental strategy, see
[`../incremental/`](../incremental/README.md). For the architecture
behind these backends, see
[`../execution-and-incremental-design.md`](../execution-and-incremental-design.md).

## Connectors and engines

A backend is resolved from the connector type plus an engine. The
engine defaults to `pydantic`; `duckdb` is opt-in per side via
`state_backend_connector.<side>.params.engine`:

```yaml
state_backend_connector:
  primary: postgres_metadata          # engine defaults to pydantic
  secondary:
    connector: s3_data_target
    params:
      engine: duckdb                  # opt into the DuckDB engine
```

When no backend is registered for a `(connector, engine)` combination,
the factory raises `Backend '<connector>' with engine '<engine>' is not
available`.

| Connector | Type id | Engines with an execution backend |
|-----------|---------|-----------------------------------|
| [PostgreSQL](./postgresql.md) | `postgresql` | `pydantic` |
| [BigQuery](./bigquery.md) | `bigquery` | `pydantic` |
| [Snowflake](./snowflake.md) | `snowflake` | `pydantic` |
| [DuckDB](./duckdb.md) | `duckdb` | `pydantic` |
| [Local file](./local.md) | `local` | `pydantic`, `duckdb` |
| [S3 blob storage](./s3-blob-storage.md) | `s3_blob_storage` | `pydantic`, `duckdb` |

## Commands

| Command | Backend family | Method(s) exercised |
|---------|----------------|---------------------|
| `nld flow execute` | Execution + incremental | `retrieve_current_state`, `write_processing_state`, `write_post_processing_state` (+ partial variants); `save_execution_info`, `save_step_info`, `save_execution_state`, `save_execution_history_complete` |
| `nld flow state execution get-state` | Execution | `get_latest_execution_info(with_steps=False)` |
| `nld flow state execution get-history` | Execution | `get_execution_history(limit=…)` |
| `nld flow state execution get-steps` | Execution | `get_execution_history(limit=1)` then reads `info.steps` |
| `nld flow state incremental get-state` | Incremental | `get_processing_state`, `get_post_processing_state` |
| `nld flow state incremental compute` | Incremental | `compute_incremental_state` (in memory, via `retrieve_current_state`); `--persist` adds `save_planned_processing_state` → `write_planned_processing_state` |
| `nld flow state incremental get-planned` | Incremental | `get_planned_processing_states` → `read_planned_processing_states` (lists `PLANNED` state plans for the flow, newest first) |

See the `how-to-get-incremental-info` and `how-to-get-execution-info`
skills for the CLI flags and output shapes.

## Legend

The per-connector and per-strategy tables use:

- **✅** — implemented.
- **❌** — raises `NotImplementedError`.
- **`[]`** — the call succeeds but returns an empty result.
- **—** — not applicable; no backend is registered for that
  combination.

## General availability summary

### Execution backend

Header reads (`get-state`, `get-history`) are derived from
`retrieve_latest_execution_state` on the base
`ExecutionBackendStateManager`, so every execution backend supports
them. `get-steps` depends on whether the backend reads step rows back:

| Connector / engine | `get-state` | `get-history` | `get-steps` |
|--------------------|:-----------:|:-------------:|:-----------:|
| `postgresql` / `pydantic` | ✅ | ✅ | ✅ |
| `bigquery` / `pydantic` | ✅ | ✅ | `[]` |
| `snowflake` / `pydantic` | ✅ | ✅ | `[]` |
| `duckdb` / `pydantic` | ✅ | ✅ | `[]` |
| `local` / `pydantic` | ✅ | ✅ | ✅ |
| `local` / `duckdb` | ✅ | ✅ | ✅ |
| `s3_blob_storage` / `pydantic` | ✅ | ✅ | ✅ |
| `s3_blob_storage` / `duckdb` | ✅ | ✅ | ✅ |

PostgreSQL splices step rows from `*_execution_step_history` back into
the read. The other three pydantic-table backends (BigQuery, Snowflake,
DuckDB) store step rows in the same kind of table but do not join them
on read, so `get-steps` returns `[]` while the header reads work. The
file and artifact backends (local, S3) persist steps inline (JSON / a
JSON column) and rehydrate them on read.

### Incremental backend

`compute` (preview) resolves the next run's processing state in memory
from `retrieve_current_state`, so it is available wherever the flow
runs. `get-state` needs the `get_processing_state` /
`get_post_processing_state` accessors, implemented on PostgreSQL only.
`compute --persist` needs the planned-state write surface. `get-planned`
reads the same planned-state slot, so it tracks the `compute --persist`
column exactly.

| Strategy | Connector / engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|--------------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_key` | `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `by_key` | `bigquery` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_key` | `duckdb` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_key` | `local` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_key` | `local` / `duckdb` | ✅ | ❌ | ✅ | ❌ |
| `by_key` | `s3_blob_storage` / `pydantic` | ✅ | ❌ | ✅ | ✅ |
| `by_key` | `s3_blob_storage` / `duckdb` | ✅ | ❌ | ✅ | ✅ |
| `by_source_tst` | `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `by_source_tst` | `bigquery` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `snowflake` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `duckdb` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `local` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `no_increment` | any / `pydantic`, `duckdb` | ✅ (no-op) | ❌ | ✅ (empty) | — |

`by_key` has no Snowflake backend; `by_source_tst` has no S3 backend and
no DuckDB-engine backend. `no_increment` is a connector-agnostic
pass-through: it persists no state, so `get-state` has nothing to read
and there is no planned-state slot.
