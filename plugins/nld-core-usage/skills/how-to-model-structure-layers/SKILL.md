---
name: how-to-model-structure-layers
description: >
  Model the relationship between structures of different layers (e.g. a raw
  table and its refined table) with an nld-core StructureModel. Declares
  field-level mappings + cardinality between two structures, then validates them
  against the real structures with `nld structure model validate`. Use when you
  want explicit, checkable lineage between raw and refined (or view and refined,
  raw_json and raw).
user-invocable: true
---

# How to Model Structure Layers (raw ↔ refined)

**Classification**: Atomic Skill | Structure Modeling

---

## Definition

- **What**: Author a `StructureModel` YAML that links two structures via named
  `links`, each carrying `left_to_right_mappings` (join keys) and a
  `cardinality`, then validate it with the CLI.
- **When**: After both layers exist as structures (e.g. `raw_web_hr_apec_companies`
  and `refined_web_hr_apec_company`) and you want the raw→refined mapping to be
  explicit, queryable, and validated — not just implicit in transformation SQL.
- **Why**: A `StructureModel` is checkable lineage. `validate` confirms every
  mapped field exists on both sides, so a renamed/dropped column surfaces as an
  error instead of silently rotting. It complements the business dictionary
  (which maps names to canonical *concepts*) by mapping *columns across layers*.

For the entity internals (models, cardinality enum, namespace resolution,
Python API), see the `guide-structure-model` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- Both referenced structures must already exist under the entity path
  (`<entity_path>/structure/<ns>/...`). Create/refresh them first
  (see the lakehouse `dev-structure-update` skill).
- nld-core with the `nld structure model` CLI (list/info/validate).

---

## Filesystem layout

StructureModels are the built-in `structure_model` entity
(`folder_name="structure_model"`, resolved relative to `entity_path`). With
`entity_path: assets`, files live at:

```
assets/structure_model/<ns path>/<model_name>.yml      # namespaced
assets/structure_model/<model_name>.yml                # root namespace
```

The file `name:` must match the model name (file stem is used when omitted).

---

## The model file

A model is named after a structure and lists that structure's join links.

```yaml
name: refined_web_hr_wttj_job              # the model is about this structure
description: Known join links for refined_web_hr_wttj_job
links:
  raw:                                     # link name
    left_structure: wttj.refined_web_hr_wttj_job        # the associated structure
    right_structure: wttj.raw_web_hr_wttj_jobs          # the joined table
    cardinality: one_to_one
    left_to_right_mappings:                # join keys
      - {left: cd_job_reference, right: job_reference}   # names differ -> pair
  company:
    left_structure: wttj.refined_web_hr_wttj_job
    right_structure: wttj.refined_web_hr_wttj_company
    cardinality: many_to_one
    left_to_right_mappings:
      - cd_organization_reference          # identical both sides -> shorthand
```

Key rules:

- **`left_structure` / `right_structure`** are `NldEntityReference` strings:
  `"<namespace>.<structure_name>"` (use a leading `.` or no dot for the root
  namespace). They stay strings on disk and are resolved on demand — do **not**
  inline the structure.
- **Standard rule: associated structure on the left.** When you keep one model
  per structure, the structure the model is named after is the `left_structure`
  of every link; `right_structure` is the joined table.
- **`left_to_right_mappings`** holds the **join keys**. Each entry is a single
  column name (when identical on both sides) or a `{left, right}` pair (when the
  names differ). The left column is on `left_structure`, the right on
  `right_structure`. Every column must exist or `validate` fails.
- **`cardinality`** is one of: `one_to_one`, `one_to_many`, `many_to_one`,
  `many_to_many`, `one_to_zero`, `zero_to_one`, `many_to_zero`, `zero_to_many`.
  Same-row cross-layer joins are `one_to_one`; a child→parent FK is `many_to_one`.
- **`condition`** (optional) — a filter expression for conditional joins.
- **`attributes`** (optional) — free-form metadata (e.g. `{join_type: left}`).

Prefer **one model per structure** (named after it), listing every table it
joins to — cross-layer (same row across raw/refined/…) and cross-entity (FK).

---

## The commands

```
nld structure model list   [--namespace <ns>]
nld structure model info    --name <model> [--namespace <ns>]
nld structure model validate [--name <model>] [--namespace <ns>]
```

| Command | Purpose |
|---------|---------|
| `list` | List the models visible from a namespace, with link counts. |
| `info` | Print a model's links: left/right structures, cardinality, condition, attributes, and each `field_mapping` (`left -> right`). |
| `validate` | Resolve each link's structures and check every mapped field exists. Validates one model with `--name`, or **all** visible models when omitted. Exits non-zero and lists the offending fields when invalid. |

---

## Process

1. **Confirm both structures exist** (`nld structure info --name <s> --namespace <ns>`).
2. **Author the model** at `assets/structure_model/<ns>/<entity>_layers.yml`
   following the template above. Put one link per layer pair you want lineage
   for (raw→refined; optionally view→refined, raw_json→raw).
3. **List** to confirm discovery: `nld structure model list --namespace <ns>`.
4. **Inspect**: `nld structure model info --name <model> --namespace <ns>` and
   eyeball the mappings.
5. **Validate** (the gate): `nld structure model validate --namespace <ns>`.
   Fix any reported missing fields (typically a rename drift between layers).
6. Re-run `validate` until clean; commit the model alongside the structures.

---

## Recipes

### Lineage for one entity, raw → refined
One link, `one_to_one`, raw columns on the left, refined on the right. Validate
with `--name`.

### Whole-namespace check in CI / pre-merge
`nld structure model validate --namespace apec` validates every model under the
namespace and exits non-zero on the first invalid mapping — drop it into a
pre-merge step so layer renames can't silently break lineage.

### Multi-layer chain
Add `raw_json_to_raw` and `view_to_refined` links (or separate models) to model
the full `raw_json → raw → view → refined` path; `validate` checks each hop.

---

## Guidelines for agents

- **Model after both layers exist**, then validate immediately — an unvalidated
  model is worse than none (it implies a checked lineage that isn't).
- **Left = upstream, right = downstream.** Keep the direction consistent
  (raw→refined) so `info` reads as a transformation map.
- **Pair with the dictionary, don't duplicate it.** The dictionary says
  `raison_sociale` and `ds_legal_name` both mean `legal_name`; the structure
  model says *this raw column becomes that refined column*. Use both.
- **A failing `validate` is a real signal** — usually a column was renamed or
  dropped in one layer. Fix the structures or the mapping, never silence it.

---

## Cross-references

- Architectural reference: `guide-structure-model` skill.
- Layer structures themselves: lakehouse `dev-structure-update`,
  `dev-data-refinement`.
- Canonical concept naming: `how-to-use-business-dictionary`,
  `nld-data-conventions`.
