---
name: guide-governance
description: >
  Architectural guide for the nld-core governance/ownership entities — the
  namespaced, inheritable `structure_owner` (data responsibility) and
  `flow_owner` (technical-execution responsibility) declarations, their
  lineage-based resolution, the registry accessors, and the `nld ownership`
  CLI. Read when working on ownership declarations under governance/structure/
  or governance/flow/, or the governance code in nld/governance/.
user-invocable: false
---

# Guide: Governance & Ownership

Architectural reference for the nld-core governance subsystem — two namespaced
nld entities that make ownership **declared, queryable and validated** rather
than tribal knowledge.

## When to Use

Activate this guide when working on:
- `structure_owner` / `flow_owner` YAML definitions under
  `governance/structure/` and `governance/flow/`
- `nld/governance/` code (ownership models, lineage `lookup.py`, tasks)
- The `nld ownership` CLI (resolve / list)
- Questions of the form "who owns this structure / flow?"

## Two accountabilities, two entities

A structure has two distinct kinds of owner, and the subsystem keeps them
separate:

| Entity | Folder | Answers | Propagation |
|--------|--------|---------|-------------|
| `structure_owner` | `governance/structure/` | **Data** responsibility — is the data correct, complete, fit for purpose? | Inherited down the namespace; a structure with no declaration resolves its data owner(s) by walking **lineage** up to the owned sources. |
| `flow_owner` | `governance/flow/` | **Technical-execution** responsibility — scheduling, retries, failures, infrastructure (explicitly *not* data quality). | Inherited down the namespace; becomes the technical owner of the structure the flow **produces**. Does **not** propagate along data lineage. |

Both are `search_direction="parents"` entities (like the business dictionary):
the **nearest** declaration up the namespace wins.

## Models

Defined in `nld/governance/ownership/`. Both entities share one base shape.

### `OwnerBase` (→ `StructureOwner`, `FlowOwner`)

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Declaration name (inherited; defaults to file stem). |
| `team` | `str` | Accountable team. **Required.** |
| `contact` | `str \| None` | Escalation channel — slack channel or email. |
| `description` | `str \| None` | What this ownership covers. |
| `targets` | `list[str] \| None` | Specific structure/flow names this declaration applies to. **Omitted ⇒ namespace default** (applies to every entity beneath). When set, it is a **per-entity override** and wins over the namespace default. |

`StructureOwner` and `FlowOwner` add no fields — they exist as distinct types so
the registry can keep data and technical declarations apart. Each has a
`Namespaced…Owner` wrapper (`NldNamespacedBaseModelWrapper`) returned by registry
accessors.

## Filesystem & namespace

- Built-in entities `structure_owner` (`folder_name="governance/structure"`) and
  `flow_owner` (`folder_name="governance/flow"`), resolved relative to the
  project `entity_path`. With `entity_path: assets`, files live at
  `assets/governance/structure/<ns path>/<name>.yml`; root-namespace files sit
  directly under `governance/structure/`.
- The subdirectory path under the folder is the namespace, exactly like every
  other entity (`governance/structure/fr_company/owner.yml` → namespace
  `fr_company`).
- Registry accessors (local, no parent walk):
  `get_structure_owner(key, namespace)`, `get_structure_owner_dict(namespace)`,
  `get_structure_owner_keys(namespace)`, and the `get_flow_owner*` equivalents.

## Resolution semantics

Resolution lives in `nld/governance/lookup.py` and consumes the **flow
dependency graph** (see `guide-flows` / `how-to-trace-flow-lineage`).

- **Structure → (data owner(s), technical owner(s))**
  - *Data owner*: the nearest `structure_owner` declaration for the structure;
    if it has none of its own, the **union** of the owners of all upstream
    **sources** reached by walking lineage. A derived structure fed by several
    owned sources is owned jointly by all of them.
  - *Technical owner*: the `flow_owner` of the flow that **produces** the
    structure. A source structure (no producing flow) has **no** technical
    owner.
- **Flow → technical owner**: the nearest `flow_owner` declaration.

A per-entity override (`targets` naming the structure/flow) always beats the
namespace default at the same or a deeper level.

## CLI

```
nld ownership resolve --structure <name> --namespace <ns> [--format text|json]
nld ownership resolve --flow <name>      --namespace <ns> [--format text|json]
nld ownership resolve --namespace <ns>                    [--format text|json]
nld ownership list   [--namespace <ns>]
```

- `resolve --structure` emits the (data owner(s), technical owner(s)) pair.
- `resolve --flow` emits the technical owner.
- `resolve --namespace` only (no `--structure`/`--flow`) resolves the pair for
  **every** structure under that namespace and its descendants.
- `list` shows the declarations visible from a namespace (nearest wins).
- Human-friendly table by default; `--format json` for the full machine-readable
  payload, including resolution provenance (declared vs. resolved-via-lineage).

## Examples

`governance/structure/fr_company/owner.yml` — a namespace default:

```yaml
name: fr_company_owner
team: Ops
contact: "#ops-data"
description: Namespace default for fr_company
```

`governance/flow/owner.yml` — root flow-owner default, overridden deeper:

```yaml
# governance/flow/owner.yml
name: default_flow_owner
team: Data Eng
contact: "#pipelines"
description: Default technical owner for all flows
```

```yaml
# governance/flow/legal_unit_activity/owner.yml  (override for that subtree)
name: legal_unit_activity_flow_owner
team: Ops Eng
contact: "#ops-pipelines"
description: Technical owner override for legal_unit_activity flows
```

A per-entity override using `targets`:

```yaml
name: critical_table_owner
team: Finance Data
contact: "#finance-data"
targets:
  - refined_company_revenue   # only this structure; siblings keep the default
```

## Relationship to other entities

- **Flows** (`guide-flows`) define the producer of each structure and the
  dependency graph that lineage resolution walks.
- **Structures** (`guide-structures`) are the subject whose data ownership is
  resolved.
- Resolution reuses the same flow-dependency graph as `nld flow deps`
  (`how-to-trace-flow-lineage`).
