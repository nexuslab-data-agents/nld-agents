# Structure Convention

## Scope

These conventions apply to all NLD-managed structures: `raw_`, `v_raw_*_latest`, `refined_`, business, and consumer tables/views.

They do **not** apply to externally-managed structures where the schema is determined by the ingestion tool (DLT) or the source system:
- `source_*` (external source definition)
- `landing_*` (S3 landing zone files)
- `raw_json_*` (DLT-managed JSON staging tables)

## Field Ordering

### Rule: Functional key first

The functional key (primary key / business identifier) must always be the **first field** in the `fields:` section of the structure YAML.

This ensures:
- Consistent field ordering across all structures
- The business key is immediately visible when reading the structure
- SQL `SELECT *` outputs start with the identifying column

**Example**:

```yaml
fields:
  job_reference:                    # Functional key — always first
    data_type: CHARACTER VARYING
    description: Job reference code
  job_name:                         # Other fields follow
    data_type: CHARACTER VARYING
  contract_type:
    data_type: CHARACTER VARYING
```

### Rule: Template-provided fields are implicit

Fields provided by templates (`raw_standard_tracking`, `refined_standard_tracking`, etc.) are **not listed** in the `fields:` section. They are added automatically by the template system.

The `fields:` section only contains entity-specific business fields.

## Characterisations

### Naming Convention

```
<structure_name>__<constraint_suffix>
```

| Constraint | Suffix | Example |
|---|---|---|
| Primary key | `pk_<structure_name>` | `pk_refined_web_hr_wttj_job` |
| Functional key | `<structure_name>__functional_key` | `raw_web_hr_wttj_jobs__functional_key` |
| Unique | `<structure_name>__<field>_key` | `raw_web_hr_wttj_jobs__dlt_id_key` |

### Functional Key vs Primary Key

- **Functional key**: The business identifier of the entity. Used by `DEDUPLICATED_SELECT` for deduplication.
- **Primary key**: The technical unique constraint on the table. Used by `UPSERT` for conflict resolution.

On `raw_*` tables the primary key is always the **functional key fields +
`ts_src_extracted_at`**: the raw layer keeps one record per source extraction,
so the functional key alone is not unique. `ts_src_extracted_at` carries
`exclude_from_upsert_match`, so UPSERT conflict matching still happens on the
functional key alone. On `refined_*` and downstream tables (one record per
entity), the functional key and primary key point to the **same field(s)**.

### Choosing the Functional Key

1. **Prefer the source system's business identifier** over the extraction slug. Look for fields like `reference`, `id`, `code` in the source JSON.
2. **Verify uniqueness and non-null coverage**: the functional key must be 100% non-null and unique across the dataset.
3. **Fall back to the extraction slug** (`key` column) if no suitable business key exists or if the business key has NULLs.

## Templates by Layer

| Layer | Structure Type | Templates |
|---|---|---|
| `raw_json_*` | TABLE | `raw_standard_tracking` + `raw_dlt_tracking` |
| `raw_*` (loaded from `raw_json_*`) | TABLE | `raw_standard_tracking` + `raw_dlt_tracking_excluded_from_upsert_update` |
| `v_raw_*_latest` | VIEW | `raw_standard_tracking` |
| `refined_*` | TABLE | `refined_standard_tracking` |
| business | TABLE | `nld_standard_tracking` |
| consumer | VIEW | `nld_standard_tracking` |

> **dlt tracking on the raw layer.** The dlt bookkeeping fields (`_dlt_id`,
> `_dlt_load_id`) must not drive UPSERT change detection on a `raw_*` table
> populated by the SQL UPSERT flow: a re-ingestion regenerates `_dlt_load_id`
> and would otherwise rewrite every row. Use
> `raw_dlt_tracking_excluded_from_upsert_update` (its dlt fields carry
> `exclude_from_upsert_update`) for `raw_*` tables loaded from `raw_json_*`.
> Keep the plain `raw_dlt_tracking` on `raw_json_*` (the dlt ingestion target).
> When a source has no `raw_json_*` layer and the `raw_*` table is itself the
> dlt ingestion target (e.g. bulk-file products), keep the plain
> `raw_dlt_tracking`.

## Tags

| Tag | When to use |
|---|---|
| `target_structure_is_managed_by_flow_execution` | Only on `raw_json_*` tables (DLT-managed schema) |

## Table Naming by Layer

The following naming rules apply to the **business** ("Gold") and **consumer**
("Platinum") layers. Acquisition layers (`source_`, `landing_`, `raw_json_`,
`raw_`, `v_raw_*_latest`, `refined_`) follow their own conventions documented
in the [Raw Layer](../data-layers/raw.md) and
[Refinement Layer](../data-layers/refinement.md) pages.

### Business Layer ("Gold")

See [Business Layer](../data-layers/business.md) for the full description.

| Structure type    | Description                                                                                                  | Naming convention                                                          |
|-------------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| Reference table   | Reference / dimension-like data of the Gold layer                                                            | `R_{DOMAIN}_{DESCRIPTION}`                                                 |
| Fact table        | Transactional / fact data of the Gold layer                                                                  | `F_{DOMAIN}_{DESCRIPTION}`                                                 |

### Consumer Layer ("Platinum")

See [Consumer Layer](../data-layers/consumer.md) for the full description.

| Structure type    | Description                                                                                                  | Naming convention                                                          |
|-------------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| Dimension table   | Dimension table of the Platinum layer                                                                        | `DIM_{DOMAIN}_{DESCRIPTION}`                                               |
| Datamart table    | Datamart table of the Platinum layer                                                                         | `DTM_{DOMAIN}_{DESCRIPTION}`                                               |

### Auxiliary Structures (Business & Consumer)

These rules apply to the business **and** consumer layers.

| Structure type        | Description                                                                                                                                                           | Naming convention                                  |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| Display view          | View exposing data of a layer to downstream consumers (typically the next layer). Must reuse the underlying table name; a specific name may be used when the view filters/transforms the data. | Same name as underlying table                      |
| Temporary work table  | Working table used during a data process, not meant to be persisted.                                                                                                  | `W_{DOMAIN}_{DESCRIPTION}`                         |
| Parameter table       | Table maintained manually by Data Engineers, for technical or business needs (e.g. a manually-curated unit-of-measure master data).                                   | `P_{DOMAIN}_{DESCRIPTION}` (e.g. `P_CUS_TENANT_DATA_RANGE`, `P_CUS`, `P_UOM`) |
| Technical table       | Table for technical needs such as logging or monitoring.                                                                                                              | `T_{DOMAIN}_{DESCRIPTION}` (e.g. `T_LOG_RUN`, `T_LOG_INC`) |
