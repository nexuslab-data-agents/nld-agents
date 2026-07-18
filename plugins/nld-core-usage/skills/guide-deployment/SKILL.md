---
name: guide-deployment
description: >
  Architectural guide for the nld-core deployment system — the structure
  deploy path (`nld structure deploy`: live diff, DDL, A/R/D drift gate,
  adopt/allow-drift/rebuild), the flow deploy path (`nld flow deploy`:
  definition-hash change detection, baselines, view recreation, planned
  reloads), repository-only impact analysis (`nld deploy impact`), the
  `.deployments/` change files (renames, reloads, backfill defaults), and
  the metadata backend tables that make deployments auditable and
  exactly-once. Read when working on deploy code in nld/structure/deploy/,
  nld/flow/deploy/, or nld/deploy/, or reasoning about what a deploy will do.
user-invocable: false
---

# Guide: Deployment

Architectural reference for the nld-core deployment system — how asset
definitions (structures and flows) are applied to target databases, tracked,
and audited.

## When to Use

Activate this guide when the agent is working on:
- Structure deploy code in `nld/structure/deploy/`
- Flow deploy code in `nld/flow/deploy/` or `nld/flow/task/data_flow_deploy_task.py`
- Deployment-wide code in `nld/deploy/` (impact analysis, change files)
- `.deployments/` change files or the `metadata_backend_connector` setting
- CI deploy gates, drift errors, or the deploy metadata tables (`_nld_*`)

## Document Resolution

For each document, first check the project-local path; if not found, read the
bundled copy.

| Document | Path |
|----------|------|
| Structure deployment (diff, DDL, drift, change-file format, connector capabilities) | `${CLAUDE_PLUGIN_ROOT}/docs/structure/structure-deployment.md` |
| Flow deployment (change detection, scope, executor, metadata tables) | `${CLAUDE_PLUGIN_ROOT}/docs/flow/flow-deployment.md` |

## The deployment model

Three commands share one model:

| Command | Role | Needs DB |
|---|---|---|
| `nld deploy impact --git-base <ref>` | Classify changed + downstream-impacted assets from the repository alone | no |
| `nld structure deploy` | Diff and apply TABLE structures directly | yes |
| `nld flow deploy` | Detect changed flows, deploy their target structures, record flow versions, resolve directives | yes |

Shared principles:

- **The diff is always live.** Nothing is planned ahead and replayed; every
  run recomputes desired-vs-actual against the target. `--preview` prints the
  computed change set and exits `2` when changes are pending, `0` when in
  sync — the CI gate contract.
- **Three states.** D = desired (assets), A = actual (live schema), R =
  recorded (metadata backend). Drift is the A−R remainder; drift the intended
  D−R change does not explain refuses the deploy, reconciled by `--adopt`
  (rebaseline), `--allow-drift` (proceed), or `--rebuild` (recreate).
- **Never destructive by default.** Removed assets are recorded, not dropped;
  rebuilds archive the old table (`__nld_backup_<ts>`); undeclared renames
  surface as reviewable drop+add in preview instead of silently applying.
- **Exactly-once directives.** Schema intentions that a diff cannot infer
  (renames, reloads, one-shot backfills) are declared in `.deployments/`
  change files, applied chronologically once, and logged in
  `_nld_deployment_change`.
- **Identity is backend-held.** Each asset's stable `uid` is minted by the
  backend on first record (deploy or adopt) and carried across declared
  renames; asset YAML never contains it.

## Development environment patterns

The deploy model serves every environment the same way — what differs is where
the data comes from:

- **CI / staging / prod**: `nld flow deploy --no-interactive` applies the
  committed assets; `--preview` in a gate step asserts the target is in sync.
- **Fresh developer environment**: `nld structure deploy --rebuild` on an
  empty database creates every in-scope structure from the assets in one shot;
  repopulation is an explicit separate step (flow executions or a data
  import).
- **Snowflake development on production data**: deploy the working tree
  against a zero-copy clone (or a prod-data-connected dev database) to
  validate changes on real data shape and volume without copying.
- **PostgreSQL development**: iterate against locally extracted data, or
  against a prod-like snapshot imported into the dev database, then deploy
  normally.
- **Existing live environment, empty backend**: adopt-all bootstrap
  (`how-to-bootstrap-deployment-backend`).

Production has no runtime destructive gate and no destructive-confirmation
flag: destructive changes are caught at review time in the PR preview, and a
DDL error at apply time fails that structure loudly — its metadata is not
written, its dependents are skipped, and the run ends `partial`/`failed` with
the failure recorded.

## Per-connector capabilities

Deployment behavior is parameterized by `ConnectorDeployCapabilities`
(`nld/connector/base/deploy_capabilities.py`, one subclass per connector):

| Capability | postgresql | bigquery | snowflake | duckdb |
|---|---|---|---|---|
| ALTER COLUMN SET/DROP DEFAULT | yes | yes | no — a default change triggers REBUILD | yes |
| `enforce_field_order_default` | yes | no | yes | no |
| Declared renames in place (`rename_field` / `rename_structure`) | yes | no — refused | yes | yes |
| Comparable characterisations | INDEX, PRIMARY_KEY, UNIQUE | PRIMARY_KEY | PRIMARY_KEY, UNIQUE | INDEX, PRIMARY_KEY, UNIQUE |
| Dependent-view detection | yes | yes | yes | yes |
| Atomic rebuild swap (single transaction) | yes | no | no | no |

Type comparison folds ANSI aliases for every engine plus connector-specific
aliases (e.g. Snowflake folds every integer spelling into NUMERIC and maps
`TIMESTAMP` to `TIMESTAMP_NTZ`). Full table and DDL-builder deltas:
`structure-deployment.md`.

`reload` directives depend on the flow's incremental **state backend**, not
the deploy connector: planning a full refresh requires a backend with
planned-state support (PostgreSQL, Snowflake, and S3 blob storage state
backends) and a state-tracking incremental type (`by_key`,
`by_source_tst`). Otherwise the directive records a warning outcome and a
manual `nld flow execute <flow> --full` is advised; stateless flows record
`no-op (every run is already a full refresh)`.

## Metadata backend

`metadata_backend_connector` in `nld_project.yml` names the connection whose
active schema hosts all deploy metadata. It is required by `nld flow deploy`
and by change files; without it, `nld structure deploy` still works, keeping
per-target metadata in each deploy schema. Tables are auto-created; the schema
must pre-exist.

| Table | Owner | Grain |
|---|---|---|
| `_nld_structure_state` | structure deploy | current recorded schema per structure |
| `_nld_structure_history` | structure deploy | append-only deployment events (DDL, diffs, chain) |
| `_nld_structure_deployment` | structure deploy | one row per `nld structure deploy` run |
| `_nld_flow_state` | flow deploy | current recorded version per flow (hash components) |
| `_nld_flow_history` | flow deploy | append-only flow deployment events |
| `_nld_flow_deployment` | flow deploy | one row per `nld flow deploy` run (status + counters) |
| `_nld_flow_deployment_flow_change` / `_nld_flow_deployment_structure_change` | flow deploy | per-asset outcomes of a run |
| `_nld_deployment_change` | both | applied-log of change files (exactly-once, content-hashed) |

The history tables alone reconstruct what was deployed, what DDL ran, and
when — the audit trail is the backend, not the git history of any artifact.

## Change files

`.deployments/<change_id>.yaml`, `change_id` = `<date>_<time>[_<slug>]`
(e.g. `2026-07-02_1430_rename-order-status`), applied in change_id order.
Directives are grouped by target asset — `changes.structures.<name>` entries
declare `rename_field`, `rename_structure`, or `backfill_default`;
`changes.flows.<name>` entries declare `rename_flow` or `reload` (renames
keyed by the pre-rename name). Applied files are immutable (content-hash
checked); unapplied files older than an applied one are an out-of-order
error. Full format: `structure-deployment.md`.

## Typical lifecycles

- **PR review**: `nld deploy impact --git-base origin/main` (no credentials)
  → reviewers see changed assets, blast radius, and pending change files.
- **CI gate**: `nld structure deploy --preview` / `nld flow deploy --preview`
  — exit 2 blocks on pending changes or asserts A == R.
- **Apply on merge**: `nld flow deploy --no-interactive`.
- **Migrating an existing database**: adopt-all then baseline — the
  `how-to-bootstrap-deployment-backend` skill.

## Cross-References

- Operational how-tos: `how-to-deploy-a-project`,
  `how-to-check-deploy-impact`, `how-to-bootstrap-deployment-backend`.
- Structure definitions and characterisations: `guide-structures`.
- Flow definitions, write strategies, dependency graph: `guide-flows`.
- Planned incremental state (reload consumption): `guide-incremental`.
