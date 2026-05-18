---
name: guide-flows
description: >
  Architectural guide for the nld-core flow system — SQLFlowTask and DataFlowTask
  lifecycle, write strategies (OVERWRITE, VIEW, INSERT, UPSERT, DELETE_INSERT,
  UPSERT_LOGICAL_DELETE), SQL execution, query automation, incremental filtering,
  and the flow dependency graph.
user-invocable: false
---

# Guide: Flows & SQL Execution

Architectural reference for the nld-core flow system — SQL query automation,
write strategies, flow lifecycle, and execution pipeline.

## When to Use

Activate this guide when the agent is working on:
- Flow code in `nld/flow/`
- SQLFlowTask or DataFlowTask implementations
- Write strategy logic (OVERWRITE, VIEW, INSERT, UPSERT, DELETE_INSERT, UPSERT_LOGICAL_DELETE)
- SQL query templates and flow YAML definitions
- Flow dependency graph or deployment logic
- Flow deployment subsystem in `nld/flow/deploy/` (planner, executor, manifest, deployment metadata backend)
- CLI commands (`nld flow deps`, `nld flow deploy plan`, `nld flow deploy execute`). Note that `deploy execute` defaults to an in-memory plan; pass `--from-plan` for the manifest-based mode and `--no-interactive` for CI.

## Document Resolution

This guide references four documentation files. For each, first check the
project-local path. If not found, read the bundled copy.

| Document | Path |
|----------|------|
| Flow design | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-design.md` |
| SQL execution | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-sql-execution.md` |
| Flow execute internals | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-execute-internals.md` |
| Flow deployment | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-deployment.md` |

### Key Sections

**flow-design.md** — high-level architecture and principles:

| Task | Section |
|------|---------|
| Understanding flow purpose and principles | "1. Purpose: SQL Query Automation", "2. Core Principles" |
| Working with SQLFlowTask | "3. SQLFlowTask" |
| Understanding write strategies | "3.1b SQL Write Strategies" |
| Flow dependency and deployment | "5. Flow Dependency Graph", "6. Change Use Cases for Deployment" |
| CLI commands | "8. CLI Commands" |

**flow-sql-execution.md** — detailed execution mechanics (851 lines, read by section):

| Task | Section |
|------|---------|
| Understanding the execution pipeline | "1. Overview", "6. Execution Flow" |
| Project setup and YAML format | "2. Project Setup", "2.4 Flow Definition YAML" |
| Write strategy details and architecture | "3. Write Strategies" |
| Incremental filtering in SQL | "4. Incremental Filtering" |
| SQL file resolution and naming | "7. SQL File Resolution" |
| Configuration reference | "8. Configuration Reference" |
| State backend connector formats (legacy string vs primary/secondary mapping) | "8.3 State Backend Connector Formats" |
| Error handling | "9. Error Handling" |

**flow-execute-internals.md** — Mermaid-driven walkthrough of the
`nld flow execute` pipeline:

| Task | Section |
|------|---------|
| End-to-end CLI → task pipeline | "1. End-to-end pipeline" |
| Per-flow lifecycle (executor + task) sequence | "2. DataFlowExecutor — per-flow lifecycle" |
| Init-parameter assembly (4 sources, 2 mandatory checks) | "3. Init-parameter assembly" |
| Incremental logic resolver and consumers | "4. Incremental logic resolution" |
| State-manager wiring | "5. State-manager wiring" |
| `task.run()` pre/post processing orchestration | "6. task.run — the actual flow" |

**flow-deployment.md** — architecture of the `nld flow deploy` pipeline:

| Task | Section |
|------|---------|
| User stories with sequence diagrams (start here for any deploy task) | "1. User stories" |
| Default in-memory deploy / `--from-plan` review-then-apply / `--manifest-path` / `--plan-only` / `--no-interactive` (CI) / `--no-backfill` / failure recovery / removed flow stories | "1.1" through "1.8" |
| Three-layer architecture (orchestrator + planner + executor) and high-level internal sequence | "2. Pipeline overview" |
| Orchestrator `FlowDeployExecuteTask` (CLI flag handling, mutual exclusion, routing decision tree) | "3. Orchestrator — `FlowDeployExecuteTask`" |
| Planner internal sequence and pipeline detail | "4. Planner — `FlowDeployPlanner`" |
| Executor internal sequence (manifest resolution, idempotency, interleaved DDL/backfill, cascade-skip) | "5. Executor — `FlowDeployExecutor`" |
| `DeployManifest` schema (`flows`, `structures`, `links`) | "6. Manifest schema" |
| Deployment metadata tables in the metadata backend | "7. Metadata backend" |
| Default mode internals (in-memory plan, `--interactive/--no-interactive`, `--no-backfill` propagation, `--manifest-path` implies `--from-plan`) | "8. Default mode internals — in-memory plan" |
| CLI option reference for `deploy plan` and `deploy execute` | "9. CLI reference" |

## Critical Rules

### Parameter Dictionaries in Flow Classes

In all incremental and execution classes, `backend_parameters` and `flow_parameters`
are read-only dictionaries. Their values must be accessed directly from the dictionary
without using default values.

```python
# Good - direct access without default
self.backend_parameters["s3_root_path"]

# Bad - using default value
self.backend_parameters.get("s3_root_path", "/default/path")
```

For S3 backends the parameter is `s3_root_path`. Local backends keep
their own keys. `s3_root_path` is derived by
`determine_parameters_for_flow_definition` on `S3BackendMixin` from
`S3Structure.s3_root_path` (composed `s3_root_prefix` +
`s3_folder_path`, defaulting to the structure name); the same override
is inherited by execution and `by_key` incremental S3 state backends.
The derived value is merged with per-side YAML
`state_backend_connector.<side>.params` and explicit kwargs in that
precedence (**derived < `config.params` < kwargs**).

For per-side state-backend params (e.g. `file_format` on an S3
secondary), see `state_backend_connector` in §8.3 of
`flow-sql-execution.md`.

## Cross-References

- For incremental processing and state management within flows, see the
  `guide-incremental` skill.
- For structure targets referenced by flows, see the `guide-structures` skill.
- For structure deployment (DDL diff, schema history) invoked by the flow
  deploy executor, see the structure deploy section of the
  `guide-structures` skill.
