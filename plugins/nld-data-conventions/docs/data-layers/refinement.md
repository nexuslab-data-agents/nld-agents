# Refinement Layer

## Overview

The refinement layer transforms raw data into clean, standardized, typed columns suitable for business consumption. It sits between the raw layer (ingested JSON/flat data) and the business layer (business logic, joins, aggregations).

```
Raw Table → v_raw_*_latest (deduplicated view) → Refined Table → v_refined_* (exposed view)
```

## Input

The refinement always reads from a **raw latest view** (`v_raw_*_latest`), which provides deduplicated data using the `DEDUPLICATED_SELECT` strategy. This ensures the refinement operates on exactly one row per entity key.

## Output

A **refined table** with:
- Semantic column names using standard prefixes
- Proper SQL data types (not raw strings)
- A primary key matching the functional key of the raw source
- Tracking timestamps via the `refined_standard_tracking` template

## Field Naming Conventions

All refined fields use semantic prefixes. See [Column Convention](../field/field-naming-convention.md) for the full reference.

Summary of prefixes: `cd_` (code), `ds_` (description), `dt_` (date), `ts_` (timestamp), `fl_` (flag/boolean), `nb_` (number), `yr_` (year), `id_` (identifier), `num_` (numeric).

### Dual Field Pattern

For fields requiring transformation or validation, keep both the raw source value and the transformed value. The source value uses a `_src` suffix:

```sql
, tranche_effectifs AS cd_staff_range_src          -- Raw source value (as-is)
, coalesce(tranche_effectifs, '#') AS cd_staff_range  -- Cleaned/transformed value
```

```sql
, unite_purgee AS fl_purged_status_src             -- Raw string value
, CASE
    WHEN lower(unite_purgee) IN ('true','t','1') THEN true
    ELSE false
  END AS fl_purged_status                           -- Transformed boolean
```

This pattern enables:
- Audit trail: compare source vs transformed values
- Debugging: identify transformation issues
- Downstream flexibility: consumers can choose which version to use

## SQL Transformation Patterns

### Simple Rename
```sql
code AS cd_siren
```

### String to Boolean
```sql
CASE
  WHEN lower(flag_field) IN ('true','t','1','yes','y') THEN true
  WHEN lower(flag_field) IN ('false','f','0','no','n') THEN false
END AS fl_is_active
```

### String to Date with Bounds
```sql
LEAST(
  coalesce(
    CASE
      WHEN date_field::text ~ '^\d{4}-\d{2}-\d{2}$'
      THEN to_date(date_field::text, 'YYYY-MM-DD')
    END,
    DATE '1900-01-01'
  ),
  CURRENT_DATE + INTERVAL '1 month'
) AS dt_creation
```

### String to Integer
```sql
CASE
  WHEN nb_field ~ '^\d+$' THEN nb_field::int
END AS nb_employees
```

### Null Coalescing
```sql
coalesce(code_field, '#') AS cd_category
```

### JSON Field Extraction (from raw_data jsonb column)
```sql
raw_data->'page'->>'slug' AS cd_slug
, (raw_data->'page'->>'updated_at')::timestamp AS ts_source_updated_at
, (raw_data->'page'->'metas'->>'title')::text AS ds_page_title
```

## Tracking Timestamps

Every refined SQL must include these 6 tracking columns at the end of the SELECT:

```sql
, ts_src_extracted_at
, ts_src_inserted_at
, ts_src_updated_at
, ts_updated_at AS ts_prv_layer_updated_at
, CURRENT_TIMESTAMP AS ts_inserted_at
, CURRENT_TIMESTAMP AS ts_updated_at
```

These are provided by the `refined_standard_tracking` template in the structure YAML.

## Write Strategy

Refinement flows use `UPSERT` with `incremental: by_source_tst`:
- New rows are inserted
- Existing rows (matching primary key) are updated
- Incremental processing based on source timestamp changes

## Files Required

For each refined entity:

| File | Path | Purpose |
|------|------|---------|
| Flow YAML | `assets/flows/<ns>/refinement/refined_<prefix>_<entity>.yaml` | Flow configuration |
| SQL | `assets/flows/<ns>/refinement/refined_<prefix>_<entity>.sql` | Transformation SQL |
| Structure | `assets/structure/<ns>/refined_<prefix>_<entity>.yml` | Table schema |
