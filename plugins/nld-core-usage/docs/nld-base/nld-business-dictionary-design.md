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

A single business term, expressed in its dictionary's primary language;
alternate languages are provided via `translations`.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Canonical term name (singular). |
| `plural` | `str \| None` | Plural form of the name (e.g. `employees` for `employee`). |
| `grammatical_class` | `str \| None` | One of `noun`, `adjective`, `verb`, `pronoun`, `adverb`, `preposition`, or empty. |
| `preferred_term` | `str \| None` | Name of another term to prefer over this one (e.g. `legal_entity` → `company`). |
| `description` | `str` | Business meaning of the term. |
| `synonyms` | `list[str]` | Alternative names referring to the same concept. Used by `find_by_synonym`. |
| `examples` | `list[Example]` | Example usages — sample column/table names or composed terms. A bare string is shorthand for a value-only example. |
| `related_terms` | `list[str]` | Names of other terms in the dictionary that are semantically related. |
| `translations` | `list[TermTranslation]` | The term rendered in other languages. |

### `Example(NldBaseModel)`

A concrete usage of a term.

| Field | Type | Purpose |
|-------|------|---------|
| `value` | `str` | The example usage (e.g. a sample column/table name `ds_legal_name`, or a composed term `gender_parity`). |
| `description` | `str \| None` | What this particular usage means. |

A bare YAML string expands to a value-only `Example` (`{value: <string>}`), so
`examples: [id_customer]` and `examples: [{value: id_customer}]` are equivalent.

### `TermTranslation(NldBaseModel)`

A term rendered in another language.

| Field | Type | Purpose |
|-------|------|---------|
| `language` | `str` | ISO 639 language code of this translation (e.g. `fr`). |
| `name` | `str` | Term name in this language (singular). |
| `plural` | `str \| None` | Plural form of the name in this language. |
| `description` | `str \| None` | Business meaning in this language. |
| `synonyms` | `list[str]` | Alternative names in this language. |
| `examples` | `list[Example]` | Example usages in this language. |

### `BusinessDictionary(NldNamedBaseModel)`

A namespaced vocabulary. The `name` field (inherited from
`NldNamedBaseModel`) matches the namespace leaf (e.g. `general`, `finance`,
`retail`). The dictionary declares the primary language of its terms; terms are
indexed by canonical name:

```python
class BusinessDictionary(NldNamedBaseModel):
    language: str  # primary ISO 639 code of the terms, default "en"
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

Each YAML file is a `BusinessDictionary` serialization. The dictionary's
`language` is the primary language of its terms; a term may carry `plural`,
`translations`, and rich `examples`:

```yaml
name: general
language: en
terms:
  customer:
    name: customer
    plural: customers
    grammatical_class: noun
    description: An individual or organisation purchasing a product or service.
    synonyms:
      - client
      - buyer
    examples:
      - id_customer                                   # value-only shorthand
      - { value: cd_customer_status, description: Lifecycle status code }
    related_terms:
      - order
    translations:
      - language: fr
        name: client
        plural: clients
        synonyms:
          - acheteur
  order:
    name: order
    plural: orders
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

`resolve_term` and `find_by_synonym` take the `NldEntityRegistry`, the query
string, and an optional namespace, and return `Term | None`. `find_terms`
returns every match as a list.

### `resolve_term(registry, term_name, namespace=None) -> Term | None`

Exact canonical-name match on `Term.name` (dict key in `terms`). Walks the
hierarchy; returns the nearest override.

### `find_by_synonym(registry, synonym, namespace=None) -> Term | None`

Case-insensitive match against the term's `name`, `plural`, or any entry in
`synonyms`. Matching covers `translations` too — each translation's `name`,
`plural`, and `synonyms` — so a term resolves from any of its languages. Walks
the hierarchy; returns the first namespace-wise nearest match.

### `find_terms(registry, query, match_name=True, match_synonym=False, match_related=False, namespace=None) -> list[FindMatch]`

Returns **every** term matching `query` across the visible hierarchy. The scope
flags select which `Term` fields participate:

- `match_name` — canonical `name`/`plural` (and translation names/plurals).
- `match_synonym` — `synonyms` (and translation synonyms).
- `match_related` — `related_terms`.

Matching is case-insensitive exact string equality against each enabled field.
Each `FindMatch` carries the `term`, `matched_on` (`"name"`, `"synonym"`, or
`"related_term"`), and `source_namespace`. When the same term name appears in
multiple namespaces the deepest (most specific) definition wins, preserving the
override semantics of `resolve_term` / `find_by_synonym`.

Use `resolve_term` when the caller already knows the canonical name. Use
`find_by_synonym` for the single nearest match of a free-text term. Use
`find_terms` when you need all matches and the field that matched (this is what
the `nld business dict find` CLI is built on).

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
  consistent with the field-naming conventions (`id_`, `cd_`, `dt_`, …). Use
  the `{value, description}` form when the usage needs explaining; the bare
  string otherwise.
- **Keep terms singular** and put the plural in `plural` so both forms resolve.
- **Set the dictionary `language`** and add `translations` for terms used in
  more than one language — `find_by_synonym` and `find_terms` match translation
  names and synonyms, so a term resolves from any of its languages.
- **Keep `related_terms` to canonical names** that exist somewhere in the
  visible hierarchy — these are navigational, not definitional.
