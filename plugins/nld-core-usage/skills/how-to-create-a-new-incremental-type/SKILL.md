---
name: how-to-create-a-new-incremental-type
description: Author a new external incremental type for nld-core and register it from `nld_project.yml`. Walks through the four runtime surfaces (logic, state-manager, state models, backend) the `FlowIncrementalTypeRegistry` requires, and points at a complete `custom_incremental/` reference implementation that extends by_source_tst with a `--days-from` backfill parameter.
user-invocable: false
---

# How To: Create a New Incremental Type

`nld-core` resolves an incremental type at runtime by looking up its
`FlowIncrementalTypeManifest` in `FlowIncrementalTypeRegistry`. Built-in
types (`by_key`, `by_source_tst`, `no_increment`) live under
`nld.flow.incremental.impl/`; external types live in any importable
package and are registered through `additional_incremental_types` in
`nld_project.yml`. There are no other extension points.

## When to Use

Activate this skill when authoring or reviewing an incremental type that
does not ship with nld-core — e.g. a partition-based type, a CDC-stream
type, or a `by_source_tst` variant that adds custom parameters. For
configuring an existing built-in, see
`how-to-determine-incremental-strategy`.

## The Four Required Surfaces

A registered incremental type points at four importable artefacts. The
registry holds only their dotted paths; the factory imports them on first
use.

| Surface | What it is | Field on `FlowIncrementalTypeManifest` |
|---------|-----------|----------------------------------------|
| **Logic** | A module-level `FlowIncrementalLogic[ParamsCls]` instance, paired with a `FlowIncrementalDefinition` and a `FlowIncrementalParams` subclass that lists every CLI-visible parameter in `param_definitions`. | `logic_module` |
| **State manager** | A subclass of `IncrementalStateManager` parameterised by your three state classes and your params class. Owns `init_processing_state`, `update_processing_state`, `create_post_processing_state`, and the `sql_filter_manager` property. | `state_manager_module` |
| **State models** | Three pydantic models — `FlowState`, `FlowSourceState`, `FlowProcessingState` subclasses — declared in the logic and state-manager generics. Carry the persisted watermark, the per-run source snapshot, and the per-run processing record. The `FlowState` and `FlowProcessingState` subclasses each implement the abstract `render_state_text()` so `nld flow state incremental get-state` can render them; the `FlowProcessingState` subclass also implements `get_display_log()` (and overrides `get_pull_timestamps()` for timestamp strategies). | (imported by `logic_module` and `state_manager_module`) |
| **Backend package** | A package containing one module per `(backend_type, engine)` pair the type supports. Each module subclasses `IncrementalBackendStateManager[Connector, State, SourceState, ProcessingState]`. The base subclass goes in the file named by the template with `base` as the backend type — `base_with_{engine}.py` by default. | `backend_package` |

The optional `backend_module_template` controls the per-backend filename
pattern (defaults to `{backend_type}_with_{engine}`). `fallback_to_base_backend`
(defaults to `True`) lets the factory fall back to the `base_*` module
when no per-backend file exists for the requested pair.

## Reference Implementation: `by_source_tst_with_days_from`

The folder `custom_incremental/` in this skill contains a complete,
nld-project-free example: a `by_source_tst` variant that exposes a
`--days-from N` runtime parameter for floor-style backfills.

Behaviour: `--days-from N` floors the effective lower bound of the next
pull at `now - N days`. If the persisted watermark is already older than
`now - N days`, the watermark is honoured (it pulls more, never less);
if the watermark is younger or absent, the floor wins and the run
backfills the last `N` days.

| File under `custom_incremental/` | Maps to |
|----------------------------------|---------|
| `logic.py` | `logic_module` — defines `BY_SOURCE_TST_WITH_DAYS_FROM_FLOW_INCREMENTAL_LOGIC`, the `FlowIncrementalDefinition`, and a `FlowIncrementalParams` subclass declaring `days_from: int \| None`. |
| `state.py` | three state models (`State`, `SourceState`, `ProcessingState`) — same shape as `by_source_tst` because the persisted watermark is unchanged. |
| `manager.py` | `state_manager_module` — `IncrementalStateManager` subclass. Reads `incremental_parameters.days_from` inside `update_processing_state` and floors `pull_from_timestamp` at `now - days_from`. |
| `sql_filter_manager.py` | timestamp-range filter, reused without modification. |
| `backend/__init__.py` | empty marker. |
| `backend/base_with_pydantic.py` | abstract `IncrementalBackendStateManager` subclass typed on the three state models. |
| `backend/postgresql_with_pydantic.py` | concrete PostgreSQL backend persisting state + processing-state rows via the `Psycopg2SQLConnector` `pydantic_manager`. |
| `nld_project_snippet.yml` | copy-pasteable `additional_incremental_types:` entry. |

Other backends (BigQuery, Snowflake, DuckDB, S3-blob-storage) follow the
same pattern as `postgresql_with_pydantic.py`: subclass the matching
`PostgreSQLBackendMixin`/`BigQueryBackendMixin`/etc. and override the
schema/table accessors. The example ships only `base` and `postgresql`
to keep the reference small; consult the built-in
`nld.flow.incremental.impl.by_source_tst.backend` package when a real
deployment needs the others.

## Authoring Steps

1. **Pick a name.** `^[a-z][a-z0-9_]*$` is the convention. It must not
   collide with a built-in or another external type; the registry raises
   on duplicate registration.

2. **Implement the four surfaces.** Use the `custom_incremental/`
   files as a template. Keep CLI-visible parameters in
   `FlowIncrementalParamDefinition` instances on the definition; the
   executor filters task parameters by
   `DataFlowDefinition.get_init_params_keys()`, which sources those
   names from the resolved logic. A parameter missing from
   `param_definitions` is silently dropped at runtime. Implement
   `render_state_text()` on both the `FlowState` and the
   `FlowProcessingState` subclass — it is abstract, so a missing
   implementation fails at instantiation, and it is what `nld flow
   state incremental get-state` prints for the type; keep any
   strategy-specific rendering helpers in the type's own `state.py`.

3. **Decide on planned-state support.** `FlowIncrementalDefinition.supports_planned_state`
   defaults to `False`. Set it `True` on the definition when the
   strategy can produce a `PLANNED` processing state that a later run
   adopts via `nld flow execute --planned-state-strategy`, and override
   `IncrementalStateManager.is_planned_processing_state_fresh` on the
   state manager when a baseline can supersede an earlier plan (the
   base returns `True`; `by_source_tst` checks DELTA /
   BACKFILL_DELTA window invariants against the persisted watermark,
   `by_key` keeps every plan fresh). Backends inherit the
   `supports_planned_state=True` from `PostgreSQLIncrementalBackendMixin`
   and `S3IncrementalBackendMixin`; a custom backend mixin must set
   the `ClassVar` itself to be plan-capable. The `nld flow state
   incremental compute --persist`, `nld flow execute
   --state-compute-only`, and `nld flow state incremental get-planned`
   commands gate on the AND of the strategy and backend layers.

4. **Wire the backend.** Place at minimum `base_with_<engine>.py`
   (abstract) plus one concrete `<backend_type>_with_<engine>.py` per
   supported pair. Each concrete subclass overrides
   `retrieve_current_state`, `get_processing_state`,
   `get_post_processing_state`, `write_processing_state`, and
   `write_post_processing_state`. Backend subclasses may also override
   the classmethod `determine_parameters_for_flow_definition(
   data_flow_definition)` to derive backend parameters from the typed
   flow context (target structure, predecessors, …); the default
   returns `{}`. The S3 mixin uses this hook to derive `s3_root_path`
   from `S3Structure`, and the override is shared by execution and
   incremental S3 backends.

5. **Register in `nld_project.yml`.**

   ```yaml
   additional_incremental_types:
     - name: by_source_tst_with_days_from
       logic_module: custom_incremental.logic
       state_manager_module: custom_incremental.manager
       backend_package: custom_incremental.backend
   ```

   `Project.from_dict` validates each entry into a
   `FlowIncrementalTypeManifest` (rejecting empty names, undotted module
   paths, and templates missing `{backend_type}` or `{engine}`) and
   registers it. A duplicate name raises `NldProjectError`.

6. **Verify registration.**

   ```bash
   nld project info
   ```

   The output lists registered incremental types under
   `additional_incremental_types`. The factory accepts the new name in
   any flow definition's `incremental.type:` field once the registration
   succeeds.

7. **Smoke test.** Point a flow's `incremental.type` at the new name,
   run it with `nld flow run`, and inspect `nld flow state incremental
   get-state` to confirm the persisted watermark advances as expected.

## Constraints

- The four surfaces must be importable from the python paths declared in
  the manifest. `Project` only validates that the paths are dotted; the
  factory imports them on first use, and an `ImportError` there surfaces
  as a `IncrementalStateManagerImportError` at flow runtime.
- The registry is a process-wide singleton. Tests that register a
  temporary type must `unregister(name)` in teardown.
- External types are available only in contexts that load `Project`
  (the same constraint applies to `additional_entities`). Standalone
  scripts that bypass `Project` will not see them.

## Cross-References

- `guide-incremental` — the registry, factory, and module layout this
  skill plugs into.
- `how-to-determine-incremental-strategy` — picking a built-in instead
  of authoring one.
- `nld.flow.incremental.impl.by_source_tst.*` in nld-core — the canonical
  built-in this example extends.
