# Incremental backend availability

This area summarises, per incremental type, which connectors and
engines back it and which commands each combination supports. It is the
strategy-oriented view of the same data presented connector-by-connector
in [`../backends/`](../backends/README.md).

For the incremental architecture (state classes, processing lifecycle,
factory, planned-state slot), see
[`../execution-and-incremental-design.md`](../execution-and-incremental-design.md).

## Types

| Type | Summary | Detail |
|----------|---------|--------|
| `by_key` | Per-key state and processing decisions. | [by_key.md](./by_key.md) |
| `by_source_tst` | Timestamp-window watermark state. | [by_source_tst.md](./by_source_tst.md) |
| `no_increment` | Pass-through; persists no incremental state. | [no_increment.md](./no_increment.md) |

## Command axes

Each strategy page reports availability against four axes:

- **Flow execution** — `retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state` (used by `nld flow execute`).
- **`get-state`** — `get_processing_state` / `get_post_processing_state`
  (used by `nld flow state incremental get-state`).
- **`compute`** — `nld flow state incremental compute` without
  `--persist`; resolves the next run's processing state in memory from
  `retrieve_current_state`, so it is available wherever the flow runs.
- **`compute --persist`** — adds a planned-state write
  (`write_planned_processing_state`); requires
  `supports_planned_state=True` on both the strategy
  (`FlowIncrementalDefinition`) and the primary backend
  (`IncrementalBackendStateManager`). When either layer is off the
  CLI returns `persisted=False` instead of attempting the write.
  `nld flow state incremental get-planned` (list PLANNED plans) and
  `nld flow execute --state-compute-only` / `--planned-state-policy`
  consume the same slot, so they share availability with
  `compute --persist`.

## Legend

- **✅** — implemented.
- **❌** — raises `NotImplementedError`.
- **—** — not applicable; no backend registered for that combination.

## At a glance

| Type | Connectors with a backend | `get-state` | `compute --persist` |
|----------|---------------------------|-------------|---------------------|
| `by_key` | postgresql, bigquery, duckdb, local, s3_blob_storage | postgresql only | postgresql, s3_blob_storage |
| `by_source_tst` | postgresql, bigquery, snowflake, duckdb, local | postgresql, snowflake | postgresql, snowflake |
| `no_increment` | any (pass-through) | — | — |

`read_processing_state` / `read_post_processing_state` back `get-state`. For
`by_source_tst` they are implemented on PostgreSQL and Snowflake; on the
remaining connectors `get-state` raises `NotImplementedError`, while
`compute` (preview) still works because it reads through
`retrieve_current_state`.
