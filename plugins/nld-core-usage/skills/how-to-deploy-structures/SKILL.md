---
name: how-to-deploy-structures
description: >
  Deploy TABLE structures to their target database with `nld structure deploy`
  — preview the computed diff and DDL first (`--preview`, exit code 2 when
  changes are pending, `--output` for a JSON change set), then apply. Covers
  scoping (`--name` / `--namespace`), the drift gate and its three
  reconciliation paths (`--adopt` / `--allow-drift` / `--rebuild`), declared
  renames via `.deployments/` change files, and the dependent-view refusal
  that hands off to `nld flow deploy`. Use when a structure YAML changed and
  the live table must follow.
user-invocable: true
---

# How to Deploy Structures

**Classification**: Atomic Skill | Deployment

---

## Definition

- **What**: Synchronize the live database tables with the TABLE structure
  assets, computing the diff against the live target and executing the DDL.
- **When**: A structure YAML was added or edited, a rename directive is
  pending, or a CI gate needs to verify the target is in sync.
- **Requires**: The project's connections configured; the target schema (and
  the metadata schema, if a `metadata_backend_connector` is set) must already
  exist. Deep concepts live in the `guide-deployment` skill.

## Commands

```bash
# Preview: diff + DDL, nothing executed, nothing recorded
nld structure deploy --preview [--output changes.json]

# Apply, whole project or scoped
nld structure deploy
nld structure deploy --namespace <ns>
nld structure deploy --name <structure> [--namespace <ns>]
```

- Scope: without `--name`, every TABLE structure in the namespace that is not
  an external source and not managed by flow execution deploys. `--name`
  targets one structure (TABLE only).
- `--preview` exits `2` when changes are pending, `0` when in sync — CI drift
  gates branch on the exit code. `--output` writes the change entries as a
  JSON array (also written when empty).
- Preview entries carry an action per structure: `CREATE` (table absent),
  `ALTER` (field/characterisation diffs), `REBUILD` (order enforcement or an
  engine-unsupported default change — backup-and-swap), `NONE`.

## Drift gate

Before applying, the live schema (A) is compared with the recorded state (R);
differences the intended change (D − R) does not explain refuse the deploy
with a precise per-column report. Pick one reconciliation path:

```bash
nld structure deploy --adopt        # record the live schema as the new baseline, then deploy
nld structure deploy --allow-drift  # deploy against the live schema, record nothing extra
nld structure deploy --rebuild      # drop and recreate from the assets (destructive)
```

- `--adopt` writes a flagged `state_refresh` baseline (never overwrites
  history) and is the bootstrap path for a database whose tables predate the
  metadata backend — see `how-to-bootstrap-deployment-backend`.
- `--rebuild` recreates in-scope structures ignoring recorded and live state.
  The drop has no CASCADE: a dependent view fails it loudly. On an empty
  database this is also the fresh-environment path: one command creates every
  in-scope structure from the assets, and repopulation is an explicit separate
  step.
- Metadata-only edits (descriptions, tags, non-structural characterisations)
  never trip the drift gate and record a `ddl_applied=false` deployment.

## Renames

An undeclared rename previews as a destructive DROP + ADD. Declare it instead
in a `.deployments/<change_id>.yaml` change file (`rename_field` /
`rename_structure`), which produces an in-place `ALTER … RENAME` ahead of the
diff. Change files require a configured `metadata_backend_connector`, apply
chronologically exactly once, and are immutable once applied. Format and
lifecycle: `guide-deployment` skill.

## Dependent views

When a change requires dropping dependent views (column drop/modify or a
rebuild), `nld structure deploy` refuses and directs to `nld flow deploy`,
which recreates the views by re-executing their VIEW flows. Exception:
`--adopt` drops the views and leaves recreation to the next flow deploy.

## Failure semantics

A failing structure is recorded and the run continues with the independent
rest (structures waiting on a failed rename target are skipped). The run ends
`partial`/`failed` with a summary error; failed structures get no metadata
row, so a rerun recomputes the same change. The run itself is recorded in
`_nld_structure_deployment`.

## Cross-References

- Concepts (A/R/D drift model, metadata tables, change files, per-connector
  capabilities): `guide-deployment` skill.
- Flow-orchestrated deployment (views, reloads, flow baselines):
  `how-to-deploy-flows`.
- Blast-radius analysis before deploying: `how-to-check-deploy-impact`.
- Bootstrap of an existing database: `how-to-bootstrap-deployment-backend`.
