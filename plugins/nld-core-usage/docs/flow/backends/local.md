# Local file backend

**Type id**: `local` · **Engines**: `pydantic`, `duckdb`

The local backend persists state as files on the connector's root
path. See the [backends overview](./README.md) for the legend and
command list.

## Execution backend

`local_with_pydantic.py` and `local_with_duckdb.py` under
`core/nld/flow/execution/backend/`.

| Command | `pydantic` | `duckdb` | Notes |
|---------|:----------:|:--------:|-------|
| `nld flow execute` (write path) | ✅ | ✅ | Execution info, state, and history persisted as JSON files. |
| `nld flow state execution get-state` | ✅ | ✅ | |
| `nld flow state execution get-history` | ✅ | ✅ | |
| `nld flow state execution get-steps` | ✅ | ✅ | Steps are stored inline (JSON file / JSON column) and rehydrated on read — `local_with_duckdb` via `_duckdb_row_to_execution_info`. |

## Incremental backend

| Strategy | Engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|--------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_key` | `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_key` | `duckdb` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `pydantic` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `duckdb` | — | — | — | — |
| `no_increment` | `pydantic`, `duckdb` | ✅ (no-op) | ❌ | ✅ (empty) | — |

Backend modules: `impl/by_key/backend/local_with_pydantic.py`,
`impl/by_key/backend/local_with_duckdb.py`,
`impl/by_source_tst/backend/local_with_pydantic.py`.

- **`by_source_tst` / `duckdb`** — no backend is registered; only the
  `pydantic` engine is available for `by_source_tst` on local.
- **Flow execution** — `retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state` are implemented for the registered
  combinations.
- **`get-state`** — the read accessors are not overridden; the base
  raises `NotImplementedError`.
- **`compute`** — resolves the next run's processing state in memory
  from `retrieve_current_state`.
- **`compute --persist`** — no planned-state mixin; the planned-state
  write surface raises `NotImplementedError`.
