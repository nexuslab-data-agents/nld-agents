---
name: how-to-execute-a-flow
description: >
  Run an nld flow locally with `nld flow execute` — the generic CLI mechanics:
  determine the flow's incremental type first with `nld flow info`, then apply
  the runtime options that incremental type accepts (`--limit`/`--keys` for
  BY_KEY, `--pull-from`/`--pull-to` for BY_SOURCE_TST, none for NO_INCREMENT),
  plus the common `--full` / `--with-delta` options. Use when you want to execute
  or bound-test any nld flow (extraction, ingestion, SQL) from the shell. The
  product-specific setup (secrets, venv, where the product lives) is layered on
  top by the platform skill.
user-invocable: true
---

# How to Execute a Flow

**Classification**: Atomic Skill | Flow Execution

---

## Definition

- **What**: Run a flow defined in an nld project from the shell with
  `nld flow execute`, applying the runtime options its incremental type accepts.
- **When**: During development or testing, to run a specific flow (extraction,
  ingestion, or SQL transformation) defined under the project's flows path.
- **Why**: Validate that a flow works before deploying. Bounded runs give fast
  feedback without processing the full dataset.

For the flow lifecycle, write strategies and the dependency graph, see the
`guide-flows` skill. For the incremental types these options interact with, see
`guide-incremental`.

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

## Step 1 — Determine the incremental type (always first)

The runtime options a flow accepts depend entirely on its **incremental type**.
Before executing, inspect the flow:

```
nld flow info --name <flow-name>
```

Read the **`Incremental:`** line of the output. It is one of:

| Incremental | Meaning |
|-------------|---------|
| `no_increment` | No delta tracking — every run is a full run. |
| `by_source_tst` | Delta by a source timestamp watermark. |
| `by_key` | Delta by a key-state machine. |

The flow name is the YAML filename without extension (e.g. `<entity>_extraction`
for `.../flows/<sub>/<entity>_extraction.yaml`), resolved via `nld_project.yml`.

> Then jump to the section below that matches the type — that is where the
> incremental-specific options live.

---

## Step 2 — Execute

### The standard command

```
nld flow execute --name <flow-name>
```

With no extra options this runs the flow's **default loading strategy**
(typically the normal DELTA for incremental types, FULL for `no_increment`).
**Custom runtime options are available depending on the incremental type** — see
the matching section below.

### Common options (all incremental types)

These are real CLI options and appear in `nld flow execute --help`:

| Option | Effect |
|--------|--------|
| `--full` | Force the **FULL** strategy — process the whole source state, ignoring delta/incremental state. |
| `--with-delta` | Run a delta pass alongside the requested strategy. |

> The incremental-specific options below (`--limit`, `--keys`, `--pull-from`,
> `--pull-to`) are **runtime passthrough parameters** of the incremental logic,
> **not** Click options of `nld flow execute`. They do **not** appear in
> `nld flow execute --help` — that is by design. Trust them; never gate on
> `--help` or treat their absence from it as an error. A passthrough option that
> does not belong to the flow's incremental type is silently dropped.

---

## `no_increment`

Always runs **FULL** — there is no incremental state to bound.

```
nld flow execute --name <flow-name>
```

- **No incremental-specific options.** `--limit`, `--keys`, `--pull-from`,
  `--pull-to` have no effect (silently dropped).
- `--full` is redundant (the run is already full).

Typical for direct ingestion and SQL transforms with no watermark.

---

## `by_source_tst`

Delta is driven by a **source timestamp watermark**. You can override the window
for a bounded backfill.

| Option | Required | Effect |
|--------|----------|--------|
| `--pull-from=<datetime>` | No | Override the window **start**. Triggers a BACKFILL_DELTA over the given range. |
| `--pull-to=<datetime>` | No | Override the window **end**. With `--pull-from` set, both bounds give a BACKFILL over `[from, to]`. |
| `--full` | No | Force FULL — re-pull everything, ignoring the watermark. |

`<datetime>` is ISO-8601 (e.g. `2026-06-01T00:00:00`).

```
# normal delta from the persisted watermark
nld flow execute --name <entity>_extraction

# bounded backfill over an explicit window
nld flow execute --name <entity>_extraction \
  --pull-from=2026-06-01T00:00:00 --pull-to=2026-06-08T00:00:00
```

> The built-in `by_source_tst` accepts **no** `--limit` or `--days-from`. A
> `--days-from`-style backfill exists only in the external custom incremental
> type (see `how-to-create-a-new-incremental-type`).

---

## `by_key`

Delta is driven by a **key-state machine**. You can bound the run to a subset of
keys for fast testing.

| Option | Required | Effect |
|--------|----------|--------|
| `--limit=<N>` | No | Process at most `N` keys. Selects the **BACKFILL** strategy — ideal for a bounded test. |
| `--keys=<k1,k2,...>` | No | Process exactly the listed keys (comma-separated). Selects BACKFILL. |
| `--full` | No | Force FULL — process every key in the source state. **Overrides `--limit`/`--keys`.** |
| `--with-delta` | No | Combined with `--limit`/`--keys`, runs BACKFILL_DELTA. |

```
# bounded test over 10 keys
nld flow execute --name <entity>_extraction --limit=10

# specific keys
nld flow execute --name <entity>_extraction --keys=AAA,BBB,CCC

# full run (default delta if omitted)
nld flow execute --name <entity>_extraction
```

> **Never combine `--limit` with `--full`** — `--full` wins and processes the
> whole source state, silently turning a "bounded test" into a full run.

---

## Critical rules

### ALWAYS
- Run `nld flow info --name <flow>` **first** to read the incremental type, then
  pick options from the matching section.
- Run from a directory with `nld_project.yml`.
- Use `--limit=N` (BY_KEY) **alone** for a bounded test.

### NEVER
- Combine `--full` with `--limit`/`--keys`/`--pull-from`/`--pull-to` (the bound
  becomes a full run).
- Pass a BY_KEY option (`--limit`, `--keys`) to a `by_source_tst` or
  `no_increment` flow, or a BY_SOURCE_TST option (`--pull-from`, `--pull-to`) to
  any other type — it is silently dropped.
- Gate on `nld flow execute --help` for the passthrough options — they are
  incremental-type runtime params, absent from `--help` by design.

---

## Cross-references

- Flow lifecycle, write strategies, dependency graph: `guide-flows`.
- Incremental types (BY_KEY, BY_SOURCE_TST, NO_INCREMENT) and their semantics:
  `guide-incremental`, `how-to-determine-incremental-strategy`.
- Authoring a new incremental type (and its custom passthrough params, e.g.
  `--days-from`): `how-to-create-a-new-incremental-type`.
- Connections the flow needs: `how-to-check-connections`.
- Inspecting what a run did: `how-to-get-execution-info`,
  `how-to-get-incremental-info`.
