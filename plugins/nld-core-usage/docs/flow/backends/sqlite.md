# SQLite backend

**Type id**: `sqlite` · **Engines**: `pydantic`

The `sqlite` connector backs a SQLite database file. SQLite has one
always-attached namespace, so every backend table lives in `main`
whatever schema the connection declares. Timestamps are stored as ISO
8601 UTC text and JSON payloads as text. See the
[backends overview](./README.md) for the legend and command list.

## Execution backend

`core/nld/flow/execution/backend/sqlite_with_pydantic.py`

| Command | Support | Notes |
|---------|:-------:|-------|
| `nld flow execute` (write path) | ✅ | Header, state, history, and step rows in `_nld_execution_*` tables. |
| `nld flow state execution get-state` | ✅ | Base default, derived from `retrieve_latest_execution_state`. |
| `nld flow state execution get-history` | ✅ | Base default. |
| `nld flow state execution get-steps` | ✅ | `_get_steps_for(flow_uid)` reads the step rows from `*_execution_step_history`. |

## Incremental backend

| Strategy | Backend module | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|----------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_source_tst` | `impl/by_source_tst/backend/sqlite_with_pydantic.py` | ✅ | ✅ | ✅ | ✅ |
| `by_key` | — | — | — | — | — |
| `no_increment` | shared pass-through base | ✅ (no-op) | ❌ | ✅ (empty) | — |

- **`by_key`** — no SQLite backend is registered.
- **Flow execution** — `retrieve_current_state`,
  `write_processing_state`, `write_post_processing_state` are
  implemented for `by_source_tst`.
- **`get-state`** — `read_processing_state` and
  `read_post_processing_state` read the live-slot tables
  (`_nld_incremental_by_source_tst_processing_state`,
  `_nld_incremental_by_source_tst_state`).
- **`compute --persist`** and **`get-planned`** —
  `SQLiteIncrementalBackendMixin` persists state plans in
  `_nld_incremental_plans`, with the detailed-state payload in
  `_nld_incremental_plans_by_source_tst_planned_processing_state`, so a
  deploy `reload` directive can leave a PLANNED plan for the next run.
