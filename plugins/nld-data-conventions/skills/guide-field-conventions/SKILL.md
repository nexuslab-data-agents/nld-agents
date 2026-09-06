---
name: guide-field-conventions
description: >
  NLD data conventions for fields — column naming prefixes (cd_, ds_, dt_, ts_,
  fl_, nb_, yr_, id_, num_) and field characterisations (record lifecycle tracking,
  logical deletion, source tracking, UPSERT behavior control).
user-invocable: false
---

# Guide: Field Conventions

Reference for NLD field-level data conventions — column naming and field
characterisations.

## When to Use

Activate this guide when the agent is:
- Naming new columns in a structure YAML
- Adding or modifying field characterisations in field templates
- Working with record lifecycle tracking fields (ts_inserted_at, ts_updated_at)
- Working with logical deletion fields (fl_deleted, ts_deleted_at)
- Working with UPSERT behavior (exclude_from_match, exclude_from_update)

## Documentation

| Document | Path |
|----------|------|
| Field naming convention | `${CLAUDE_PLUGIN_ROOT}/docs/field/field-naming-convention.md` |
| Field characterisations | `${CLAUDE_PLUGIN_ROOT}/docs/field/field-characterisation.md` |

### Key Topics

**Column naming** — all columns use semantic prefixes:
- `cd_` (code), `ds_` (description/string), `dt_` (date), `ts_` (timestamp)
- `fl_` (flag/boolean), `nb_` (number/count), `yr_` (year), `id_` (identifier), `num_` (numeric)
- **`id_` vs `cd_`**: a field is never both. `id_<entity>` = a unique identifier (own id or a foreign key to another id), native type, no trailing `_id`, no `cd_` prefix. `cd_<x>` = a code/slug/category, always VARCHAR. `cd_<x>_id` is invalid — use `id_<x>` (identifier) or `cd_<x>` (code). In a referential the composite key is a code (`cd_genre = 'igdb-31'`) and each source id is `id_igdb_genre`, never `cd_igdb_genre_id`.
- Source/Landing/Raw layers keep original source names (no prefix, no translation)
- Refined layer is the translation boundary — all names in English with prefixes
- Source timestamps must map to template fields (`ts_src_inserted_at`, `ts_src_updated_at`), never custom columns

**Field characterisations** — metadata annotations on field templates:
- Record lifecycle: `rec_insert_tst`, `rec_insert_by`, `rec_last_update_tst`, `rec_last_update_by`
  (the two `_by` columns are built-in from nld-core 0.1.2a4; the framework never
  fills them, but it keeps `rec_insert_by` out of the UPSERT `UPDATE SET`)
- Logical deletion: `rec_deletion_flag`, `rec_deletion_tst`
- Source tracking: `src_extraction_tst`, `src_insert_tst`, `src_update_tst`
- Data format: `epoch_ms` (timestamp as Unix epoch milliseconds)
- UPSERT control: `exclude_from_match`, `exclude_from_update`

## Cross-References

- The prefixes here name a **column** by its content type (`cd_`, `ds_`, …). The
  prefix that names a whole **table** by its type — `R_`/`F_`/`M_` (business),
  `DIM_`/`DTM_` (consumer), `P_` parameter, `W_` work, `T_` technical — is a
  separate convention. Don't stop at column prefixes: for `p_` (a
  manually-curated parameter / mapping table) and the rest, see "Structure naming
  by type" in the `guide-structure-conventions` skill.
- For structure-level conventions (characterisations, ordering, templates), see
  the `guide-structure-conventions` skill.
