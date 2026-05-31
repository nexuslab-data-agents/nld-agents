# Structure Characterisation

## Overview

Structure characterisations are metadata annotations applied at the **table/view level** in structure YAML files. They define logical constraints (keys, uniqueness) that drive NLD framework behaviors such as UPSERT conflict resolution and DEDUPLICATED_SELECT deduplication.

## Structure-Level Characterisations

| Characterisation | Purpose | NLD Framework Usage | Naming Convention |
|-----------------|---------|---------------------|-------------------|
| `primary_key` | Technical unique constraint on the table | Used by UPSERT for conflict resolution (`ON CONFLICT`) | `pk_<structure_name>` |
| `functional_key` | Business identifier of the entity | Used by DEDUPLICATED_SELECT for deduplication (latest record per key) | `<structure_name>__functional_key` |
| `unique` | Additional unique constraint (not the functional key) | Enforces uniqueness on specific fields | `<structure_name>__<field>_key` |

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
- name: raw_opendata_stock_etablissement__functional_key
  characterisation: functional_key
  linked_fields:
  - siret
```

