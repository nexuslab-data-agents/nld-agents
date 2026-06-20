---
name: guide-structure-audit
description: >
  Architectural guide for the nld-core StructureAudit entity — a namespaced,
  machine-readable data-analysis audit of one structure (target environment,
  run metadata, per-column coverage and value distributions), its validation
  against the referenced structure, the registry accessors, and the
  `nld structure audit` CLI. Read when working on structure_audit definitions,
  audit YAML under assets/audits/structure/, or the audit code in
  nld/structure/audit/.
user-invocable: false
---

# Guide: Structure Audits

Architectural reference for the nld-core `StructureAudit` entity — a
standardised, machine-readable record of the *measured* facts about one
structure at a point in time.

## When to Use

Activate this guide when working on:
- `structure_audit` YAML definitions under `assets/audits/structure/`
- `nld/structure/audit/` code (audit, target, metadata, column, distribution)
- The `nld structure audit` CLI (list / info / validate / render)
- Capturing column coverage and value distributions for a structure

For the step-by-step authoring/validation workflow, see
`how-to-audit-a-structure`.

## What an audit captures (and what it does not)

A `StructureAudit` records *measurements only*: the environment it was run
against, run metadata (sampling, date coverage, row count), and a per-column
listing carrying coverage and the column's value distribution. Field-selection
decisions — which columns to keep in a downstream layer and why — are an agent
judgement, **not** a measurement, and are deliberately excluded from the entity.

## Models

Defined in `nld/structure/audit/`.

### `StructureAudit(NldNamedBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Audit name (inherited; defaults to file stem). |
| `description` | `str \| None` | Free-text description. |
| `structure` | `NldEntityReference[Structure]` | Reference to the audited structure (`<namespace>.<structure_name>`). |
| `target` | `AuditTarget` | Environment and physical location the audit was run against. |
| `metadata` | `AuditMetadata` | Run provenance: sampling, date coverage, row count. |
| `columns` | `dict[str, AuditColumn]` | Per-column listing; each key sets the column's `name`, in ordinal order. |

Helpers: `get_column(name)`, `get_columns()`, `get_column_names()`,
`has_column(name)`, `get_columns_with_distribution()`, and `_is_valid()`
(see Validation).

### `AuditTarget(NldBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `environment` | `str` | Target environment (`dev` / `stg` / `prd`). Required. |
| `connection` | `str \| None` | Name of the nld connection used to query the data. |
| `connector_type` | `str \| None` | Connector type (e.g. `postgresql`, `bigquery`). |
| `database` | `str \| None` | Database the audited structure lives in. |
| `schema` | `str \| None` | Schema the audited structure lives in (alias of `schema_`). |
| `table` | `str \| None` | Physical table or view name that was audited. |

### `AuditMetadata(NldBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `audited_at` | `str \| None` | ISO 8601 timestamp when the audit was produced. A bare YAML date is widened to midnight. |
| `row_count` | `int \| None` | Total number of rows in the audited structure (or sample). |
| `sampling` | `AuditSampling` | How the figures were drawn. |
| `date_coverage` | `AuditDateCoverage \| None` | Time span the audited data covers, when pertinent. |

- `AuditSampling`: `sampled` (`bool`, default `False`), `method` (`str \| None`),
  `sample_size` (`int \| None`), `fraction` (`float \| None`, 0–1). When
  `sampled` is `False` the figures cover every row and the other fields are
  irrelevant.
- `AuditDateCoverage`: `field_characterisation` (the field characterisation the
  span is measured on, e.g. `rec_source_extraction_tst`), `from` (alias of
  `from_`), `to`. Omit the whole block for structures with no date dimension.

### `AuditColumn(NldNamedBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Column name (defaults to the dict key in `columns`). |
| `data_type` | `str \| None` | Database data type of the column. |
| `nullable` | `bool \| None` | Whether the column is nullable in the structure. |
| `primary_key` | `bool` | Whether the column is part of the structure's primary key (default `False`). |
| `coverage` | `AuditColumnCoverage` | Measured coverage and value-range statistics. |
| `distribution` | `AuditDistribution \| None` | Value distribution (top-N buckets). |
| `notes` | `str \| None` | Free-text remarks about the column. |

- `AuditColumnCoverage`: `non_null` (`int`), `pct` (`float`, non-null over total),
  `distinct` (`int`), `min`, `max` (numeric or temporal columns).
- `AuditDistribution`: `top_n` (`int`, default `10`), `truncated` (`bool`, `True`
  when distinct values exceed `top_n`), `values` (`list[AuditDistributionValue]`).
- `AuditDistributionValue`: `value` (the distinct value; `null` counts missing
  values), `count` (`int`), `pct` (`float \| None`). Buckets are ordered by
  count descending.

### `NamespacedStructureAudit`

A `NldNamespacedBaseModelWrapper[StructureAudit]` — a `StructureAudit` together
with the namespace it was loaded from. Returned by registry accessors.

## Filesystem & namespace

- Built-in entity `structure_audit`, `folder_name="audits/structure"`, resolved
  relative to the project `entity_path`. With `entity_path: assets`, files live
  at `assets/audits/structure/<ns path>/<audit>.yml`; root namespace files sit
  directly under `assets/audits/structure/`.
- Registry accessors: `get_structure_audit(key, namespace)`,
  `get_structure_audit_dict(namespace)`,
  `get_structure_audit_keys(namespace)`,
  `list_structure_audit_keys(namespace)` (local, no parent walk).

## Naming convention

An audit's name (and file stem) is the audited structure name, with **no version
suffix**. Production is the audited-by-default reference, so a `prd` audit keeps
the bare structure name (`raw_web_hr_wttj_jobs`); a non-production audit appends
its environment (`raw_web_hr_wttj_jobs_dev`).

## Reference semantics

`structure` is an `NldEntityReference[Structure]`, a `str` of the form
`"<namespace>.<structure_name>"`. It is **stored as a string** and resolved on
demand via `NldEntityReference.resolve(entity_type)`. Keep it as a string in
YAML; never inline the structure body.

## Validation

`StructureAudit._is_valid()` resolves the referenced structure from the registry
and checks that **every** audited column is an actual field of that structure. It
returns a list of error strings (empty == valid) and requires an active
`NldExecutionContext` with loaded entities.

The CLI surfaces this:

```
nld structure audit validate [--name <audit>] [--namespace <ns>]
```

Validates one audit (`--name`) or all visible audits, and exits non-zero
(listing the offending columns) when an audited column is not a field of the
referenced structure.

Inspect, list, and render:

```
nld structure audit list   [--namespace <ns>]
nld structure audit info    --name <audit> [--namespace <ns>]
nld structure audit render  --name <audit> [--namespace <ns>] [--stdout]
                            [--override-output-folder-path <dir>]
```

`render` produces a standard markdown report from the audit; by default it
writes to a timestamped folder under `output/`, or use `--stdout` to print and
`--override-output-folder-path` to choose the folder.

## Relationship to other entities

- **Structures** (`guide-structures`) are the subject an audit measures and
  validates against.
- **Structure models** (`guide-structure-model`) map columns *across*
  structures; an audit measures the columns *within* one structure. They are
  complementary.

## Example

```yaml
name: raw_web_hr_wttj_jobs                 # the audited structure name (prd)
description: Data analysis audit of the WTTJ jobs raw table
structure: wttj.raw_web_hr_wttj_jobs
target:
  environment: prd
  connector_type: postgresql
  database: nld_isis_clh
  schema: acquisition_web_hr
  table: raw_web_hr_wttj_jobs
metadata:
  audited_at: 2026-04-04T00:00:00
  row_count: 1251
  sampling:
    sampled: false
  date_coverage:
    field_characterisation: rec_source_extraction_tst
    from: 2025-10-19
    to: 2026-04-01
columns:
  cd_job_reference:
    data_type: CHARACTER VARYING
    nullable: false
    primary_key: true
    coverage: { non_null: 1251, pct: 100.0, distinct: 1251 }
  contract_type:
    data_type: CHARACTER VARYING
    nullable: false
    coverage: { non_null: 1251, pct: 100.0, distinct: 8 }
    distribution:
      top_n: 10
      truncated: false
      values:
        - { value: full_time, count: 884, pct: 70.7 }
        - { value: internship, count: 171, pct: 13.7 }
  ds_salary:
    data_type: NUMERIC
    nullable: true
    coverage: { non_null: 217, pct: 17.3, distinct: 95, min: 6, max: 70000000 }
    notes: Sparse free-text salary, low coverage
```
