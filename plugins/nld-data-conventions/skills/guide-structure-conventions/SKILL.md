---
name: guide-structure-conventions
description: >
  NLD data conventions for structures — structure characterisations (primary_key,
  functional_key, unique), field ordering rules, structure templates, and naming
  conventions for raw, refined, business, and consumer layers.
user-invocable: false
---

# Guide: Structure Conventions

Reference for NLD structure-level data conventions — characterisations, field
ordering, templates, and layer-specific rules.

## When to Use

Activate this guide when the agent is:
- Creating or modifying structure YAML files
- Defining primary keys, functional keys, or unique constraints
- Ordering fields in a structure definition
- Working with structure templates (raw_standard_tracking, refined_standard_tracking, etc.)
- Working with raw, refined, business, or consumer layer structures

## Documentation

| Document | Path |
|----------|------|
| Structure characterisations | `${CLAUDE_PLUGIN_ROOT}/docs/structure/structure-characterisation.md` |
| Structure conventions | `${CLAUDE_PLUGIN_ROOT}/docs/structure/structure-convention.md` |

### Key Topics

**Structure characterisations** — table-level metadata:
- `primary_key` — technical unique constraint, drives UPSERT conflict resolution
- `functional_key` — business identifier, drives DEDUPLICATED_SELECT deduplication
- `unique` — additional unique constraints

**Structure conventions**:
- Functional key must always be the first field in the `fields:` section
- Applies to `raw_*`, `v_raw_*_latest`, `refined_*`, business, and consumer structures
- Does NOT apply to externally-managed structures (`source_*`, `landing_*`, `raw_json_*`)

## Cross-References

- For field-level conventions (column naming, characterisations), see the
  `guide-field-conventions` skill.
