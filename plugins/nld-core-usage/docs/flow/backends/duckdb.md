# DuckDB backend

**Type id**: `duckdb` · **Engines**: `pydantic`

The `duckdb` connector backs a DuckDB database file. It is distinct
from the **DuckDB engine** (`engine: duckdb`), which is a query engine
some connectors (local, S3) offer on top of their own storage. See the
[backends overview](./README.md) for the legend and command list.

## Execution backend

`core/nld/flow/execution/backend/duckdb_with_pydantic.py`

| Command | Support | Notes |
|---------|:-------:|-------|
| `nld flow execute` (write path) | ✅ | Header, state, history, and step rows persisted. |
| `nld flow state execution get-state` | ✅ | Base default, derived from `retrieve_latest_execution_state`. |
| `nld flow state execution get-history` | ✅ | Base default. |
| `nld flow state execution get-steps` | `[]` | Step rows live in `*_execution_step_history` but are not joined on read, so the header reads back without steps. |

## Incremental backend

| Strategy | Backend module | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|----------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_key` | `impl/by_key/backend/duckdb_with_pydantic.py` | ✅ | ❌ | ✅ | ❌ |
| `by_source_tst` | `impl/by_source_tst/backend/duckdb_with_pydantic.py` | ✅ | ❌ | ✅ | ❌ |
| `no_increment` | shared pass-through base | ✅ (no-op) | ❌ | ✅ (empty) | — |

- **Flow execution** — `retrieve_current_state`, `write_processing_state`,
  `write_post_processing_state` are implemented for both strategies.
- **`get-state`** — the read accessors are not overridden; the base
  raises `NotImplementedError`.
- **`compute`** — resolves the next run's processing state in memory
  from `retrieve_current_state`.
- **`compute --persist`** — no planned-state mixin; the planned-state
  write surface raises `NotImplementedError`.
