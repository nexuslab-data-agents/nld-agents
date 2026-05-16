# Raw Layer

## Overview

The raw layer is the first structured representation of data in the platform. It contains complete data from external sources with proper column typing and naming, but without business transformations.

For JSON-based sources (web extraction, API ingestion), the raw layer involves two sub-layers:

```
S3 Landing Zone
  ↓ ingestion (DLT)
raw_json_<prefix>_<entity>          (jsonb raw_data column - temporary staging)
  ↓ flatten (SQL flow)
raw_<prefix>_<entity>               (flat typed columns - actual raw layer)
  ↓ v_raw_*_latest                  (deduplicated view)
```

For flat sources (CSV, Excel, direct API with tabular data), data lands directly into the raw layer without the `raw_json_` intermediate:

```
Source (CSV, Excel, API)
  ↓ direct ingestion (DLT)
raw_<prefix>_<entity>               (flat columns from source)
  ↓ v_raw_*_latest                  (deduplicated view)
```

## Sub-Layers

### raw_json_ (JSON staging)

**Purpose**: Temporary storage for ingested JSON data before flattening.

**Naming**: `raw_json_<prefix>_<entity>` (e.g., `raw_json_web_hr_wttj_companies`)

**Characteristics**:
- Contains a `key` column (entity identifier) and a `raw_data` column (jsonb)
- One row per entity per extraction timestamp
- Created by the `NldStandardDltLandingIngestionTask` from S3 landing zone data
- Not meant for direct consumption - serves as input for the raw flatten SQL flow
- No deduplicated view needed - the flatten flow reads directly from this table

**Structure templates**: `raw_standard_tracking` + `raw_dlt_tracking`

**Tags**: `target_structure_is_managed_by_flow_execution` (DLT manages the table)

### raw_ (flattened raw)

**Purpose**: The actual raw layer with flat, typed columns extracted from the JSON data.

**Naming**: `raw_<prefix>_<entity>` (e.g., `raw_web_hr_wttj_companies`)

**Characteristics**:
- All business-relevant fields extracted as individual typed columns
- Column names match the source field names (no semantic prefix convention yet - that's for the refined layer)
- Created by a SQL flow that reads directly from `raw_json_` table and flattens the JSON
- Write strategy: `UPSERT` or `OVERWRITE` depending on the entity
- Has a deduplicated view `v_raw_<prefix>_<entity>_latest` for downstream consumption
- **Exclude fields already mapped to technical tracking columns**: if a JSON field was configured as `source_updated_at_field` or `source_inserted_at_field` in the ingestion `json_resource_config`, it is already available as `ts_src_updated_at` / `ts_src_inserted_at` in `raw_json_` and must NOT be duplicated as a business column in `raw_`

**Structure templates**: `raw_standard_tracking` + `raw_dlt_tracking`

## Deduplicated Views

Every raw table (both `raw_json_` and `raw_`) has a corresponding `v_*_latest` view created with the `DEDUPLICATED_SELECT` transformation:

| Table | View | Dedup Key |
|-------|------|-----------|
| `raw_<prefix>_<entity>` | `v_raw_<prefix>_<entity>_latest` | `functional_key` (entity key) |

> **Note**: `raw_json_` tables do not have a deduplicated view. The raw flatten flow reads directly from `raw_json_` and handles deduplication in the SQL or via the UPSERT write strategy on the `raw_` target.

The view uses `ROW_NUMBER() OVER (PARTITION BY <key> ORDER BY ts_updated_at DESC)` with `WHERE fl_deleted = 0` to return only the most recent non-deleted version of each entity.

## Data Flow Summary

### JSON-based sources (two-step)

```
1. Ingestion:    S3 landing → raw_json_web_hr_wttj_companies
2. Flatten:      → raw_web_hr_wttj_companies (SQL flow extracting JSON fields)
3. Dedup view:   → v_raw_web_hr_wttj_companies_latest
4. Refinement:   → refined_web_hr_wttj_company (downstream)
```

### Flat sources (single-step)

```
1. Ingestion:    Source → raw_opendata_stock_etablissement
2. Dedup view:   → v_raw_opendata_stock_etablissement_latest
3. Refinement:   → refined_opendata_fr_company_establishment (downstream)
```

## Files Required

### For raw_json_ sub-layer (JSON sources)

| File | Path | Purpose |
|------|------|---------|
| Ingestion flow | `assets/flows/<ns>/ingestion/<entity>_ingestion.yaml` | DLT ingestion from S3 |
| Raw JSON structure | `assets/structure/<ns>/raw_json_<prefix>_<entity>.yml` | Table with key + raw_data |

### For raw_ sub-layer (flatten from JSON)

| File | Path | Purpose |
|------|------|---------|
| Flatten flow | `assets/flows/<ns>/raw/raw_<prefix>_<entity>.yaml` | SQL flow to flatten JSON |
| Flatten SQL | `assets/flows/<ns>/raw/raw_<prefix>_<entity>.sql` | JSON extraction SQL |
| Raw structure | `assets/structure/<ns>/raw_<prefix>_<entity>.yml` | Flat table structure |
| Dedup view flow | `assets/flows/<ns>/raw/v_raw_<prefix>_<entity>_latest.yaml` | DEDUPLICATED_SELECT view |
| Dedup view SQL | `assets/flows/<ns>/raw/v_raw_<prefix>_<entity>_latest.sql` | Rendered SQL |
| Dedup view structure | `assets/structure/<ns>/v_raw_<prefix>_<entity>_latest.yml` | View structure |

### For raw_ (flat sources, no JSON)

| File | Path | Purpose |
|------|------|---------|
| Ingestion flow | `assets/flows/<ns>/ingestion/<entity>_ingestion.yaml` | DLT direct ingestion |
| Raw structure | `assets/structure/<ns>/raw_<prefix>_<entity>.yml` | Table with flat columns |
| Dedup view flow | `assets/flows/<ns>/raw/v_raw_<prefix>_<entity>_latest.yaml` | DEDUPLICATED_SELECT view |
| Dedup view SQL | `assets/flows/<ns>/raw/v_raw_<prefix>_<entity>_latest.sql` | Rendered SQL |
| Dedup view structure | `assets/structure/<ns>/v_raw_<prefix>_<entity>_latest.yml` | View structure |

## Column Conventions

### raw_json_ tables
- `key` - Entity identifier (CHARACTER VARYING, NOT NULL)
- `raw_data` - Full JSON payload (jsonb)
- Template-provided tracking columns

### raw_ tables (flattened)
- Columns use **source field names** (not semantic prefixes - those are for the refined layer)
- Data types should match the source as closely as possible
- Functional key should be defined as a characterisation
- Template-provided tracking columns
