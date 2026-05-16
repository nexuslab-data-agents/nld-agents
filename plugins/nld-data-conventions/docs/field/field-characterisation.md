# Field Characterisation

## Overview

Field characterisations are metadata annotations applied at the **column level** in field template YAML files. They serve two purposes:

1. **Semantic tagging** — identify the role of a field (e.g., insertion timestamp, deletion flag, DLT identifier)
2. **Framework behavior control** — drive UPSERT behavior (exclude fields from match or update)

Field characterisations are **never** applied directly in structure files. They are always defined inside field templates, which are then included via structure templates.

## Field Characterisations Reference

### Record Lifecycle Tracking

These characterisations tag fields that track the lifecycle of a record at the **current data layer**.

| Characterisation | Column Name | Data Type | Default | Description |
|-----------------|-------------|-----------|---------|-------------|
| `rec_insert_tst` | `ts_inserted_at` | TIMESTAMP WITH TIME ZONE | CURRENT_TIMESTAMP | When the record was created at this layer |
| `rec_last_update_tst` | `ts_updated_at` | TIMESTAMP WITH TIME ZONE | CURRENT_TIMESTAMP | When the record was last updated at this layer |
| `rec_insert_by` | `ds_inserted_by` | CHARACTER VARYING | | User/process that created the record |
| `rec_last_update_by` | `ds_updated_by` | CHARACTER VARYING | | User/process that last updated the record |

### Logical Deletion Tracking

These characterisations tag fields that support soft-delete patterns.

| Characterisation | Column Name | Data Type | Default | Description |
|-----------------|-------------|-----------|---------|-------------|
| `rec_deletion_flag` | `fl_deleted` | BIGINT | 0 | Deletion flag (1 = deleted) |
| `rec_deletion_tst` | `ts_deleted_at` | TIMESTAMP WITH TIME ZONE | | When the record was logically deleted |
| `rec_deletion_by` | `ds_deleted_by` | CHARACTER VARYING | | User/process that deleted the record |

### Source System Tracking

These characterisations tag fields that preserve timestamps from the **original source system**.

| Characterisation | Column Name | Data Type | Description |
|-----------------|-------------|-----------|-------------|
| `rec_source_extraction_tst` | `ts_src_extracted_at` | TIMESTAMP WITH TIME ZONE | When the data was extracted from the source |
| `rec_source_insert_tst` | `ts_src_inserted_at` | TIMESTAMP WITH TIME ZONE | When the record was created in the source system |
| `rec_source_last_update_tst` | `ts_src_updated_at` | TIMESTAMP WITH TIME ZONE | When the record was last updated in the source system |

### Previous Layer Tracking

These characterisations tag fields that carry forward timestamps from the **upstream data layer**.

| Characterisation | Column Name | Data Type | Description |
|-----------------|-------------|-----------|-------------|
| `rec_previous_layer_insert_tst` | `ts_prv_layer_inserted_at` | TIMESTAMP WITH TIME ZONE | When the record was inserted in the previous layer |
| `rec_previous_layer_update_tst` | `ts_prv_layer_updated_at` | TIMESTAMP WITH TIME ZONE | When the record was last updated in the previous layer |

### DLT Tracking

These characterisations tag fields managed by the DLT ingestion framework.

| Characterisation | Column Name | Data Type | Description |
|-----------------|-------------|-----------|-------------|
| `dlt_id` | `_dlt_id` | CHARACTER VARYING | DLT-assigned unique record identifier |
| `dlt_load_id` | `_dlt_load_id` | CHARACTER VARYING | DLT load batch identifier |

### Ingestion Tracking

These characterisations tag fields that track the source file from which a record was ingested (CSV/file-based ingestion).

| Characterisation | Column Name | Data Type | Description |
|-----------------|-------------|-----------|-------------|
| `ingestion_file_name` | `ds_src_integrated_filename` | CHARACTER VARYING | Name of the ingested source file |
| `ingestion_file_row_number` | `id_src_integrated_file_row_number` | BIGINT | Row number within the ingested source file |

### Data Format

These characterisations describe the encoding format of a field value, enabling downstream tools to interpret or convert it correctly.

| Characterisation | Description | Typical Data Type | Example Values |
|-----------------|-------------|-------------------|----------------|
| `epoch_ms` | Timestamp stored as Unix epoch in **milliseconds** | BIGINT | `1758793419000` (= 2025-09-25 11:43:39 UTC) |

Apply `epoch_ms` on source/raw fields that store timestamps as integer milliseconds since Unix epoch. This signals to ingestion tools (e.g., `JsonFromLandingResourceConfig.source_updated_at_field`) and downstream transformations that the value must be divided by 1000 before converting to a timestamp.

### UPSERT Behavior Control

These characterisations modify how the NLD UPSERT process handles specific fields. They are applied **alongside** a semantic characterisation on the same field.

| Characterisation | Effect | Typically Applied To |
|-----------------|--------|---------------------|
| `exclude_from_upsert_update` | Field is **not updated** during UPSERT (preserves original value on conflict) | `rec_insert_tst` — insertion timestamp should never change after first insert |
| `exclude_from_upsert_match` | Field is **not compared** when determining if a record has changed | Timestamp fields (`rec_last_update_tst`, `rec_deletion_tst`, `rec_source_*_tst`, `rec_previous_layer_*_tst`) — prevents timestamp drift from triggering unnecessary updates |

## Field Template Mechanics

### Template Structure

A field template defines a single column with its characterisations and lineage:

```yaml
field:
  name: ts_inserted_at
  description: Technical - The record was created at (date and time)
  data_type: TIMESTAMP WITH TIME ZONE
  default: CURRENT_TIMESTAMP
  characterisations:
  - rec_insert_tst
  - exclude_from_upsert_update
lineage:
  expression: CURRENT_TIMESTAMP
  structure_type_overrides:
    VIEW:
      source_characterisation: rec_insert_tst
```

### `override_existing_field_on_characterisation`

Some field templates include this property to allow the template to **replace** an existing field that already carries a specific characterisation. This is used when a downstream layer redefines a tracking field inherited from an upstream structure:

```yaml
field:
  name: fl_deleted
  description: Technical - The record deletion flag (1 means record is deleted)
  data_type: BIGINT
  default: 0
  characterisations:
  - rec_deletion_flag
override_existing_field_on_characterisation: rec_deletion_flag
```

### `source_characterisation` (Lineage)

Field templates use `source_characterisation` in their lineage section to map values from upstream structures. The NLD framework resolves the source field by matching the characterisation name:

```yaml
lineage:
  expression: {source_field}
  source_characterisation: rec_last_update_tst
  structure_type_overrides:
    VIEW:
      source_characterisation: rec_previous_layer_update_tst
```

This means: "For TABLE structures, read the upstream field tagged `rec_last_update_tst`. For VIEW structures, read the upstream field tagged `rec_previous_layer_update_tst`."

## Distribution by Structure Template

| Structure Template | Field Characterisations Included |
|-------------------|--------------------------------|
| `raw_standard_tracking` | `ingestion_file_name`, `ingestion_file_row_number`, `rec_source_extraction_tst`, `rec_source_insert_tst`, `rec_source_last_update_tst`, `rec_previous_layer_update_tst`, `rec_insert_tst`, `rec_last_update_tst`, `rec_deletion_flag`, `rec_deletion_tst`, `rec_deletion_by` |
| `raw_dlt_tracking` | `dlt_load_id`, `dlt_id` |
| `refined_standard_tracking` | `rec_source_extraction_tst`, `rec_source_insert_tst`, `rec_source_last_update_tst`, `rec_previous_layer_update_tst`, `rec_insert_tst`, `rec_last_update_tst` |
| `refined_standard_tracking_with_logical_deletion` | Same as `refined_standard_tracking` + `rec_deletion_flag`, `rec_deletion_tst`, `rec_deletion_by` |
| `nld_standard_tracking` | `rec_source_extraction_tst`, `rec_source_insert_tst`, `rec_source_last_update_tst`, `rec_previous_layer_update_tst`, `rec_insert_tst`, `rec_last_update_tst` |
| `nld_standard_tracking_with_logical_deletion` | Same as `nld_standard_tracking` + `rec_deletion_flag`, `rec_deletion_tst`, `rec_deletion_by` |
