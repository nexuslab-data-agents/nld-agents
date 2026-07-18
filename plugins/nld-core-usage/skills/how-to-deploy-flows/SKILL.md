---
name: how-to-deploy-flows
description: >
  Deploy nld flows with `nld flow deploy` — detect changed flow definitions
  via their YAML/SQL/Python hashes, deploy their target structures, record
  baselines in the metadata backend, and resolve pending deployment change
  files (flow renames, planned reloads). Covers preview (exit code 2 when
  changes are pending), scoping (`--name`/`--namespace`/`--upstream`/
  `--downstream`), the interactive confirmation and `--no-interactive` for
  CI, and drift reconciliation (`--adopt`/`--allow-drift`/`--rebuild`). Use
  when flow or structure assets changed and the target environment must
  follow, or as the CI apply step.
user-invocable: true
---

# How to Deploy Flows

**Classification**: Atomic Skill | Deployment

---

## Definition

- **What**: Apply the current flow and structure assets to the target
  environment: structure DDL, flow version recording, view recreation, and
  deployment directives. Deployment never executes flows (VIEW flows excepted,
  to recreate dropped views).
- **When**: After editing flow YAML / SQL / task code, after adding a
  `.deployments/` change file, or as the automated apply step on merge.
- **Requires**: `metadata_backend_connector` set in `nld_project.yml` (the
  deploy refuses without it) and that connection's schema existing.

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

`--preview` exits `2` when changes are pending, `0` when in sync. A declined
prompt cancels cleanly (exit 0, nothing applied).

## What gets deployed

- A flow is `NEW` (no recorded baseline), `CHANGED` (its YAML, SQL, or task
  Python hash differs from the recorded one), `UNCHANGED` (skipped), or
  `REMOVED` (recorded as removed; the target table is never dropped).
- Each changed flow's target structure deploys first (same diff/DDL/drift
  machinery as `nld structure deploy`), then the flow's new version is
  recorded. Flows deploy in topological order; a failure cascade-skips its
  transitive dependents and the run ends `partial`/`failed` in
  `_nld_flow_deployment`.
- Dependent views dropped by table DDL are recreated by re-executing their
  VIEW flows within the same run.
- Pending `.deployments/` change files apply chronologically, exactly once:
  `rename_flow` moves the flow identity and its table; `reload` plans a full
  refresh the next `nld flow execute` consumes (deploy itself never runs the
  flow — check with `nld flow state incremental get-planned`).

## Drift

Structure drift refusals surface exactly as in `nld structure deploy`;
reconcile with `--adopt` (rebaseline live schema), `--allow-drift` (proceed),
or `--rebuild` (recreate from assets, destructive).

## Typical CI pattern

```bash
nld deploy impact --git-base origin/main   # PR analysis, repo-only
nld flow deploy --preview --output changes.json  # gate: exit 2 = pending
nld flow deploy --no-interactive           # apply on merge
```

## Cross-References

- Concepts and internals: `guide-deployment` skill and the guide-flows
  `flow-deployment.md` document.
- Structure-only path: `how-to-deploy-structures`.
- Bootstrap of an existing database: `how-to-bootstrap-deployment-backend`.
- Executing flows and consuming planned reloads: `how-to-execute-a-flow`,
  `how-to-get-incremental-info`.
