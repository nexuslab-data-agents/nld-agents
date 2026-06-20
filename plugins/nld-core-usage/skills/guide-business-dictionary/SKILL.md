---
name: guide-business-dictionary
description: >
  Architectural guide for the nld-core BusinessDictionary entity — a namespaced,
  YAML-based business vocabulary used by agents to name tables and fields.
  Covers the Term/BusinessDictionary models (multi-language translations,
  singular/plural, rich examples), namespace hierarchy resolution (nearest
  override wins), the `resolve_term` / `find_by_synonym` / `find_terms` Python
  API, and the `NldEntityRegistry.get_business_dictionary*` accessors.
user-invocable: false
---

# Guide: Business Dictionary

Architectural reference for the nld-core `BusinessDictionary` entity — the
namespaced vocabulary system that agents consult when naming tables and
fields, and that runtime code can query for canonical business terms.

## When to Use

Activate this guide when the agent is working on:
- Code under `nld/business/` (`dictionary.py`, `lookup.py`)
- Authoring or editing `business/dictionary/**/*.yml` vocabulary files
- Adding term `translations`, `plural` forms, or `{value, description}` examples
- Calling `resolve_term`, `find_by_synonym`, or `find_terms`
- Using `NldEntityRegistry.get_business_dictionary` /
  `get_business_dictionary_dict` / `get_business_dictionary_keys` /
  `list_business_dictionary_keys`
- Naming tables or fields and needing to pick the canonical business term
- Adding synonyms, examples, or related terms to an existing namespace
- Creating a namespace-specific override of a general term

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/nld-business-dictionary-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| Motivation and overall design | "1. Overview" |
| `Term` and `BusinessDictionary` models | "2. Models" |
| YAML file layout (`business/dictionary/<ns>/<ns>.yml`) | "3. Filesystem Layout" |
| Namespace hierarchy and override rules | "4. Namespace Resolution" |
| `resolve_term` / `find_by_synonym` / `find_terms` | "5. Python Lookup API" |
| Registry accessors | "6. Entity Registry Integration" |
| Concept-curation discipline for vocabulary files | "7. Authoring Discipline" |

## Cross-References

- The BusinessDictionary inherits from `NldNamedBaseModel` and is wrapped by
  `NldNamespacedBaseModelWrapper` — see the `guide-base-model` skill for the
  base class hierarchy and namespace resolution mechanics.
- For naming conventions the dictionary terms ultimately feed into (column
  prefixes like `cd_`, `id_`, `dt_`, structure and field characterisations),
  see the `nld-data-conventions` skills.
