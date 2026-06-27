---
name: guide-base-model
description: >
  Architectural guide for the core nld-core Pydantic layer — the NldBaseModel /
  NldNamedBaseModel hierarchy, NldNamespace, NldNamespacedBaseModelWrapper,
  NldEntityReference, the ResolutionContext reference-resolution machinery, and
  YAML/JSON serialization. Read when working on base model code in
  nld/pydantic/, namespaces, entity references, or serialization. For the entity
  registry see guide-entity-registry; for context/Project see guide-project.
user-invocable: false
---

# Guide: Base Model (Core Pydantic Layer)

Architectural reference for the foundational nld-core model system — the class
hierarchy, namespaces, entity references, and the serialization /
reference-resolution machinery every entity is built on.

This is one of four guides covering the base layer:

- **`guide-base-model`** (this) — the core Pydantic classes.
- **`guide-entity-registry`** — entity definitions, providers, registry, loading.
- **`guide-project`** — execution context, `Project`, task entity consumption.
- **`guide-project-catalog`** — the multi-project `NldProjectCatalog`.

## When to Use

Activate this guide when the agent is working on:
- Pydantic base model code in `nld/pydantic/`
- `NldNamespace` or `NldNamespacedBaseModelWrapper`
- `NldEntityReference` resolution
- `ResolutionContext` and string-reference resolution during deserialization
- YAML/JSON entity serialization (`from_yaml`, `from_dict`, `to_dict`, `write_yaml_file`)
- Dynamic entity subclass resolution (e.g. connector-specific `Structure`)

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/base-model-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| Class hierarchy overview | "1. Class Hierarchy Overview" |
| NldBaseModel / NldNamedBaseModel | "2.1", "2.2" |
| ResolutionContext | "2.3", and the pattern in "3.2 ResolutionContext Pattern" |
| Namespaces and wrappers | "2.4 NldNamespace", "2.5 NldNamespacedBaseModelWrapper" |
| Entity references | "2.6 NldEntityReference" |
| Dynamic entity class resolution | "3.1 Dynamic Entity Class Resolution" |

## Cross-References

- `guide-entity-registry` — how these models are stored, loaded and retrieved.
- `guide-project` — how a running task consumes entities via the context.
- For Structure models that inherit from this base system, see `guide-structures`.
