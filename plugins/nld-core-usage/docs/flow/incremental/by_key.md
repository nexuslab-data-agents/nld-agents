# by_key — backend availability

Per-key incremental strategy. State models: `ByKeyState`,
`ByKeyProcessingState`. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

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
  `PostgreSQLPlannedStateMixin`, tables `_nld_incremental_plans` +
  `_nld_incremental_plans_by_key_planned_state`) and on S3 (via
  `S3PlannedStateMixin`, one folder per plan under
  `<state-root>/plans/<plan_state_uid>/`). On S3 the planned-state
  write works even though the live-state `get-state` accessors do not.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
