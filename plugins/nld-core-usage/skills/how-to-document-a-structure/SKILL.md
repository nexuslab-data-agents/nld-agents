---
name: how-to-document-a-structure
description: >
  Create or refresh an nld-core Structure YAML from a real database table/view:
  extract the schema with `nld connection get-structure`, document every
  JSON/VARIANT/ARRAY column's nested schema recursively with the `fields`
  attribute, declare characterisations (keys/unique), and validate with
  `nld structure info`. The generic nld-core mechanics — independent of any data
  layer or product layout (those are layered on by the platform skill).
user-invocable: true
---

# How to Document a Structure

**Classification**: Atomic Skill | Structure Authoring

---

## Definition

- **What**: Author a Structure YAML that accurately describes a database table or
  view — its columns, the nested schema of complex columns, and its
  characterisations — and validate it.
- **When**: After a table/view exists (post-ingestion or transformation), or when
  an existing structure YAML drifted from the table.
- **Why**: The Structure is the single source of truth for the data model; it
  drives SQL rendering, deployment and lineage. A wrong/opaque structure breaks
  all three.

For the entity internals (connector subclasses, deployment, field
characterisations), see the `guide-structures` skill. For naming the columns,
see `how-to-use-business-dictionary`. **Templates, the data-layer → template
mapping, and where the file lives are platform conventions — see your platform's
structure-documentation skill.**

---

## Step 1 — Extract the schema from the database

The table/view must exist in a reachable database.

```bash
nld connection get-structure --connection-name <connection> --schema <schema> --object <table_or_view>
```

This writes a structure YAML with all columns, data types, primary keys and
unique constraints read from the live object. Resolve `<connection>` with
`nld connection list` — do not assume a fixed name.

---

## Step 2 — Document JSON / VARIANT / ARRAY columns (recursively)

Complex columns (`jsonb`, `json`, `VARIANT`, `ARRAY`, or DLT `__v` variant
columns) must be described with a nested `fields:` attribute — never left as
opaque blobs. **Query real data; never guess the schema.**

### Sample the column

```sql
-- top-level keys of a jsonb object
SELECT DISTINCT jsonb_object_keys(<column>::jsonb)
FROM <schema>.<object> WHERE <column> IS NOT NULL LIMIT 100;

-- type of each value
SELECT key, jsonb_typeof(value) AS value_type
FROM <schema>.<object>, jsonb_each(<column>::jsonb)
WHERE <column> IS NOT NULL LIMIT 50;
```

### Recurse into nested objects/arrays

For every sub-field that is itself `object` or `array`, repeat — do not stop at
the first level.

```sql
-- a nested object inside an array inside an object…
SELECT DISTINCT u.key, jsonb_typeof(u.value) AS val_type
FROM <schema>.<object> t,
     jsonb_array_elements(t.<col>->'<path>') elem,   -- arrays
     jsonb_each(elem->'<sub_path>') u                 -- objects
WHERE elem->'<sub_path>' IS NOT NULL LIMIT 30;
```

### Document with `fields`

```yaml
fields:
  company_data:
    data_type: jsonb
    description: Full company profile from source API
    fields:
      name:
        data_type: CHARACTER VARYING
      offices:
        data_type: ARRAY
        description: Office locations
        fields:
          city:
            data_type: CHARACTER VARYING
          is_headquarters:
            data_type: BOOLEAN
      stats:
        data_type: jsonb
        fields:
          total_jobs:
            data_type: INTEGER
```

**Rules for nested `fields`:**
- Only document fields **consistently present** across multiple samples.
- Leaf values use standard SQL types (`CHARACTER VARYING`, `INTEGER`,
  `BOOLEAN`, `TIMESTAMP`, …).
- Arrays of objects → document the object schema inside `fields`; arrays of
  scalars → `data_type: ARRAY` with a description of the element type.
- **Every jsonb/ARRAY field gets its own `fields`.**
- Stop recursion only at leaf scalars or volatile/dynamic key structures
  (user-generated keys, no consistent schema).

---

## Step 3 — Assemble the Structure YAML

```yaml
structure_type: TABLE            # or VIEW
connector_type: postgresql
properties:
  database: <database>
  schema: <schema>
# templates: [...]               # which templates apply is a platform convention
fields:
  <field>:
    data_type: <type>
    description: <optional>
  <json_field>:
    data_type: jsonb
    fields:
      <nested_field>:
        data_type: <type>
characterisations:
  - name: <structure_name>__<suffix>
    characterisation: <type>
    linked_fields:
      - <field>
```

> When the structure uses **templates** (tracking-field bundles), the
> template-provided fields must **not** be repeated in `fields:`. Which templates
> apply per data layer, and where the file is placed, are platform conventions —
> see your platform's structure-documentation skill.

### Characterisations (nld-core)

| Type | Multiplicity | Meaning |
|------|--------------|---------|
| `primary_key` | 1 | Primary key |
| `technical_unique_key` | 1 | Technical uniqueness (e.g. `_dlt_id`) |
| `functional_unique_key` | 1 | Functional uniqueness |
| `functional_key` | N | Business key (non-unique) |
| `unique` | N | Unique constraint |
| `index` | N | Non-unique index |

Naming: `<structure_name>__<suffix>` (e.g. `..._dlt_id_key`,
`..._functional_key`, `pk_<structure_name>`).

---

## Step 4 — Validate

```bash
nld structure info --structure-name <namespace>.<structure_name>
```

Fix YAML / unknown-template errors and re-run until clean.

---

## Critical rules

### NEVER
- Guess a JSON column's schema without querying real data.
- Use the raw `nld connection get-structure` output as-is when templates are in
  play (template fields would be duplicated — strip them per the platform skill).

### ALWAYS
- Query sample data for **every** JSON/VARIANT/ARRAY column and recurse to the
  leaves.
- Declare `characterisations` for primary keys, unique constraints and
  functional keys.
- Validate with `nld structure info`.

---

## Cross-references

- Entity internals, deployment, characterisations: `guide-structures`.
- Naming columns from the canonical vocabulary: `how-to-use-business-dictionary`.
- Inter-structure links once structures exist: `how-to-model-structure-layers`.
- Templates, layer→template mapping, file placement: the platform's
  structure-documentation skill.
