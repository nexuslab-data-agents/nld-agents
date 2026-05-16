## Field Characterisation

This document describes the field characterisation system implemented in
`nld/structure/field/`. It complements the structure YAML reference in
`.agents/docs/architecture/structure-design.md`, which covers how
characterisations are written in YAML files.

### Table of Contents

1. [Overview](#1-overview)
2. [Core Classes](#2-core-classes)
3. [Default Characterisations Implemented in Code](#3-default-characterisations-implemented-in-code)
4. [Common Optional Characterisations](#4-common-optional-characterisations)
5. [Adding a New Characterisation](#5-adding-a-new-characterisation)

---

### 1. Overview

A **field characterisation** attaches a typed semantic role to a field of
a structure. Unlike the raw `data_type`, which describes how the value is
stored, a characterisation describes what the value **means** to the
platform: is it mandatory, is it the technical insert timestamp, is it a
foreign reference, is it an amount in a currency, etc.

Characterisations are consumed by many parts of the framework — SQL
rendering, upsert generation, structure diffing, deduplicated select
transformations, source/target field mapping, lineage resolution — so
adding the right characterisation on a field unlocks behavior across the
stack without ad-hoc flags.

### 2. Core Classes

All defined in `core/nld/structure/field/`.

| Class | File | Purpose |
|-------|------|---------|
| `FieldCharacterisation` | `field_characterisation.py` | Per-field instance attached to a `Field`. Has a `name`, a `characterisation` type, and an optional `attributes` dict. |
| `FieldCharacterisationDefinition` | `field_characterisation_def.py` | Declarative metadata for a characterisation type: `description`, `allowed_attributes`, `applicable_to_single_field_per_structure`. |
| `FieldCharacterisationDefinitionNames` | `field_characterisation_def.py` | `NldStrEnum` of the characterisation type names known to the framework. |
| `FieldCharacterisationDefinitions` | `field_characterisation_def.py` | Container holding the concrete `FieldCharacterisationDefinition` instances for the names above. |
| `FieldCharacterisationDefinitionAttributesNames` | `field_characterisation_def.py` | `NldStrEnum` of allowed attribute keys (currently only `ENFORCED`). |

`FieldCharacterisation` accepts two YAML formats (full object and short
string) — see section "Field Characterisations" of
`.agents/docs/architecture/structure-design.md`.

### 3. Default Characterisations Implemented in Code

The following characterisations are defined today in
`core/nld/structure/field/field_characterisation_def.py`. They are the
ones the framework actively understands; YAML may reference any string,
but only these are wired into platform behavior.

#### 3.1 Generic constraints

| Name | Single per structure | Description |
|------|:--------------------:|-------------|
| `mandatory` | No | Field cannot be null. Accepts the `enforced` attribute. |
| `unique` | No | Field values must be unique. Accepts the `enforced` attribute. |

#### 3.2 Record technical timestamps (target side)

| Name | Single per structure | Description |
|------|:--------------------:|-------------|
| `rec_insert_tst` | Yes | Timestamp of first insertion in the current structure. |
| `rec_last_update_tst` | Yes | Timestamp of last update in the current structure. |
| `rec_previous_layer_update_tst` | Yes | Timestamp of last update in the previous layer (used for incremental flows that compare against the upstream layer). |

#### 3.3 Record technical timestamps (source side)

| Name | Single per structure | Description |
|------|:--------------------:|-------------|
| `rec_source_insert_tst` | Yes | Timestamp of first insertion in the source structure. |
| `rec_source_last_update_tst` | Yes | Timestamp of last update in the source structure. |
| `rec_source_extraction_tst` | Yes | Timestamp at which the record was extracted from the source. |

#### 3.4 Logical deletion

| Name | Single per structure | Description |
|------|:--------------------:|-------------|
| `rec_deletion_flag` | Yes | Logical deletion flag (`1` = deleted, `0` = active). |
| `rec_deletion_tst` | Yes | Timestamp of the logical deletion. |
| `rec_deletion_user_name` | Yes | User that applied the logical deletion. |

#### 3.5 Upsert behavior

| Name | Single per structure | Description |
|------|:--------------------:|-------------|
| `exclude_from_upsert_match` | No | Field is updated on upsert but excluded from the change detection (`IS DISTINCT FROM`) check. |
| `exclude_from_upsert_update` | No | Field is excluded from both `UPDATE SET` and change detection on upsert (insert-only field). |

#### 3.6 Allowed attributes

The only attribute key currently recognized is:

| Attribute | Applies to | Meaning |
|-----------|------------|---------|
| `enforced` | `mandatory`, `unique` | When `True`, the constraint must be enforced at the backend level (e.g. `NOT NULL` / `UNIQUE` constraint in DDL). When `False`, the characterisation is informational only. |

> Note: a number of additional names appear as `auto()` placeholders in
> `FieldCharacterisationDefinitions` (e.g. `rec_insert_user_name`,
> `rec_archive_flag`, `rec_master_source_*`). These are reserved names
> with no concrete `FieldCharacterisationDefinition` yet — they should be
> promoted to full definitions before being used in YAML.

### 4. Common Optional Characterisations

The following characterisations are **not yet implemented in code** but
are the recommended set to use when a project needs to attach functional
semantics to fields. New definitions should be added to
`FieldCharacterisationDefinitions` (and their names to
`FieldCharacterisationDefinitionNames`) as the need arises, grouped by
the category column below.

| Name | Category | Description |
|------|----------|-------------|
| `free_text` | DATA_ENTRY | Free-form text input with no validation applied at entry time. |
| `uom` | MEASURE | Unit of measure code (e.g. `KG`, `G`, `CAR`, `L`, `mL`, `M3`). |
| `amount_in_uom` | MEASURE | Numeric amount expressed in a unit of measure (not a currency). |
| `quantity` | MEASURE | Plain quantity, dimensionless or paired with a separate unit field. |
| `currency` | CURRENCY | Currency code (e.g. `EUR`, `USD`). |
| `amount_in_cur` | CURRENCY | Monetary amount expressed in a currency. Typically paired with a `currency` field. |
| `functional_timestamp` | DATETIME | Business-meaningful timestamp (e.g. delivery received at, order created at), as opposed to a technical record timestamp. |
| `snapshot_date` | DATETIME | Date identifying the snapshot the row belongs to (e.g. stock snapshot date). |
| `validity_start_timestamp` | DATETIME | Timestamp at which the entry starts being valid. |
| `validity_end_timestamp` | DATETIME | Timestamp at which the entry stops being valid. |
| `validity_start_date` | DATETIME | Date at which the entry starts being valid. |
| `validity_end_date` | DATETIME | Date at which the entry stops being valid. |
| `date_yyyymmdd` | DATETIME | Functional date stored as a string or integer in `YYYYMMDD` format. |
| `date_ddmmyyyy` | DATETIME | Functional date stored as a string or integer in `DDMMYYYY` format. |
| `time_hhmmss` | DATETIME | Functional time-of-day stored as a string or integer in `HHMMSS` format. |
| `time_hhmm` | DATETIME | Functional time-of-day stored as a string or integer in `HHMM` format. |
| `priority` | FUNCTIONAL | Priority indicator stored as a strictly positive integer, where `1` denotes the highest priority. |
| `tec_external_reference` | FUNCTIONAL | Foreign-key style reference to another structure, resolved against the **technical** key of the target structure. |
| `func_external_reference` | FUNCTIONAL | Foreign-key style reference to another structure, resolved against the **functional** key of the target structure. |
| `hierarchy_parent_info` | FUNCTIONAL | Field carrying the parent reference of a hierarchical relationship. |
| `hierarchy_child_info` | FUNCTIONAL | Field carrying the child reference of a hierarchical relationship. |
| `reporting_technical_info` | REPORTING_USAGE | Technical field exposed only for reporting purposes (e.g. a stable unique identifier on a master-data structure). |
| `reporting_ordering` | REPORTING_USAGE | Field used as the default ordering key for reporting layers. |

#### Categories at a glance

| Category | Purpose |
|----------|---------|
| `DATA_ENTRY` | Free-form input fields with no validation. |
| `MEASURE` | Physical measures and amounts expressed in a unit of measure. |
| `CURRENCY` | Monetary amounts and their currency reference. |
| `DATETIME` | Functional dates, timestamps, and validity windows (including non-standard string-encoded formats). |
| `FUNCTIONAL` | Cross-structure references, hierarchies, and other functional roles. |
| `REPORTING_USAGE` | Fields whose purpose is purely to support reporting layers. |

### 5. Adding a New Characterisation

When promoting one of the optional characterisations above (or
introducing a brand-new one), do all of the following so the rest of the
framework picks it up automatically:

1. Add the name to `FieldCharacterisationDefinitionNames` in
   `core/nld/structure/field/field_characterisation_def.py`. Keep the
   enum value lowercase to match the normalization done in
   `FieldCharacterisation.normalize_characterisation`.
2. Add a `FieldCharacterisationDefinition` instance to
   `FieldCharacterisationDefinitions` in the same file. Set
   `applicable_to_single_field_per_structure` deliberately:
   - `True` for unique technical roles (e.g. `rec_insert_tst`).
   - `False` for constraints that may apply to many fields (e.g.
     `mandatory`).
3. If the new characterisation accepts attributes, add the attribute keys
   to `FieldCharacterisationDefinitionAttributesNames` and list them in
   `allowed_attributes` on the definition.
4. Update the relevant tables in this document and in
   `.agents/docs/architecture/structure-design.md` (section "Standard
   Field Characterisation Definitions") so the YAML reference stays in
   sync with the code.
