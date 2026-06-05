# Snowflake backend

**Type id**: `snowflake` · **Engines**: `pydantic`

See the [backends overview](./README.md) for the legend and command
list.

## Execution backend

`core/nld/flow/execution/backend/snowflake_with_pydantic.py`

| Command | Support | Notes |
|---------|:-------:|-------|
| `nld flow execute` (write path) | ✅ | Header, state, history, and step rows persisted. |
| `nld flow state execution get-state` | ✅ | Base default, derived from `retrieve_latest_execution_state`. |
| `nld flow state execution get-history` | ✅ | Base default. |
| `nld flow state execution get-steps` | `[]` | Step rows live in `*_execution_step_history` but are not joined on read, so the header reads back without steps. |

## Incremental backend

| Strategy | Backend module | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|----------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_source_tst` | `impl/by_source_tst/backend/snowflake_with_pydantic.py` | ✅ | ✅ | ✅ | ✅ |
| `by_key` | — | — | — | — | — |
| `no_increment` | shared pass-through base | ✅ (no-op) | ❌ | ✅ (empty) | — |

- **`by_key`** — no Snowflake backend is registered. A `by_key` flow
  cannot use a Snowflake state backend.
- **Flow execution** (`by_source_tst`) — `retrieve_current_state`,
  `write_processing_state`, `write_post_processing_state` are
  implemented.
- **`get-state`** (`by_source_tst`) — `read_processing_state` and
  `read_post_processing_state` read the live-slot tables.
- **`compute`** — resolves the next run's processing state in memory
  from `retrieve_current_state`.
- **`compute --persist`** (`by_source_tst`) — `SnowflakeIncrementalBackendMixin`
  persists state plans in `_nld_incremental_plans`, with the
  processing-state payload in
  `_nld_incremental_plans_by_source_tst_planned_processing_state`.
  `get-planned` lists the PLANNED plans from the same slot.
