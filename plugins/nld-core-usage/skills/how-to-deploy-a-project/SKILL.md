---
name: how-to-deploy-a-project
description: >
  Deploy an nld project's flows and structures with `nld flow deploy` — the
  one command that detects changed flow definitions via their YAML/SQL/Python
  hashes, computes and applies the structure DDL they need, records versions
  in the metadata backend, and resolves pending deployment change files
  (renames, planned reloads, backfill defaults). Covers preview (exit code 2
  when changes are pending, `--output` for a JSON change set), scoping
  (`--name`/`--namespace`/`--upstream`/`--downstream`), the interactive
  confirmation and `--no-interactive` for CI, and drift reconciliation
  (`--adopt`/`--allow-drift`/`--rebuild`). Use whenever flow or structure
  assets changed and a target environment must follow, or as the CI apply
  step.
user-invocable: true
---

# How to Deploy a Project

**Classification**: Atomic Skill | Deployment

---

## Definition

- **What**: Apply the current flow and structure assets to a target
  environment in one command: structure DDL, flow version recording, view
  recreation, and deployment directives. Deployment never executes flows
  (VIEW flows excepted, to recreate dropped views).
- **When**: After editing flow YAML / SQL / task code or structure YAML,
  after adding a `.deployments/` change file, or as the automated apply step
  on merge.
- **Requires**: `metadata_backend_connector` set in `nld_project.yml` (the
  deploy refuses without it) and that connection's schema existing.

Deploying always goes through `nld flow deploy` — it covers the structures
too: every in-scope flow's target structure is diffed against the live
database and deployed (CREATE / ALTER / REBUILD) right before the flow's
version is recorded. There is no separate structure step in the normal
workflow.

## Commands

```bash
# Preview the change set (flows + structure DDL), apply nothing
nld flow deploy --preview [--output changes.json]

# Apply — prompts "Proceed with deployment?" unless --no-interactive
nld flow deploy
nld flow deploy --no-interactive          # CI

# Scoped
nld flow deploy --name <flow> [--namespace <ns>]
nld flow deploy --namespace <ns>
nld flow deploy --name <flow> --downstream   # include transitive dependents
nld flow deploy --name <flow> --upstream     # include transitive ancestors
```

`--preview` exits `2` when changes are pending, `0` when in sync — the CI
gate contract. A declined prompt cancels cleanly (exit 0, nothing applied).

## What gets deployed

- A flow is `NEW` (no recorded baseline), `CHANGED` (its YAML, SQL, or task
  Python hash differs from the recorded one), `UNCHANGED` (skipped), or
  `REMOVED` (recorded as removed; the target table is never dropped).
  Removal detection runs only when the scope covers the full extent being
  compared — unscoped and `--namespace` deploys; a `--name` or
  `--upstream`/`--downstream` deploy skips it, so out-of-scope flows are
  never reported as removed.
- Each changed flow's target structure deploys first: the diff is computed
  against the live target and resolves to `CREATE` (table absent), `ALTER`
  (field/characterisation diffs), or `REBUILD` (order enforcement or an
  engine-unsupported default change — backup-and-swap, the old table
  archived as `__nld_backup_<ts>`). Flows deploy in topological order; a
  failure cascade-skips its transitive dependents and the run ends
  `partial`/`failed` in `_nld_flow_deployment`.
- Dependent views dropped by table DDL are recreated by re-executing their
  VIEW flows within the same run. A dependent view no nld VIEW flow manages
  fails the deploy before anything is dropped.
- Pending `.deployments/` change files apply chronologically, exactly once:
  renames (`rename_field` / `rename_structure` / `rename_flow`) produce
  in-place `ALTER … RENAME` ahead of the diff — an undeclared rename
  previews as a destructive DROP + ADD instead; `backfill_default` fills a
  column's NULLs once; `reload` plans a full refresh the next
  `nld flow execute` consumes (deploy itself never runs the flow — check
  with `nld flow state incremental get-planned`).
- Structures tagged `external_source` or
  `target_structure_is_managed_by_flow_execution`, and live tables with no
  matching asset, are never touched.

## Drift

Before applying, each structure's live schema is compared with its recorded
state; differences the intended change does not explain refuse the deploy
with a precise per-column report. Reconcile with:

```bash
nld flow deploy --adopt        # record the live schema as the new baseline, then deploy
nld flow deploy --allow-drift  # deploy against the live schema, record nothing extra
nld flow deploy --rebuild      # recreate structures from the assets (destructive)
```

Metadata-only edits (descriptions, tags, non-structural characterisations)
never trip the drift gate.

## Typical CI pattern

```bash
nld deploy impact --git-base origin/main         # PR analysis, repo-only
nld flow deploy --preview --output changes.json  # gate: exit 2 = pending
nld flow deploy --no-interactive                 # apply on merge
```

## The structure-only command

`nld structure deploy` exists for the cases outside the normal workflow: the
adopt-all bootstrap of an existing database
(`how-to-bootstrap-deployment-backend`) and a structure-scoped CI drift gate
(`nld structure deploy --preview`). Day-to-day deployment does not use it.

## Cross-References

- Concepts and internals (drift model, metadata tables, change-file format,
  per-connector capabilities): `guide-deployment` skill, plus
  `flow-deployment.md` / `structure-deployment.md` in the plugin docs.
- Blast-radius analysis before deploying: `how-to-check-deploy-impact`.
- Bootstrap of an existing database: `how-to-bootstrap-deployment-backend`.
- Executing flows and consuming planned reloads: `how-to-execute-a-flow`,
  `how-to-get-incremental-info`.
