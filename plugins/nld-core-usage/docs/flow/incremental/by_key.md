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
  `PostgreSQLIncrementalBackendMixin`, table `_nld_incremental_plans`
  for state plans + `_nld_incremental_plans_by_key_planned_state` for
  the processing-state payload) and on S3 (via
  `S3IncrementalBackendMixin`, one folder per plan under
  `<state-root>/plans/<plan_state_uid>/` with `state_plan.json` +
  `by_key_planned_state.json`). On S3 the planned-state write works
  even though the live-state `get-state` accessors do not.
- **`get-planned`** (`nld flow state incremental get-planned`) lists the
  PLANNED plans from the same slot, so it is available on the same
  backends as `compute --persist` (PostgreSQL and S3).

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
