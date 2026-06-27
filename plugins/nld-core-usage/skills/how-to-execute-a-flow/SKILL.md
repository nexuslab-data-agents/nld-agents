---
name: how-to-execute-a-flow
description: >
  Run an nld flow locally with `nld flow execute` — the generic CLI mechanics:
  flow-name resolution via nld_project.yml, the `--limit` (bounded, BY_KEY
  BACKFILL) vs `--full` semantics, and when `--limit` applies. Use when you want
  to execute or bound-test any nld flow (extraction, ingestion, SQL) from the
  shell. The product-specific setup (secrets, venv, where the product lives) is
  layered on top by the platform skill.
user-invocable: true
---

# How to Execute a Flow

**Classification**: Atomic Skill | Flow Execution

---

## Definition

- **What**: Run a flow defined in an nld project from the shell with
  `nld flow execute`, and bound it for testing with `--limit`.
- **When**: During development or testing, to run a specific flow (extraction,
  ingestion, or SQL transformation) defined under the project's flows path.
- **Why**: Validate that a flow works before deploying. Bounded runs give fast
  feedback without processing the full dataset.

For the flow lifecycle, write strategies and the dependency graph, see the
`guide-flows` skill. For the incremental types that `--limit` interacts with,
see `guide-incremental`.

---

## Prerequisites

- Run from a directory with `nld_project.yml` (same requirement as every `nld`
  CLI command). The CLI resolves flows through that project config.
- A reachable target connection for whatever the flow reads/writes (resolve
  names with `nld connection list`; see `how-to-check-connections`).

> Any product-specific setup the flow needs — local credentials, an activated
> virtual environment, the directory the product lives in — is **not** part of
> this generic skill. On a data platform, follow the platform's execution skill,
> which wraps this one with that setup.

---

## The command

```
nld flow execute --name <flow-name> [--limit=<N>] [--full]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--name <flow-name>` | Yes | The flow name — the YAML filename (without `.yaml`/`.yml`) under the project's flows path. The CLI resolves it via `nld_project.yml`. |
| `--limit=<N>` | No | Process at most `N` entities. **BY_KEY flows only** (see below). Use for bounded testing — it selects the BACKFILL strategy. |
| `--full` | No | Process every key in the source state. **Overrides `--limit`.** |

### Flow-name resolution

`--name` is the flow YAML's filename without extension, located under the
project's flows path (e.g. `<entity>_extraction` for
`.../flows/<sub>/<entity>_extraction.yaml`). The CLI maps name → file via
`nld_project.yml`.

### `--limit` vs `--full`

- `--limit=N` applies **only** to flows whose incremental logic is **BY_KEY**
  (the key-state machine can take a bounded subset → BACKFILL). For non-BY_KEY
  flows (e.g. direct ingestion, SQL transforms) it has no effect.
- **Never combine `--limit` with `--full`** — `--full` wins and processes the
  whole source state, silently turning a "bounded test" into a full run.
- ℹ️ `--limit` / `--full` are **runtime passthrough parameters** of the BY_KEY
  incremental logic, **not** Click options of `nld flow execute`. They do **not**
  appear in `nld flow execute --help` — that is expected. Trust them; never gate
  on `--help` or treat their absence from it as an error.

| Flow kind | Incremental | `--limit` |
|-----------|-------------|-----------|
| Extraction (key-based) | BY_KEY | Optional — e.g. `--limit=10` for a bounded test |
| Direct ingestion / SQL transform | not BY_KEY | No effect — omit |

---

## Recipes

### 1. Bounded test of a key-based flow

```
nld flow execute --name <entity>_extraction --limit=10
```

Runs the BACKFILL strategy over 10 keys — fast feedback that the flow produces
coherent output before a full run.

### 2. Full run

```
nld flow execute --name <entity>_extraction
```

(Or `--full` to force every key regardless of incremental state.)

### 3. Run a non-key flow

```
nld flow execute --name <entity>_ingestion
```

`--limit` is unnecessary (not BY_KEY).

---

## Critical rules

### ALWAYS
- Run from a directory with `nld_project.yml`.
- Use `--limit=N` **alone** for a bounded test.

### NEVER
- Combine `--full` with `--limit` (the bounded test becomes a full run).
- Gate on `nld flow execute --help` for `--limit` / `--full` — they are BY_KEY
  runtime passthrough params, absent from `--help` by design.

---

## Cross-references

- Flow lifecycle, write strategies, dependency graph: `guide-flows`.
- Incremental types (BY_KEY and friends): `guide-incremental`,
  `how-to-determine-incremental-strategy`.
- Connections the flow needs: `how-to-check-connections`.
- Inspecting what a run did: `how-to-get-execution-info`,
  `how-to-get-incremental-info`.
