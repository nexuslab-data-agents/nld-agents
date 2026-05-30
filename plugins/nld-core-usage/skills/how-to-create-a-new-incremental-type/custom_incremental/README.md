# `custom_incremental/` — Reference Implementation

A `by_source_tst` variant exposing a `--days-from N` runtime parameter
that floors the next pull's lower bound at `now - N days`.

Reference for the `how-to-create-a-new-incremental-type` skill — see
that SKILL.md for context, authoring steps, and how to register the
type from `nld_project.yml`.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | re-exports |
| `logic.py` | `FlowIncrementalDefinition`, params class with `days_from`, top-level `FlowIncrementalLogic` |
| `state.py` | `State` / `SourceState` / `ProcessingState` pydantic models |
| `manager.py` | `IncrementalStateManager` subclass — floors `pull_from_timestamp` using `days_from` |
| `sql_filter_manager.py` | timestamp-range SQL filter |
| `backend/__init__.py` | marker |
| `backend/base_with_pydantic.py` | abstract `IncrementalBackendStateManager` subclass |
| `backend/postgresql_with_pydantic.py` | PostgreSQL backend |
| `nld_project_snippet.yml` | copy-pasteable registration entry |

## Floor semantics

`days_from` is honoured when the persisted watermark is younger than
`now - days_from`, or when no watermark exists. A watermark older than
`now - days_from` is preserved (the run pulls more, never less). The
floor only affects `FlowLoadingStrategies.DELTA` runs; `FULL`,
`BACKFILL`, and `BACKFILL_DELTA` keep their existing semantics.
