# by_key — backend availability

Per-key incremental type. State models: `ByKeyState`,
`ByKeyProcessingState`. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

## Type rules

Axes: anchor = source · source selection = partial, by key · dimension =
key · change detection = the source key inventory, plus the per-key source
update timestamp when the source reports one.

| Rule | `by_key` |
|------|----------|
| Params declared | `--full`, `--keys`, `--limit`, `--with-delta` |
| `FULL` | `--full` — every key the inventory presents (re-attempts terminal keys) |
| `DELTA` | no params — inventory keys minus terminal ones (`SUCCEEDED`, `PERMANENTLY_EXCLUDED`), except the `SUCCEEDED` keys the source updated since their last success |
| `BACKFILL` | `--keys` and/or `--limit` — exactly that selection, terminal keys included |
| `BACKFILL_DELTA` | `--keys`/`--limit` + `--with-delta` — that selection minus terminal keys, with the same exception for updated `SUCCEEDED` keys |
| Rejected | `--full` + `--with-delta` raises; `BACKFILL` / `BACKFILL_DELTA` without `--keys` or `--limit` is refused |
| State advancement | **all four** strategies merge the run's per-key outcomes into the authoritative state |
| Options | `incremental.options.reprocess_updated_keys` (default `true`) |

Keys are always selected from the **source inventory**: a key present in
the state but absent from the inventory is never processed, not even by
`FULL`. These rules belong to this type alone — see the
[overview](./README.md) for the comparison with `by_source_tst`.

## Source updates

A key that succeeded is selected again by `DELTA` and `BACKFILL_DELTA`
when the source reports it changed since. The flow task fills
`ByKeySingleKeySourceState.last_updated_at` in `retrieve_source_state`
(e.g. Steam's `GetAppList` `last_modified`), and the comparison runs per
key:

- the reference is `ByKeySingleKeyState.source_last_updated_at`, the
  source timestamp the last successful run saw — source clock against
  source clock;
- a key processed before that field existed has none: it compares with
  its `last_successfully_processed_at` until its next success stores one;
- a key re-selects only when the source timestamp is **strictly** later;
  a NULL source timestamp never re-selects;
- `PERMANENTLY_EXCLUDED` keys stay terminal (only `FULL` or `--keys`
  brings them back), and `FAILED` keys are retried as before;
- a failed re-attempt keeps the stored timestamp, so the key is selected
  again on the next run.

The timestamp travels with the processing state and the planned detail,
so a run executed from a precomputed plan stores it too. It is on by
default; a flow whose source timestamps must not trigger re-processing
opts out:

```yaml
incremental:
  type: by_key
  options:
    reprocess_updated_keys: false
```

Re-selection can multiply the work of one run (the first run after a
source starts reporting timestamps re-selects every key updated since its
fetch). A task with a per-run budget caps `get_keys_to_process()` itself
and excludes the rest: excluded keys keep their state and are selected
again by the next `DELTA`.

## Availability by connector / engine

| Connector / engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|--------------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `bigquery` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `duckdb` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `local` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `local` / `duckdb` | ✅ | ❌ | ✅ | ❌ |
| `s3_blob_storage` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `s3_blob_storage` / `duckdb` | ✅ | ✅ | ✅ | ✅ |
| `snowflake` / `pydantic` | ✅ | ✅ | ✅ | ✅ |

Backend modules live under `core/nld/flow/incremental/impl/by_key/backend/`.

## Notes

- **Flow execution** — implemented on every registered backend
  (`retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state`, plus the partial-state variants for
  immediate per-key persistence).
- **`get-state`** — `read_processing_state` /
  `read_post_processing_state` are implemented on PostgreSQL, Snowflake
  and S3 blob storage (the latest run's
  `<s3_root_path>/<run timestamp>/state/key_processed_state.<ext>` and
  `<s3_root_path>/state/key_state.<ext>`).
- **Snowflake** — `SnowflakeByKeyStateBackendManager`
  (`impl/by_key/backend/snowflake_with_pydantic.py`) covers the full
  lifecycle: state rows in `_nld_incremental_by_key_state`, the
  processing slot in `_nld_incremental_by_key_processing_state`, and
  planned states via `SnowflakeIncrementalBackendMixin`
  (`_nld_incremental_plans` +
  `_nld_incremental_plans_by_key_planned_processing_state`).
- **`compute --persist`** — available on PostgreSQL (via
  `PostgreSQLIncrementalBackendMixin`, table `_nld_incremental_plans`
  for state plans + `_nld_incremental_plans_by_key_planned_processing_state`
  for the detailed-state payload), on Snowflake (see above), and on S3 (via
  `S3IncrementalBackendMixin`, single index file
  `<state-root>/state_plans.<json|parquet>` for state-plan metadata
  plus per-plan
  `<state-root>/plans/<plan_state_uid>/by_key_planned_processing_state.<json|parquet>`
  for the detailed-state payload).
- **`get-planned`** (`nld flow state incremental get-planned`) lists the
  PLANNED plans from the same slot, so it is available on the same
  backends as `compute --persist` (PostgreSQL, Snowflake and S3).
- **SQLite** — no `by_key` backend is registered.
- **Schema upgrades are manual** — the SQL backends create their tables
  when missing but never alter an existing one. A table created by an
  older version needs the new column added before the upgraded flows run,
  e.g. `ALTER TABLE <schema>._nld_incremental_by_key_state ADD COLUMN
  source_last_updated_at TIMESTAMPTZ` on each by_key table (DuckDB: drop
  the processing table index first, it refuses to alter an indexed
  table). Parquet and JSON state files need nothing: a missing column
  reads as NULL.
- **Planned-state freshness** — `by_key` overrides
  `is_planned_processing_state_fresh` to return `True` for every plan:
  a plan may legitimately re-request a key that a later run already
  processed, so the baseline state cannot make a key plan stale. This
  makes `--planned-state-policy auto` behave like `trust` for
  `by_key`.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
