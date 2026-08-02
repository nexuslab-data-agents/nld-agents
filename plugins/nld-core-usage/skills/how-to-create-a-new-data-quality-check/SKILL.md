---
name: how-to-create-a-new-data-quality-check
description: >
  Author a new external data quality rule for nld-core and register it
  from `nld_project.yml`. Walks through the `DataQualityRule` contract
  (build_measures, evaluate, param validation), the measure-kind
  vocabulary and alias rules of the single-scan measurement query, and a
  complete percentage-range reference implementation living in a data
  product package.
user-invocable: false
---

# How To: Create a New Data Quality Check

`nld-core` resolves a data quality rule at runtime by looking up its name
in `DataQualityRuleRegistry`. Built-in rules live under
`nld.flow.quality.rules/`; external rules live in any importable package
and are registered through `additional_quality_rules` in
`nld_project.yml`. There are no other extension points.

## When to Use

Activate this skill when authoring or reviewing a data quality rule that
does not ship with nld-core — e.g. a domain-specific range check, a
cross-column consistency check, or a variant of a built-in with fixed
parameters. For configuring existing rules on a flow, see the
`guide-data-quality` skill.

## The Rule Contract

A rule is a `DataQualityRule` subclass providing three things:

| Member | Role |
|---|---|
| `name` (ClassVar) | Registry key, must match the manifest `name` |
| `requires_column` / `requires_baseline` (ClassVars) | Drive config validation and the pre-write `COUNT(*)` capture |
| `build_measures(check, context)` | The aggregates this check needs, merged into the flow's single-scan SELECT |
| `evaluate(check, context, measures)` | Turns the measured values into a `DataQualityCheckResult` |
| `_validate_params(check)` (optional) | Config-time param validation, surfaced by `check_coherence` |

Rules never issue SQL themselves: they declare `QualityMeasure` entries
(kind + column + params) and read the measured values back by alias, so
a rule is engine-agnostic by construction.

Available measure kinds: `ROW_COUNT`, `NON_NULL_COUNT`, `DISTINCT_COUNT`,
`MIN_VALUE`, `MAX_VALUE`, `BELOW_THRESHOLD_COUNT`,
`ABOVE_THRESHOLD_COUNT`, `EMPTY_STRING_COUNT`, `NOT_IN_SET_COUNT`.

**Alias rule**: measures are deduplicated on alias across all checks of a
flow. Use the shared alias helpers (`build_min_value_alias`, …) only for
parameter-free measures; prefix parameterized measures (threshold and set
counts) with a rule-specific tag so two rules on the same column can
never collide.

## Reference Implementation

A complete external rule, as deployed in a data product package
(`assets/utils/quality_rules.py`): NULL values allowed, values outside
[0, 100] counted as violations.

```python
from typing import Any, ClassVar

from nld.flow.quality import (
    DataQualityCheckConfig,
    DataQualityCheckResult,
    DataQualityContext,
    DataQualityRule,
    QualityMeasure,
    QualityMeasureKinds,
)
from nld.flow.quality.sql_measures import (
    build_max_value_alias,
    build_min_value_alias,
)

PERCENTAGE_RANGE_MAX = 100
PERCENTAGE_RANGE_MIN = 0


def _build_below_range_alias(column: str) -> str:
    """Rule-specific alias so shared threshold aliases cannot collide."""
    return f"prng_blw_{column.lower()}"


def _build_above_range_alias(column: str) -> str:
    """Rule-specific alias so shared threshold aliases cannot collide."""
    return f"prng_abv_{column.lower()}"


class ColumnPercentageRangeRule(DataQualityRule):
    """Check a numeric column stays inside the 0-100 percentage range."""

    name: ClassVar[str] = "column_percentage_range"
    requires_column: ClassVar[bool] = True

    def build_measures(
        self,
        check: DataQualityCheckConfig,
        context: DataQualityContext,
    ) -> list[QualityMeasure]:
        column: str = check.column  # type: ignore[assignment]
        return [
            QualityMeasure(
                alias=build_min_value_alias(column),
                column=column,
                kind=QualityMeasureKinds.MIN_VALUE,
            ),
            QualityMeasure(
                alias=build_max_value_alias(column),
                column=column,
                kind=QualityMeasureKinds.MAX_VALUE,
            ),
            QualityMeasure(
                alias=_build_below_range_alias(column),
                column=column,
                kind=QualityMeasureKinds.BELOW_THRESHOLD_COUNT,
                threshold=float(PERCENTAGE_RANGE_MIN),
            ),
            QualityMeasure(
                alias=_build_above_range_alias(column),
                column=column,
                kind=QualityMeasureKinds.ABOVE_THRESHOLD_COUNT,
                threshold=float(PERCENTAGE_RANGE_MAX),
            ),
        ]

    def evaluate(
        self,
        check: DataQualityCheckConfig,
        context: DataQualityContext,
        measures: dict[str, Any],
    ) -> DataQualityCheckResult:
        column: str = check.column  # type: ignore[assignment]
        min_observed = measures.get(build_min_value_alias(column))
        max_observed = measures.get(build_max_value_alias(column))

        # SUM over an empty table returns NULL, meaning zero violations.
        below_count = int(measures.get(_build_below_range_alias(column)) or 0)
        above_count = int(measures.get(_build_above_range_alias(column)) or 0)
        violations = below_count + above_count

        passed = violations == 0
        message = (
            None
            if passed
            else (
                f"{violations} value(s) outside "
                f"[{PERCENTAGE_RANGE_MIN}, {PERCENTAGE_RANGE_MAX}]"
            )
        )
        return DataQualityCheckResult(
            column=column,
            message=message,
            observed=f"{min_observed} → {max_observed}",
            passed=passed,
            rule=self.name,
            severity=check.severity,
            violation_count=violations,
        )
```

## Registration

Declare the rule in the project's `nld_project.yml`; the class is
imported, instantiated, and registered when the project loads:

```yaml
additional_quality_rules:
  - name: column_percentage_range
    rule_class: assets.utils.quality_rules.ColumnPercentageRangeRule
```

Registration fails loudly when the name collides with a registered rule,
when `rule_class` is not a `DataQualityRule` subclass, or when the class
`name` differs from the manifest `name`. `nld project info` lists the
registered additional rules.

## Use It on a Flow

```yaml
quality_checks:
  checks:
    - rule: column_percentage_range
      columns:
        - num_parity_men
        - num_parity_women
```

## Result Conventions

- Set `violation_count` to the number of rows not matching the check —
  it is persisted with the step and rendered as `violations=N`.
- Do not repeat the column name in the message (it is in the step name)
  nor the observed values (they are in the `observed` field).
- Set `expected` only when it carries run-specific information the rule
  name does not imply (a configured threshold, an allowed set, a
  baseline).
- Report an unevaluable check as `passed=True, skipped=True` with the
  skip reason in `message` — never fail a run for missing inputs.

## Testing

- Unit-test `evaluate` with hand-built `measures` dicts (pass, fail,
  empty-table NULL sums, missing measures → skipped).
- Unit-test `build_measures` aliases and kinds; `validate_check` for
  missing column and bad params.
- Exercise the registration path with a project fixture declaring
  `additional_quality_rules`, mirroring
  `tests/unit/project/test_project_additional_quality_rules.py` in
  nld-core.
