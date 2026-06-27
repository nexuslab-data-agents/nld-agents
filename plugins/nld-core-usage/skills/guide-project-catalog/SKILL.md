---
name: guide-project-catalog
description: >
  Architectural guide for the nld-core NldProjectCatalog — the platform-level
  multi-project model (nld_project_catalog.yml) that records every nld project,
  its path, and the cross-project predecessor DAG. Covers the
  NldProjectCatalogEntry/NldProjectCatalog models, name-keyed YAML +
  predecessor validation, the from_yaml/get_entry/predecessors_of API, and how
  it underpins cross-product scheduling. Read when working on
  nld_project_catalog.yml or nld/project/project_catalog.py.
user-invocable: false
---

# Guide: Project Catalog (Multi-Project Model)

Architectural reference for `NldProjectCatalog` — the nld-core model that sits
**above** individual projects and records the cross-project dependency graph of
a whole platform.

This is one of four guides covering the base layer:

- `guide-base-model` — the core Pydantic classes.
- `guide-entity-registry` — entity definitions, providers, registry, loading.
- `guide-project` — a single project's execution context and `Project` container.
- **`guide-project-catalog`** (this) — the multi-project `NldProjectCatalog`.

## When to Use

Activate this guide when the agent is working on:
- `nld_project_catalog.yml` (the platform catalogue of projects)
- `nld/project/project_catalog.py` (`NldProjectCatalog`, `NldProjectCatalogEntry`)
- Cross-project predecessor links / the platform dependency DAG
- Catalog-driven project loading, or resolving an `external` cross-product
  reference (a scheduling `nld_project`) to a catalogued project

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/project-catalog-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| What the catalogue models & why | "1. What it models" |
| Entry / catalogue models | "2. Models" |
| `nld_project_catalog.yml` shape | "3. YAML shape" |
| Loading & lookup API | "4. Python API" |
| Links to Project / scheduling / platform registry | "5. Relationship to other concepts" |

## Cross-References

- `guide-project` — each catalogue entry points at one project's `nld_project.yml`.
- `guide-scheduling` — a per-flow `FlowPrecondition` with `external: true` +
  `nld_project` names a catalogued project; the catalogue is the project-grain
  view of the same cross-product dependency.
