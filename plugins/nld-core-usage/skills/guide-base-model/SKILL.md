---
name: guide-base-model
description: >
  Architectural guide for the NldBaseModel hierarchy, Pydantic foundations,
  entity management system (NldNamespace, NldNamespacedBaseModelWrapper,
  NldEntityReference), entity registry, YAML/JSON serialization, and the
  context classes (NldExecutionContext, TaskRequest, Project).
user-invocable: false
---

# Guide: Base Model & Entity System

Architectural reference for the nld-core Pydantic-based model system — the
class hierarchy, entity management, namespace resolution, and context classes.

## When to Use

Activate this guide when the agent is working on:
- Pydantic base model code in `nld/pydantic/`
- Entity loading, serialization, or registry code
- NldNamespace or NldNamespacedBaseModelWrapper
- NldEntityReference resolution
- NldExecutionContext, TaskRequest, or Project classes
- YAML/JSON entity serialization (`from_yaml`, `from_dict`, `to_dict`, `write_yaml_file`)
- Adding a new entity type to the registry

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/nld-base-model-design.md`.

### Key Sections (721 lines — read by section, not in full)

| Task | Section |
|------|---------|
| Class hierarchy overview | "1. Class Hierarchy Overview" |
| Core Pydantic layer | "2. Core Pydantic Layer" (NldBaseModel, NldNamedBaseModel, NldNamespace) |
| ResolutionContext pattern | "2.3 ResolutionContext" |
| Namespace and wrappers | "2.4 NldNamespace", "2.5 NldNamespacedBaseModelWrapper" |
| Entity references | "2.6 NldEntityReference" |
| Entity management (definitions, providers, registry) | "3. Entity Management Layer" |
| Search direction (children vs parents) | "3.2 Search Direction" |
| Context classes and entity access | "4. Context Classes & Entity Consumption" |
| NldExecutionContext | "4.3 NldExecutionContext" |
| Key patterns (dynamic resolution, filesystem loading) | "5. Key Patterns" |
| Complete entity access chain example | "5.5 Complete Entity Access Chain" |

## Cross-References

- For Structure models that inherit from this base system, see the
  `guide-structures` skill.
- For Flow tasks that use the execution context, see the `guide-flows` skill.
