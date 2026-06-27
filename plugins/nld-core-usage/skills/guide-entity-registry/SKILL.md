---
name: guide-entity-registry
description: >
  Architectural guide for the nld-core entity-management layer — EntityDefinition,
  search direction (children vs parents), EntityProvider's three-level store,
  NldEntityRegistry typed accessors, the standard entity-type table, filesystem
  entity loading, and selective/lazy loading (requested_entity_definitions,
  always_load, accessors-return-empty). Read when adding an entity type, working
  on registry/loading code, or namespace resolution.
user-invocable: false
---

# Guide: Entity Registry & Management

Architectural reference for how nld-core declares, stores, loads, and retrieves
entities — the layer between the core models (`guide-base-model`) and the
running task (`guide-project`).

This is one of four guides covering the base layer:

- `guide-base-model` — the core Pydantic classes.
- **`guide-entity-registry`** (this) — entity definitions, providers, registry, loading.
- `guide-project` — execution context, `Project`, task entity consumption.
- `guide-project-catalog` — the multi-project `NldProjectCatalog`.

## When to Use

Activate this guide when the agent is working on:
- Adding or modifying an entity type (`EntityDefinition`, `folder_name`, `search_direction`)
- Registry / provider code (`nld/service/`)
- Entity loading from the filesystem, or selective / lazy loading
- Namespace resolution and duplicate-priority rules
- Registry accessors (`get_<entity>` / `get_<entity>_dict` / `list_<entity>_keys`)

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/entity-registry-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| Entity type metadata | "1. EntityDefinition" |
| children vs parents search | "2. Search Direction" |
| Storage & retrieval service | "3. EntityProvider" |
| Typed accessors + entity-type table | "4. NldEntityRegistry" |
| Typed wrappers | "5. Typed Wrappers" |
| Filesystem loading | "6. Entity Loading from Filesystem" |
| Selective / lazy loading, `always_load` | "6. → Selective / lazy entity loading" |
| Namespace resolution worked example | "7. Namespace Resolution with Search Direction" |

## Cross-References

- `guide-base-model` — `NldNamespace`, `NldEntityReference`, `ResolutionContext`
  that this layer relies on.
- `guide-project` — how a task obtains and queries the registry.
- The governance, scheduling, and business-dictionary entity types have dedicated
  guides: `guide-governance`, `guide-scheduling`, `guide-business-dictionary`.
