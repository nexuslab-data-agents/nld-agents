# by_key — backend availability

Per-key incremental type. State models: `ByKeyState`,
`ByKeyProcessingState`. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

## Type rules

Axes: anchor = source · source selection = partial, by key · dimension =
key · change detection = the source key inventory.

| Rule | `by_key` |
|------|----------|
| Params declared | `--full`, `--keys`, `--limit`, `--with-delta` |
| `FULL` | `--full` — every key the inventory presents (re-attempts terminal keys) |
| `DELTA` | no params — inventory keys minus terminal ones (`SUCCEEDED`, `PERMANENTLY_EXCLUDED`) |
| `BACKFILL` | `--keys` and/or `--limit` — exactly that selection, terminal keys included |
| `BACKFILL_DELTA` | `--keys`/`--limit` + `--with-delta` — that selection minus terminal keys |
| Rejected | `--full` + `--with-delta` raises; `BACKFILL` / `BACKFILL_DELTA` without `--keys` or `--limit` is refused |
| State advancement | **all four** strategies merge the run's per-key outcomes into the authoritative state |

Keys are always selected from the **source inventory**: a key present in
the state but absent from the inventory is never processed, not even by
`FULL`. These rules belong to this type alone — see the
[overview](./README.md) for the comparison with `by_source_tst`.

## Availability by connector / engine

| Connector / engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|--------------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `bigquery` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `duckdb` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `local` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `local` / `duckdb` | ✅ | ❌ | ✅ | ❌ |
| `s3_blob_storage` / `pydantic` | ✅ | ❌ | ✅ | ✅ |
| `s3_blob_storage` / `duckdb` | ✅ | ❌ | ✅ | ✅ |
| `snowflake` | — | — | — | — |

Backend modules live under `core/nld/flow/incremental/impl/by_key/backend/`.

## Notes

- **Snowflake** — no `by_key` backend is registered; a `by_key` flow
  cannot use a Snowflake state backend.
- **Flow execution** — implemented on every registered backend
  (`retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state`, plus the partial-state variants for
  immediate per-key persistence).
- **`get-state`** — `get_processing_state` /
  `get_post_processing_state` are implemented on PostgreSQL only.
- **`compute --persist`** — available on PostgreSQL (via
  `PostgreSQLIncrementalBackendMixin`, table `_nld_incremental_plans`
  for state plans + `_nld_incremental_plans_by_key_planned_processing_state`
  for the detailed-state payload) and on S3 (via
  `S3IncrementalBackendMixin`, single index file
  `<state-root>/state_plans.<json|parquet>` for state-plan metadata
  plus per-plan
  `<state-root>/plans/<plan_state_uid>/by_key_planned_processing_state.<json|parquet>`
  for the detailed-state payload). On S3 the planned-state write
  works even though the live-state `get-state` accessors do not.
- **`get-planned`** (`nld flow state incremental get-planned`) lists the
  PLANNED plans from the same slot, so it is available on the same
  backends as `compute --persist` (PostgreSQL and S3).
- **Planned-state freshness** — `by_key` overrides
  `is_planned_processing_state_fresh` to return `True` for every plan:
  a plan may legitimately re-request a key that a later run already
  processed, so the baseline state cannot make a key plan stale. This
  makes `--planned-state-policy auto` behave like `trust` for
  `by_key`.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
