# Structure Deployment

Structure deployment synchronizes YAML structure definitions with a target
database (PostgreSQL, BigQuery, Snowflake, DuckDB). The diff is always
recomputed against the live target: the desired state from the assets (D) is
compared with the actual database schema (A) under the control of the recorded
state (R) held in the metadata backend.

## CLI

```
nld structure deploy [--name <structure>] [--namespace <ns>]
                     [--preview] [--output <path>]
                     [--adopt | --allow-drift | --rebuild]
```

| Option | Effect |
|--------|--------|
| `--name` | Deploy one structure (TABLE only; its own namespace is resolved from the registry) |
| `--namespace` | Scope to a namespace; default is the root namespace |
| `--preview` | Compute and print diff + DDL; execute nothing, record nothing. Exit `2` when changes are pending, `0` when in sync |
| `--output` | With `--preview`, write the change entries as a JSON array to this path (written even when empty) |
| `--adopt` | On drift: record the live schema as a flagged `state_refresh` baseline, then deploy against it. Also permits dependent-view drops |
| `--allow-drift` | On drift: deploy against the live schema without recording a new baseline |
| `--rebuild` | Recreate the in-scope structures from the assets, ignoring recorded and live state (destructive) |

Without `--name`, the scope is every TABLE structure in the namespace that is
not an external source and not managed by flow execution. Live tables with no
matching asset are never diffed, dropped, or recorded — they are invisible to
structure deploy. Views are deployed by `nld flow deploy` VIEW flows, never by
structure deploy.

**Key files:**

| File | Purpose |
|------|---------|
| `nld/structure/deploy/structure_deploy_executor.py` | Run orchestration: scope resolution, per-structure loop, run record, summary error |
| `nld/structure/deploy/structure_deploy_manager.py` | Per-(connection, schema) deployment logic: drift gate, change-set computation, execution, adoption |
| `nld/structure/deploy/deploy_target_factory.py` | One manager + prefetched snapshot per (connection, schema) target; metadata backend pinning |
| `nld/structure/deploy/deploy_snapshot.py` | Schema-wide prefetch of live structures, state rows, and the view dependency graph |
| `nld/structure/deploy/structure_diff_computer.py` | Desired-vs-actual diff (fields, characterisations, order) |
| `nld/structure/deploy/structure_diff_ddl_statement_builder.py` | DDL generation (connector subclasses under `nld/connector/*/service/`) |
| `nld/structure/deploy/structure_drift.py` | A−R drift classification against the intended D−R change |
| `nld/structure/deploy/rename_resolver.py` | Declared rename resolution (in-place ALTER, no-op detection) |
| `nld/structure/deploy/rebuild_strategy_builder.py` | Backup-and-swap REBUILD statement sequence |
| `nld/structure/deploy/structure_metadata_backend_manager.py` | Metadata tables: state, history, deploy-run records |
| `nld/structure/deploy/metadata_recorder.py` | History/state writes, backend identity (`uid`) resolution across renames |
| `nld/structure/deploy/structure_schema_history.py` | Schema snapshot + hash models |
| `nld/deploy/change_file_loader.py` | `.deployments/` change-file loading, ordering, immutability |
| `nld/connector/base/deploy_capabilities.py` | `ConnectorDeployCapabilities` base + ANSI type aliases |

## Diff computation

The expanded desired structure (templates merged via `get_all_fields()`) is
compared against the live schema:

- **FieldDiff** — `ADD` / `DROP` / `MODIFY` per column, detecting data_type,
  length, precision, nullability, and default changes. Types are normalized
  through ANSI aliases plus the connector's `comparable_data_type_aliases`;
  primary-key columns compare as non-nullable; defaults are compared only when
  the asset declares one (a live serial/sequence default never churns).
- **CharacterisationDiff** — `ADD` / `DROP` / `MODIFY` for `PRIMARY_KEY`,
  `UNIQUE`, `INDEX`, intersected with the connector's
  `comparable_characterisations`.
- **Order mismatch** — computed only when field order is enforced: the
  structure's `enforce_field_order` (optional boolean) overrides the
  connector's `enforce_field_order_default`. Mismatch when common fields
  disagree on relative order, or a new field is declared before an existing
  one on an engine without positioned ADD COLUMN. Appended fields and drops
  never force a rebuild alone.

Metadata-only changes (descriptions, tags, properties, business_metadata,
non-structural characterisations) generate no DDL; they record a deployment
with `ddl_applied=false` and summary "definition updated (no schema changes)".

## Deploy strategies

| Action | Chosen when | DDL |
|--------|-------------|-----|
| `CREATE` | Table absent | CREATE TABLE + defaults + indexes/unique constraints (PK inline) |
| `ALTER` | Table exists, field/characterisation diffs | Per-diff ALTER statements; declared renames lead the sequence |
| `REBUILD` | Order mismatch, or a default change on an engine without `alter_column_set_default` | Backup-and-swap (below) |
| `NONE` | Hashes unchanged | — |

The backup-and-swap REBUILD: build `<name>__nld_new` from the desired
definition, `INSERT … SELECT` the intersection of columns in desired order
with casts to the declared types, rename the old table to
`<name>__nld_backup_<ts>` (suffix minted once per run), rename the new copy
into place, and re-add the comparable characterisations. The old table is
archived, never dropped. PostgreSQL performs the swap atomically in one
transaction; other engines run per-statement.

`--rebuild` is the separate destructive path: `DROP TABLE IF EXISTS` (no
CASCADE — a dependent view fails the drop loudly) + CREATE from the asset.

Structure removal is never destructive: a table whose asset disappeared is
left in place; only the metadata row can be soft-deleted (`fl_deleted`).

Pre/post hooks: `pre_deployment_sql_hook` / `post_deployment_sql_hook` on the
structure (the structure's list overrides a template's) run before/after the
DDL, Jinja-rendered with `schema`, `structure_name`, `object_path`, plus
project variables (built-ins cannot be shadowed).

## Drift gate

Drift is the A−R remainder: differences between the actual schema and the
recorded state that the intended change (D−R) does not explain — plus the
old/new names of pending declared renames, which are expected. Unexpected
drift refuses the deploy with a per-column report
(`recorded=… actual=…`), or `table_missing` when the recorded table was
dropped outside nld. Reconciliation is one of `--adopt` (rebaseline),
`--allow-drift` (proceed), `--rebuild` (recreate).

The gate is skipped when: no metadata backend is configured, the structure has
no recorded row (first deploy), a declared rename is pending for it, or
`--allow-drift`/`--adopt` is passed. Characterisation-only differences never
refuse a deploy. Preview applies the same refusals as apply.

## Dependent views

Views are needed for recreation when a change drops or modifies a column, or
rebuilds the table. Dependent views are discovered recursively from a
schema-wide dependency graph (deepest-first drop order). `nld structure
deploy` refuses when views must drop and directs to `nld flow deploy`, which
recreates them by re-executing their VIEW flows; `--adopt` instead drops them
and leaves recreation to the next flow deploy.

## Metadata backend

Tables are auto-created (`track_timestamps=true`); the metadata schema itself
must pre-exist. Where the tables live depends on the configuration and the
path:

- Without a `metadata_backend_connector`, each (connection, schema) target
  keeps `_nld_structure_state` / `_nld_structure_history` in its own deploy
  schema on its own connector; there is no run record and change files are
  refused.
- With a `metadata_backend_connector`, the tables are created on that
  connection. The `nld flow deploy` path pins every target's state/history to
  the connection's active schema; the `nld structure deploy` path keeps each
  target's state/history under the target's deploy schema name and writes the
  run record (`_nld_structure_deployment`) and the change-file applied-log
  (`_nld_deployment_change`) to the active schema.

- **`_nld_structure_state`** — one row per structure (PK
  `namespace, structure_name`): `object_path`, `structure_type`,
  `deployment_id`, `uid`, `deployed_at`, `structure_schema_snapshot`,
  `structure_snapshot`, `structure_schema_hash`, `structure_hash`,
  `record_source` (`deployment` | `state_refresh`), `fl_deleted`,
  `ts_deleted_at`. Upserted after every recorded deployment and on adopt.
- **`_nld_structure_history`** — append-only, one row per deployment event
  (PK `deployment_id`): the state columns plus `diff_summary`, `ddl_applied`,
  `ddl_statements`, `previous_deployment_id` (chain). The history alone
  reconstructs what DDL ran and when.
- **`_nld_structure_deployment`** — one row per apply run (PK
  `deployment_id`): `started_at`, `completed_at`, `status`
  (`running` → `success`/`partial`/`failed`), and per-run counters
  (`structures_total`, `structures_in_success`, `structures_in_error`,
  `structures_skipped`). Written only on the `metadata_backend_connector`'s
  active schema.

Hashes: `structure_schema_hash` covers the physical snapshot only (fields with
name/data_type/length/precision/nullable/default_value, structure
characterisations, structure_type, namespace); `structure_hash` covers the
full definition including descriptions and tags. The `uid` is the stable
backend identity of an asset: minted on first record and carried through every
later record, including across declared renames. It exists only in the
backend — asset YAML never carries it.

Metadata is written after successful execution: a failed structure gets no new
state/history row and a rerun recomputes the same change.

## Deployment change files

Declared, reviewable schema directives live in `.deployments/<change_id>.yaml`
at the project entities root. `change_id` matches
`^\d{4}-\d{2}-\d{2}_\d{4}(_[a-z0-9][a-z0-9-]*)?$` and must equal the file
basename; files apply in chronological (change_id) order, exactly once. Each
entry sets exactly one directive:

| Directive | Keys | Consumed by |
|-----------|------|-------------|
| `rename_field` | `structure`, `from`, `to` | structure deploy |
| `rename_structure` | `from`, `to` | structure deploy |
| `rename_flow` | `from`, `to` (target table follows the flow name) | flow deploy |
| `backfill_default` | `structure`, `field`, `value` (one-shot NULL fill) | structure deploy |
| `reload` | `flow`, `mode` (default `full`) | flow deploy |

```yaml
change_id: 2026-07-02_1430_rename-order-status
changes:
  - rename_field:
      structure: sales.refined_order
      from: cd_status
      to: cd_order_status
```

Change files require a configured `metadata_backend_connector`. The applied
log is the `_nld_deployment_change` table (PK `change_id`, with `applied_at`,
`content_hash`, `deployment_id`, `directive_outcomes`). An applied file is
immutable — a content-hash mismatch is an error ("declare a new change file
instead") — and an unapplied file older than an applied one is an
out-of-order-gap error, never silently skipped. A file is recorded as applied
only when every directive resolved in the run; a scoped deploy leaves files
with out-of-scope directives pending.

Rename resolution is idempotent four-way logic: old exists / new absent ⇒
in-place `ALTER … RENAME`; new exists / old absent ⇒ no-op (already
effective); neither ⇒ no-op (CREATE uses the new name); both ⇒ error. A
structure reclaiming a name a pending rename moves away deploys only after the
rename target freed it, as a plain CREATE with a fresh identity. On engines
without in-place rename (BigQuery) declared renames are refused.

`backfill_default` runs after DDL and hooks as
`UPDATE <schema>.<table> SET <field> = <value> WHERE <field> IS NULL`; it is
refused when the target structure is a VIEW.

## Connector capabilities

`ConnectorDeployCapabilities` parameterizes the engine differences:

| Capability | postgresql | bigquery | snowflake | duckdb |
|---|---|---|---|---|
| `alter_column_set_default` | yes | yes | no (default change ⇒ REBUILD) | yes |
| `enforce_field_order_default` | yes | no | yes | no |
| `rename_column_in_place` / `rename_table_in_place` | yes | no | yes | yes |
| `comparable_characterisations` | INDEX, PRIMARY_KEY, UNIQUE | PRIMARY_KEY | PRIMARY_KEY, UNIQUE | INDEX, PRIMARY_KEY, UNIQUE |

All engines share the ANSI alias set (`CHARACTER VARYING→VARCHAR`,
`DECIMAL→NUMERIC`, `INT→INTEGER`, `TIMESTAMP WITHOUT TIME ZONE→TIMESTAMP`)
plus connector-specific aliases (e.g. Snowflake folds every integer spelling
into NUMERIC and maps `TIMESTAMP` to `TIMESTAMP_NTZ`).

## Bootstrap of an existing database

`--adopt` seeds the backend from a database whose tables predate it: for each
asset-matched structure the live schema is recorded as a `state_refresh`
baseline (no DDL, data untouched), minting a fresh `uid` when the asset has no
prior record. Unmanaged tables are not adopted and stay invisible. Adopt
never overwrites history — it inserts a flagged record and upserts the state
row. An adopt that finds no live table falls through to recreating the
structure from the asset.

## Failure semantics

A failing structure is recorded and the run continues with the independent
rest; structures whose claimed name a failed rename target never freed are
skipped. The run ends `success`, `partial`, or `failed` (recorded with
counters in `_nld_structure_deployment`) and a summary error lists every
failure. Statement execution is sequential without cross-structure rollback;
within a backup REBUILD the new copy is fully built before the swap, so a
pre-swap failure leaves the original table serving and the leftover
`<name>__nld_new` is dropped on the next attempt.
