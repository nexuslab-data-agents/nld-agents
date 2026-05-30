# S3 blob storage backend

**Type id**: `s3_blob_storage` · **Engines**: `pydantic`, `duckdb`

The S3 backend persists state as artifacts on the connector's root
path (`s3_root_path`, derived from the flow's `S3Structure` target).
See the [backends overview](./README.md) for the legend and command
list.

## Execution backend

`s3_blob_storage_with_pydantic.py` and `s3_blob_storage_with_duckdb.py`
under `core/nld/flow/execution/backend/` (shared base
`s3_blob_storage_base.py`).

| Command | `pydantic` | `duckdb` | Notes |
|---------|:----------:|:--------:|-------|
| `nld flow execute` (write path) | ✅ | ✅ | Execution artifacts written under the state root. |
| `nld flow state execution get-state` | ✅ | ✅ | |
| `nld flow state execution get-history` | ✅ | ✅ | |
| `nld flow state execution get-steps` | ✅ | ✅ | Steps are serialized inline (parquet JSON column / inline JSON) and rehydrated — `_read_execution_info_from_parquet_row` / `_duckdb_row_to_execution_info`. |

## Incremental backend

| Strategy | Engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|----------|--------|:--------------:|:-----------:|:---------:|:-------------------:|
| `by_key` | `pydantic` | ✅ | ❌ | ✅ | ✅ |
| `by_key` | `duckdb` | ✅ | ❌ | ✅ | ✅ |
| `by_source_tst` | `pydantic`, `duckdb` | — | — | — | — |
| `no_increment` | `pydantic`, `duckdb` | ✅ (no-op) | ❌ | ✅ (empty) | — |

Backend modules: `impl/by_key/backend/s3_blob_storage_base.py`,
`s3_blob_storage_with_pydantic.py`, `s3_blob_storage_with_duckdb.py`.

- **`by_source_tst`** — no S3 backend is registered for this strategy.
- **Flow execution** (`by_key`) — `retrieve_current_state`,
  `write_processing_state`, `write_post_processing_state` are
  implemented for both engines.
- **`get-state`** — the read accessors are not overridden; the base
  raises `NotImplementedError`. The persisted-plan slot is writable on
  S3 even though the live-state read accessors are not — `compute
  --persist` and `get-state` are independent.
- **`compute`** — resolves the next run's processing state in memory
  from `retrieve_current_state`.
- **`compute --persist`** and **`get-planned`** — the `by_key` S3 base
  mixes in `S3IncrementalBackendMixin`, which provides the state-plan
  persistence for the planned-state slot: one plan folder per
  `plan_state_uid` under `<state-root>/plans/<plan_state_uid>/`, with
  the state plan written to `state_plan.json`. The per-strategy backend
  writes the processing-state payload as a sibling file in the same
  folder (`by_key_planned_state.json`). The plan lifecycle
  (cancel-on-supersede, COMPLETED / CANCELLED transitions) lives on
  `IncrementalStateManager`. See
  `../execution-and-incremental-design.md` §4.5.
