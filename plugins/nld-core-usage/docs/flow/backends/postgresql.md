# PostgreSQL backend

**Type id**: `postgresql` · **Engines**: `pydantic`

PostgreSQL is the reference backend: every read and write surface is
implemented for both backend families. See the
[backends overview](./README.md) for the legend and command list.

## Execution backend

`core/nld/flow/execution/backend/postgresql_with_pydantic.py`

| Command | Support | Notes |
|---------|:-------:|-------|
| `nld flow execute` (write path) | ✅ | Header, state, history, and step rows in `_nld_execution_*` tables. |
| `nld flow state execution get-state` | ✅ | |
| `nld flow state execution get-history` | ✅ | |
| `nld flow state execution get-steps` | ✅ | Overrides `get_latest_execution_info` / `get_execution_history` to splice rows from `*_execution_step_history` via `_get_steps_for(flow_uid)`. |

## Incremental backend

| Strategy | Backend module | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|----------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_key` | `impl/by_key/backend/postgresql_with_pydantic.py` | ✅ | ✅ | ✅ | ✅ |
| `by_source_tst` | `impl/by_source_tst/backend/postgresql_with_pydantic.py` | ✅ | ✅ | ✅ | ✅ |
| `no_increment` | shared pass-through base | ✅ (no-op) | ❌ | ✅ (empty) | — |

- **Flow execution** — `retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state` (plus partial variants for `by_key`).
- **`get-state`** — `get_processing_state` and `get_post_processing_state`
  read the live processing-state / post-processing-state tables.
- **`compute --persist`** and **`get-planned`** — both strategies mix
  in `PostgreSQLIncrementalBackendMixin`, which provides the state-plan
  persistence for the planned-state slot: the shared table
  `_nld_incremental_plans` (one row per state plan via
  `BackendStatePlanRow`). Each per-strategy backend also creates and
  owns its processing-state table
  (`_nld_incremental_plans_<strategy>_planned_state`). The plan
  lifecycle (cancel-on-supersede, COMPLETED / CANCELLED transitions)
  lives on `IncrementalStateManager` (see
  `../execution-and-incremental-design.md` §4.5).
