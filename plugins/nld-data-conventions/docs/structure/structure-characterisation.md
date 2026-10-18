# Structure Characterisation

## Overview

Structure characterisations are metadata annotations applied at the **table/view level** in structure YAML files. They define logical constraints (keys, uniqueness) that drive NLD framework behaviors such as UPSERT conflict resolution and DEDUPLICATED_SELECT deduplication.

## Structure-Level Characterisations

| Characterisation | Purpose | NLD Framework Usage | Naming Convention |
|-----------------|---------|---------------------|-------------------|
| `primary_key` | Technical unique constraint on the table | Used by UPSERT for conflict resolution (`ON CONFLICT`) | `pk_<structure_name>` |
| `business_key` | Business identifier of the entity | Used by DEDUPLICATED_SELECT for deduplication (latest record per key) | `<structure_name>__business_key` |
| `unique` | Additional unique constraint (not the business key) | Enforces uniqueness on specific fields | `<structure_name>__<field>_key` |

`business_key` was formerly named `functional_key`. The old name still loads
with a deprecation warning naming the structure file, so existing structures keep
working until it is removed in a future release; rename the `characterisation:`
value when you touch the file. The characterisation `name:` (e.g.
`<structure_name>__functional_key`) can stay as is: no DDL is derived from it.

## Raw Layer Primary Key Rule

Every `raw_*` table's `primary_key` MUST be the business key fields **plus
`ts_src_extracted_at`** (the `rec_source_extraction_tst` tracking field from the
`raw_standard_tracking` template):

```yaml
- name: pk_raw_<domain>_<entity>
  characterisation: primary_key
  linked_fields:
  - <business key field(s)>
  - ts_src_extracted_at
```

The raw layer keeps one record per source extraction, so the business key
alone is not unique — only the pair (business key, extraction timestamp) is.
UPSERT behaviour is unchanged: `ts_src_extracted_at` carries the
`exclude_from_upsert_match` characterisation, so conflict matching still happens
on the business key alone while the constraint stays honest about the table's
actual grain.

## YAML Syntax

Structure characterisations are defined in the `characterisations:` section at the root level of a structure file:

```yaml
structure_type: TABLE
connector_type: postgresql
properties:
  database: nld_demo_clh
  schema: acquisition_opendata
templates:
  - raw_standard_tracking
  - raw_dlt_tracking
fields:
  siret:
    data_type: CHARACTER VARYING
  siren:
    data_type: CHARACTER VARYING
characterisations:
- name: raw_opendata_stock_etablissement__dlt_id_key
  characterisation: unique
  linked_fields:
  - _dlt_id
- name: raw_opendata_stock_etablissement__business_key
  characterisation: business_key
  linked_fields:
  - siret
- name: pk_raw_opendata_stock_etablissement
  characterisation: primary_key
  linked_fields:
  - siret
  - ts_src_extracted_at
```

