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
  mixes in `S3IncrementalBackendMixin`, which persists all state-plan
  metadata for the flow in a single index file at
  `<state-root>/state_plans.<json|parquet>`, keyed by
  `plan_state_uid`. `read_state_plan` / `read_state_plans` resolve to
  one S3 GET regardless of plan-history length;
  `write_state_plan` is a single read-modify-write on the index, and
  the mixin assumes a single writer per flow. The per-strategy backend
  writes the detailed-state payload as a per-plan file under
  `<state-root>/plans/<plan_state_uid>/by_key_planned_processing_state.<json|parquet>`.
  `file_format` on the connector's `params` controls both file
  extensions: `json` writes the full Pydantic envelope; `parquet`
  writes rows against `get_state_plans_index_schema()` /
  `get_by_key_processing_state_schema()` with the envelope `flow_uid`
  / `strategy` carried in PyArrow schema metadata. The plan lifecycle
  (cancel-on-supersede, COMPLETED / CANCELLED transitions) lives on
  `IncrementalStateManager`. See
  `../execution-and-incremental-design.md` §4.5.
