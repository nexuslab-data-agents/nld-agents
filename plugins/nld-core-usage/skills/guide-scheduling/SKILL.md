---
name: guide-scheduling
description: >
  Architectural guide for the nld-core scheduling subsystem — the `environments`
  block in nld_project.yml (EnvironmentsConfig + `--env`/`NLD__ENVIRONMENT`
  resolution), the per-flow, per-environment `FlowScheduling` entity (schedule vs
  flow triggers, predecessors, external/cross-product references), the
  SchedulingResolver/Validator services, and the `nld scheduling` CLI. Read when
  working on scheduling YAML under scheduling/, environment config, or
  nld/scheduling/ code. For the cross-project catalogue see guide-project-catalog.
user-invocable: false
---

# Guide: Scheduling & Environments

Architectural reference for the nld-core scheduling subsystem — a **declarative,
environment-aware** spec for *which* flows run *when* and *in what order*. It is
implementation-agnostic: a platform (e.g. a Kestra generator) consumes this spec
to produce the actual scheduler config.

## When to Use

Activate this guide when working on:
- `environments` in `nld_project.yml`, the `--env` flag, or `NLD__ENVIRONMENT`
- `scheduling/` YAML definitions (`FlowScheduling` entities)
- `nld/scheduling/` code (models, resolver, graph, validator, tasks)
- The `nld scheduling` CLI (validate / deps)
- Cross-project (`nld_project_catalog.yml`) dependency declarations

## Environments

`nld_project.yml` gains an optional `environments` block. An environment selects
a connection profile and may override project variables for that environment
only.

```yaml
name: my_project
version: 1.0.0

environments:
  default: prd
  values:
    dev:
      connection_profile: dev
      variables:
        schema_name: opendata_dev
    prd:
      connection_profile: default
```

Models (`nld/project/environment_config.py`):

- `EnvironmentConfig`: `connection_profile` (`str | None`), `variables`
  (`dict[str, str]`).
- `EnvironmentsConfig`: `default` (`str | None`), `values`
  (`dict[str, EnvironmentConfig]`).

**Active-environment precedence** (`resolve_name`):
`--env` flag → `NLD__ENVIRONMENT` variable → `environments.default`.
When environments are declared, the resolved name must be one of them
(otherwise `NldUnknownEnvironmentError`).

> `Project` also gained a free-form `properties: dict[str, Any]` key-value field
> for platform metadata that the core model does not need to interpret.

## FlowScheduling entity

Built-in entity `flow_scheduling` (`folder_name="scheduling"`,
`category=data_flow`), one file per scheduled flow under
`scheduling/<ns path>/<name>.yaml`. Defined in
`nld/scheduling/models/scheduling.py`.

### `FlowScheduling(NldNamedBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Scheduling name (inherited; file stem). |
| `flow` | `NldEntityReference[DataFlowDefinition]` | The scheduled flow — registry-resolved and validated. |
| `params` | `dict[str, Any]` | Platform-specific knobs (data_sub_product, process_type, runner hints…). The core model never grows an attribute for these. |
| `environments` | `dict[str, EnvironmentScheduling]` | Per-environment scheduling, keyed by environment name. |

Helpers: `for_environment(env)`, `is_active_in(env)` (present **and** `enabled`
**and** has a `trigger`), `merged_params(env)` (flow-level `params` overlaid with
the environment's `params`).

### `EnvironmentScheduling`

| Field | Type | Purpose |
|-------|------|---------|
| `enabled` | `bool` (default `True`) | Whether the flow is scheduled in this env. |
| `trigger` | `Trigger \| None` | How it fires (see below). Absent ⇒ not scheduled. |
| `params` | `dict[str, Any]` | Env-level overrides of the flow-level `params`. |

### Triggers (`nld/scheduling/models/trigger.py`)

A discriminated union on `kind`:

- **`ScheduleTrigger`** — `kind: schedule`, `cron: "<expr>"`. Time-based.
- **`FlowTrigger`** — `kind: flow`, `predecessors: list[FlowPrecondition]`. Runs
  after upstream schedulings reach a terminal state. **When `predecessors` is
  empty, the resolver derives them from the flow dependency graph;** an explicit
  list overrides the derivation.

### `FlowPrecondition`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `NldEntityReference[FlowScheduling]` | The upstream **scheduling** that must complete first (scheduling depends on scheduling). |
| `external` | `bool` (default `False`) | When `False`, resolved against the local registry — a dangling predecessor is a load-time error. When `True`, the upstream lives in another data product; the reference is informational only, never resolved/validated locally. |
| `nld_project` | `str \| None` | For an external predecessor, the upstream **data product** (its nld project name); `name` is then the bare entity name. Only valid when `external: true` (validator enforces this). Consumers resolve `nld_project` to their platform's namespace. |
| `states` | `list[...]` | Terminal states that satisfy the precondition. Default `["SUCCESS", "WARNING"]`. |

## Services

In `nld/scheduling/services/`:

- **`SchedulingResolver`** — derives a `FlowTrigger`'s predecessors from the flow
  dependency graph when they are not declared explicitly.
- **`SchedulingGraph`** — the environment's trigger graph.
- **`SchedulingValidator`** — gates on cycles in that graph.

## CLI

```
nld scheduling validate --env <env>
nld scheduling deps     --env <env> [--format json|...] [--flow-name <f>]
                                    [--namespace <ns>] [--upstream] [--downstream]
```

- `validate` — checks the environment's scheduling graph is acyclic.
- `deps` — outputs the scheduling dependency graph for an environment, with the
  usual lineage filters.

Both are environment-aware (`--env`, same precedence as above).

## Examples

`scheduling/clh/business/dwh/flow_a.yaml` — flow-triggered in prd, cron in stg:

```yaml
name: flow_a
flow: clh.business.dwh.flow_a
environments:
  prd:
    trigger:
      kind: flow
      predecessors:
        - name: clh.business.dwh.flow_b
  stg:
    trigger:
      kind: schedule
      cron: "0 2 * * *"
```

Disabled in one env, and a cross-product (external) predecessor:

```yaml
name: flow_c
flow: clh.business.dwh.flow_c
params:
  data_sub_product: sirene
  process_type: refinement
environments:
  prd:
    trigger:
      kind: flow          # predecessors derived from the flow graph
  stg:
    enabled: false
```

```yaml
# an external predecessor lives in another data product
environments:
  stg:
    trigger:
      kind: flow
      predecessors:
        - name: some_upstream_scheduling
          external: true
          nld_project: clh_acquisition_opendata
```

## Cross-project dependencies

An `external` precondition's `nld_project` names a project in the platform-level
**`NldProjectCatalog`** (`nld_project_catalog.yml`) — the cross-project DAG that
records every project and the predecessor links between them. The catalogue
expresses the dependency at the *project* grain; a `FlowPrecondition` with
`external: true` expresses the same dependency at the *flow* grain. See
**`guide-project-catalog`** for the full model and YAML.

## Relationship to other entities & layers

- **Flows** (`guide-flows`, `how-to-trace-flow-lineage`) provide the dependency
  graph the resolver derives predecessors from.
- **Connections** (`guide-connections`) — an environment selects a
  `connection_profile`.
- This entity is the *spec*; platform-specific scheduler config (e.g. Kestra
  workflows) is **generated** from it — it is not the scheduler itself.
