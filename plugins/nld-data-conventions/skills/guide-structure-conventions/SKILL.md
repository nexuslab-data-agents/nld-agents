---
name: guide-structure-conventions
description: >
  NLD data conventions for structures — structure characterisations (primary_key,
  functional_key, unique), field ordering rules, structure templates, and table
  naming conventions per layer, including the business/consumer table prefixes
  (r_ referential, f_ fact, m_ mart, w_ working, p_ parameter, t_ technical,
  dim_/dtm_ consumer, v_ display views).
user-invocable: false
---

# Guide: Structure Conventions

Reference for NLD structure-level data conventions — characterisations, field
ordering, templates, and layer-specific rules.

## When to Use

Activate this guide when the agent is:
- Creating or modifying structure YAML files
- Naming a table or view in any layer (business prefixes: `r_` referential,
  `f_` fact, `m_` mart, `w_` working, `p_` parameter, `t_` technical;
  consumer: `dim_`/`dtm_`; display views: `v_<table>`)
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
- On `raw_*` tables the `primary_key` is always the functional key fields +
  `ts_src_extracted_at` (the raw layer keeps one record per extraction, so the
  functional key alone is not unique; `ts_src_extracted_at` is
  `exclude_from_upsert_match` so UPSERT still matches on the functional key)

## Cross-References

- For field-level conventions (column naming, characterisations), see the
  `guide-field-conventions` skill.
