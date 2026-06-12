---
name: guide-structures
description: >
  Architectural guide for nld-core Structure definitions, field characterisations,
  connector-specific subclass resolution, and structure deployment (diff, DDL
  generation, schema history). Covers YAML definition rules and dynamic class
  resolution across PostgreSQL, BigQuery, and Snowflake.
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
| Understanding dynamic class resolution | "Structure Inheritance & Dynamic Class Resolution" |
| Working with PostgreSQL-specific structures | "PostgreSQLStructure" |
| Adding field characterisations | "Field Characterisations", "Standard Field Characterisation Definitions" |
| Understanding tags and metadata | "Tags", "Business Metadata" |
| Full YAML example | "Complete Example" |

**structure-deployment.md** — read when working on deployment, DDL, or schema history.

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
- Output is a table: `Name | Namespace | Type | <each filtered property> | Tags`.

```
# every structure tagged with a given layer property
nld structure list --property layer=landing

# raw external-source structures in one namespace
nld structure list --namespace apec --property layer=raw --tag external_source
```

Other `nld structure` subcommands: `info` (single structure detail), `adapt`,
`deploy plan` / `deploy execute`, `render`. For inter-structure join models, see
the `guide-structure-model` skill (`nld structure model list/info/validate`).

## Cross-References

- For inter-structure join models (links, cardinality, field mappings), see the
  `guide-structure-model` skill.
- For flows that reference structures as targets, see the `guide-flows` skill.
- For the underlying Pydantic model system that Structure inherits from, see
  the `guide-base-model` skill.
