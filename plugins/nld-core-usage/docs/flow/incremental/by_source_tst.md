# by_source_tst — backend availability

Timestamp-window incremental type. State models: `BySourceTstState`
(holds `last_pull_to_timestamp`), `BySourceTstProcessingState`. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

## Type rules

Axes: anchor = source · source selection = partial, by extraction
timestamp · dimension = time window · change detection = the technical
extraction timestamp.

| Rule | `by_source_tst` |
|------|-----------------|
| Params declared | `--full`, `--pull-from`, `--pull-to`, `--with-delta` (**never read**) |
| `FULL` | `--full` — window `[None, now]`, the filter drops the lower bound |
| `DELTA` | no params — `[watermark, now]` |
| `BACKFILL` | `--pull-from` **and** `--pull-to` — that fixed window |
| `BACKFILL_DELTA` | `--pull-from` alone — `[from, now]` |
| Ignored | `--pull-from` / `--pull-to` under `FULL` / `DELTA` (logged as `IncrementalParameterIgnored`); `--with-delta` always |
| State advancement | `FULL`, `DELTA`, `BACKFILL_DELTA` advance `last_pull_to_timestamp`; **`BACKFILL` does not** |

Two rules are specific to this type and do not generalise:

- Replaying an explicit `[pull_from, pull_to]` window deliberately leaves
  the watermark untouched (`by_key` records replayed keys instead).
- `--full` combined with `--with-delta` is accepted here and has no
  effect; on `by_key` the same combination raises.

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
  every plan as fresh. `--planned-state-policy strict` raises
  `StalePlannedStateException` when the check fails.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
