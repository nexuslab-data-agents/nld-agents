---
name: how-to-check-deploy-impact
description: >
  Compute the deployment blast radius of the current repository state with
  `nld deploy impact --git-base <ref>` — a repository-only analysis (no
  database connection) that classifies changed flows, changed structures,
  pending deployment change files, and the downstream flows/structures they
  impact through the flow dependency graph. Use in a PR or CI gate to see
  what a merge will deploy, or locally to check the scope of edits before
  running a deploy.
user-invocable: true
---

# How to Check Deploy Impact

**Classification**: Atomic Skill | Deployment

---

## Definition

- **What**: Identify the changed and impacted assets of the working tree
  relative to a git ref, from the repository alone.
- **When**: Reviewing a PR, gating CI, or checking locally which flows and
  structures a set of edits will touch before deploying.
- **Requires**: A git checkout of the nld project. No database credentials —
  the command never opens a connector.

## Command

```bash
nld deploy impact --git-base origin/main [--root-folder-path <path>]
```

- `--git-base <ref>` (required) — the git ref to diff against
  (e.g. `origin/main`, `HEAD`).
- The diff covers the working tree **and untracked files**, so uncommitted
  edits are included.

## What it reports

```
Impact analysis against 'origin/main' (repo-only):
  Changed flows: sales.raw_order
  Changed structures: none
  Pending change files: 2026-07-03_1200_raw-order-refresh
  Impacted downstream flows: sales.refined_order
  Impacted downstream structures: sales.raw_order, sales.refined_order
  Changed files outside assets: <paths>   # only when some paths map to no asset
```

Classification rules:

- **Changed flows / structures** — files under `flows/<ns…>/<name>.<ext>` and
  `structure/<ns…>/<name>.<ext>` (extensions `.yml`, `.yaml`, `.sql`, `.py`)
  map to the asset `<ns>.<name>`; a flow's YAML and its SQL map to the same
  flow.
- **Pending change files** — changed or untracked files under `.deployments/`
  are listed by their `change_id`. The applied-log in the database is never
  consulted; this is the repository's view of what a deploy would pick up.
- **Impacted downstream flows / structures** — the transitive successors of
  every changed node in the flow dependency graph (flow → target structure,
  predecessor structure → flow), minus the changed sets themselves. A flow's
  own target structure appears under *impacted structures* when only the flow
  file changed. Predecessors are declared in flow YAML, which is why no
  database is needed.
- **Changed files outside assets** — paths that map to no asset (wrong root
  folder, wrong extension). Review these manually; they deploy nothing.

## Exit codes

`0` on success, `1` on any error (e.g. the git command fails). The impact
command itself has no "changes pending" exit code — for a CI drift gate use
`nld structure deploy --preview` / `nld flow deploy --preview`, which exit `2`
when changes are pending and `0` when the target is in sync.

## Typical CI pattern

```bash
# PR analysis step — no credentials needed
nld deploy impact --git-base origin/main

# Drift gate against the live target (needs credentials)
nld structure deploy --preview          # exit 2 => changes pending
```

## Cross-References

- Deployment concepts (drift model, metadata backend, change files):
  `guide-deployment` skill.
- Applying the changes: `how-to-deploy-a-project`.
- The dependency graph the expansion runs on: `how-to-trace-flow-lineage`
  (`nld flow deps`).
