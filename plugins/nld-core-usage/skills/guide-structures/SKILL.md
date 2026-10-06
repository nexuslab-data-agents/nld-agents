---
name: guide-structures
description: >
  Architectural guide for nld-core Structure definitions, field characterisations,
  connector-specific subclass resolution, and structure deployment (diff, DDL
  generation, schema history). Covers YAML definition rules, dynamic class
  resolution across PostgreSQL, BigQuery, Snowflake, DuckDB and SQLite, view
  structures generated from their flow (`nld structure generate`), and the
  Structure → Pydantic model / JSON Schema export.
user-invocable: false
---

# Guide: Structures & Schema Management

Architectural reference for the nld-core Structure system — YAML-based schema
definitions, field characterisations, dynamic connector-specific resolution, and
deployment lifecycle.

## When to Use

Activate this guide when the agent is working on:
- Structure models in `nld/structure/`
- Field characterisation code in `nld/structure/field/`
- Structure YAML definition files
- Structure deployment, DDL generation, or schema diff logic
- Adding or modifying field characterisation definitions

## Document Resolution

This guide references three documentation files. For each, first check the
project-local path. If not found, read the bundled copy.

| Document | Path |
|----------|------|
| Structure YAML rules | `${CLAUDE_PLUGIN_ROOT}/docs/structure/structure-design.md` |
| Structure deployment | `${CLAUDE_PLUGIN_ROOT}/docs/structure/structure-deployment.md` |
| Field characterisations | `${CLAUDE_PLUGIN_ROOT}/docs/structure/field-characterisation.md` |

### Key Sections

**structure-design.md** — read based on task:

| Task | Section |
|------|---------|
| Writing a Structure YAML | "Structure Root Properties", "Field Definition" |
| Defining a field directly from a field template | "Field From a Field Template", "Field Template Lineage" |
| Understanding dynamic class resolution | "Structure Inheritance & Dynamic Class Resolution" |
| Working with PostgreSQL-specific structures | "PostgreSQLStructure" |
| Adding field characterisations | "Field Characterisations", "Standard Field Characterisation Definitions" |
| Understanding tags and metadata | "Tags", "Business Metadata" |
| Column order enforcement (`enforce_field_order`) and deployment SQL hooks (`pre_deployment_sql_hook` / `post_deployment_sql_hook`) | "Structure Root Properties"; behavior in `structure-deployment.md` |
| Generating a view structure from its flow (`generation_metadata`) | "Generated Structures" |
| Exposing a structure as a Pydantic model or JSON Schema (`build_pydantic_model`) | "Exporting a Structure as a Pydantic Model" |
| Full YAML example | "Complete Example" |

**structure-deployment.md** — read when working on deployment, DDL, drift
detection, or schema history (`nld structure deploy`). Cross-cutting
deployment concepts (metadata backend pinning, `.deployments/` change files,
impact analysis) live in the `guide-deployment` skill.

**field-characterisation.md** — read when working with semantic field roles
(PRIMARY_KEY, TIMESTAMP, FOREIGN_KEY, etc.) or field-level characterisation
definitions.

## CLI: listing & filtering structures

`nld structure list` enumerates structures, optionally filtered by property
and/or tag:

```
nld structure list [--namespace <ns>] [--property key=value]... [--tag <tag>]...
```

- `--property key=value` and `--tag` are **repeatable** and **ANDed** (a
  structure must match every given pair / tag).
- Filtering is against the **merged** properties/tags (`get_all_properties` /
  `get_all_tags`), so template-contributed values are included.
- Output is a table: `Name | Namespace | Type | <each filtered property> | Tags`,
  sorted by name then namespace.

A structure name may exist in several namespaces (`sales.customer` and
`marketing.customer`); `list` shows each copy on its own row. Commands taking
`--name` resolve the copy stored in `--namespace`, or the only copy visible
from it; when several are visible the command fails with
`AmbiguousEntityException` listing the candidates — pass the namespace holding
the copy, or the qualified `<namespace>.<name>`.

```
# every structure tagged with a given layer property
nld structure list --property layer=landing

# raw external-source structures in one namespace
nld structure list --namespace apec --property layer=raw --tag external_source
```

Other `nld structure` subcommands: `info` (single structure detail), `adapt`,
`validate`, `generate` (see below), `deploy` (see the
`how-to-deploy-a-project` skill), `render`. For
inter-structure join models, see the `guide-structure-model` skill
(`nld structure model list/info/validate`).

## CLI: validating field characterisations

`nld structure validate` checks every field characterisation against the
effective catalogue (the built-in definitions merged with project-declared ones
visible from the structure's namespace):

```
nld structure validate [--name <structure>] [--namespace <ns>] [--format json]
```

It applies three checks (one finding per problem) and exits non-zero when any
structure is invalid:

- **Unknown characterisation** — the tag is not in the effective catalogue.
  Message: `Unknown field characterisation '<token>'; not a known definition`.
- **Disallowed attribute** — an attribute key is outside the definition's
  `allowed_attributes`. Message: `Attribute '<attr>' not allowed for '<token>'`.
- **Single-field violation** — a definition marked
  `applicable_to_single_field_per_structure` appears on more than one field.
  Message: `'<token>' set on <n> fields, expected at most 1`.

A structure generated by `nld structure generate` is also regenerated in memory
from its flow: when the result differs from the file, it is reported as `STALE`
— a warning only, never a failure (`stale_reasons` in the JSON output).

See
`field-characterisation.md` §6 for the catalogue resolution and how a project
declares its own `field_characterisation_definition` under
`characterisations/field/`.

## CLI: generating a flow's target structure

`nld structure generate` writes the target structure YAML of a flow that has
a **single predecessor** (typically a `VIEW` over a refined table), and keeps
it in sync with that source:

```
nld structure generate --name <flow> [--namespace <flow ns>]   # create, or merge into the existing file
nld structure generate [--namespace <ns>]                      # regenerate every generated structure
nld structure generate --check                                 # write nothing; diff + non-zero exit when stale
```

Without `--name`, the command regenerates every structure holding a
`generation_metadata` block whose flow namespace is related to `--namespace`
(an ancestor, itself or a descendant; every one when omitted). `--check`
combines with both forms and needs no database.

- The target is the flow's `target_structure` (default: the flow name in the
  flow namespace); an existing file is found under the project layout and
  merged, never overwritten.
- Fields come from the flow `.sql` (a single-table `SELECT`), else
  `target_from_sources_mapping`, else every source field.
- Regeneration rewrites the field list, types and nested fields; user edits
  (descriptions, characterisations, extra templates, hooks) are kept.
- The file records a `generation_metadata` block (`flow`, `source`); staleness
  (`validate`, `flow deploy`, `--check`) regenerates the structure in memory
  from that flow and compares the result with the file.

Rules, ownership table and an example: `structure-design.md` →
"Generated Structures".

## Cross-References

- For inter-structure join models (links, cardinality, field mappings), see the
  `guide-structure-model` skill.
- For flows that reference structures as targets, see the `guide-flows` skill.
- For the underlying Pydantic model system that Structure inherits from, see
  the `guide-base-model` skill.
