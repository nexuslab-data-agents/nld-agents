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

## Cross-References

- For flows that reference structures as targets, see the `guide-flows` skill.
- For the underlying Pydantic model system that Structure inherits from, see
  the `guide-base-model` skill.
