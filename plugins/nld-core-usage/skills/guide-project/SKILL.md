---
name: guide-project
description: >
  Architectural guide for the nld-core project & execution-context layer — the
  Project container (nld_project.yml, entity_path, environments, properties),
  TaskRequest, NldExecutionContext (contextvars, load_entities, connectors),
  StandardTask, and the complete task→entity access chain. Read when working on
  Project loading, the execution context, task wiring, or nld_project.yml shape.
user-invocable: false
---

# Guide: Project & Execution Context

Architectural reference for how a running task consumes entities — the context
classes and the `Project` container that owns the entity registry.

This is one of four guides covering the base layer:

- `guide-base-model` — the core Pydantic classes.
- `guide-entity-registry` — entity definitions, providers, registry, loading.
- **`guide-project`** (this) — execution context, `Project`, task entity consumption.
- `guide-project-catalog` — the multi-project `NldProjectCatalog`.

## When to Use

Activate this guide when the agent is working on:
- `Project` loading or the `nld_project.yml` shape (`entity_path`, `environments`, `properties`)
- `NldExecutionContext`, `TaskRequest`, or `contextvars`-based context access
- `StandardTask` and how tasks pick up the active context
- `load_entities()` / `init_project()` / connector loading from the context
- The task → registry → entity access chain

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/project-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| How a task reaches entities | "1. Entity Access Chain" |
| Task input parameters | "2. TaskRequest" |
| Execution context | "3. NldExecutionContext" |
| Project container + nld_project.yml | "4. Project" |
| Standard task base class | "5. StandardTask" |
| End-to-end worked example | "6. Complete Entity Access Chain" |

## Cross-References

- `guide-entity-registry` — the registry the project owns and how loading works
  (including selective loading via `load_entities`).
- `guide-project-catalog` — when a platform is several projects.
- `guide-scheduling` — the `environments` block on `nld_project.yml`.
- `guide-connections` — connectors loaded on demand from the context.
