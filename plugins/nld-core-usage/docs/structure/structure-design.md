## Structure YAML Definition Rules

This document describes the standard YAML format for defining data structures in the nexuslabdata framework.

### Structure Root Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Unique identifier (typically file name without extension) |
| `connector_type` | string | No | Target backend: `postgresql`, `snowflake`, `flat_file`, `pandas`, `pydantic` |
| `structure_type` | string | Yes | Object type: `TABLE`, `VIEW`, `FLAT_FILE` |
| `description` | string | No | Full description of the structure |
| `short_description` | string | No | Brief description for display purposes |
| `stats` | dict[str, str \| int] | No | Statistics about the structure (e.g., `row_count`, `size_bytes`) |
| `tags` | list[string] | No | Tags for categorization (can also be inherited from namespace config) |
| `properties` | dict[str, str] | No | Technical properties (e.g., `file_format`, `encoding`, `source`) |
| `business_metadata` | dict[str, str] | No | Business metadata (e.g., `owner`, `domain`, `grouping`) |
| `origin` | dict[str, Any] | No | Definition origin and flow relationships (e.g., `creation_method`, `loading_flows`) |
| `options` | dict[str, Any] | No | Additional options for the structure |
| `characterisations` | list | No | Structure-level characterisations |
| `enforce_field_order` | boolean | No | Whether deployment enforces the declared column order on the physical table. Unset falls back to the connector's `enforce_field_order_default` capability (PostgreSQL and Snowflake enforce by default; BigQuery and DuckDB do not). When enforced, an order mismatch triggers a data-preserving REBUILD — see `structure-deployment.md` |
| `pre_deployment_sql_hook` | list[string] | No | SQL statements run before the structure's deployment DDL. The structure's list overrides a template's; Jinja-rendered with `schema`, `structure_name`, `object_path`, and project variables |
| `post_deployment_sql_hook` | list[string] | No | SQL statements run after the structure's deployment DDL. Same override and rendering rules as `pre_deployment_sql_hook` |
| `fields` | dict | Yes | Field definitions (keyed by field name) |

### Structure Inheritance & Dynamic Class Resolution

Structure supports connector-specific subclasses that are dynamically resolved
when loading entities from YAML files. This is driven by the `connector_type`
field and a subclass registry on the `Structure` class.

#### Subclass Registry

**File:** `core/nld/structure/structure/structure.py`

Structure maintains a module-level registry (`_STRUCTURE_SUBCLASS_REGISTRY`)
mapping connector type strings to fully qualified class paths. Three class
methods manage the registry:

| Method | Description |
|--------|-------------|
| `get_registry_attribute_key()` | Returns the entity dict key used for registry lookup (returns `"connector_type"`) |
| `register_subclass(connector_type, class_path)` | Registers a subclass class path for a connector type |
| `get_registered_class_path(connector_type)` | Returns the registered class path, or `None` if not found |

Registration happens automatically when a `ConnectorPlugin` with a
`structure_class_path` is loaded by the `ConnectorFactory`.

#### Dynamic Resolution Flow

When loading structures from YAML, `_resolve_entity_class()` in
`core/nld/service/model_read_util.py` checks whether the base model type
has a registry (via `get_registry_attribute_key` and
`get_registered_class_path`). If a matching `connector_type` is found in the
entity dict and a subclass is registered for it, the subclass is used for
instantiation instead of the base `Structure` class.

```
YAML: connector_type: postgresql
       ↓
get_registry_attribute_key() → "connector_type"
       ↓
entity_dict["connector_type"] → "postgresql"
       ↓
get_registered_class_path("postgresql") → "nld.connector.postgresql..."
       ↓
import_class_inside_module() → PostgreSQLStructure
       ↓
PostgreSQLStructure.from_dict(entity_dict)
```

This pattern is generic and works with any `NldBaseModel` subclass that
implements `get_registry_attribute_key()` and `get_registered_class_path()`.

#### PostgreSQLStructure

**File:** `core/nld/connector/postgresql/postgresql_structure.py`

Connector-specific subclass that provides typed property accessors for
PostgreSQL-specific properties stored in the generic `properties` dictionary.

| Property | Return Type | Source Key |
|----------|-------------|------------|
| `database_name` | `str \| None` | `properties["database"]` |
| `schema_name` | `str \| None` | `properties["schema"]` |

Both properties return `None` when the key is not present in `properties`.

**Example YAML:**

```yaml
name: pg_users
connector_type: postgresql
structure_type: TABLE
properties:
  database: my_db
  schema: public
fields:
  id:
    data_type: INTEGER
```

When loaded, this produces a `PostgreSQLStructure` instance with:

```python
structure.database_name  # "my_db"
structure.schema_name    # "public"
```

#### S3Structure

**File:** `core/nld/connector/s3_blob_storage/s3_structure.py`

Connector-specific subclass for the S3 blob storage connector. Exposes
typed accessors over the generic `properties` dict so S3 backends rely on
a stable contract rather than reading untyped attributes off the
surrounding task or data product.

| Property | Return Type | Source Key | Default |
|----------|-------------|------------|---------|
| `s3_root_prefix` | `str` | `properties["s3_root_prefix"]` | `""` |
| `file_format` | `str \| None` | `properties["file_format"]` | `None` |

`s3_root_prefix` is the bucket-relative root under which artifacts for
this structure live. `file_format` advertises the on-disk format and is
also consumed by the S3 state backend (e.g. as `params.file_format` on
`StateBackendConnectorConfig`).

The S3 state backend manager composes `s3_root_path` from
`s3_root_prefix` plus an `s3_folder_path` (defaulting to the structure
name) inside `determine_parameters_for_flow_definition` on
`S3BackendMixin`. The same override is inherited by the execution and
`by_key` incremental S3 state backends, so `s3_root_path` is derived
from the typed structure on both sides.

**Example YAML:**

```yaml
name: orders_raw
connector_type: s3_blob_storage
structure_type: TABLE
properties:
  s3_root_prefix: landing
  file_format: parquet
fields:
  id:
    data_type: INTEGER
```

### Properties

Technical properties about the structure's source and format:

```yaml
properties:
  file_format: csv
  encoding: utf-8
  delimiter: ","
  source: opendata
```

#### Standard Properties

| Property | Description |
|----------|-------------|
| `file_format` | File format (e.g., `csv`, `parquet`, `json`) |
| `encoding` | Character encoding (e.g., `utf-8`, `latin-1`) |
| `delimiter` | Field delimiter for delimited files |
| `source` | Data source identifier |
| `source_system` | Source system name |

### Tags

Tags categorize structures and control behavior during deployment and execution.

```yaml
tags:
  - external_source
  - read_only
```

#### Special Tags

| Tag | Effect |
|-----|--------|
| `external_source` | Structure is excluded from deployment (managed externally) |
| `target_structure_is_managed_by_flow_execution` | Structure is excluded from direct deployment (managed by flow execution) |

#### Namespace-Level Tags

Tags can also be defined at the namespace level in the `namespaces` block of
`nld_project.yml` via the `tags` field on `StructureNamespaceMapping`. These
tags are automatically injected into all structures in that namespace after
entity loading, with deduplication against the structure's own tags.

```yaml
# nld_project.yml
namespaces:
  source.external_crm:
    structure:
      default_connection_name: pg_main
      database_name: main_db
      schema_name: external_crm
      tags:
        - external_source
```

All structures under the `source.external_crm` namespace (and child namespaces)
will inherit the `external_source` tag without needing to declare it individually.

**File:** `core/nld/structure/config/structure_config.py` (StructureNamespaceMapping)<br/>
**Injection:** `core/nld/project/project.py` (_apply_structure_config_tags)

### Business Metadata

Business-level metadata about the structure:

```yaml
business_metadata:
  owner: data_team
  domain: master_data
  grouping: reference_data
  steward: john.doe@company.com
  classification: internal
```

#### Standard Business Metadata

| Property | Description |
|----------|-------------|
| `classification` | Data classification: `public`, `internal`, `confidential`, `restricted` |
| `data_product` | Associated data product name |
| `domain` | Business domain (e.g., `master_data`, `transactional`, `analytics`) |
| `grouping` | Logical grouping for organization |
| `owner` | Team or person owning the data |
| `steward` | Data steward contact |

### Origin

Definition origin, generation history, and flow relationships:

```yaml
origin:
  creation_method: derived_from_source  # manual | derived_from_source | generated_from_rules
  source_structure: raw_customers       # if derived from another structure
  generation_rule: target_snowflake     # if generated from rules
  created_at: "2024-01-15T10:30:00Z"
  last_modified_at: "2024-06-20T14:15:00Z"
  loading_flows:
    - flow_load_customers
    - flow_refresh_daily
```

#### Standard Origin Properties

| Property | Type | Description |
|----------|------|-------------|
| `creation_method` | string | How the structure was created: `manual`, `derived_from_source`, `generated_from_rules` |
| `source_structure` | string | Source structure name (if derived) |
| `generation_rule` | string | Rule/template used for generation |
| `created_at` | string | ISO 8601 timestamp of initial creation |
| `last_modified_at` | string | ISO 8601 timestamp of last modification |
| `loading_flows` | list[str] | Flow names that load data into this structure |

### Options

Additional options for the structure as key-value pairs:

```yaml
options:
  partition_key: date_column
  clustering_keys:
    - region
    - category
  retention_days: 90
```

Options are flexible and can store any structure-specific configuration that doesn't fit in other properties.

### Characterisations (Common Design)

Both FieldCharacterisation and StructureCharacterisation share the same base design pattern:
- Inherit from `NldNamedBaseModel` (provides `name` attribute)
- Have a `characterisation` field (the type of characterisation)
- Have an `attributes` field (optional dict for additional properties)
- StructureCharacterisation additionally has `linked_fields` (list of field names)

#### Characterisation Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for this characterisation instance |
| `characterisation` | string | Yes | The characterisation type (e.g., `primary_key`, `mandatory`) |
| `attributes` | dict[str, Any] | No | Additional attributes for this characterisation |
| `linked_fields` | list[str] | No | Field names linked to this characterisation (StructureCharacterisation only) |

### Structure Characterisations

Structure characterisations define constraints and behaviors linked to fields:

```yaml
characterisations:
  - name: pk_table_name
    characterisation: primary_key
    linked_fields:
      - field1
      - field2
    attributes: {}
```

#### Standard Structure Characterisation Definitions

| Definition Name | Description | Linked to Fields |
|-----------------|-------------|------------------|
| `primary_key` | Primary key constraint | Yes |
| `technical_unique_key` | Technical uniqueness constraint | Yes |
| `functional_unique_key` | Functional uniqueness constraint | Yes |
| `functional_key` | Functional key definition | Yes |
| `unique` | General uniqueness constraint | Yes |

### Field Definition

Fields are defined as a dictionary where keys are field names. The field order in the YAML file determines their position in the structure.

```yaml
fields:
  FIELD_NAME:
    description: Field description
    short_description: Brief description
    data_type: VARCHAR
    length: 100
    precision: 0
    default_value: null
    characterisations:
      - mandatory
      - unique
```

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | string | No | Full field description |
| `short_description` | string | No | Brief description |
| `data_type` | string | Yes | Data type (see Data Types section) |
| `length` | int | No | Length for string types |
| `precision` | int | No | Precision for numeric types |
| `default_value` | any | No | Default value for the field |
| `characterisations` | list | No | Field-level characterisations |
| `field_template` | string | No | Field template entity name the field is materialised from (see "Field From a Field Template") |

**Note:** Field position is determined by the order of keys in the YAML fields dictionary. There is no explicit `position` attribute.

### Field From a Field Template

A field can be fully based on a `FieldTemplate` entity without going through a
`StructureTemplate`. Declare the reference with the `field_template` attribute;
the value is a field template entity name resolved through the namespace
hierarchy (nearest ancestor namespace wins), like other entity references.

```yaml
fields:
  id_account:
    data_type: VARCHAR(32)
  ds_src_integrated_filepath:
    field_template: INGESTION_FILE_PATH
  ts_loaded_at:
    field_template: REC_INSERT_TST
    description: Overridden description
```

Behavior:

- The field is materialised from the template's embedded `field` definition
  (data type, length/precision, description, characterisations).
- Any attribute declared next to `field_template` overrides the template value
  (e.g. a custom `description`). A declared `data_type` also discards the
  template's `length`/`precision`, and declared `characterisations` replace
  the template list entirely.
- The field name is the `fields` dictionary key, so a template can be reused
  under a different name. The field position is simply its position in the
  field list — the template's `relative_position` and
  `override_existing_field_on_characterisation` attributes only apply to
  structure templates and are ignored for direct references.
- The materialised field participates in deployment, diff, and validation
  exactly like a regular declared field. `nld structure info` shows the field
  template name in the fields table Template column.
- The template's `lineage` applies during SQL rendering exactly as for
  structure-template fields (see "Field Template Lineage"), keyed on the
  declared field name.
- An unknown or unresolvable reference fails entity loading with an error
  listing the available field template names.

### Field Data Types

Data types can be specified in two formats:

**Simple format:**
```yaml
data_type: VARCHAR
length: 100
precision: 0
```

**Compact format (parsed automatically):**
```yaml
data_type: VARCHAR(100,0)
```

**Multi-word data types are supported:**
```yaml
data_type: DOUBLE PRECISION
data_type: CHARACTER VARYING(100)
data_type: TIME WITH TIME ZONE
data_type: TIMESTAMP WITHOUT TIME ZONE
```

#### Standard Data Types

| Type | Description | Uses Length | Uses Precision |
|------|-------------|-------------|----------------|
| `VARCHAR` / `TEXT` / `CHARACTER VARYING` | Variable-length string | Yes | No |
| `INTEGER` / `INT` | Integer number | No | No |
| `NUMBER` / `NUMERIC` | Decimal number | Yes | Yes |
| `DOUBLE PRECISION` | Double-precision floating-point | No | No |
| `DATE` | Date only | No | No |
| `TIMESTAMP` | Date and time | No | Yes |
| `TIMESTAMP_TZ` / `TIMESTAMP WITH TIME ZONE` | Date and time with timezone | No | Yes |
| `BOOLEAN` | True/False | No | No |

### Field Characterisations

Field characterisations inherit from `NldNamedBaseModel` and follow the common characterisation design.
They support two formats:

**Format 1: Full object (default)**

Standard format where all properties are explicitly specified:
```yaml
characterisations:
  - name: mandatory_field1
    characterisation: mandatory
    attributes:
      enforced: true
```

**Format 2: Simple string (FieldCharacterisation only)**

Shorthand format where the string represents the characterisation type.
The name is automatically duplicated from the characterisation value:
```yaml
characterisations:
  - mandatory    # Equivalent to: {name: "mandatory", characterisation: "mandatory"}
  - unique       # Equivalent to: {name: "unique", characterisation: "unique"}
```

**Note:** The key-value format (e.g., `{primary_key: {enforced: true}}`) is not supported.

#### Standard Field Characterisation Definitions

| Definition Name | Description | Single per Structure |
|-----------------|-------------|----------------------|
| `mandatory` | Field cannot be null | No |
| `unique` | Field values must be unique | No |
| `rec_insert_tst` | Record insert timestamp | Yes |
| `rec_last_update_tst` | Record last update timestamp | Yes |
| `rec_previous_layer_update_tst` | Last update timestamp in the previous layer | Yes |
| `rec_source_insert_tst` | Source insert timestamp | Yes |
| `rec_source_last_update_tst` | Source last update timestamp | Yes |
| `rec_source_extraction_tst` | Source extraction timestamp | Yes |
| `rec_deletion_flag` | Logical deletion flag | Yes |
| `rec_deletion_tst` | Deletion timestamp | Yes |
| `rec_deletion_by` | User that applied the logical deletion | Yes |
| `exclude_from_upsert_update` | Field excluded from UPDATE SET and change detection on upsert | No |
| `exclude_from_upsert_match` | Field updated but excluded from change detection on upsert | No |

### Field Template Lineage

Field templates can define lineage rules that control how template fields are
populated during SQL rendering. The `lineage` attribute on a `FieldTemplate`
specifies either a raw SQL `expression` or a `source_characterisation` to
cross-reference in the source structure.

Lineage applies whether the field template reaches the structure through a
`StructureTemplate` or is referenced directly by a field via `field_template`
(see "Field From a Field Template"). For a direct reference, the rendered
expression is aliased to the declared field name, and it takes precedence over
name-based auto-mapping so the lineage rule is never shadowed by a same-named
source field.

#### Structure Type Overrides

The `structure_type_overrides` dictionary allows per-target-type lineage rules
that take precedence over the default when the target structure type matches.
Keys are structure types (normalized to uppercase), and values are
`FieldTemplateLineageRule` objects.

```yaml
templates:
  - name: ts_inserted_at
    field:
      data_type: TIMESTAMP_TZ
      characterisations:
        - rec_insert_tst
    lineage:
      expression: CURRENT_TIMESTAMP
      structure_type_overrides:
        VIEW:
          source_characterisation: rec_insert_tst
```

In this example, the default lineage uses `CURRENT_TIMESTAMP` for TABLE
targets. When the target structure type is VIEW, the override uses the
`rec_insert_tst` characterisation from the source structure instead.

Resolution is handled by `FieldTemplateLineage.resolve_for_target_type()`,
which returns the override rule if a matching structure type exists, or the
default rule otherwise.

### Complete Example

```yaml
name: raw_opendata_ape_code_5levels
connector_type: postgresql
structure_type: TABLE
description: Class APE code for french companies
short_description: APE Code 5 Levels
tags:
  - opendata
  - reference
stats:
  row_count: 733
  size_bytes: 45000
properties:
  file_format: csv
  encoding: utf-8
  source: opendata
business_metadata:
  classification: public
  domain: reference_data
  grouping: master_data
  owner: data_team
origin:
  creation_method: derived_from_source
  source_structure: raw_opendata_ape_code
  created_at: "2024-01-15T10:30:00Z"
  last_modified_at: "2024-06-20T14:15:00Z"
  loading_flows:
    - flow_load_ape_codes
characterisations:
  - name: pk_ape_code_5levels
    characterisation: primary_key
    linked_fields:
      - NIV5
    attributes: {}
fields:
  NIV5:
    description: Level 5 correspondant aux sous classes
    short_description: Level 5 - Sub-classes
    data_type: VARCHAR
    length: 6
    characterisations:
      - name: pk_niv5
        characterisation: primary_key
        attributes:
          enforced: true
      - mandatory
      - unique
  NIV4:
    description: Level 4 correspondant aux classes
    data_type: VARCHAR
    length: 5
    characterisations:
      - mandatory
  TS_UPDATED_AT:
    description: Technical - Last update timestamp
    data_type: timestamp_tz
    characterisations:
      - rec_last_update_tst
```
