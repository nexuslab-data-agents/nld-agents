---
name: guide-scheduling
description: >
  Architectural guide for the nld-core scheduling subsystem — the `environments`
  block in nld_project.yml (EnvironmentsConfig + `--env`/`NLD__ENVIRONMENT`
  resolution), the per-flow, per-environment `FlowScheduling` entity (schedule vs
  flow triggers, automatic lineage derivation adjusted by
  additional_predecessors/excluded_predecessors, external/cross-product
  references), the declared `frequency` (intended execution cadence, tracked
  independently of the cron), the SchedulingResolver/Validator/FrequencyReporter
  services, and the `nld scheduling` CLI. Read when working on scheduling YAML
  under scheduling/, environment config, or nld/scheduling/ code. For the
  cross-project catalogue see guide-project-catalog.
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
- The `nld scheduling` CLI (validate / deps / frequency)
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
| `frequency` | `ExecutionFrequency \| None` | Intended execution cadence of the asset, used as the default across environments. See **Execution frequency** below. |

Helpers: `for_environment(env)`, `is_active_in(env)` (present **and** `enabled`
**and** has a `trigger`), `merged_params(env)` (flow-level `params` overlaid with
the environment's `params`), `resolved_frequency(env)` (the env-level
`frequency`, falling back to the flow-level one).

### `EnvironmentScheduling`

| Field | Type | Purpose |
|-------|------|---------|
| `enabled` | `bool` (default `True`) | Whether the flow is scheduled in this env. |
| `trigger` | `Trigger \| None` | How it fires (see below). Absent ⇒ not scheduled. |
| `params` | `dict[str, Any]` | Env-level overrides of the flow-level `params`. |
| `frequency` | `ExecutionFrequency \| None` | Env-level override of the flow-level `frequency`. |

### Triggers (`nld/scheduling/models/trigger.py`)

A discriminated union on `kind`:

- **`ScheduleTrigger`** — `kind: schedule`, `cron: "<expr>"`. Time-based.
- **`FlowTrigger`** — `kind: flow`. Runs after upstream schedulings reach a
  terminal state. The resolver **always** derives the automatic lineage from
  the flow dependency graph, then unions in `get_all_predecessors()`:

  ```
  automatic lineage | get_all_predecessors()
  ```

  - `additional_predecessors: list[FlowPrecondition]` — extra dependencies the
    flow-lineage derivation cannot see (an external/cross-product dependency,
    or a same-product one the flow graph doesn't express). Same shape as
    `FlowPrecondition` (`external`/`nld_project` supported).
  - `predecessors: list[FlowPrecondition]` — the deprecated name for
    `additional_predecessors`. The two are the **same kind of addition and
    combine** rather than being separate modes — existing YAML keeps working
    unchanged, and callers switch to the new name at their own pace.
  - `excluded_predecessors: list[FlowPrecondition]` — cancels a matching entry
    (same `name`/`external`/`nld_project`) out of
    `predecessors`/`additional_predecessors`. This is a **self-contained
    adjustment of this trigger's own explicit list** — it never reaches into
    the automatically derived lineage, so excluding something that was never
    added (or that only exists in the derived lineage) is a silent no-op, not
    an error. Unlike the old design, `external: true` is allowed here: it
    cancels a matching external addition.

  `FlowTrigger.get_all_predecessors()` does the actual combining:
  `predecessors + additional_predecessors`, minus anything matched out by
  `excluded_predecessors`. The resolver's remaining validation rejects a
  `get_all_predecessors()` entry that duplicates the derived lineage
  (`NldSchedulingPredecessorError`) — a redundant no-op that is almost
  certainly a mistake.

### `FlowPrecondition`

Shape shared by `predecessors`, `additional_predecessors`, and
`excluded_predecessors`:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `NldEntityReference[FlowScheduling]` | The upstream **scheduling** that must complete first (scheduling depends on scheduling). |
| `external` | `bool` (default `False`) | When `False`, resolved against the local registry — a dangling predecessor is a load-time error. When `True`, the upstream lives in another data product; the reference is informational only, never resolved/validated locally. |
| `nld_project` | `str \| None` | For an external predecessor, the upstream **data product** (its nld project name); `name` is then the bare entity name. Only valid when `external: true` (validator enforces this). Consumers resolve `nld_project` to their platform's namespace. |
| `states` | `list[...]` | Terminal states that satisfy the precondition. Default `["SUCCESS", "WARNING"]`. |

## Execution frequency

`frequency` (`nld/scheduling/models/frequency.py`) is the **intended execution
cadence** of a scheduled asset — first-class metadata, never read back from the
trigger. Two reasons it cannot be derived: a flow-triggered asset has no cron at
all, and a cron says when a run *fires*, not the cadence consumers are promised.
An asset that declares nothing is reported as undeclared, not given a guessed
cadence.

`ExecutionFrequency` values, from the most frequent to the least:
`continuous`, `hourly`, `intraday` (several runs a day, coarser than hourly),
`daily`, `weekly`, `monthly`, `quarterly`, `yearly`, plus `on_demand` — which
has no cadence at all and is therefore excluded from every comparison.

Declaration follows the `params` rule: flow-level `frequency` is the default,
an environment's `frequency` overrides it for that environment only
(`resolved_frequency(env)`). The resolved value lands on the scheduling graph
node, so it appears in `nld scheduling deps` (JSON `frequency` attribute and the
Mermaid node label).

**Consistency rule.** A flow-triggered asset cannot deliver more often than the
slowest thing it waits for, so `SchedulingFrequencyReporter` compares the
declared cadence against the **coarsest** cadence among the assets triggering it
(walking further up when a direct trigger declares nothing). Declaring `hourly`
behind a `daily` ingestion is flagged as inconsistent. The check is
environment-scoped: the same declaration can be coherent in prd and inconsistent
in stg where the ingestion only runs weekly. Schedule-triggered assets have no
upstream cadence and are never flagged — the cron is not parsed.

Nothing here is a hard failure: `nld scheduling validate` still gates on cycles
only, and the frequency report warns.

## Services

In `nld/scheduling/services/`:

- **`SchedulingResolver`** — always derives a `FlowTrigger`'s automatic
  lineage from the flow dependency graph, then unions in
  `get_all_predecessors()` (which already nets `predecessors` +
  `additional_predecessors` against `excluded_predecessors`). Raises
  `NldSchedulingPredecessorError` only when an entry duplicates the derived
  lineage.
- **`SchedulingGraph`** — the environment's trigger graph. Each node carries its
  trigger kind, cron and resolved `frequency`.
- **`SchedulingValidator`** — gates on cycles in that graph.
- **`SchedulingFrequencyReporter`** — builds a `SchedulingFrequencyReport`
  (`entries`, `undeclared_entries`, `inconsistent_entries`,
  `count_by_frequency()`); each `SchedulingFrequencyEntry` exposes the declared
  `frequency`, the `upstream_frequency` it is checked against, `is_declared` and
  `is_inconsistent`.

## CLI

```
nld scheduling validate  --env <env>
nld scheduling deps      --env <env> [--format json|...] [--flow-name <f>]
                                     [--namespace <ns>] [--upstream] [--downstream]
nld scheduling frequency --env <env> [--frequency <value>]
```

- `validate` — checks the environment's scheduling graph is acyclic.
- `deps` — outputs the scheduling dependency graph for an environment, with the
  usual lineage filters.
- `frequency` — reports every scheduled asset with its declared cadence, the
  cadence its triggers allow, and a status (`ok` / `undeclared` /
  `inconsistent`), plus a per-cadence breakdown. `--frequency` narrows the
  report to one cadence ("which assets are daily?").

All three are environment-aware (`--env`, same precedence as above).

## Examples

`scheduling/clh/business/dwh/flow_a.yaml` — flow-triggered in prd (automatic
lineage, adjusted), cron in stg:

```yaml
name: flow_a
flow: clh.business.dwh.flow_a
frequency: daily          # intended cadence, both environments
environments:
  prd:
    trigger:
      kind: flow
      additional_predecessors:
        - name: clh.business.dwh.flow_external_input
  stg:
    frequency: weekly     # staging refreshes less often
    trigger:
      kind: schedule
      cron: "0 2 * * 1"
```

`excluded_predecessors` cancels a matching entry back out — useful when an
environment- or template-level override needs to drop one addition without
re-declaring the rest:

```yaml
environments:
  prd:
    trigger:
      kind: flow
      additional_predecessors:
        - name: clh.business.dwh.flow_external_input
        - name: clh.business.dwh.flow_staging_probe
      excluded_predecessors:
        - name: clh.business.dwh.flow_staging_probe   # only relevant in stg
```

Disabled in one env, pure automatic derivation (no adjustments) in the other:

```yaml
name: flow_c
flow: clh.business.dwh.flow_c
params:
  data_sub_product: sirene
  process_type: refinement
environments:
  prd:
    trigger:
      kind: flow          # predecessors derived from the flow graph, unadjusted
  stg:
    enabled: false
```

```yaml
# an external predecessor lives in another data product — add it since the
# local flow graph cannot see across products
environments:
  stg:
    trigger:
      kind: flow
      additional_predecessors:
        - name: some_upstream_scheduling
          external: true
          nld_project: clh_acquisition_opendata
```

Legacy field name (deprecated — behaves exactly like `additional_predecessors`,
prefer that name in new YAML):

```yaml
environments:
  prd:
    trigger:
      kind: flow
      predecessors:            # combines with the derived lineage, not a
        - name: clh.business.dwh.flow_b   # replacement for it
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
