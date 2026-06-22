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
6. [The Effective Catalogue, Project-Declared Definitions, and Validation](#6-the-effective-catalogue-project-declared-definitions-and-validation)

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
| `FieldCharacterisation` | `field_characterisation.py` | Per-field instance attached to a `Field`. Has a `name`, a `characterisation` type (lowercased on load), and an optional `attributes` dict. |
| `FieldCharacterisationDefinition` | `field_characterisation_definition.py` | A namespaced NLD entity (`NldNamedBaseModel`) describing a characterisation type: `description`, `allowed_attributes`, `applicable_to_single_field_per_structure`. The registry loads it as entity type `field_characterisation_definition`. |
| `FieldCharacterisationDefinitionNames` | `field_characterisation_definition.py` | `NldStrEnum` of the characterisation type names backed by a built-in definition. |
| `FieldCharacterisationDefinitions` | `field_characterisation_definition.py` | Container holding the concrete built-in `FieldCharacterisationDefinition` instances for the names above. |
| `FieldCharacterisationDefinitionAttributesNames` | `field_characterisation_definition.py` | `NldStrEnum` of allowed attribute keys (e.g. `enforced`). |
| `FIELD_CHARACTERISATION_DEFINITIONS` | `field_characterisation_definition.py` | The built-in catalogue: a dict keyed by the lowercase characterisation token, collecting every `FieldCharacterisationDefinition` declared on `FieldCharacterisationDefinitions`. |
| `NamespacedFieldCharacterisationDefinition` | `field_characterisation_definition.py` | A `FieldCharacterisationDefinition` paired with the namespace it resolves from. |
| `resolve_field_characterisation_definitions` | `field_characterisation_catalog.py` | Merges the built-in catalogue with project-declared definitions visible from a namespace into the effective catalogue (see §6). |
| `CharacterisationValidationFinding` | `field_characterisation_catalog.py` | A single field characterisation validation finding: the offending field name, the characterisation token, and a message. |

`FieldCharacterisation` accepts two YAML formats (full object and short
string) — see section "Field Characterisations" of
`.agents/docs/architecture/structure-design.md`.

### 3. Default Characterisations Implemented in Code

The following characterisations are declared as built-in
`FieldCharacterisationDefinition` instances in
`core/nld/structure/field/field_characterisation_definition.py`. They form
the base catalogue every namespace starts from; projects extend it with
their own definitions (§6).

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
| `rec_deletion_by` | Yes | User that applied the logical deletion. |

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
| `linked_field` | `amount_in_cur`, `amount_in_uom` | Single field name of the currency / unit-of-measure that this amount is expressed in (an amount is expressed in exactly one currency / unit). Use when the currency / unit is held in a **sibling field**; when it is a fixed constant use `currency` / `unit_of_measure` instead. See §4 MEASURE / CURRENCY. |
| `currency` | `amount_in_cur` | Literal ISO 4217 currency code (e.g. `EUR`) carried inline, for an amount whose currency is a **fixed constant** with no per-row currency field. Mutually exclusive with `linked_field`. See §4 CURRENCY. |
| `unit_of_measure` | `duration`, `amount_in_uom` (and other unit-bearing measures) | Literal unit the measure is expressed in (e.g. `month`, `year`, `day`, `KG`). Unlike `uom`/`linked_field`, the unit is a literal value carried inline, not a reference to a sibling field. On `amount_in_uom` it is the **fixed-unit** alternative to `linked_field` (mutually exclusive). See §4 MEASURE. |
| `aggregation_applied_rule` | `duration` (and other aggregated measures) | The aggregation already applied to produce the value (e.g. `min`, `max`, `average`, `sum`). Use when a column is a pre-aggregated measure (e.g. a min / max / average duration). See §4 MEASURE. |
| `base` | `percentage` | The scale the ratio is expressed on: `100` for a 0–100 percentage, `1` for a 0–1 fraction. See §4 MEASURE. |
| `referential` | `referenced` | Name of the referential / list of values the field draws from (e.g. `contract_type`). See §4 CODE. |
| `multi_value` | `referenced` | `true` when the column holds several values concatenated (e.g. comma-separated); default `false`. See §4 CODE. |
| `standard` | `language`, `country` | The standard the code follows (e.g. `iso_639`, `iso_3166`). See §4 CODE. |
| `format` | `functional_date`, `functional_time` | The encoded format of the value (e.g. `yyyymmdd`, `ddmmyyyy`, `hhmmss`, `hhmm`). See §4 DATETIME. |

### 4. Common Characterisations

The following characterisations are the **standard set projects use** to
attach functional semantics to fields. They are the agreed vocabulary a
project should reach for first — before inventing an ad-hoc name — when
characterising a field. They are not part of the built-in catalogue (§3);
a project that uses one makes the framework recognise it by declaring a
project-level definition for it (§6) or by promoting it into the built-in
catalogue (§5), grouped by the category it belongs to. A characterisation
that is neither built-in nor project-declared is reported as unknown by
`nld structure validate` (§6).

Ready-made `FieldCharacterisationDefinition` files for the whole common set
live in `field_characterisations/` next to this document; copy the ones a
project needs into its `characterisations/field/` directory (§6.2). See
`field_characterisations/README.md`.

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
| `amount_in_uom` | Numeric amount expressed in a unit of measure (not a currency). Carries **either** a `linked_field` attribute naming its single `uom` field, **or** — when the unit is a fixed constant with no sibling field — a literal `unit_of_measure` attribute (e.g. `KG`). Exactly one of the two. |
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

When the unit is a **fixed constant** for the whole column and there is no
per-row unit field, carry it inline as a literal `unit_of_measure` attribute
instead of `linked_field` (the amount then needs no paired `uom` field):

```yaml
fields:
  net_weight_in_kg:
    data_type: NUMERIC
    characterisations:
      - name: weight
        characterisation: amount_in_uom
        attributes:
          unit_of_measure: KG
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
| `amount_in_cur` | Monetary amount expressed in a currency. Carries **either** a `linked_field` attribute naming its single `currency` field, **or** — when the currency is a fixed constant with no sibling field — a literal `currency` attribute (e.g. `EUR`). Exactly one of the two. |

An `amount_in_cur` resolves its currency in one of two **mutually exclusive**
ways: by **sibling field** (`linked_field`) or by **fixed value** (`currency`,
a literal ISO 4217 code). Exactly one must be present; both present or both
absent is invalid. A `currency` field can govern **several** amounts
(`linked_fields`, a list), while an `amount_in_cur` is expressed in **exactly
one** currency (`linked_field`, a single name):

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

When the currency is a **fixed constant** for the whole column and there is no
per-row currency field (e.g. a revenue figure always expressed in euros), carry
it inline as a literal `currency` attribute instead of `linked_field` (the
amount then needs no paired `currency` field):

```yaml
fields:
  num_revenue:
    data_type: BIGINT
    characterisations:
      - name: num_revenue
        characterisation: amount_in_cur
        attributes:
          currency: EUR
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
| `referenced` | A value drawn from a referential / controlled list of values (a coded enumeration / nomenclature), as opposed to free text. Carries an optional `referential` attribute (the list name) and an optional `multi_value` attribute. |
| `language` | A language code from a standard referential. Carries a `standard` attribute (e.g. `iso_639`). |
| `country` | A country code from a standard referential. Carries a `standard` attribute (e.g. `iso_3166`). |

```yaml
fields:
  contract_type:
    data_type: CHARACTER VARYING
    characterisations:
      - name: contract_type
        characterisation: referenced
        attributes:
          referential: contract_type
  organization_industry:
    data_type: CHARACTER VARYING
    characterisations:
      - name: organization_industry
        characterisation: referenced
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

A characterisation becomes part of the effective catalogue (§6) in one of
two ways. Declare it as a **project-level definition** when it is specific
to one project or domain; promote it into the **built-in catalogue** when
it is a cross-project role that nld-core itself should ship.

**Project-level definition.** Add a YAML file under
`<entity_path>/characterisations/field/<name>.yml` in the project. The
file is a `FieldCharacterisationDefinition`:

```yaml
name: scd_flag
description: SCD2 current-row flag, project-specific characterisation
allowed_attributes:
  - enforced
applicable_to_single_field_per_structure: true
```

The registry loads it as a `field_characterisation_definition` entity and
overlays it on the built-in catalogue for that namespace (§6). No nld-core
code change is needed.

**Built-in catalogue.** To make a characterisation available to every
project, do all of the following in nld-core so the rest of the framework
picks it up automatically:

1. Add the name to `FieldCharacterisationDefinitionNames` in
   `core/nld/structure/field/field_characterisation_definition.py`. Keep
   the enum value lowercase to match the normalization done in
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

### 6. The Effective Catalogue, Project-Declared Definitions, and Validation

#### 6.1 The effective catalogue

The set of characterisations a structure may use in a given namespace is
the **effective catalogue**:
`resolve_field_characterisation_definitions(registry, namespace)` starts
from the built-in catalogue (`FIELD_CHARACTERISATION_DEFINITIONS`, §3) and
overlays every project-declared definition visible from that namespace. A
project declaration overrides a built-in of the same (case-insensitive)
name. Keys are the lowercase characterisation token, matching what fields
store.

#### 6.2 Project-declared definitions

A project declares a `FieldCharacterisationDefinition` as a YAML file
under `<entity_path>/characterisations/field/<name>.yml` (entity type
`field_characterisation_definition`, resolved against parent namespaces).
Each file carries `name`, `description`, an optional `allowed_attributes`
list, and `applicable_to_single_field_per_structure`. The common set (§4) is
provided ready-made under `field_characterisations/` next to this document —
copy the needed files into `characterisations/field/` rather than authoring
them by hand. The registry exposes them through:

| Accessor | Returns |
|----------|---------|
| `get_field_characterisation_definition_dict(namespace)` | All visible definitions as `NamespacedFieldCharacterisationDefinition`, keyed by name. |
| `get_field_characterisation_definition(entity_key, namespace)` | One definition by name. |
| `get_field_characterisation_definition_keys(namespace)` | Names visible from the namespace (parent search included). |
| `list_field_characterisation_definition_keys(namespace)` | Names declared directly in the namespace. |

#### 6.3 Validation

`nld structure validate` checks field characterisations against the
effective catalogue:

```
nld structure validate [--name <structure>] [--namespace <ns>] [--format json]
```

It validates one structure when `--name` is given, otherwise every
structure visible from `--namespace`. For each field characterisation it
checks that:

- the characterisation is a known definition in the effective catalogue,
- every attribute it carries is listed in the definition's
  `allowed_attributes`, and
- a definition marked `applicable_to_single_field_per_structure` appears
  on at most one field of the structure.

Each problem is reported as a `CharacterisationValidationFinding`. The
command renders a human-readable summary by default and the full payload
with `--format json`; it exits non-zero when any structure is invalid.
