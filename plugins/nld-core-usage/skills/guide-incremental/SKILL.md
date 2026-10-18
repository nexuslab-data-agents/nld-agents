---
name: guide-incremental
description: >
  Architectural guide for the nld-core incremental processing system — built-in
  by_key, by_source_tst, by_target_period, and no_increment types under `impl/`,
  the typed per-type `incremental.options`, the
  FlowIncrementalTypeRegistry plugin point, the `flow.additional_incremental_types`
  project YAML hook, state management, execution logging, processing lifecycle,
  and backend implementations.
user-invocable: false
---

# Guide: Incremental Processing & Execution

Architectural reference for the nld-core incremental processing module —
loading strategies, state management, execution logging, and the processing
lifecycle.

## When to Use

Activate this guide when the agent is working on:
- Incremental processing code in `nld/flow/incremental/` — including the
  built-in types under
  `nld/flow/incremental/impl/{by_key,by_source_tst,by_target_period,no_increment}/`
- Execution logging in `nld/flow/execution/`
- State management in `nld/flow/state/`
- IncrementalConfig, ProcessingState, or ExecutionLog classes
- Backend implementations for incremental/execution/state modules
- Choosing or configuring an incremental type for a flow
- Registering an external incremental type via
  `flow.additional_incremental_types` in `nld_project.yml`

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/flow/execution-and-incremental-design.md`.

Backend support matrices (which connector/engine supports which command
for execution and incremental state) live at
`${CLAUDE_PLUGIN_ROOT}/docs/flow/backends/` (connector-by-connector) and
`${CLAUDE_PLUGIN_ROOT}/docs/flow/incremental/` (strategy-by-strategy).
Consult them when asked whether a backend supports `get-state`,
`get-steps`, or `compute --persist`.

### Key Sections (long — read by section, not in full)

| Task | Section |
|------|---------|
| High-level architecture overview | "1. Overview", "1.1 Architecture Diagram" |
| Engine architecture and flow workflow | "1.2 Engine Architecture", "1.3 Flow Execution Workflow" |
| Understanding incremental types | "2.5 Incremental Types" (by_key, by_source_tst, no_increment) |
| Key classes and state hierarchy | "2.2 Key Classes", "2.3 State Classes Hierarchy" |
| Loading strategies | "2.4 Loading Strategies" |
| Step activation flags | "2.5.4 Step Activation Flags" |
| Factory pattern for incremental | "2.6 Factory Pattern" |
| Backend implementations | "2.7 Backend and Engine Implementations" |
| Execution logging | "3. Execution Logging Module" |
| State management | "4. State Management Module" |
| Dual state backend (primary + optional secondary mirror) | "4.4 Dual State Backend (Primary + Optional Secondary)" |
| Full processing lifecycle | "5. Processing Lifecycle" (Phases 1-5) |
| Using incremental in DataFlowTask | "6. Usage in DataFlowTask" |
| File reference | "7. File Reference" |

## Critical Rules

### Loading-strategy rules belong to the incremental type, never to the framework

`FULL` / `DELTA` / `BACKFILL` / `BACKFILL_DELTA` are a shared vocabulary,
not a shared contract. Each type owns three rules — its parameter
grammar (`resolve_strategy()`), what each strategy selects, and which
strategies advance the persisted state — and the built-ins deliberately
differ:

| Rule | `by_key` | `by_source_tst` | `by_target_period` |
|------|----------|-----------------|--------------------|
| `BACKFILL` from | `--keys` / `--limit` | `--pull-from` **and** `--pull-to` | `--periods` / `--period-from [--period-to]` |
| `BACKFILL_DELTA` from | `--keys`/`--limit` + `--with-delta` | `--pull-from` alone | period params + `--with-delta` |
| `--full` + `--with-delta` | raises `ValueError` | accepted, no effect (`--with-delta` is declared but never read) | raises `ValueError` |
| State advanced by | all four strategies | `FULL`, `DELTA`, `BACKFILL_DELTA` — **not** `BACKFILL` | period outcomes: all four; scan watermark: scan-based `DELTA` and `FULL` only |

Never "fix" one type to match another, and never state one of these rules
as a general rule in code comments, error messages, or docs. When adding
a type, define and publish its own rules table. Full details in
`execution-and-incremental-design.md` §2.4.1 and the per-type pages under
`docs/flow/incremental/`.

The execution state has its own, genuinely global rule
(`save_execution_state()` runs for `FULL`, `DELTA`, `BACKFILL_DELTA`);
do not confuse it with the per-type incremental-state rule above.

### Source availability is declared, not inferred

`FlowIncrementalDefinition.source_availability` (`SourceAvailability`:
`full` | `partial`, default `full`) states whether one read of the source
presents its complete extent; every built-in type keeps `full`. A flow
whose source is only partially visible per read (a rotating listing)
overrides it in its YAML with `incremental: {type: ..., source_availability: partial}`. Like
`source_selection` and `target_update_granularity`, it is declarative
metadata the execution lifecycle does not branch on — see
`execution-and-incremental-design.md` §2.5.0.

### CLI parameters must be registered on the strategy definition

CLI flags such as `--full`, `--with-delta`, `--pull-from`, `--pull-to` only
reach `FlowIncrementalParams` if they are listed in the strategy's
`param_definitions` (e.g. `BY_SOURCE_TST_INCREMENTAL_DEFINITION` in
`nld/flow/incremental/impl/by_source_tst/logic.py`). The executor filters
`task_request.get_parameters()` by `DataFlowDefinition.get_init_params_keys()`,
which equals `task_class.get_init_params_keys()` plus the param names
exposed by `DataFlowDefinition.resolve_incremental_logic()` — the single
canonical resolver. The resolver picks the per-flow `incremental` strategy
first, then the task class `_INCREMENTAL_LOGIC` ClassVar, then
`NO_INCREMENT_FLOW_INCREMENTAL_LOGIC`. The task class itself does not
expose incremental params on `get_init_params()` — that responsibility
sits entirely on the definition. A flag missing from `param_definitions`
is silently dropped, and `resolve_strategy()` then falls back to the default
(typically `DELTA`) — even if the user passed `--full`.

`nld flow execute` accepts unknown options: type-specific flags
(`--keys`, `--pull-from`, `--periods`, `--period-from`, …) are parsed by an
argparser built from the resolved type's `param_definitions`
(`period_from` → `--period-from`), so they need no Click option. Only
flags shared by every type (`--full`, `--with-delta`) are also declared in
`nld/cli/flow/params_flow.py` and `nld/cli/flow/main_flow.py`.

### Type settings live in a typed `incremental.options` block

A type that needs per-flow settings (e.g. `by_target_period`'s
`granularity` and `period_field`) declares an `options_model` (a
`FlowIncrementalOptions` subclass, unknown keys forbidden) on its
`FlowIncrementalDefinition`. The flow YAML carries the raw mapping in
`IncrementalConfig.options`; `DataFlowDefinition.check_coherence`
validates it (and runs the model's `check_flow_coherence`, e.g. "the
column exists on the target"), and the factory hands the validated model
to the parameter class as `options`. Types without `options_model`
reject any option. `options` defaults to `None`, so existing flows keep
their deploy hash.

### Target-scoped types and write strategies

A definition may declare `allowed_write_strategies` (checked at flow load
and before every SQL write) and `target_scoped=True` (each run owns a
scope of the target). For a target-scoped type `SQLFlowTask` always
applies the type's SQL filter (even without predecessors, so it can
refuse), skips the whole write when `has_nothing_to_process()` is True,
and hands `get_target_scope_condition()` to the write strategy —
`DELETE_INSERT_SCOPED` deletes that scope before inserting.
`by_target_period` is the built-in target-scoped type.

### Source-state retrieval for SQL flows

`requires_source_state_retrieval` on the definition is the envelope of the
type; `IncrementalStateManager.requires_source_state_retrieval()` narrows
it to the resolved run (a declared `by_target_period` replay never scans).
`SQLFlowTask.retrieve_source_state` calls the manager's
`retrieve_source_state_from_sql(sql_query, predecessors, connector)` when
the narrowed flag holds; the base implementation is a no-op, and
`by_target_period` scans its MASTER predecessors there. The `compute`
source-request prompt follows the narrowed flag too.

### Planned-state support is a two-layer opt-in

Engagement of the planned-state slot is gated on both the strategy
and the backend. `FlowIncrementalDefinition.supports_planned_state`
(default `False`) declares strategy-side capability;
`IncrementalBackendStateManager.supports_planned_state` (`ClassVar`,
default `False`) declares backend-side capability. The built-ins set
strategy support on `by_key`, `by_source_tst` and `by_target_period`; the
`PostgreSQLIncrementalBackendMixin`, `SnowflakeIncrementalBackendMixin`,
`SQLiteIncrementalBackendMixin` and `S3IncrementalBackendMixin` set
backend support so every backend built on them inherits it. A
flow recomputes the processing state whenever either layer is off,
regardless of the `--planned-state-policy` value on
`nld flow execute`.

Plan-capable strategies that need a baseline-aware freshness check
override `IncrementalStateManager.is_planned_processing_state_fresh`;
the base returns `True` for strategies with explicit windows. See
`execution-and-incremental-design.md` §4.5 for the per-strategy
overrides and the `nld flow execute --planned-state-policy`
interaction.

## Module Layout

```
core/nld/flow/incremental/
├── models/                              # leaf layer: data/definition models
│   ├── state.py                         # FlowState, FlowSourceState, FlowProcessingState; FlowStatePlan, FlowPlannedProcessingState, FlowPlannedProcessingDetailedState
│   ├── logic.py                         # FlowIncrementalLogic, FlowIncrementalDefinition, param defs
│   ├── config.py                        # IncrementalConfig (incl. per-flow source_availability override)
│   ├── events.py
│   ├── manifest.py                      # FlowIncrementalTypeManifest
│   ├── referential.py                   # state/selection/availability/granularity enums, IncrementalPlanStatus
│   ├── request.py
│   └── constants.py
├── base/                                # abstract managers + SQL filter (depends downward on models)
│   ├── manager.py                       # IncrementalStateManager (owns planned-state lifecycle), IncrementalBackendStateManager (persistence primitives)
│   └── sql_filter_manager.py
├── backend/                             # connector-specific planned-state persistence
│   ├── plan.py                          # BackendStatePlanRow + state_plan_to_row / row_to_state_plan helpers
│   ├── postgresql/backend_mixin.py      # PostgreSQLIncrementalBackendMixin (state-plan I/O)
│   ├── snowflake/backend_mixin.py       # SnowflakeIncrementalBackendMixin (state-plan I/O)
│   ├── sqlite/backend_mixin.py          # SQLiteIncrementalBackendMixin (state-plan I/O)
│   └── s3_blob_storage/backend_mixin.py # S3IncrementalBackendMixin (state-plan I/O)
├── services/
│   ├── factory.py                       # resolves a name to its logic/manager/backend via the registry
│   └── registry.py                      # FlowIncrementalTypeRegistry + get_flow_incremental_type_registry()
└── impl/                                # built-in incremental types
    ├── __init__.py                      # registers by_key, by_source_tst, by_target_period, no_increment manifests
    ├── by_key/{logic,manager,sql_filter_manager,state,schema}.py + backend/
    ├── by_source_tst/   (same shape)
    ├── by_target_period/{logic,manager,period,sql_builder,sql_filter_manager,state}.py + backend/
    └── no_increment/    (same shape)
```

A `by_key` backend may declare `supports_key_state_merge()`, which the
DuckDB-engine backends (`local` and `s3_blob_storage`, through
`ByKeyDuckDBKeyStateMixin`) do: their parquet key state is read and merged
on disk through DuckDB queries, so a run holds only the keys it processes
rather than every key ever recorded. `IncrementalStateManager` then defers
loading `latest_incremental_state` until something actually reads it. See
`docs/flow/incremental/by_key.md`, "Key state merged on disk".

Built-in incremental types are seeded into the registry the first time
`nld.flow.incremental.impl` is imported. External types are added through
`Project.flow_config.additional_incremental_types`, declared in the `flow`
block of `nld_project.yml`.

## Identifier Vocabulary

Runtime code refers to an incremental type via the parameter name
`incremental_type` (factory kwargs, event constructors, local variables).
The registry key — `by_key`, `by_source_tst`, `by_target_period`,
`no_increment`, or the
`name` of an external type — is the value bound to `incremental_type`
at the registry boundary (`incremental_type = manifest.name`). The
`FlowIncrementalTypeManifest.name` field and the
`flow.additional_incremental_types[*].name` YAML key keep the literal name
`name`.

## Registering an External Incremental Type

`FlowIncrementalTypeRegistry` (`nld/flow/incremental/services/registry.py`)
is the single lookup boundary the factory consults. A project declares
extra entries in the `flow` block of `nld_project.yml`, alongside the other
flow-domain extension points:

```yaml
flow:
  additional_incremental_types:
    - name: by_partition
      logic_module: my_pkg.incrementals.by_partition.logic
      state_manager_module: my_pkg.incrementals.by_partition.manager
      backend_package: my_pkg.incrementals.by_partition.backend
      # optional:
      # backend_module_template: "{backend_type}_with_{engine}"
      # fallback_to_base_backend: true
```

`Project.from_dict` validates the entries into `FlowIncrementalTypeManifest`
instances and registers them on project load. A name that collides with a
built-in or another external type raises `NldProjectError` at registration
time.

The four runtime surfaces an external type must expose are described in
the `how-to-create-a-new-incremental-type` skill, which ships a complete
`by_source_tst_with_days_from` reference implementation.

`nld project info` lists every registered incremental type in its
`Flow configuration` block, alongside the rest of the project configuration.

## Cross-References

- For step-by-step instructions to author an external incremental type,
  see the `how-to-create-a-new-incremental-type` skill.
- For the flow lifecycle that wraps incremental logic, see the `guide-flows` skill.
- For the SQL-side plumbing (executor → SQLFlowTask → incremental filter), see
  section "4.2 CLI parameter plumbing" in `flow-sql-execution.md`.
- For an end-to-end Mermaid trace of how the resolver feeds the
  executor and the task, see `flow-execute-internals.md` (section 4
  "Incremental logic resolution").
- For per-backend command availability (execution and incremental
  state), see `docs/flow/backends/` and `docs/flow/incremental/`.
