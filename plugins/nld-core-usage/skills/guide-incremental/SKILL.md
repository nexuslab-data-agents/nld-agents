---
name: guide-incremental
description: >
  Architectural guide for the nld-core incremental processing system — built-in
  by_key, by_source_tst, and no_increment types under `impl/`, the
  FlowIncrementalTypeRegistry plugin point, the `additional_incremental_types`
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
  built-in types under `nld/flow/incremental/impl/{by_key,by_source_tst,no_increment}/`
- Execution logging in `nld/flow/execution/`
- State management in `nld/flow/state/`
- IncrementalConfig, ProcessingState, or ExecutionLog classes
- Backend implementations for incremental/execution/state modules
- Choosing or configuring an incremental type for a flow
- Registering an external incremental type via
  `additional_incremental_types` in `nld_project.yml`

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/flow/execution-and-incremental-design.md`.

Backend support matrices (which connector/engine supports which command
for execution and incremental state) live at
`${CLAUDE_PLUGIN_ROOT}/docs/flow/backends/` (connector-by-connector) and
`${CLAUDE_PLUGIN_ROOT}/docs/flow/incremental/` (strategy-by-strategy).
Consult them when asked whether a backend supports `get-state`,
`get-steps`, or `compute --persist`.

### Key Sections (900 lines — read by section, not in full)

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
expose incremental params on `get_init_params()` anymore — that responsibility
sits entirely on the definition. A flag missing from `param_definitions`
is silently dropped, and `resolve_strategy()` then falls back to the default
(typically `DELTA`) — even if the user passed `--full`.

When adding a new incremental flag, update **both** the strategy's
`param_definitions` and the Click option / command decorator in
`nld/cli/flow/params_flow.py` and `nld/cli/flow/main_flow.py`.

## Module Layout

```
core/nld/flow/incremental/
├── base/                                # abstract contracts (logic, manager, sql_filter_manager, state)
├── models/
│   ├── config.py                        # IncrementalConfig
│   ├── events.py
│   ├── manifest.py                      # FlowIncrementalTypeManifest
│   ├── referential.py
│   ├── request.py
│   └── constants.py
├── services/
│   ├── factory.py                       # resolves a name to its logic/manager/backend via the registry
│   └── registry.py                      # FlowIncrementalTypeRegistry + get_flow_incremental_type_registry()
└── impl/                                # built-in incremental types
    ├── __init__.py                      # registers by_key, by_source_tst, no_increment manifests
    ├── by_key/{logic,manager,sql_filter_manager,state,schema}.py + backend/
    ├── by_source_tst/   (same shape)
    └── no_increment/    (same shape)
```

Built-in incremental types are seeded into the registry the first time
`nld.flow.incremental.impl` is imported. External types are added through
`Project.additional_incremental_types` declared in `nld_project.yml`.

## Identifier Vocabulary

Runtime code refers to an incremental type via the parameter name
`incremental_type` (factory kwargs, event constructors, local variables).
The registry key — `by_key`, `by_source_tst`, `no_increment`, or the
`name` of an external type — is the value bound to `incremental_type`
at the registry boundary (`incremental_type = manifest.name`). The
`FlowIncrementalTypeManifest.name` field and the
`additional_incremental_types[*].name` YAML key keep the literal name
`name`.

## Registering an External Incremental Type

`FlowIncrementalTypeRegistry` (`nld/flow/incremental/services/registry.py`)
is the single lookup boundary the factory consults. A project declares
extra entries in `nld_project.yml` alongside `additional_entities`:

```yaml
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

`nld project info` lists every registered incremental type alongside
additional entities and python paths.

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
