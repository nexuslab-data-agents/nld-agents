---
name: how-to-bootstrap-deployment-backend
description: >
  Initialize the deployment metadata backend of an nld project whose database
  already exists (tables deployed by hand or by another system, metadata
  empty): adopt-all the live structures with `nld structure deploy --adopt`,
  record every flow's baseline with a first `nld flow deploy`, then verify a
  normal change deploys cleanly. Use when migrating a live environment to the
  nld deployment model without rebuilding it, or when standing up the
  metadata backend for an existing PostgreSQL/BigQuery/Snowflake target.
user-invocable: true
---

# How to Bootstrap the Deployment Backend

**Classification**: Atomic Skill | Deployment

---

## Definition

- **What**: Seed the deployment metadata backend (`_nld_structure_*`,
  `_nld_flow_*` tables) from a database whose tables are already live, without
  touching data, so that subsequent deploys work normally.
- **When**: A project's tables exist but the metadata backend is empty — the
  migration path onto the deployment model.
- **Requires**: Project connections configured; `metadata_backend_connector`
  set in `nld_project.yml` when flow deploy or change files are used; the
  metadata schema existing (tables are auto-created, the schema is not).

## Procedure

```bash
# 1) Structures: adopt-all seeds the recorded state from the live schema
#    (no DDL, data untouched)
nld structure deploy --adopt [--namespace <ns>]

# 2) Flows: the first deploy records every flow's baseline
#    (no reload scheduled, no structure DDL — diffs are empty after adopt)
nld flow deploy --no-interactive

# 3) Verify the backend works: preview should now be clean
nld flow deploy --preview        # expect exit 0, empty change set
```

What each step does:

1. **Adopt-all** — for every asset-matched structure, the live schema is
   recorded as a flagged `state_refresh` baseline (never overwriting history)
   and a stable `uid` is minted. Live tables with no matching asset are not
   adopted and stay invisible to every later deploy. If an asset's table does
   not exist yet, the deploy creates it from the asset.
2. **First flow deploy** — every flow is `NEW` and records its baseline
   hashes; target structures were just adopted, so no DDL runs and no reload
   is scheduled (`nld flow state incremental get-planned` stays empty).
3. From here on, edits deploy normally: the next change previews as exactly
   its diff (`D − R` is clean).

## Limitation

Flow-level change detection is meaningful from the second deploy onward:
nothing records which flow versions were live before the bootstrap, so the
first flow deploy baselines the current repository state as-is.

## Verification checklist

- `_nld_structure_state` has one row per asset-matched structure with
  `record_source = 'state_refresh'`; row counts of the live tables unchanged.
- `_nld_flow_state` has one row per flow after step 2.
- A trivial asset edit previews as exactly one ALTER (and nothing else).

## Cross-References

- Concepts (drift model, metadata tables, adopt semantics):
  `guide-deployment` skill.
- Day-to-day deployment: `how-to-deploy-structures`, `how-to-deploy-flows`.
