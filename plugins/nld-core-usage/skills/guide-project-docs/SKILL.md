---
name: guide-project-docs
description: >
  Architectural guide for the nld-core `nld docs` command group — the local
  back + front UI of a whole nld project. Covers the repository-only
  `ProjectSnapshot`, documentation read from `<entity>.md` / `_namespace.md` /
  the project README, coverage and broken-reference gating with
  `nld docs check`, the buildless generated site (`snapshot.js` so it opens
  from `file://`), the stdlib server's read-only `/api/snapshot` and
  `/api/state`, the best-effort live-state collector (deployment drift, latest
  executions, declared-cadence SLA, data freshness) and its cache, the
  `none`/`file`/`api` state sources, and per-project catalog builds. Read when
  working on `nld/docs/`, `nld/cli/docs/`, or publishing a project's
  documentation.
user-invocable: false
---

# Guide: Project Documentation UI (`nld docs`)

`nld docs` turns an nld project into a web application — generated, served
and deployed locally — showing every namespace, structure, field, flow,
template, standard, owner, term and lineage edge the repository declares,
optionally overlaid with the live state of the running system.

Two properties shape everything:

- **The document is built from the repository alone** — no database is
  contacted, so it can be produced in CI, diffed between commits, and read
  offline.
- **The live state is a separate, best-effort layer** — every section
  degrades to "unavailable" with its reason, so the project view always
  works with no environment at all.

## When to Use

Activate this guide when the agent is working on:
- `nld/docs/` (snapshot, documentation resolution, site builder, server,
  state collector) or `nld/cli/docs/`
- Any `nld docs` command: `build`, `deploy`, `serve`, `check`,
  `state build`, `catalog build`
- Documenting assets with markdown sidecars (`<entity>.md`,
  `_namespace.md`, the project `README.md`)
- Gating CI on documentation coverage or broken cross-references
- Publishing a project's (or a platform's) documentation, and deciding how
  the published page reaches its live state

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/project-docs/project-docs-design.md`.

### Key Sections

| Task | Section |
|------|---------|
| The commands and every option | "1. CLI" |
| What the snapshot holds, and diffing two builds | "2. The snapshot (`ProjectSnapshot`)" |
| Which markdown file documents what | "3. Where documentation comes from" |
| Coverage, issue kinds, what `check` fails on | "4. Coverage and issues" |
| The generated files and the `file://` case | "5. The generated site" |
| Deployment drift, executions, SLA, freshness, caching | "6. The live state" |
| `/api/*`, and `none` / `file` / `api` state sources | "7. How the page reaches its state" |
| One site per catalogued project, plus an index | "8. Platform catalog builds" |
| Module responsibilities | "9. Code map" |

## Working Rules

- **Documentation is filesystem-driven.** To document an asset, add
  `<entity>.md` next to it — nothing is declared in the YAML. A namespace
  takes `_namespace.md`, the project takes `README.md` (or `PROJECT.md`).
- **Name the catalog when the project reads another one.** `--catalog`
  turns a cross-project reference from a `broken_reference` **error** into
  an `external_reference`; without it, a refined layer reading its
  acquisition layer reports a page of false alarms.
- **`check` is the CI gate.** It exits 1 on a broken reference and under
  `--min-coverage`; nothing else about `nld docs` fails a build.
- **Diff `content_json()`, not the snapshot.** `meta` carries
  `generated_at`, so it changes on every run.
- **Keep `serve` on loopback.** Binding `--host` elsewhere with the state
  API on exposes the live-state API beyond the machine; use `--no-state` or
  a loopback address on a shared network. The command warns, it does not
  refuse.
- **A published site uses `state build`, not the API.** It has no endpoint
  to call: collect the state into `state.json` from a scheduled job and the
  site stays static. The state is then only as fresh as the job.
- **Do not add a dependency for the front-end.** The template is buildless
  stdlib-served HTML/CSS/JS with no build step and no CDN; `nld docs`
  introduced no new dependency, and that is a property to preserve.

## Cross-References

- `guide-project` — the `Project` container and `nld_project.yml` the
  snapshot reads.
- `guide-entity-registry` — the entity types and loading the snapshot walks.
- `guide-project-catalog` — `nld_project_catalog.yml`, which
  `nld docs catalog build` reads.
- `guide-scheduling` — the declared `frequency` the SLA section compares a
  flow's last successful run against.
- `guide-deployment` — the deployment metadata the state layer diffs the
  repository against.
- `how-to-get-execution-info` — the same execution state, read from the
  shell instead of the UI.
