## Field Characterisation

This document describes the field characterisation system implemented in
`nld/structure/field/`. It complements the structure YAML reference in
`.agents/docs/architecture/structure-design.md`, which covers how
characterisations are written in YAML files.

### Table of Contents

1. [Overview](#1-overview)
2. [Core Classes](#2-core-classes)
3. [Default Characterisations Implemented in Code](#3-default-characterisations-implemented-in-code)
4. [Common Characterisations](#4-common-characterisations)
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

The attribute keys recognized today are:

| Attribute | Applies to | Meaning |
|-----------|------------|---------|
| `enforced` | `mandatory`, `unique` | When `True`, the constraint must be enforced at the backend level (e.g. `NOT NULL` / `UNIQUE` constraint in DDL). When `False`, the characterisation is informational only. |
| `linked_fields` | `currency`, `uom` | List of the amount field names this currency / unit-of-measure field qualifies (a single currency or unit field can govern several amounts). See §4 MEASURE / CURRENCY. |
| `linked_field` | `amount_in_cur`, `amount_in_uom` | Single field name of the currency / unit-of-measure that this amount is expressed in (an amount is expressed in exactly one currency / unit). See §4 MEASURE / CURRENCY. |
| `unit_of_measure` | `duration` (and other unit-bearing measures) | Literal unit the measure is expressed in (e.g. `month`, `year`, `day`). Unlike `uom`/`linked_field`, the unit is a literal value carried inline, not a reference to a sibling field. See §4 MEASURE. |
| `aggregation_applied_rule` | `duration` (and other aggregated measures) | The aggregation already applied to produce the value (e.g. `min`, `max`, `average`, `sum`). Use when a column is a pre-aggregated measure (e.g. a min / max / average duration). See §4 MEASURE. |
| `base` | `percentage` | The scale the ratio is expressed on: `100` for a 0–100 percentage, `1` for a 0–1 fraction. See §4 MEASURE. |
| `referential` | `referential_value` | Name of the referential / list of values the field draws from (e.g. `contract_type`). See §4 CODE. |
| `multi_value` | `referential_value` | `true` when the column holds several values concatenated (e.g. comma-separated); default `false`. See §4 CODE. |
| `standard` | `language`, `country` | The standard the code follows (e.g. `iso_639`, `iso_3166`). See §4 CODE. |
| `format` | `functional_date`, `functional_time` | The encoded format of the value (e.g. `yyyymmdd`, `ddmmyyyy`, `hhmmss`, `hhmm`). See §4 DATETIME. |

> Note: a number of additional names appear as `auto()` placeholders in
> `FieldCharacterisationDefinitions` (e.g. `rec_insert_user_name`,
> `rec_archive_flag`, `rec_master_source_*`). These are reserved names
> with no concrete `FieldCharacterisationDefinition` yet — they should be
> promoted to full definitions before being used in YAML.

### 4. Common Characterisations

The following characterisations are the **standard set projects use** to
attach functional semantics to fields. They are **not yet implemented in
code** as concrete `FieldCharacterisationDefinition` instances, but they
are the agreed vocabulary a project should reach for first — before
inventing an ad-hoc name — when characterising a field. New definitions
should be added to `FieldCharacterisationDefinitions` (and their names to
`FieldCharacterisationDefinitionNames`) as the need arises, grouped by the
category they belong to.

#### 4.1 Categories at a glance

| Category | Purpose |
|----------|---------|
| `DATA_ENTRY` | Free-form input fields with no validation. |
| `MEASURE` | Physical measures and amounts expressed in a unit of measure. |
| `CURRENCY` | Monetary amounts and their currency reference. |
| `DATETIME` | Functional dates, timestamps, and validity windows (including non-standard string-encoded formats). |
| `FUNCTIONAL` | Cross-structure references, priorities, and other functional roles. |
| `HIERARCHY` | Fields carrying the parent / child references of a hierarchical relationship. |
| `REPORTING_USAGE` | Fields whose purpose is purely to support reporting layers. |
| `GEO` | Geographic information — coordinates and postal codes. |
| `CODE` | Values drawn from a controlled list of values (referentials, language / country codes). |
| `WEB` | Web addresses and slugs. |

The characterisations of each category follow.

#### 4.2 DATA_ENTRY

| Name | Description |
|------|-------------|
| `free_text` | Free-form text input with no validation applied at entry time. |

#### 4.3 MEASURE

| Name | Description |
|------|-------------|
| `uom` | Unit of measure code (e.g. `KG`, `G`, `CAR`, `L`, `mL`, `M3`). Carries a `linked_fields` attribute listing the amount fields it qualifies. |
| `amount_in_uom` | Numeric amount expressed in a unit of measure (not a currency). Carries a `linked_field` attribute naming its single `uom` field. |
| `quantity` | Plain quantity, dimensionless or paired with a separate unit field. |
| `duration` | A length of time. Carries a `unit_of_measure` attribute (literal, e.g. `month`, `year`) and, when pre-aggregated, an `aggregation_applied_rule` attribute (e.g. `min`, `max`, `average`). |
| `percentage` | A ratio / proportion. Carries a `base` attribute giving the scale: `100` for a 0–100 percentage, `1` for a 0–1 fraction. |

A `uom` field can govern **several** amounts (`linked_fields`, a list), while an
`amount_in_uom` is expressed in **exactly one** unit (`linked_field`, a single
name):

```yaml
fields:
  unit_of_measure:
    data_type: VARCHAR
    characterisations:
      - name: unit_of_measure
        characterisation: uom
        attributes:
          linked_fields:
            - net_weight_in_uom
            - gross_weight_in_uom
  net_weight_in_uom:
    data_type: NUMERIC
    characterisations:
      - name: net_weight_in_uom
        characterisation: amount_in_uom
        attributes:
          linked_field: unit_of_measure
  gross_weight_in_uom:
    data_type: NUMERIC
    characterisations:
      - name: gross_weight_in_uom
        characterisation: amount_in_uom
        attributes:
          linked_field: unit_of_measure
```

A `duration` carries its unit as a literal attribute (`unit_of_measure`), and an
`aggregation_applied_rule` when the value is a pre-aggregated measure (e.g. a
minimum / maximum / average duration):

```yaml
fields:
  contract_duration_min:
    data_type: INTEGER
    characterisations:
      - name: contract_duration_min
        characterisation: duration
        attributes:
          unit_of_measure: month
          aggregation_applied_rule: min
  average_age:
    data_type: NUMERIC
    characterisations:
      - name: average_age
        characterisation: duration
        attributes:
          unit_of_measure: year
          aggregation_applied_rule: average
```

#### 4.4 CURRENCY

| Name | Description |
|------|-------------|
| `currency` | Currency code (e.g. `EUR`, `USD`). Carries a `linked_fields` attribute listing the amount fields it qualifies. |
| `amount_in_cur` | Monetary amount expressed in a currency. Carries a `linked_field` attribute naming its single `currency` field. |

A `currency` field can govern **several** amounts (`linked_fields`, a list),
while an `amount_in_cur` is expressed in **exactly one** currency
(`linked_field`, a single name):

```yaml
fields:
  reporting_currency:
    data_type: VARCHAR
    characterisations:
      - name: reporting_currency
        characterisation: currency
        attributes:
          linked_fields:
            - sales_in_reporting_currency
            - cost_in_reporting_currency
  sales_in_reporting_currency:
    data_type: NUMERIC
    characterisations:
      - name: sales_in_reporting_currency
        characterisation: amount_in_cur
        attributes:
          linked_field: reporting_currency
  cost_in_reporting_currency:
    data_type: NUMERIC
    characterisations:
      - name: cost_in_reporting_currency
        characterisation: amount_in_cur
        attributes:
          linked_field: reporting_currency
```

#### 4.5 DATETIME

| Name | Description |
|------|-------------|
| `functional_timestamp` | Business-meaningful timestamp (e.g. delivery received at, order created at), as opposed to a technical record timestamp. |
| `snapshot_date` | Date identifying the snapshot the row belongs to (e.g. stock snapshot date). |
| `validity_start_timestamp` | Timestamp at which the entry starts being valid. |
| `validity_end_timestamp` | Timestamp at which the entry stops being valid. |
| `validity_start_date` | Date at which the entry starts being valid. |
| `validity_end_date` | Date at which the entry stops being valid. |
| `functional_date` | Functional date stored as a string or integer in a non-standard encoded format. Carries a `format` attribute giving the layout (e.g. `yyyymmdd`, `ddmmyyyy`). |
| `functional_time` | Functional time-of-day stored as a string or integer in a non-standard encoded format. Carries a `format` attribute giving the layout (e.g. `hhmmss`, `hhmm`). |
| `functional_year` | Business-meaningful year stored as an integer (e.g. a company creation year), as opposed to a full date. |
| `time_period` | A period / granularity of time (e.g. `monthly`, `yearly`), typically qualifying an amount or rate. |

#### 4.6 FUNCTIONAL

| Name | Description |
|------|-------------|
| `priority` | Priority indicator stored as a strictly positive integer, where `1` denotes the highest priority. |
| `tec_external_reference` | Foreign-key style reference to another structure, resolved against the **technical** key of the target structure. |
| `func_external_reference` | Foreign-key style reference to another structure, resolved against the **functional** key of the target structure. |
| `source_identifier` | A stable identifier issued by the source system, exposed as-is. Not a reference to another modelled structure (use `*_external_reference` for that). |

#### 4.7 HIERARCHY

| Name | Description |
|------|-------------|
| `hierarchy_parent_info` | Field carrying the parent reference of a hierarchical relationship. |
| `hierarchy_child_info` | Field carrying the child reference of a hierarchical relationship. |

#### 4.8 REPORTING_USAGE

| Name | Description |
|------|-------------|
| `reporting_technical_info` | Technical field exposed only for reporting purposes (e.g. a stable unique identifier on a master-data structure). |
| `reporting_ordering` | Field used as the default ordering key for reporting layers. |

#### 4.9 GEO

| Name | Description |
|------|-------------|
| `latitude` | Geographic latitude in decimal degrees. |
| `longitude` | Geographic longitude in decimal degrees. |
| `zip_code` | Postal / ZIP code. |

#### 4.10 CODE

| Name | Description |
|------|-------------|
| `referential_value` | A value drawn from a referential / controlled list of values (a coded enumeration / nomenclature), as opposed to free text. Carries an optional `referential` attribute (the list name) and an optional `multi_value` attribute. |
| `language` | A language code from a standard referential. Carries a `standard` attribute (e.g. `iso_639`). |
| `country` | A country code from a standard referential. Carries a `standard` attribute (e.g. `iso_3166`). |

```yaml
fields:
  contract_type:
    data_type: CHARACTER VARYING
    characterisations:
      - name: contract_type
        characterisation: referential_value
        attributes:
          referential: contract_type
  organization_industry:
    data_type: CHARACTER VARYING
    characterisations:
      - name: organization_industry
        characterisation: referential_value
        attributes:
          referential: industry
          multi_value: true
  job_language:
    data_type: CHARACTER VARYING
    characterisations:
      - name: job_language
        characterisation: language
        attributes:
          standard: iso_639
  office_country_code:
    data_type: CHARACTER VARYING
    characterisations:
      - name: office_country_code
        characterisation: country
        attributes:
          standard: iso_3166
```

#### 4.11 WEB

| Name | Description |
|------|-------------|
| `url` | A web URL. |
| `slug` | A URL slug / opaque human-readable identifier used in web addresses. |

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
