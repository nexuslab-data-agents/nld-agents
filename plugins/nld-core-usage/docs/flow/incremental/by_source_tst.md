# by_source_tst — backend availability

Timestamp-window incremental strategy. State models: `BySourceTstState`
(holds `last_pull_to_timestamp`), `BySourceTstProcessingState`. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

## Availability by connector / engine

| Connector / engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|--------------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `bigquery` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `snowflake` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `duckdb` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `local` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `s3_blob_storage` | — | — | — | — |

All registered `by_source_tst` backends use the `pydantic` engine.
Backend modules live under
`core/nld/flow/incremental/impl/by_source_tst/backend/`.

## Notes

- **S3 blob storage** — no `by_source_tst` backend is registered.
- **`by_source_tst` does not retrieve source state**
  (`requires_source_state_retrieval` is `False`), so `compute` does not
  prompt for source authorization — it resolves the watermark window
  from the persisted state alone.
- **Flow execution** — implemented on every registered backend.
- **`get-state`** — `read_processing_state` /
  `read_post_processing_state` are implemented on PostgreSQL and Snowflake.
- **`compute --persist`** — available on PostgreSQL and Snowflake (via
  `PostgreSQLIncrementalBackendMixin` / `SnowflakeIncrementalBackendMixin`,
  table `_nld_incremental_plans` for state plans +
  `_nld_incremental_plans_by_source_tst_planned_processing_state` for the
  detailed-state payload).
- **`get-planned`** (`nld flow state incremental get-planned`) lists the
  PLANNED plans from the same slot, so it is available on PostgreSQL and
  Snowflake.
- **Planned-state freshness** — `by_source_tst` overrides
  `is_planned_processing_state_fresh`. `BACKFILL` and `FULL` plans
  (explicit windows) are always fresh. `BACKFILL_DELTA` plans are
  fresh only when `status_changed_at > last_pull_to_timestamp`. `DELTA`
  plans require that condition *and* equality between the plan's
  `pull_from_timestamp` and the baseline watermark, because DELTA
  derives its window from it. A `None` baseline (first run) treats
  every plan as fresh. `--planned-state-strategy strict` raises
  `StalePlannedStateException` when the check fails.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
