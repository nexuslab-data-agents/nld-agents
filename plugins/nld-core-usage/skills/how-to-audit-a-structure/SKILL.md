---
name: how-to-audit-a-structure
description: >
  Author a StructureAudit YAML that records the measured facts about a
  structure (target, run metadata, per-column coverage and value
  distributions), validate it against the real structure with
  `nld structure audit validate`, and render a markdown report with
  `nld structure audit render`. Use when you have measured a structure's
  columns and want a versioned, checkable audit committed next to the data.
user-invocable: true
---

# How to Audit a Structure

**Classification**: Atomic Skill | Structure Analysis

---

## Definition

- **What**: Author a `StructureAudit` YAML under `assets/audits/structure/`
  capturing a structure's target, run metadata, and per-column coverage and
  value distributions, then validate and render it with the CLI.
- **When**: After you have measured a structure's columns (row counts, non-null
  coverage, distinct counts, value distributions) and want those measurements
  recorded as a versioned entity rather than free-form notes.
- **Why**: A `StructureAudit` is a checkable, machine-readable source of truth.
  `validate` confirms every audited column is an actual field of the referenced
  structure, so a renamed or dropped column surfaces as an error instead of a
  stale figure. `render` turns the audit into a standard markdown report.

For the entity internals (models, fields, namespace resolution, registry
accessors), see the `guide-structure-audit` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- The audited structure must already exist under the entity path
  (`<entity_path>/structure/<ns>/...`).
- The measurements themselves (coverage, distinct counts, distributions) come
  from querying the data — this skill records them; it does not compute them.

---

## Filesystem layout

StructureAudits are the built-in `structure_audit` entity
(`folder_name="audits/structure"`, resolved relative to `entity_path`). With
`entity_path: assets`, files live at:

```
assets/audits/structure/<ns path>/<audit_name>.yml      # namespaced
assets/audits/structure/<audit_name>.yml                # root namespace
```

The audit's `name:` (and file stem) is the **audited structure name, with no
version suffix**. A `prd` audit keeps the bare structure name
(`raw_web_hr_wttj_jobs`); a non-production audit appends its environment
(`raw_web_hr_wttj_jobs_dev`).

---

## The audit file

```yaml
name: raw_web_hr_wttj_jobs                 # the audited structure (prd)
description: Data analysis audit of the WTTJ jobs raw table
structure: wttj.raw_web_hr_wttj_jobs       # NldEntityReference (kept as a string)
target:
  environment: prd                         # dev / stg / prd (required)
  connector_type: postgresql
  database: nld_isis_clh
  schema: acquisition_web_hr
  table: raw_web_hr_wttj_jobs
metadata:
  audited_at: 2026-04-04T00:00:00          # ISO 8601 timestamp
  row_count: 1251
  sampling:
    sampled: false                         # true -> add method/sample_size/fraction
  date_coverage:                           # omit when there is no date dimension
    field_characterisation: rec_source_extraction_tst
    from: 2025-10-19
    to: 2026-04-01
columns:
  cd_job_reference:                        # key sets the column name
    data_type: CHARACTER VARYING
    nullable: false
    primary_key: true
    coverage: { non_null: 1251, pct: 100.0, distinct: 1251 }
  contract_type:
    data_type: CHARACTER VARYING
    nullable: false
    coverage: { non_null: 1251, pct: 100.0, distinct: 8 }
    distribution:                          # low-cardinality columns only
      top_n: 10
      truncated: false                     # true when distinct > top_n
      values:
        - { value: full_time, count: 884, pct: 70.7 }
        - { value: internship, count: 171, pct: 13.7 }
  ds_salary:
    data_type: NUMERIC
    nullable: true
    coverage: { non_null: 217, pct: 17.3, distinct: 95, min: 6, max: 70000000 }
    notes: Sparse free-text salary, low coverage
```

Key rules:

- **`structure`** is an `NldEntityReference` string
  (`"<namespace>.<structure_name>"`). Keep it a string; never inline the
  structure body. Every audited column must be a field of this structure or
  `validate` fails.
- **`target.environment`** is required. Add `connection`, `connector_type`,
  `database`, `schema`, `table` to make the audit reproducible across
  environments.
- **`metadata.sampling`**: set `sampled: false` for a full pass. When `true`,
  add `method`, `sample_size`, and/or `fraction` (0–1) to describe how the
  sample was drawn.
- **`metadata.date_coverage`** is measured on the field carrying
  `field_characterisation` (e.g. `rec_source_extraction_tst`), not a hard-coded
  column. Omit the block for structures with no date dimension.
- **`coverage`** records `non_null`, `pct` (non-null over total), and optionally
  `distinct`, `min`, `max`.
- **`distribution`** is for low-cardinality columns. Cap at `top_n` (default
  `10`), set `truncated: true` when the column has more distinct values than
  listed, and order `values` by `count` descending.
- Record only **measured facts**. Field-selection decisions are not part of the
  entity.

---

## The commands

```
nld structure audit list   [--namespace <ns>]
nld structure audit info    --name <audit> [--namespace <ns>]
nld structure audit validate [--name <audit>] [--namespace <ns>]
nld structure audit render  --name <audit> [--namespace <ns>] [--stdout]
                            [--override-output-folder-path <dir>]
```

| Command | Purpose |
|---------|---------|
| `list` | List the audits visible from a namespace. |
| `info` | Print an audit's target, metadata, columns, and distributions. |
| `validate` | Resolve the referenced structure and check every audited column exists on it. Validates one audit with `--name`, or **all** visible audits when omitted. Exits non-zero and lists the offending columns when invalid. |
| `render` | Render the audit to a standard markdown report. Writes to a timestamped folder under `output/` by default; `--stdout` prints it; `--override-output-folder-path` chooses the folder. |

---

## Process

1. **Confirm the structure exists**
   (`nld structure info --name <s> --namespace <ns>`).
2. **Measure** the structure's columns (row count, non-null coverage, distinct
   counts, min/max, value distributions for low-cardinality columns).
3. **Author the audit** at `assets/audits/structure/<ns>/<structure>.yml`
   following the template above, naming it after the audited structure.
4. **List** to confirm discovery:
   `nld structure audit list --namespace <ns>`.
5. **Inspect**: `nld structure audit info --name <audit> --namespace <ns>`.
6. **Validate** (the gate):
   `nld structure audit validate --namespace <ns>`. Fix any reported column that
   is not a field of the structure (typically a typo or a drifted column name).
7. **Render** the report when you need a readable artifact:
   `nld structure audit render --name <audit> --namespace <ns>`.

---

## Cross-references

- Architectural reference: `guide-structure-audit` skill.
- The audited structures themselves: `guide-structures`.
- Column naming prefixes (`cd_`, `id_`, `dt_`, …) in audited columns: see the
  `nld-data-conventions` skills.
