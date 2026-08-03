---
name: guide-data-quality
description: >
  Architectural guide for the nld-core data quality check system — the
  post-write quality step of the flow execution lifecycle, the flow-level
  `quality_checks` YAML block, the six built-in rules (row_count_growth,
  column_not_empty, column_min_value, column_unique, column_freshness,
  value_in_set), the valid/warning/error result status and its escalation
  through the declared warning/error/blocking severity, result
  persistence as DATA_QUALITY execution steps, the single-scan
  engine-portable measurement query, and the `additional_quality_rules`
  extension point.
user-invocable: false
---

# Guide: Flow Data Quality Checks

Architectural reference for the nld-core data quality check system — the
post-write step that evaluates rules against a flow's target structure
and records the results in the execution state.

## When to Use

Activate this guide when the agent is working on:
- Quality check code in `nld/flow/quality/`
- The `quality_checks` block of a flow definition YAML
- The data quality lifecycle hooks on `DataFlowTask`
  (`get_data_quality_context`, baseline capture, `run_data_quality_checks`)
- Check result statuses (`valid`, `warning`, `error`), the declared
  severities they escalate through (`warning`, `error`, `blocking`), or
  `DataQualityBlockingViolationException`
- The `DATA_QUALITY` steps shown by `nld flow state execution get-steps`
- Registering external rules through `additional_quality_rules`

For authoring a new rule, use the `how-to-create-a-new-data-quality-check`
skill instead.

## Document Resolution

This guide references one documentation file. First check the
project-local path. If not found, read the bundled copy.

| Document | Path |
|----------|------|
| Data quality reference | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-data-quality.md` |

### Key Sections

| Task | Section |
|------|---------|
| Where the step runs in `task.run()` | "1. Lifecycle placement" |
| The `quality_checks` YAML block and shorthands | "2. Configuration — flow level only" |
| Built-in rules and their params | "3. Built-in rules" |
| Result status, severity escalation and outcomes | "4. Status, severity and outcomes" |
| Step payload shape and CLI display | "5. Result recording and display" |
| Portable measurement SQL and measure kinds | "6. Measurement — one scan, engine-portable" |
| External rule registration | "7. Extensibility" |

## Critical Rules

- **Flow-level configuration only.** No check runs without a
  `quality_checks` block on the flow definition: there are no derived
  defaults and no project- or namespace-level check configuration.
- **Status and severity are orthogonal.** The result `status` is what the
  rule found (`valid` | `warning` | `error`, most rules being binary and
  emitting only the first and last); the declared `severity` is how far a
  non-valid status escalates. A `warning` status never fails a step
  whatever the severity — a rule that qualifies its own finding is never
  escalated. Read the combination off `is_valid`, `is_step_failure` and
  `is_blocking` rather than recomposing it.
- **Only `blocking` fails the execution.** The `warning` and `error`
  severities complete the run with the `WARNING` status (WARNING and
  FAILED step respectively); an `error` status on a `blocking` check
  raises `DataQualityBlockingViolationException` after every check result
  is recorded, marking the execution FAILED and leaving the incremental
  state untouched.
- **Payloads live in step metadata.** Check results are persisted in the
  step `metadata` dict under the `DATA_QUALITY` category — never as new
  step columns, because the metadata backend tables are never ALTERed.
- **One scan per flow.** All measures are merged into a single aggregate
  SELECT built with unquoted references and quoted lowercase aliases —
  the idiom that keeps one SQL shape portable across PostgreSQL,
  Snowflake, BigQuery, and DuckDB.
- **Hash impact.** `quality_checks` is part of the flow definition hash:
  editing checks flags the flow as CHANGED on the next `nld flow deploy`.

## Cross-References

- For the surrounding `run()` pipeline, see the `guide-flows` skill.
- For authoring an external rule, see
  `how-to-create-a-new-data-quality-check`.
- For reading the recorded check steps from the shell, see
  `how-to-get-execution-info`.
