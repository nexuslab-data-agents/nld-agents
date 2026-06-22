# Common Field Characterisation Definitions

Ready-to-use `FieldCharacterisationDefinition` files for the **common
characterisations** described in `../field-characterisation.md` §4. Each `.yml`
is one definition: a coded semantic role (`free_text`, `references`,
`amount_in_cur`, …) that a project attaches to a field.

The built-in catalogue shipped in nld-core covers only the technical roles
(`mandatory`, `unique`, the `rec_*` timestamps, `exclude_from_upsert_*`). The
functional common-set names here are **not** built-in, so a structure that uses
one is reported as unknown by `nld structure validate` until the project
declares its definition. These files are that declaration, prepared once for
every project.

## Installing them in a project

Copy the definitions a project needs into its
`<entity_path>/characterisations/field/` directory. The registry loads them as
`field_characterisation_definition` entities, resolved against parent
namespaces, and overlays them on the built-in catalogue (see
`../field-characterisation.md` §6).

```
cp field_characterisations/references.yml \
   field_characterisations/amount_in_cur.yml \
   <project>/<entity_path>/characterisations/field/
```

Copy only the ones the project actually uses, or all of them to make the whole
common set available. The file name matches the definition `name`.

## File format

```yaml
name: amount_in_cur
description: "Monetary amount expressed in a currency. …"
applicable_to_single_field_per_structure: false
allowed_attributes:
    - linked_field
    - currency
```

- `name` — the lowercase characterisation token stored on fields.
- `description` — what the role means.
- `applicable_to_single_field_per_structure` — `true` when the role may appear
  on at most one field of a structure (e.g. `snapshot_date`, the validity
  bounds), `false` otherwise.
- `allowed_attributes` — the attribute keys the role accepts (omitted when it
  accepts none). `nld structure validate` rejects any attribute outside this
  list.

## Definitions

| Category | Definitions |
|----------|-------------|
| DATA_ENTRY | `free_text` |
| MEASURE | `uom`, `amount_in_uom`, `quantity`, `duration`, `percentage` |
| CURRENCY | `currency`, `amount_in_cur` |
| DATETIME | `functional_timestamp`, `snapshot_date`, `validity_start_timestamp`, `validity_end_timestamp`, `validity_start_date`, `validity_end_date`, `functional_date`, `functional_time`, `functional_year`, `time_period` |
| FUNCTIONAL | `priority`, `source_identifier` |
| HIERARCHY | `hierarchy_parent_info`, `hierarchy_child_info` |
| REPORTING_USAGE | `reporting_technical_info`, `reporting_ordering` |
| GEO | `latitude`, `longitude`, `zip_code` |
| CODE | `references`, `language`, `country` |
| WEB | `url`, `slug` |
