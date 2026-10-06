# by_target_period — rules and backend availability

Calendar-period incremental type: each run **replaces whole periods of the
target** (days, ISO weeks, months or years) and remembers the outcome per
period. State models: `ByTargetPeriodState` (calendar, scan watermark
`last_scan_at`, one entry per period ever seen) and
`ByTargetPeriodProcessingState` (the periods of one run). See the
[incremental availability overview](./README.md) for the command axes and
legend, and `guide-incremental` for the architecture.

## Configuration

The type is configured through the typed `incremental.options` block
(validated at flow load; unknown keys fail):

```yaml
incremental:
  type: by_target_period
  options:
    perimeter: rolling        # declared | discovered | rolling
    granularity: DAY          # DAY | WEEK | MONTH | YEAR
    period_field: dt_order    # target column replaced per period
write_strategy: DELETE_INSERT_SCOPED
predecessors:
  orders:
    full_path: raw.orders
    role: MASTER
```

| Option | Required | Meaning |
|--------|----------|---------|
| `perimeter` | yes | Where a DELTA run finds its periods (see below) |
| `granularity` | yes | `DAY` (`2026-07-14`), `WEEK` (`2026-W29`, see `week_start`), `MONTH` (`2026-07`) or `YEAR` (`2026`) — the period key format |
| `period_field` | yes | Target column holding the period (DATE or TIMESTAMP); the scoped delete applies to it |
| `source_period_field` | no | Same column on the MASTER predecessors, when its name differs (default `period_field`) |
| `scan_field` | no | Modification timestamp scanned on the MASTER predecessors (default: their `rec_last_update_tst` field) |
| `period_timezone` | no | IANA timezone of the calendar (default `UTC`) |
| `lookback_periods` | no | `rolling` only — number of periods of the window (default 1) |
| `include_current_period` | no | `rolling` only — the window ends with the current period instead of the last complete one |
| `max_periods_per_run` | no | Refuses a run selecting more periods (use `--limit` to split it) |
| `week_start` | no | `WEEK` only — `MONDAY` (default: ISO weeks keyed `2026-W29`) or `SUNDAY` (weeks keyed by their Sunday, `2026-07-12`; any day given on the command line is moved to its Sunday) |

Perimeters:

- **`declared`** — the caller passes the periods (`--periods=…`,
  `--period-from=… [--period-to=…]`); a DELTA run without them is refused.
  `nld flow execute` takes these flags in `--key=value` form, e.g.
  `nld flow execute --name sales --period-from=2026-01 --period-to=2026-03`.
  Typical caller: a scheduler that knows which month to (re)build.
- **`discovered`** — a DELTA run scans each MASTER predecessor for the
  periods holding rows modified since the last successful scan, then
  replaces those periods. Catches late or corrected rows.
- **`rolling`** — a DELTA run replaces the last `lookback_periods` periods
  relative to the run date (yesterday for a daily flow with the defaults).

Every DELTA also retries the **pending** periods of earlier runs: failed
ones, and discovered periods left out by `--limit`.

## Type rules

Axes: perimeter authority = declared / source scan / run date ·
selection dimension = calendar period · target update granularity =
period · change detection = none (declared, rolling) or the scan field
(discovered).

| Rule | `by_target_period` |
|------|--------------------|
| Params declared | `--full`, `--periods`, `--period-from`, `--period-to`, `--limit`, `--with-delta` |
| `DELTA` | no params — the perimeter's periods + the pending periods (refused for `declared`) |
| `FULL` | `--full` — every period present in the source (source scan, any perimeter) **and** every period already recorded in the state, so a period that vanished from the source is emptied |
| `BACKFILL` | `--periods` and/or `--period-from [--period-to]` — exactly those periods, even succeeded ones |
| `BACKFILL_DELTA` | the same + `--with-delta` — the declared periods minus the `SUCCEEDED` ones |
| `--full` + `--with-delta` | raises |
| `--limit N` | caps any strategy to its N oldest periods; the others are `EXCLUDED` |
| Ignored | period params under `FULL` (logged as `IncrementalParameterIgnored`) |
| Period outcome | recorded by all four strategies; a failed period becomes `FAILED` even if it succeeded before |
| Scan watermark | advances on a successful run whose periods came from a scan (`DELTA` of `discovered`, `FULL`); never on `BACKFILL` / `BACKFILL_DELTA` |

Period literals must match the granularity (`2026-07` for `MONTH`) or the
run is refused with the expected format.

## Write strategies

The type is **target-scoped**: each run owns the rows of its periods.

| Strategy | Verdict |
|----------|---------|
| `DELETE_INSERT_SCOPED` | recommended — deletes the period rows, then inserts the filtered query; rows that vanished from the source go too |
| `DELETE_INSERT`, `UPSERT` | allowed — keyed replacement inside the periods; vanished rows survive |
| `INSERT` | allowed — append-only targets |
| `OVERWRITE`, `VIEW`, `UPSERT_LOGICAL_DELETE` | rejected at flow load and at run time |

The delete and the insert are separate statements: a failure between them
leaves the period empty and `FAILED`; the next DELTA retries it.

## SQL behaviour

- The source query is filtered on every MASTER predecessor with one
  half-open range per group of contiguous periods
  (`col >= start AND col < end`), so partition pruning keeps working. The
  predicate goes into the SELECT reading the MASTER table, so a MASTER read
  inside a CTE, a subquery or a UNION branch is filtered where its alias is
  in scope.
- DATE and naive TIMESTAMP columns are compared to local calendar
  literals; timezone-aware columns to the UTC instant of the local
  midnight, so results never depend on the session timezone.
- The `discovered` scan groups `CAST(col AT TIME ZONE tz AS DATE)` (per
  dialect) per day and buckets days into periods in Python.
- A run selecting no period executes **no statement** on the target (no
  hooks, no write) — never an unfiltered load.
- Rows whose period column is NULL are never loaded.
- On SQLite, where dates and timestamps are stored as ISO text, periods are
  compared as text (`period_timezone` only moves the rolling reference day).

## Availability by connector / engine

| Connector / engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|--------------------|:--------------:|:-----------:|:---------:|:-------------------:|
| `postgresql` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `snowflake` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `sqlite` / `pydantic` | ✅ | ✅ | ✅ | ✅ |
| `bigquery` / `pydantic` | ✅ | ✅ | ✅ | ❌ |
| `duckdb` / `pydantic` | ✅ | ✅ | ✅ | ❌ |
| `s3_blob_storage` / `pydantic` (`json` or `parquet`) | ✅ | ✅ | ✅ | ✅ |
| `local` / `pydantic` | ✅ | ✅ | ✅ | ❌ |

The SQL connectors share one backend (`SQLModelByTargetPeriodStateBackendManager`
in `backend/sql_model_base.py`) on the connector's Pydantic model manager;
planned states come from the connector's planned-state mixin where one
exists (PostgreSQL, Snowflake, SQLite). S3 keeps the state at
`{s3_root}/state/period_state.<fmt>` and each run's processing state next to
that run's data folder. Backend modules live under
`core/nld/flow/incremental/impl/by_target_period/backend/`.

## Notes

- **SQL tables** (same names on every SQL connector) —
  `_nld_incremental_by_target_period_state` (calendar + watermark),
  `_nld_incremental_by_target_period_period_state` (one row per period; a
  run rewrites only the periods it touched),
  `_nld_incremental_by_target_period_processing_state` (one row per run,
  periods as JSON) and
  `_nld_incremental_plans_by_target_period_planned_processing_state`.
- **Calendar changes** — the state records its granularity, timezone and
  week start; a run whose options differ is refused (period keys would be
  misread).
  Clear the flow's state, then rerun with `--full`.
- **Source requests** — `compute` asks for `--source-request-authorized`
  only when the resolved run scans (`FULL`, or `DELTA` of `discovered`).
- **Planned-state freshness** — a plan of another calendar is stale and is
  refused at adoption even under `trust`; a scan-based plan is stale once
  a later run moved the scan watermark past the plan's scan.
- **Period column stability** — a row whose period changes (e.g. a
  corrected order date) leaves its old copy in the former period; replay
  that period with `--periods`.
