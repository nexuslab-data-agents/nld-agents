---
name: guide-structure-model
description: >
  Architectural guide for the nld-core StructureModel entity — inter-structure
  links, field mappings, cardinality, namespace resolution, reference semantics
  (NldEntityReference), validation, and the `nld structure model` CLI. Read when
  working on structure_model definitions (same-layer join links between
  structures) or the StructureModel code in nld/structure/structure_model/.
user-invocable: false
---

# Guide: Structure Models

Architectural reference for the nld-core `StructureModel` system — how
structures are linked to each other with validated, field-level mappings.

## When to Use

Activate this guide when working on:
- `structure_model` YAML definitions (same-layer join links between structures)
- `nld/structure/structure_model/` code (model, link, cardinality)
- The `nld structure model` CLI (list / info / validate)
- Reasoning about reference resolution (`NldEntityReference`) on load

For the step-by-step authoring workflow + the **same-layer rule** (a
structure_model links only structures of the *same* layer; cross-layer
raw→refined lineage lives in the transformation SQL + `StructureAudit`, not a
structure_model), see `how-to-model-structure-layers`.

## Models

Defined in `nld/structure/structure_model/`.

### `StructureModel(NldNamedBaseModel)`

A namespaced grouping of links between structures.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Model name (inherited; defaults to file stem). |
| `description` | `str \| None` | Free-text description. |
| `links` | `dict[str, StructureModelLink]` | Named links; each key sets the link's `name`. |

Helpers: `get_link(name)`, `get_links()`, `get_link_names()`,
`has_link(name)`, and `_is_valid()` (see Validation).

### `StructureModelLink(NldNamedBaseModel)`

A directional link between two structures.

| Field | Type | Purpose |
|-------|------|---------|
| `left_structure` | `NldEntityReference[Structure]` | Left structure reference (by convention, the structure the model is about). |
| `right_structure` | `NldEntityReference[Structure]` | Right structure reference (the joined table). |
| `cardinality` | `StructureModelCardinality` | Join cardinality (required). |
| `left_to_right_mappings` | `list[StructureModelColumnMapping]` | Join keys; each item is a bare column name (identical on both sides) or a `{left, right}` pair when names differ. Non-empty. |
| `condition` | `str \| None` | Optional filter expression for conditional links. |
| `attributes` | `dict \| None` | Optional free-form metadata. |

### `StructureModelColumnMapping(NldBaseModel)`

A single join-key pairing: `left` and `right` column names. A bare YAML string
(e.g. `organization_reference`) is shorthand for an identical `{left, right}`
pair; use the explicit `{left, right}` form when the names differ.

### `StructureModelCardinality` (enum)

`one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`, `one_to_zero`,
`zero_to_one`, `many_to_zero`, `zero_to_many`.

## Filesystem & namespace

- Built-in entity `structure_model`, `folder_name="structure_model"`, resolved
  relative to the project `entity_path`. With `entity_path: assets`, files live
  at `assets/structure_model/<ns path>/<model>.yml`; root namespace files sit
  directly under `assets/structure_model/`.
- Registry accessors: `get_structure_model(key, namespace)`,
  `get_structure_model_keys(namespace)`, `get_structure_model_dict(namespace)`,
  `list_structure_model_keys(namespace)` (local, no parent walk),
  `get_structure_models(keys, namespace)`. The structure-model entity uses the
  default (children) search direction.

## Reference semantics (important)

`left_structure` / `right_structure` are `NldEntityReference[Structure]`, a
`str` subclass of the form `"<namespace>.<structure_name>"` (leading dot or no
dot → root namespace). They are **stored as strings** and resolved on demand via
`NldEntityReference.resolve(entity_type)`, which deep-copies the target from the
registry.

Reference fields are deliberately **not inlined** during `from_dict` /
`load_entities`: `NldNamedBaseModel.from_dict` skips reference resolution for
`NldEntityReference`-typed fields (inlining the resolved object would break the
str-typed field on re-validation). Keep references as strings in YAML; never
embed the structure body.

## Validation

`StructureModel._is_valid()` resolves each link's left and right structures from
the registry and checks that **every** column in `left_to_right_mappings` exists on the
corresponding structure. It returns a list of error strings (empty == valid) and
requires an active `NldExecutionContext` with loaded entities.

The CLI surfaces this:

```
nld structure model validate [--name <model>] [--namespace <ns>]
```

Validates one model (`--name`) or all visible models, prints OK/FAIL per model,
and exits non-zero (listing the offending fields) when any mapping is invalid.

Inspect and list:

```
nld structure model list [--namespace <ns>]
nld structure model info  --name <model> [--namespace <ns>]
```

## Relationship to other entities

- **Structures** (`guide-structures`) are the endpoints a model links.
- **Business dictionary** (`guide-business-dictionary`) maps names →
  canonical *concepts*; a structure model maps *join keys between same-layer
  structures*. They are complementary: dictionary for vocabulary, structure
  model for same-layer joins. (Cross-layer raw→refined lineage lives in the
  transformation SQL + `StructureAudit`, not a structure model.)

## Convention: one model per structure, associated structure on the left

A model is named after a structure and catalogues that structure's **known join
links**. **Standard rule:** the associated structure is always the
`left_structure` of every link; `right_structure` is the joined table. Join keys
go in `left_to_right_mappings` (left column = a column on the associated
structure, right column = a column on the joined table).

## Example

```yaml
name: refined_web_hr_wttj_job          # the model is about this structure
links:
  company:                             # same-layer join to another entity (FK)
    left_structure: wttj.refined_web_hr_wttj_job
    right_structure: wttj.refined_web_hr_wttj_company   # both refined
    cardinality: many_to_one
    left_to_right_mappings:
      - cd_organization_reference      # identical on both sides
```

> Both sides are the **same layer** (`refined`). A link to the structure's own
> `raw_web_hr_wttj_jobs` source would be **cross-layer lineage**, not a
> structure_model link — see `how-to-model-structure-layers`.
