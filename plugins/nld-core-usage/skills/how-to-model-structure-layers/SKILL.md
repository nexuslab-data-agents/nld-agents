---
name: how-to-model-structure-layers
description: >
  Author an nld-core StructureModel: record a structure's join links to its
  same-layer siblings (field mappings + cardinality), then validate them with
  `nld structure model validate`. A StructureModel captures joins **within a
  layer**, not raw→refined lineage (that lives in the transformation SQL and the
  StructureAudit). Covers the model file schema, the same-layer rule, how to find
  joinable siblings, the one-model-per-structure convention, and the CLI.
user-invocable: true
---

# How to Model Structure Layers

**Classification**: Atomic Skill | Structure Modeling

---

## Definition

- **What**: Author a `StructureModel` YAML that records, for one structure, its
  join `links` to **other structures of the same layer** — each link carrying
  `left_to_right_mappings` (join keys) and a `cardinality` — then validate it.
- **When**: After the structures exist, whenever you add or review
  `structure_model/**` files.
- **Why**: A `StructureModel` is checkable, queryable join metadata. `validate`
  confirms every mapped field exists on both sides, so a renamed/dropped column
  surfaces as an error instead of silently rotting.

For the entity internals (models, cardinality enum, namespace resolution, Python
API), see `guide-structure-model`. For the layer definitions, see
`nld-data-conventions:guide-data-layers`.

---

## The same-layer rule

> **Only link two structures when they belong to the same layer.**

A `StructureModel` records the join links a structure has to *other structures of
the **same** layer*. It is **not** cross-layer lineage: the path
raw → refined → business → consumer is captured by the transformation SQL and by
`StructureAudit`, **never** by a structure_model. A link whose `left_structure`
and `right_structure` resolve to **different** layers (e.g. a `refined_*` to its
`raw_*` source, or a `v_r_*` exposure view to its `r_*` base table) is **invalid**
— it is lineage, not a join.

So the two link kinds you model are both **within one layer**:
- **cross-entity foreign keys** (`refined_web_hr_wttj_job → refined_web_hr_wttj_company`),
- **hierarchy parent/child** (`refined_*_activity_hierarchy → refined_*_activity_section`).

### Identifying a structure's layer

1. **Read `properties.layer`** on the structure — the authoritative signal
   (`landing`, `raw_json`, `raw`, `raw_expo`, `refined`, `refined_expo`,
   `business`, `business_expo`, `consumer`, `consumer_expo`).
2. **If absent, infer from the name prefix / location** (a fallback for older
   structures that don't set the property):

   | Name prefix / location | Layer |
   |------------------------|-------|
   | `landing_*` | `landing` |
   | `raw_json_*` | `raw_json` |
   | `raw_*` | `raw` |
   | `v_raw_*_latest` | `raw_expo` |
   | `refined_*` | `refined` |
   | `v_refined_*` | `refined_expo` |
   | `r_*`, `f_*` (business product) | `business` |
   | `v_r_*`, `v_f_*` (business product) | `business_expo` |
   | base tables in a consumer product | `consumer` |
   | `v_*` views in a consumer product | `consumer_expo` |

   **Exposure views (`v_` prefixed) are their own layer** — a `v_r_` view links to
   other `v_r_` views, never to the `r_` table it is built from. A structure
   tagged `external_source` (a reference consumed from another product) belongs to
   *its own* source layer and is never a same-layer partner here.

---

## Finding the joinable siblings

For the structure you are modelling, the links come from its **own** join columns
to **sibling structures in the same layer**:

- **`references` fields** — a foreign-key column pointing at another same-layer
  structure's key ⇒ a `many_to_one` link
  (e.g. `r_fr_postal_code.cd_fr_department → r_fr_department_region`).
- **`hierarchy_parent_info` fields** — a parent-level code joining the same-layer
  level/bridge structure ⇒ `many_to_one`.

(See `nld-data-conventions:guide-field-conventions` for these characterisations.)

---

## One model per structure — always

Every owned structure gets its **own** `structure_model` file, named after it,
with that structure as the `left_structure` of every link. When the structure has
same-layer siblings, list them under `links:`; when it has **none** (a standalone
dimension — most code/category/range tables), still create the file with
`links: {}`. The empty model is a deliberate, positive statement — "reviewed, no
same-layer links" — not an omission. **Never leave a structure without a model
file.**

A model carries only `name:` and `links:` — **do not add a `description:` by
default** (set it only when a link genuinely needs an explanatory note).

---

## Filesystem layout

StructureModels are the built-in `structure_model` entity
(`folder_name="structure_model"`, resolved relative to `entity_path`). With
`entity_path: assets`:

```
assets/structure_model/<ns path>/<model_name>.yml      # namespaced
assets/structure_model/<model_name>.yml                # root namespace
```

The file `name:` must match the model name (the file stem is used when omitted).

---

## The model file

```yaml
name: refined_web_hr_wttj_job              # the model is about this structure
links:
  company:                                 # link name
    left_structure: wttj.refined_web_hr_wttj_job        # associated structure (same layer)
    right_structure: wttj.refined_web_hr_wttj_company   # joined sibling (same layer)
    cardinality: many_to_one
    left_to_right_mappings:
      - cd_organization_reference          # identical both sides -> shorthand
      # - {left: cd_org_ref, right: org_ref}  # names differ -> explicit pair
```

Key rules:

- **`left_structure` / `right_structure`** are `NldEntityReference` strings
  `"<namespace>.<structure_name>"` (leading `.` or no dot = root namespace). They
  stay strings on disk and resolve on demand.
- **Associated structure on the left.** With one model per structure, the
  structure the model is named after is the `left_structure` of every link.
- **`left_to_right_mappings`** are the join keys: a single column name (identical
  on both sides) or a `{left, right}` pair (names differ). Every column must exist
  or `validate` fails.
- **`cardinality`**: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`,
  `one_to_zero`, `zero_to_one`, `many_to_zero`, `zero_to_many`. A child→parent FK
  is `many_to_one`.
- **`condition`** (optional) — a filter for conditional joins;
  **`attributes`** (optional) — free-form metadata (e.g. `{join_type: left}`).

---

## The commands

```
nld structure model list   [--namespace <ns>]
nld structure model info    --name <model> [--namespace <ns>]
nld structure model validate [--name <model>] [--namespace <ns>]
```

| Command | Purpose |
|---------|---------|
| `list` | Models visible from a namespace, with link counts. |
| `info` | A model's links: structures, cardinality, condition, attributes, field mappings. |
| `validate` | Resolve each link's structures and check every mapped field exists. One model with `--name`, or **all** visible models when omitted. Non-zero exit + offending fields when invalid. |

---

## Process

1. **List the owned structures and their layers** (`nld structure model list` /
   read `properties.layer`, or apply the prefix table).
2. **For each structure**, collect its `references` / `hierarchy_parent_info`
   columns and resolve each to the sibling it keys into. **Keep only same-layer
   siblings.**
3. **Author** `assets/structure_model/<ns>/<structure>.yml` for **every** owned
   structure: one link per same-layer sibling, or `links: {}` when there is none.
4. **Validate** (the gate): `nld structure model validate`. Fix any reported
   missing field; re-run until clean. Commit the model alongside the structures.

---

## Worked example

`clh/business/dwh` geography, business layer:

```yaml
# assets/structure_model/fr_geography/r_fr_postal_code.yml
name: r_fr_postal_code
links:
  department:                                  # cd_fr_department is a `references` field
    left_structure: fr_geography.r_fr_postal_code
    right_structure: fr_geography.r_fr_department_region   # same (business) layer
    cardinality: many_to_one
    left_to_right_mappings:
      - cd_fr_department
```

The parallel `v_r_fr_postal_code` model links `v_r_fr_department_region` (both
`business_expo`). Standalone dimensions (activity, category, …) still get a model
with empty links:

```yaml
# assets/structure_model/fr_company/r_fr_legal_unit_activity.yml
name: r_fr_legal_unit_activity
links: {}
```

---

## Anti-patterns

- ❌ A link whose two sides are **different layers** (`refined_*` → its `raw_*`
  source; `v_r_*` → `r_*`; consumer view → business view). That is lineage, not a
  join — remove it.
- ❌ Leaving a structure with **no** model file. A standalone table still gets a
  file with `links: {}`.
- ❌ Treating a `v_*` exposure view as the same layer as its base table.
- ❌ Modelling a link to an `external_source` consumed structure.

---

## Cross-references

- Architectural reference: `guide-structure-model`.
- Layer definitions / field characterisations (`references`,
  `hierarchy_parent_info`): `nld-data-conventions:guide-data-layers`,
  `:guide-field-conventions`.
- Authoring the structures themselves: `how-to-document-a-structure`.
- Canonical concept naming: `how-to-use-business-dictionary`.
