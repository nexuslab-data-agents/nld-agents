---
name: guide-scheduling
description: >
  Architectural guide for the nld-core scheduling subsystem — the `environments`
  block in nld_project.yml (EnvironmentsConfig + `--env`/`NLD__ENVIRONMENT`
  resolution), the per-flow, per-environment `FlowTask` entity (schedule vs
  flow triggers, automatic lineage derivation adjusted by
  additional_predecessors/excluded_predecessors or fully overridden by
  predecessors, external/cross-product
  references), the declared `frequency` (intended execution cadence, tracked
  independently of the cron), the namespace-scoped scheduling policy
  (`namespaces.<ns>.scheduling`: the `max_attempts` retry budget and the
  `alerting` block that drives both nld's own alerts and the scheduler's),
  the SchedulingResolver/Validator/FrequencyReporter/SchedulingPolicy
  services, and the `nld scheduling` CLI. Read when working on scheduling YAML
  under scheduling/, environment config, alerting, or nld/scheduling/ code. For
  the cross-project catalogue see guide-project-catalog.
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
- `scheduling/` YAML definitions (`FlowTask` entities)
- `nld/scheduling/` code (models, resolver, graph, validator, tasks)
- The `nld scheduling` CLI (validate / deps / frequency / list / info)
- Cross-project (`nld_project_catalog.yml`) dependency declarations
- The `scheduling` block of a namespace in `nld_project.yml` (retry budget,
  alerting) and how a flow execution raises an alert (`nld/flow/alerting/`)

## Environments

`nld_project.yml` accepts an optional `environments` block. An environment selects
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

> `Project` also carries a free-form `properties` mapping (`dict[str, str]`)
> for platform metadata that the core model does not need to interpret.

## FlowTask entity

Built-in entity `scheduling` (`folder_name="scheduling"`,
`category="Scheduling"`), one file per scheduled flow under
`scheduling/<ns path>/<name>.yaml` — or
`<namespace folder>/scheduling/<sub path>/<name>.yaml` for a namespace stored
as a namespace folder. Defined in `nld/scheduling/models/scheduling.py`.

### `FlowTask(NldNamedBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Task name (inherited; file stem). |
| `flow` | `NldEntityReference[DataFlowDefinition]` | The scheduled flow — registry-resolved and validated. |
| `params` | `dict[str, Any]` | Platform-specific knobs (data_sub_product, process_type, runner hints…). The core model never grows an attribute for these. |
| `environments` | `dict[str, EnvironmentScheduling]` | Per-environment scheduling, keyed by environment name. |
| `frequency` | `ExecutionFrequency \| None` | Intended execution cadence of the asset, used as the default across environments. See **Execution frequency** below. |
| `max_attempts` | `int \| None` (1–10) | Retry budget of this task alone, overriding the namespace-level one. See **Scheduling policy** below. |

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
- **`FlowTrigger`** — `kind: flow`. Runs after upstream tasks reach a
  terminal state. Two modes, decided by whether `predecessors` is set:

  - **Additive mode** (`predecessors` empty) — the resolver derives the
    automatic lineage from the flow dependency graph, then unions in
    `get_all_predecessors()`:

    ```
    automatic lineage | get_all_predecessors()
    ```

  - **Override mode** (`predecessors` non-empty) — the flow dependency graph
    is **never consulted**, and the upstream set is exactly
    `get_all_predecessors()`. Use it when a task's upstream set should not
    track the flow's own dependencies.

  - `predecessors: list[FlowPrecondition]` — when non-empty, the **full
    override** of the automatic lineage (see above).
  - `additional_predecessors: list[FlowPrecondition]` — extra dependencies the
    flow-lineage derivation cannot see (an external/cross-product dependency,
    or a same-product one the flow graph doesn't express). Same shape as
    `FlowPrecondition` (`external`/`nld_project` supported).
  - `excluded_predecessors: list[FlowPrecondition]` — cancels a matching entry
    (same `name`/`external`/`nld_project`) out of
    `predecessors`/`additional_predecessors`. This is a **self-contained
    adjustment of this trigger's own explicit list** — it never reaches into
    the automatically derived lineage, so excluding something that was never
    added (or that only exists in the derived lineage) is a silent no-op, not
    an error. `external: true` is allowed here: it cancels a matching
    external addition.

  `FlowTrigger.get_all_predecessors()` does the actual combining:
  `predecessors + additional_predecessors`, minus anything matched out by
  `excluded_predecessors`. In additive mode the resolver rejects a
  `get_all_predecessors()` entry that duplicates the derived lineage
  (`NldSchedulingPredecessorError`) — a redundant no-op that is almost
  certainly a mistake. In override mode there is no derived lineage to
  collide with, so no such check applies.

### `FlowPrecondition`

Shape shared by `predecessors`, `additional_predecessors`, and
`excluded_predecessors`:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `NldEntityReference[FlowTask]` | The upstream **task** that must complete first (a task's trigger depends on another task's outcome). |
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

## Scheduling policy: retries and alerting

A namespace's scheduled runs share a policy declared under the `namespaces`
block of `nld_project.yml` (`nld/scheduling/config/scheduling_config.py`):

```yaml
namespaces:
  .:                       # the root: every namespace inherits it
    scheduling:
      alerting:
        transports: [slack]             # the technologies, by transport name
        alert_on: [FAILED, WARNING]     # SchedulingExecutionState values
        slack:                          # each transport's own settings block
          channel: data-alerts
  "*.extraction":          # a wildcard level: every extraction sub-namespace
    scheduling:
      max_attempts: 2      # retry budget, first attempt included (1 = no retry)
```

`SchedulingPolicy` (`nld/scheduling/services/policy.py`) resolves both for a
task, with one asymmetry worth knowing: **`max_attempts` takes the nearest
declaring level** (a `FlowTask` may also override it directly), while
**`alerting` walks past levels that declare none** — so `"*.extraction"`
raising only its retry budget still inherits the root channel. Switching
alerting off is therefore explicit: `alerting: {enabled: false}` on the
nearer level. `nld scheduling info --name <task>` prints both values with the
declaring line.

`max_attempts` (integer 1–10, default 1) counts the first attempt: `1` means
no retry, `2` one retry. A `FlowTask`'s own `max_attempts` wins over every
namespace level; otherwise the nearest level carrying a `scheduling` block
decides, whatever it holds — a nearer level declaring only `alerting` gets
the default budget of 1.

`AlertingConfig` (`extra="forbid"`) types `enabled` (default true),
`transports` (the technologies by name, lower-cased, no repeats — required
when enabled, so a reader can tell exactly what a namespace alerts through),
`alert_on` (at least one `SchedulingExecutionState` — `SUCCESS`, `WARNING`,
`FAILED`, `KILLED`, `CANCELLED` — in any case, a typo failing at project load;
default `[FAILED]`) and `alert_after_consecutive_failures` (integer ≥ 1,
default 1; validated and shown by `nld scheduling info`, while nld's own
alerting does not read it). Each named transport may carry a block of its own
non-secret settings under its name (`slack.channel`, `telegram.chat_id`).
Transport names, and the settings keys of the built-in transports, are
validated against the transport registry when the project loads; the
settings of a transport added through `flow.additional_alert_transports`
are checked when a flow first builds it, so loading a project never imports
its Python code.

**One declaration, two alerting layers.** The same block drives:

- **nld itself** (`nld/flow/alerting/`): once `DataFlowTask.run` ends, the
  outcome is mapped on a level — a flow exception or a `blocking` quality
  violation is `FAILED` on a failed execution; an `error`-severity violation
  is `FAILED` too but the execution completes (the pipeline goes on); any
  other violation is `WARNING`. nld raises only these two levels. If the
  level is in `alert_on`, nld posts the alert itself through every declared
  transport this environment configures; the message names the flow, the
  environment, the project, the execution status and the violated checks or
  the error. Transports live in `nld/flow/alerting/transports/`: built-in
  `slack` (an incoming webhook, `NLD__ALERTING__SLACK__WEBHOOK_URL`; the
  `channel` setting is informational, the webhook decides where the message
  goes) and `telegram` (a bot, `NLD__ALERTING__TELEGRAM__BOT_TOKEN`, posting
  to `NLD__ALERTING__TELEGRAM__CHAT_ID` or, when that variable is unset, the
  `chat_id` setting). A platform adds one with a `FlowAlertTransport`
  subclass (`name`, `required_env_vars`, `optional_env_vars`,
  `settings_keys`, `from_environment`, `send`) declared under
  `flow.additional_alert_transports` (`name` + `transport_class`) in
  `nld_project.yml`; its class is imported on first lookup only. A declared
  transport whose required secret is not in the environment is skipped with
  a log line, and a misconfigured one (Telegram without a chat id) is skipped
  with a warning — never an error. The execution context owns a
  `FlowAlertingProvider` (`context.alerting_provider`, built when the project
  is initialised, replaceable with `set_alerting_provider`) that hands each
  flow the `FlowAlertingService` in force for its namespace; the task itself
  builds nothing. The transport-neutral runtime side comes from the
  scheduler as environment variables:
  `NLD__ALERTING__OUTCOME_LINE_TEMPLATE` (a `string.Template` with `$status`,
  `$alerted`, `$level`, printed once after the run so the scheduler can read
  the outcome back), `NLD__ALERTING__ATTEMPT` / `NLD__ALERTING__MAX_ATTEMPTS`
  (a failure is alerted on the last attempt only; earlier ones are retried),
  `NLD__ALERTING__EXECUTION_REFERENCE` (the scheduler's execution id, quoted
  in the message) and `NLD__ALERTING__EXECUTION_URL` (the run's page in the
  scheduler's UI, `http(s)` only: the message links the reference to it).
  The environment named in the message is `NLD__ENVIRONMENT`, or the
  project's resolved environment. Delivery problems are logged, never
  raised: alerting cannot fail a run.
- **the scheduler**: a generator (nld-scheduling-generator for Kestra) reads
  `SchedulingPolicy.alerting()` to label each flow and to hand the pod the
  variables above — for each named transport, the variables its class
  declares, mapped to the platform's secret keys; the scheduler's own alert
  reacts to failures nld could not report (a pod that never started, an
  out-of-memory kill) and stays quiet when the outcome line says nld already
  alerted.

Run by hand with none of the variables set, nld neither posts nor prints
anything; the declaration only describes what scheduled runs do.

## Services

In `nld/scheduling/services/`:

- **`SchedulingResolver`** — resolves each `FlowTrigger`'s upstream set: a
  non-empty `predecessors` is a full override (`get_all_predecessors()`
  alone, the flow graph is never consulted); otherwise the automatic lineage
  derived from the flow dependency graph, unioned with
  `get_all_predecessors()` (which already nets `predecessors` +
  `additional_predecessors` against `excluded_predecessors`). Raises
  `NldSchedulingPredecessorError` only when an additive-mode entry
  duplicates the derived lineage.
- **`SchedulingGraph`** — the environment's trigger graph. Each node carries its
  trigger kind, cron and resolved `frequency`.
- **`SchedulingValidator`** — gates on cycles in that graph.
- **`SchedulingFrequencyReporter`** — builds a `SchedulingFrequencyReport`
  (`entries`, `undeclared_entries`, `inconsistent_entries`,
  `count_by_frequency()`); each `SchedulingFrequencyEntry` exposes the declared
  `frequency`, the `upstream_frequency` it is checked against, `is_declared` and
  `is_inconsistent`.
- **`SchedulingPolicy`** — bound to one project's
  `scheduling_namespace_config`; resolves a task's retry budget
  (`max_attempts()`, `resolve_max_attempts()` = the value with its origin)
  and alerting (`alerting()` = the config in force or None,
  `resolve_alerting()` = the declaration with its origin) from the
  namespace-scoped `scheduling` block, see above. `alerting_for_namespace()`
  answers the same question for a namespace alone — the path a running flow,
  which has no task, takes.

## CLI

```
nld scheduling validate  --env <env>
nld scheduling deps      --env <env> [--format json|mermaid] [--task-name <t>]
                                     [--namespace <ns>] [--upstream] [--downstream]
                                     [--override-output-folder-path <dir>]
nld scheduling frequency --env <env> [--frequency <value>]
nld scheduling list      [--namespace <ns>] [--env <env>]
nld scheduling info      --name <task> [--namespace <ns>]
```

- `validate` — checks the environment's scheduling graph is acyclic.
- `deps` — outputs the scheduling dependency graph for an environment, with the
  usual lineage filters. The graph file lands in a timestamped folder under
  `output/` unless `--override-output-folder-path` names the folder to write
  to — the standard file-output option shared with `nld flow deps` and other
  file-writing commands, so programmatic callers get a deterministic path
  instead of parsing stdout.
- `frequency` — reports every scheduled asset with its declared cadence, the
  cadence its triggers allow, and a status (`ok` / `undeclared` /
  `inconsistent`), plus a per-cadence breakdown. `--frequency` narrows the
  report to one cadence ("which assets are daily?").
- `list` — every scheduled task as a table (name, namespace, flow,
  frequency, effective max attempts, environments with their trigger kind).
  `--env` keeps only the tasks active in that environment ("what runs in
  prd?") and shows the environment's frequency.
- `info` — one scheduled task's declaration: its frequency, retry policy and
  alerting (each with the `nld_project.yml` line that decided it), params
  and per-environment triggers.

`validate`, `deps` and `frequency` are environment-aware (`--env`, same
precedence as above) and load the whole project, since the trigger graph
crosses namespaces. `list` and `info` load only the lineage of `--namespace`
when it is given.

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
        - name: some_upstream_task
          external: true
          nld_project: clh_acquisition_opendata
```

`predecessors` fully replaces the automatic lineage — the flow dependency
graph is not consulted at all. Use it when the scheduled order must not track
the flow's own dependencies:

```yaml
environments:
  prd:
    trigger:
      kind: flow
      predecessors:            # the complete upstream set — the derived
        - name: clh.business.dwh.flow_b   # lineage is ignored entirely
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
