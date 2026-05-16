# Column Convention

## Overview

All columns in the refined, business, and consumer layers follow a semantic prefix convention that indicates the data type and purpose of the field. This ensures consistency across all data products and makes the data model self-documenting.

## Standard Prefixes

| Prefix | Meaning | SQL Type | When to use | Examples |
|--------|---------|----------|-------------|----------|
| `cd_` | Code / identifier | CHARACTER VARYING | Codes, slugs, categorical values, foreign keys | `cd_siren`, `cd_contract_type`, `cd_company_slug` |
| `ds_` | Description / string | CHARACTER VARYING | Free-text fields, names, descriptions, addresses | `ds_company_name`, `ds_address`, `ds_page_title` |
| `dt_` | Date | DATE | Date-only values (no time component) | `dt_creation`, `dt_last_modification` |
| `ts_` | Timestamp | TIMESTAMP / TIMESTAMP WITH TIME ZONE | Date+time values | `ts_published_at`, `ts_last_login` |
| `fl_` | Flag / boolean | BOOLEAN | Boolean flags, yes/no indicators | `fl_is_active`, `fl_has_offices`, `fl_deleted` |
| `nb_` | Number / count | INTEGER | Counts, quantities, whole numbers | `nb_employees`, `nb_jobs`, `nb_offices` |
| `yr_` | Year | INTEGER | Year-only values | `yr_creation`, `yr_category` |
| `id_` | Identifier (non-code) | CHARACTER VARYING | External identifiers, association IDs | `id_association`, `id_external_ref` |
| `num_` | Numeric value | NUMERIC | Decimal values, coordinates, percentages | `num_latitude`, `num_longitude`, `num_parity_men` |

## Technical Tracking Prefixes

These prefixes are reserved for technical tracking columns provided by structure templates. They should not be used for business fields.

| Prefix/Name | Purpose | Provided by |
|-------------|---------|-------------|
| `ts_src_extracted_at` | Source extraction timestamp | raw_standard_tracking, refined_standard_tracking |
| `ts_src_inserted_at` | Source insert timestamp | raw_standard_tracking, refined_standard_tracking |
| `ts_src_updated_at` | Source last-update timestamp | raw_standard_tracking, refined_standard_tracking |
| `ts_prv_layer_updated_at` | Previous layer update timestamp | raw_standard_tracking, refined_standard_tracking |
| `ts_inserted_at` | Current layer insert timestamp | raw_standard_tracking, refined_standard_tracking |
| `ts_updated_at` | Current layer update timestamp | raw_standard_tracking, refined_standard_tracking |
| `fl_deleted` | Logical deletion flag | raw_standard_tracking |
| `ts_deleted_at` | Deletion timestamp | raw_standard_tracking |
| `ds_deleted_by` | Deleted by user/process | raw_standard_tracking |
| `ds_src_integrated_filename` | Ingestion source filename | raw_standard_tracking |
| `id_src_integrated_file_row_number` | Ingestion source row number | raw_standard_tracking |
| `_dlt_load_id` | DLT load batch identifier | raw_dlt_tracking |
| `_dlt_id` | DLT unique record identifier | raw_dlt_tracking |

## Layer-Specific Rules

### Source, Landing, Raw Layers
- Columns keep their **original source names** in the **source language** (no prefix convention, no translation)
- This preserves traceability back to the source system and avoids ambiguity
- The `key` column holds the entity identifier
- `raw_data` column holds the full JSON payload (for JSON-based sources)
- Technical tracking columns are added by templates
- Example: a French source with `raison_sociale`, `effectif`, `secteur_activite` keeps these names as-is in source, landing, raw_json, and raw layers

### Refined Layer
- All business columns use the **semantic prefix convention**
- All field names are in **English** — this is the translation boundary
- Primary key matches the functional key of the raw source
- Data types are properly cast (no raw strings for dates, booleans, numbers)
- Template provides 6 tracking timestamps
- Example: `raison_sociale` → `ds_legal_name`, `effectif` → `nb_employees`, `secteur_activite` → `cd_sector_id`

#### Source timestamps must use template fields

When the source provides creation or modification timestamps, they **must** be mapped to the template-provided tracking fields — **never** as custom business columns:

| Source concept | Maps to template field | Synonyms |
|---|---|---|
| Creation date / inserted date | `ts_src_inserted_at` | created_at, dateCreation, inserted_at |
| Modification date / updated date | `ts_src_updated_at` | modified_at, dateModification, updated_at, last_modified |

**Do not** create custom fields like `ts_src_created_at` or `ts_src_modified_at` — these are synonyms of `ts_src_inserted_at` and `ts_src_updated_at` which are already provided by the `refined_standard_tracking` template.

In the refinement SQL, override the template defaults by selecting the source timestamp with the template field name:

```sql
-- Map source creation timestamp to ts_src_inserted_at
, to_timestamp(audit_date_creation / 1000) AS ts_src_inserted_at
-- Map source modification timestamp to ts_src_updated_at
, to_timestamp(audit_date_modification / 1000) AS ts_src_updated_at
```

### Business Layer
- Same prefix convention as refined
- Business-specific aggregations and calculations
- May join multiple refined sources

### Consumer Layer
- Same prefix convention
- Optimized for consumption (may denormalize)

## Naming Guidelines

1. **Use snake_case** for all column names
2. **Be specific**: `ds_company_name` not `ds_name`
3. **Include entity context** when ambiguous: `cd_legal_unit_category` not `cd_category`
4. **Use English** for all column names
5. **Avoid abbreviations** unless widely understood (`tst` for timestamp, `src` for source)
6. **Prefix determines the type** - a `cd_` field must always be CHARACTER VARYING, a `fl_` must always be BOOLEAN
