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
| `snowflake` / `pydantic` | ✅ | ❌ | ✅ | ❌ |
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
- **`get-state`** — `get_processing_state` /
  `get_post_processing_state` are implemented on PostgreSQL only.
- **`compute --persist`** — available on PostgreSQL only (via
  `PostgreSQLPlannedStateMixin`, tables `_nld_incremental_plans` +
  `_nld_incremental_plans_by_source_tst_planned_state`).
- **`get-planned`** (`nld flow state incremental get-planned`) lists the
  PLANNED plans from the same slot, so it is likewise available on
  PostgreSQL only.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
