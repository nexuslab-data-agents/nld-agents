---
name: how-to-execute-a-flow
description: >
  Run an nld flow locally with `nld flow execute` — the generic CLI mechanics:
  determine the flow's incremental type first with `nld flow info`, then apply
  the runtime options that incremental type accepts (`--limit`/`--keys` for
  BY_KEY, `--pull-from`/`--pull-to` for BY_SOURCE_TST, `--periods` /
  `--period-from` / `--period-to` / `--limit` for BY_TARGET_PERIOD, none for
  NO_INCREMENT), plus the common `--full` / `--with-delta` options. Use when you want to execute
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
| `by_target_period` | Delta by whole calendar periods of the target. |

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

Scope is optional: `--namespace <ns>` runs every flow of a namespace, and
omitting both `--name` and `--namespace` runs **every flow in the project**,
in dependency order. Flows in different namespaces may share a name: a
`--name` matching several of them is refused as ambiguous unless one lives
in the requested namespace itself (the root namespace when `--namespace` is
omitted), so add `--namespace <ns>` to pick one.

### Common options (all incremental types)

These are real CLI options and appear in `nld flow execute --help` — but
what each one *does* is decided by the flow's incremental type, and the
types deliberately differ:

| Option | Effect |
|--------|--------|
| `--full` | Force the **FULL** strategy — process the whole source state, ignoring delta/incremental state. Honoured by every type. |
| `--with-delta` | Delta modifier. **`by_key`**: combined with `--limit`/`--keys` it selects BACKFILL_DELTA (skipping keys already terminal), and combined with `--full` it **raises**. **`by_source_tst`**: declared but never read — passing it changes nothing (use `--pull-from` alone for a delta-style backfill). **`by_target_period`**: combined with the period params it selects BACKFILL_DELTA (skipping periods already SUCCEEDED), and combined with `--full` it **raises**. **`no_increment`**: not declared. |

> The incremental-specific options below (`--limit`, `--keys`, `--pull-from`,
> `--pull-to`, `--periods`, `--period-from`, `--period-to`) are **runtime
> passthrough parameters** of the incremental logic,
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

> **Watermark rule for this type**: a bounded backfill
> (`--pull-from` **and** `--pull-to`, i.e. BACKFILL) deliberately leaves
> `last_pull_to_timestamp` untouched, so the next scheduled run resumes
> exactly where it did before. `--pull-from` alone (BACKFILL_DELTA), like
> `--full` and the plain delta run, does advance it. Do not assume this
> rule for other types — `by_key` records state for every strategy.

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
> Combining `--full` with `--with-delta` raises instead (they are mutually
> exclusive for this type).

> **State rule for this type**: every strategy — including a `--keys` /
> `--limit` backfill — merges the run's per-key outcomes into the
> persisted key state. A bounded test therefore marks the keys it
> processed as SUCCEEDED, and the next delta run skips them.

---

## `by_target_period`

Each run **replaces whole calendar periods of the target** (days, ISO weeks,
months or years) and records the outcome per period. Where a DELTA run finds
its periods depends on the flow's declared `perimeter` (`declared`,
`discovered` or `rolling`) — read it with `nld flow info` before bounding a
run.

| Option | Required | Effect |
|--------|----------|--------|
| `--periods=<p1,p2,...>` | No | Process exactly those periods. Selects **BACKFILL** — succeeded periods included. |
| `--period-from=<p>` `[--period-to=<p>]` | No | Process that range. Selects BACKFILL; without `--period-to` the range runs to the current period. |
| `--limit=<N>` | No | Cap any strategy to its **N oldest** periods; the rest are `EXCLUDED`. This is how a run refused by `max_periods_per_run` is split. |
| `--full` | No | Force FULL — every period in the source **and** every period already recorded, so a period that vanished from the source is emptied. Period params are ignored (logged as `IncrementalParameterIgnored`). |
| `--with-delta` | No | With the period params, runs BACKFILL_DELTA — the declared periods minus the `SUCCEEDED` ones. |

```
# bounded test over the 2 oldest pending periods
nld flow execute --name sales --limit=2

# rebuild one quarter
nld flow execute --name sales --period-from=2026-01 --period-to=2026-03

# normal delta: the perimeter's periods plus the pending ones
nld flow execute --name sales
```

> **Period literals must match the flow's granularity** — `2026-07-14` for
> `DAY`, `2026-W29` for ISO `WEEK` (or the Sunday date when
> `week_start: SUNDAY`), `2026-07` for `MONTH`, `2026` for `YEAR`. A
> mismatch is refused with the expected format.

> **A `declared` perimeter has no delta of its own**: a DELTA run without
> period params is refused. The caller (usually a scheduler) is the one
> that knows which period to build.

> **State rule for this type**: all four strategies record the period
> outcome, and a period that fails becomes `FAILED` even if it succeeded
> before. Every DELTA also retries the pending periods of earlier runs —
> failed ones, and discovered periods a `--limit` left out. The scan
> watermark advances only on a successful run whose periods came from a
> scan (`DELTA` of `discovered`, and `FULL`), never on a backfill.

> **A failure between the delete and the insert leaves the period empty**
> and `FAILED`; the next DELTA retries it. The two are separate statements.

---

## Critical rules

### ALWAYS
- Run `nld flow info --name <flow>` **first** to read the incremental type, then
  pick options from the matching section.
- Run from a directory with `nld_project.yml`.
- Use `--limit=N` **alone** for a bounded test (BY_KEY: N keys;
  BY_TARGET_PERIOD: the N oldest periods).

### NEVER
- Combine `--full` with `--limit`/`--keys`/`--pull-from`/`--pull-to` (the bound
  becomes a full run).
- Pass a BY_KEY option (`--keys`) to a `by_source_tst`, `by_target_period` or
  `no_increment` flow, a BY_SOURCE_TST option (`--pull-from`, `--pull-to`) or a
  BY_TARGET_PERIOD option (`--periods`, `--period-from`, `--period-to`) to any
  other type — it is silently dropped. (`--limit` is declared by both `by_key`
  and `by_target_period`, each with its own meaning.)
- Gate on `nld flow execute --help` for the passthrough options — they are
  incremental-type runtime params, absent from `--help` by design.

---

## Cross-references

- Flow lifecycle, write strategies, dependency graph: `guide-flows`.
- Incremental types (BY_KEY, BY_SOURCE_TST, BY_TARGET_PERIOD, NO_INCREMENT)
  and their semantics:
  `guide-incremental`, `how-to-determine-incremental-strategy`.
- Authoring a new incremental type (and its custom passthrough params, e.g.
  `--days-from`): `how-to-create-a-new-incremental-type`.
- Connections the flow needs: `how-to-check-connections`.
- Inspecting what a run did: `how-to-get-execution-info`,
  `how-to-get-incremental-info`.
