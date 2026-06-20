---
name: how-to-use-business-dictionary
description: >
  Look up canonical business terms from the shell with
  `nld business dict find`, or list a namespace's vocabulary with
  `nld business dict list`. Use when naming a table or field and you want
  the project's agreed vocabulary (synonyms, description, examples,
  translations, related terms) instead of guessing. Scope the search with
  `--synonym` and `--related-terms`, narrow by subdomain with `--namespace`,
  and capture the JSON output with `--output` when feeding it to another step.
user-invocable: true
---

# How to Use the Business Dictionary

**Classification**: Atomic Skill | Vocabulary Lookup

---

## Definition

- **What**: Query the project's `BusinessDictionary` from the shell via
  `nld business dict find` and consume the JSON result.
- **When**: Whenever naming a table, column, or entity, or whenever the
  user mentions a term that may have a canonical equivalent in the
  project vocabulary.
- **Why**: The dictionary is the single source of truth for names,
  synonyms, and examples. Using it keeps table and field names
  consistent across the lakehouse and lets namespace-specific
  overrides win where they exist.

For the architecture behind the entity (models, namespace resolution,
Python API), see the `guide-business-dictionary` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml` (same requirement as
  other `nld` CLI commands).
- The project must have at least one file under
  `business/dictionary/**/*.yml`. If none exist, the command returns an
  empty `matches` array rather than failing.

---

## The command

```
nld business dict find --term <query> [--synonym] [--related-terms]
                       [--namespace <ns>]
                       [--output] [--override-output-folder-path <dir>]
```

### Flags

| Flag | Required | Purpose |
|------|----------|---------|
| `--term <query>` | yes | The string to look up. Matched case-insensitively against the term's canonical `name`. |
| `--synonym` | no | Also match the query against each term's `synonyms`. |
| `--related-terms` | no | Also match the query against each term's `related_terms`. |
| `--namespace <ns>` | no | Scope the lookup to a namespace; the walker climbs parents up to the root, so namespace overrides win over `general`. Defaults to root (`.`). |
| `--output` | no | Boolean flag. Write the JSON result to `business_dictionary_find.json` under the project's standard output folder (a timestamped folder under `output/`) instead of printing to stdout. |
| `--override-output-folder-path <dir>` | no | Folder to write `business_dictionary_find.json` into. Implies `--output`. |

Flags compose. Matching precedence inside a single term is
`name → synonym → related_term` and each term appears at most once — the
deepest (most specific) namespace that has the term wins. `name` matching
covers the term's `plural` and its `translations` (each translation's name and
plural); `synonym` matching covers translation synonyms — so a term resolves
from any of its languages.

### Output shape

```json
{
  "query": "customer",
  "namespace": ".",
  "scope": { "term": true, "synonym": false, "related_terms": false },
  "matches": [
    {
      "term": {
        "name": "customer",
        "plural": "customers",
        "grammatical_class": "noun",
        "description": "...",
        "synonyms": ["client", "buyer"],
        "examples": [
          { "value": "id_customer", "description": null },
          { "value": "cd_customer_status", "description": "Lifecycle status code" }
        ],
        "related_terms": ["order"],
        "translations": [
          { "language": "fr", "name": "client", "plural": "clients", "synonyms": ["acheteur"] }
        ]
      },
      "matched_on": "name",
      "source_namespace": "."
    }
  ]
}
```

`matched_on` is always one of `"name"`, `"synonym"`, or `"related_term"`.
`source_namespace` tells you which dictionary file the term was resolved
from — useful for confirming that a namespace override actually applied. Each
`examples` entry is a `{value, description}` object (a bare string in the YAML
is serialized as a value-only object).

### Listing a namespace's vocabulary

```
nld business dict list [--namespace <ns>]
```

Lists the terms visible from a namespace (resolved nearest-first, so namespace
overrides win), with each term's source namespace, languages (primary +
translations), and synonyms. Use it to survey the available vocabulary before
naming, or to confirm which terms a subdomain inherits. Defaults to the root
namespace (`.`) when `--namespace` is omitted.

---

## Recipes

### 1. Pick the canonical name before creating a column or table

```
nld business dict find --term client
```

If `client` is a synonym of `customer`, you get zero matches with the
default scope. Re-run with `--synonym` to discover the canonical term:

```
nld business dict find --term client --synonym
```

Then name the column using the `examples` from the returned term (for
example `id_customer` rather than `id_client`).

### 2. Resolve a term inside a subdomain

```
nld business dict find --term customer --namespace finance
```

Walks `finance → general`, so a `customer` override defined in
`business/dictionary/finance/finance.yml` wins over the root
`general.yml`. Check `matches[].source_namespace` in the JSON to confirm
which file supplied the answer.

### 3. Map a free-text user term to the vocabulary

```
nld business dict find --term counterparty --synonym --namespace finance.retail
```

Any term in the `finance.retail → finance → general` chain whose `name`
or `synonyms` contains `counterparty` is returned.

### 4. Explore related concepts

```
nld business dict find --term order --related-terms
```

Returns every term that lists `order` in its `related_terms`. Useful
when you are building a table and want to discover adjacent concepts to
model at the same time.

### 5. Capture results for a downstream step

```
nld business dict find --term customer --synonym --output
```

Writes `business_dictionary_find.json` to the project's standard
timestamped output folder under `output/`; the CLI logs the resolved
path. Use `--override-output-folder-path <dir>` to place the file in a
specific folder (the file name is fixed as
`business_dictionary_find.json`):

```
nld business dict find --term customer --synonym \
    --override-output-folder-path ./out
```

Prefer these flags over redirecting stdout when composing with another
task — the CLI prints a log line to stdout when writing to a file,
which would otherwise pollute a redirected file.

---

## Guidelines for agents

- **Look first.** Before naming a new column or table from a user's free
  text, run `find --term <user_word> --synonym`. If there is a match, use
  its `examples` to shape the column name (`id_customer`, `cd_*`, `dt_*`,
  `ts_*`, …).
- **Narrow by namespace** when you know the data product's domain. The
  namespace scope is the same namespace you would pass to the Python
  `resolve_term` / `find_by_synonym` helpers.
- **Don't invent synonyms locally.** If the user keeps using a word that
  should be a synonym of an existing term, add it to the appropriate
  `business/dictionary/<ns>.yml` file instead of silently translating
  it in code.
- **Zero matches is a signal**, not a failure — consider whether a new
  term should be added to the dictionary, or whether the user's word
  should become a synonym of an existing one.

---

## Cross-references

- Architectural reference: `guide-business-dictionary` skill (models,
  filesystem layout, Python API, registry accessors).
- Field/column naming prefixes used in term `examples`: see the
  `nld-data-conventions` skills.
