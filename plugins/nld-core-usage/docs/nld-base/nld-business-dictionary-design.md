# Business Dictionary — Design Reference

## 1. Overview

The `BusinessDictionary` is a namespaced, YAML-based business vocabulary used
by agents (and runtime code) to name tables and fields consistently. Each
namespace owns a dictionary file; lookups walk the namespace hierarchy from
the most specific namespace upward to the root, so namespace-specific
overrides win over the general vocabulary at the root.

It is a standard nld-core entity, registered under the `Vocabulary` category
with entity type name `business_dictionary` and search direction `parents`
(children inherit from parents, with the nearest ancestor winning).

## 2. Models

Defined in `nld/business/dictionary.py`.

### `Term(NldBaseModel)`

A single business term.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Canonical term name. |
| `description` | `str` | Business meaning of the term. |
| `synonyms` | `list[str]` | Alternative names referring to the same concept. Used by `find_by_synonym`. |
| `examples` | `list[str]` | Example usages — typically sample column or table names (e.g. `id_customer`, `cd_customer_status`). |
| `related_terms` | `list[str]` | Names of other terms in the dictionary that are semantically related. |

### `BusinessDictionary(NldNamedBaseModel)`

A namespaced vocabulary. The `name` field (inherited from
`NldNamedBaseModel`) matches the namespace leaf (e.g. `general`, `finance`,
`retail`). Terms are indexed by canonical name:

```python
class BusinessDictionary(NldNamedBaseModel):
    terms: dict[str, Term]
```

### `NamespacedBusinessDictionary`

A `NldNamespacedBaseModelWrapper[BusinessDictionary]` — a `BusinessDictionary`
together with the namespace it was loaded from. Returned by registry
accessors.

## 3. Filesystem Layout

Dictionary files live under `business/dictionary/` at the project root. The
folder path under `business/dictionary/` is the namespace; the file is named
after the namespace leaf:

```
business/
└── dictionary/
    ├── general.yml                     # root namespace (".")
    ├── finance/
    │   ├── finance.yml                 # namespace: finance
    │   └── retail/
    │       └── retail.yml              # namespace: finance.retail
    └── …
```

Each YAML file is a `BusinessDictionary` serialization:

```yaml
name: general
terms:
  customer:
    name: customer
    description: An individual or organisation purchasing a product or service.
    synonyms:
      - client
      - buyer
    examples:
      - id_customer
      - cd_customer_status
    related_terms:
      - order
  order:
    name: order
    description: A validated request from a customer to purchase products.
    synonyms:
      - purchase
      - transaction
    examples:
      - id_order
      - dt_order_placed
    related_terms:
      - customer
```

A namespace override file only needs to redefine the terms it wants to
specialise; everything else is inherited from parent namespaces via lookup
resolution (there is no model-level merging — resolution happens at lookup
time).

```yaml
name: finance
terms:
  customer:
    name: customer
    description: A counterparty in a financial transaction.
    synonyms:
      - counterparty
      - account_holder
    examples:
      - id_counterparty
      - cd_customer_segment
    related_terms: []
```

## 4. Namespace Resolution

`nld/business/lookup.py` walks the namespace hierarchy from the deepest
namespace (closest to the caller's namespace) up to the root:

1. Build `NldNamespace(namespace)` (or root `"."` if `namespace is None`).
2. Iterate over `target.hierarchy` — every ancestor namespace including the
   target itself.
3. Collect all `BusinessDictionary` entities registered at each level.
4. Sort by namespace depth, **deepest first**, so the nearest ancestor wins.
5. Return the first match found.

Concretely, a lookup from namespace `finance.retail` sees dictionaries in
this order: `finance.retail` → `finance` → root. The first dictionary that
contains the term (or synonym) produces the answer.

## 5. Python Lookup API

Both helpers take the `NldEntityRegistry`, the query string, and an
optional namespace; both return `Term | None`.

### `resolve_term(registry, term_name, namespace=None) -> Term | None`

Exact canonical-name match on `Term.name` (dict key in `terms`). Walks the
hierarchy; returns the nearest override.

### `find_by_synonym(registry, synonym, namespace=None) -> Term | None`

Case-insensitive match against either `Term.name` or any entry in
`Term.synonyms`. Also walks the hierarchy; returns the first namespace-wise
nearest match.

Use `resolve_term` when the caller already knows the canonical name (for
example, after picking one from a UI). Use `find_by_synonym` when the caller
has a free-text term the user typed and needs to map it to the canonical
vocabulary entry.

## 6. Entity Registry Integration

`BusinessDictionary` is registered in
`nld/service/nld_entity_registry.py` as:

```python
EntityDefinition(
    name=EntityTypeNames.BUSINESS_DICTIONARY,  # "business_dictionary"
    model_type=BusinessDictionary,
    folder_name="business/dictionary",
    search_direction="parents",
    category=ENTITY_CATEGORY_VOCABULARY,       # "Vocabulary"
    display_name="Business Dictionary",
)
```

`search_direction="parents"` means registry lookups follow the same
deep-first hierarchy walk as the lookup API. The category `Vocabulary` is
added to `ENTITY_CATEGORIES` and ordered last in
`ENTITY_CATEGORY_DISPLAY_ORDER`.

### Accessors on `NldEntityRegistry`

| Method | Returns | Notes |
|--------|---------|-------|
| `get_business_dictionary(entity_key, namespace=None)` | `NamespacedBusinessDictionary` | Single dictionary by key, with nearest-override resolution. |
| `get_business_dictionary_dict(namespace=None)` | `dict[str, NamespacedBusinessDictionary]` | All visible dictionaries keyed by entity key. |
| `get_business_dictionary_keys(namespace=None)` | `list[str]` | Keys visible from the given namespace (uses search direction). |
| `list_business_dictionary_keys(namespace=None)` | `list[str]` | Keys registered at the exact namespace (no hierarchy walk). |

All accessors that take `namespace` default to the project root when it is
`None`.

## 7. Authoring Guidelines

- **One file per namespace.** Place `business/dictionary/<ns path>/<leaf>.yml`.
  The file's `name` must match the namespace leaf.
- **Start at the root** (`general.yml`) with cross-domain terms (customer,
  order, product, …). Only add namespaced files when a term genuinely has a
  different meaning in that subdomain.
- **Override sparingly.** A namespaced dictionary should only contain terms
  that need to differ from a parent. There is no model-level merge — it is
  lookup-time resolution — so a namespaced file that redeclares a term
  identically to its parent is noise.
- **Populate `synonyms` generously** so that `find_by_synonym` can map
  free-text user input to the canonical term.
- **Use real column/table names in `examples`** (e.g. `id_customer`,
  `dt_order_placed`) so agents naming fields can see concrete outputs
  consistent with the field-naming conventions (`id_`, `cd_`, `dt_`, …).
- **Keep `related_terms` to canonical names** that exist somewhere in the
  visible hierarchy — these are navigational, not definitional.
