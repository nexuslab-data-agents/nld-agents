# Project Documentation UI (`nld docs`)

`nld docs` turns an nld project into a web application: a browsable view of
every namespace, structure, field, flow, template, standard, owner, term and
lineage edge the repository declares, optionally overlaid with the live state
of the running system.

Two properties shape the whole design:

- **The document is built from the repository alone.** No database is
  contacted to build it, so it can be produced in CI, diffed between commits
  and read offline.
- **The live state is a separate, best-effort layer.** Every state section
  degrades to "unavailable" with its reason, so the project view always works
  with no environment at all.

Code lives under `core/nld/docs/`; the CLI under `core/nld/cli/docs/`.

## Table of Contents

1. [CLI](#1-cli)
2. [The snapshot](#2-the-snapshot-projectsnapshot)
3. [Where documentation comes from](#3-where-documentation-comes-from)
4. [Coverage and issues](#4-coverage-and-issues)
5. [The generated site](#5-the-generated-site)
6. [The live state](#6-the-live-state)
7. [How the page reaches its state](#7-how-the-page-reaches-its-state)
8. [Platform catalog builds](#8-platform-catalog-builds)
9. [Code map](#9-code-map)

---

## 1. CLI

```
nld docs build   [--target <dir>] [--env <env>] [--base-url <url>]
                 [--state-url <url>] [--state-source none|file|api] [--catalog <dir>]
nld docs deploy  (same options as build)
nld docs serve   [--target <dir>] [--env <env>] [--host <addr>] [--port <n>]
                 [--no-state] [--no-build] [--open] [--state-ttl <seconds>]
nld docs check   [--env <env>] [--min-coverage <ratio>] [--catalog <dir>]
nld docs state build    [--target <dir>] [--env <env>] [--base-url <url>]
                        [--state-url <url>] [--state-source none|file|api]
nld docs catalog build  [--catalog <dir>] [--target <dir>] [--env <env>]
                        [--base-url <url>]
```

| Command | What it does |
|---|---|
| `build` | Generates the static site from the project assets |
| `deploy` | Same, plus a standalone `serve.py` launcher — the self-contained deployable app |
| `serve` | Builds the site and serves it locally with the read-only live-state API |
| `check` | Reports documentation coverage and cross-references; **exits 1** on a broken reference or under `--min-coverage` |
| `state build` | Collects the live state once into a `state.json` beside a published site |
| `catalog build` | One site per project of a platform catalog, plus an index |

| Option | Meaning |
|---|---|
| `--target` | Folder the site is written to. Default `output/nld-docs` under the project root |
| `--env` | Environment the live state is read for |
| `--host` / `--port` | Bind address and port of the local server. Default `127.0.0.1:8765` |
| `--no-state` | Serve the project documentation only, without the live-state API |
| `--no-build` | Serve an already generated site instead of regenerating it |
| `--open` | Open the served site in the default browser |
| `--state-ttl` | Seconds a collected live state is served from cache. Default `60` |
| `--min-coverage` | `check` fails when the documented share of assets is under this ratio (0.0–1.0) |
| `--base-url` | Public URL the site is served from, when it is not the folder root |
| `--state-url` | Where the published page reads its live state from (an API, or a `state.json`) |
| `--state-source` | `none` / `file` / `api` — how the published page reaches its state. Default: `file` when `--state-url` is given, otherwise `none` |
| `--catalog` | Folder holding `nld_project_catalog.yml`. Default: the root folder |

Every `nld docs` command loads **every** entity type: the documentation covers
the whole project, not a slice of it.

`serve` warns when `--host` is not a loopback address and the state API is on,
because that exposes the live-state API beyond the machine — use `--no-state`
or a loopback address on a shared network. It serves until `Ctrl+C`.

`check` hides its completion line (and therefore its start line), so its
output stays clean for CI.

---

## 2. The snapshot (`ProjectSnapshot`)

One serialisable document holding the whole project (`nld/docs/models.py`,
built by `nld/docs/snapshot_builder.py`):

| Field | Holds |
|---|---|
| `schema_version` | Snapshot schema version (`1.5`) |
| `meta` | `generated_at`, `generator_version`, `environment` |
| `project` | Project-level summary and its documentation |
| `namespaces` | Every namespace, its documentation and its contents |
| `entity_types` | The entity types present, as the UI presents them: display name, category, folder name, search direction, count |
| `structures` | Per structure: type, connector, fields (nested `fields` included), characterisations, primary key, templates, tags, properties, business metadata, data/technical owners, model links, audit id, SQL hooks, `produced_by` / `consumed_by`, origin and stats |
| `flows` | Per flow: its sources/predecessors, target, strategy and documentation |
| `entities` | Every other entity type, keyed by type name |
| `terms` | The business vocabulary |
| `lineage` | The lineage graph (`nld/docs/lineage_builder.py`) |
| `counts` | Per-type counts |
| `documentation_coverage` | `DocsCoverage` — documented / total, and what is missing |
| `issues` | `DocsIssue` list — see [§4](#4-coverage-and-issues) |

Every path the snapshot carries is **relative to the project root**, so the
document does not depend on where the project was checked out.

`content_json()` serialises everything **but** `meta`, sorted — that is the
form to diff two builds with, since `meta` changes on every run.

---

## 3. Where documentation comes from

Documentation is read from the filesystem, next to the asset it describes.
Nothing has to be declared in the YAML for an asset to become documented
(`nld/docs/documentation.py`, `nld/docs/source_index.py`):

| File | Documents |
|---|---|
| `<entity>.md` next to an asset | That asset |
| `_namespace.md` in a namespace folder | That namespace |
| `README.md` or `PROJECT.md` at the project root | The project |

Each resolved file becomes a `DocsDocumentationBlock` (`title`, `content`,
`source_path`).

---

## 4. Coverage and issues

`DocsCoverage` reports `documented` of `total` documentable assets, `ratio`,
and the list of what is `missing`. `nld docs check` prints it and gates on
`--min-coverage`.

`DocsIssue` records one inconsistency found while reading the repository:

| `kind` | Means | Error? |
|---|---|---|
| `broken_reference` | An asset points at something that does not exist (a flow source, a model-link side) | **Yes** — `check` exits 1 |
| `external_reference` | A reference resolved by *another project of the platform* | No |
| `unused_template` | A template no structure uses | No |

`external_reference` is why `--catalog` matters: naming the catalog lets a
reference into another project be recognised as external rather than broken.
For a refined layer reading its acquisition layer, that is the difference
between a clean report and a page of false alarms.

---

## 5. The generated site

A buildless HTML/CSS/JS template shipped as package data
(`nld/docs/site/assets/`) — no build step, no CDN, and no new dependency.
`DocsSiteBuilder` writes:

| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js`, the SVG marks | The template assets |
| `snapshot.json` | The machine-readable document the site renders |
| `snapshot.js` | The same document as a script, so the site also opens from `file://` |
| `docs.config.json` / `docs.config.js` | `DocsSiteConfig`: `base_url`, `state_source`, `state_url`, `state_generated_at`, project name, and the catalog's projects |
| `state.json` | The collected live state, when one was written |
| `serve.py` | Standalone launcher, written by `nld docs deploy` only |
| `README.md` | How to open or serve the folder |

`nld docs deploy` prints the launcher command
(`python <target>/serve.py`).

---

## 6. The live state

`LiveStateCollector` (`nld/docs/state/collector.py`) reads the running
system into a `DocsLiveState`. Every read is best effort: a section that
cannot be reached reports itself unavailable **with the reason**, and the UI
keeps rendering everything else.

| Section | What it holds |
|---|---|
| `backend` | The metadata backend the project declares: connection name, connector type, metadata schema |
| `structure_deployments` | Per structure: when it was deployed, the deployment id, the deployed hash vs the repository hash, and whether it has `drift` |
| `flow_deployments` | The same for flows, on the flow YAML hash |
| `executions` | The latest execution of every flow that tracks its state: status, start/end, duration, error, source and previous-layer timestamps, steps |
| `sla` | Each flow's declared `frequency` against its last successful run |
| `freshness` | Each target structure's data age, derived from its producing flow |

Each section also carries its own `DocsStateSection` (`status`, `message`),
and `available` / `message` sit on the state itself.

**SLA classification** (`_sla_status`) — the latest record decides, so a
failed or still-running latest attempt is reported as such rather than as
"never run", and an unreadable backend yields `unknown` instead of a verdict:

| Status | When |
|---|---|
| `unknown` | The backend was not reached, or there is no expected interval / age |
| `never_run` | Reached, but no execution status recorded |
| `failed` / `running` | That is the latest attempt's status |
| `on_time` | `age <= expected_interval × 1.5` (`SLA_TOLERANCE_RATIO`) |
| `late` | Older than that |

The expected interval comes from the flow's declared `ExecutionFrequency`
(see `guide-scheduling`); an unparseable value yields no interval, hence
`unknown`.

**Caching.** Collecting the state opens every backend the project declares —
a full scan each time — so `nld docs serve` answers through a
`CachedStateProvider`: repeats within `--state-ttl` (default 60s) get the
same document, and the API's `refresh` forces a new collection. Without it,
two tabs polling the page would serialise those scans behind the lock.

---

## 7. How the page reaches its state

`nld docs serve` adds a stdlib HTTP server (`nld/docs/server/docs_server.py`)
with a **read-only** API:

| Endpoint | Returns |
|---|---|
| `/api/snapshot` | The snapshot the site was built from |
| `/api/state` | The live state, collected on demand and degrading on any failure |
| `/api/health` | Whether the server is up, and whether it can answer for the live state |

`/api/state` is answered on demand rather than at start-up, so starting the
server never waits on a database.

`state_source` tells the published page where to look:

| `state_source` | The page reads | Set by |
|---|---|---|
| `none` | Nothing — the project view only | The default for `build` / `deploy`, and `serve --no-state` |
| `api` | The `/api/state` endpoint | `nld docs serve` |
| `file` | A `state.json` next to the site | `nld docs state build`, or `--state-url` on a build |

`nld docs state build` exists for a published site, which has no API to call:
it collects the state once and writes it beside the site, so a scheduled job
can refresh it while the site stays static — no endpoint to expose, no
credentials in a browser, no CORS. The cost is that the state is only as
fresh as the job. It warns when no backend could be reached, because the
published state would then show every section as unavailable.

---

## 8. Platform catalog builds

A data platform is several nld projects, and a reader should not have to know
which one holds the table they are after. `nld docs catalog build` reads
`nld_project_catalog.yml` (see `guide-project-catalog`) and builds **one
self-contained site per catalogued project** — each still readable alone —
plus a generated index tying them together in the dependency order the
catalog already declares.

It reports, per project, its structure and flow counts and the folder it
landed in. A project that could not be documented is listed as a warning
with its error; the other projects still build.

---

## 9. Code map

| Module | Responsibility |
|---|---|
| `nld/docs/snapshot_builder.py` | Builds the `ProjectSnapshot` from the loaded entities |
| `nld/docs/models.py` | The snapshot models, `DocsSiteConfig`, `DocsCoverage`, `DocsIssue`, the `state_source` and issue-kind constants |
| `nld/docs/documentation.py` | Resolves the markdown documenting the project and its assets |
| `nld/docs/source_index.py` | Indexes asset source files and finds the markdown sidecars |
| `nld/docs/lineage_builder.py` | Builds the lineage graph the UI draws |
| `nld/docs/catalog.py` | `CatalogSiteBuilder`, `collect_catalog_structure_owners` |
| `nld/docs/site/site_builder.py` | Writes the site, the snapshot, the config, the state and the launcher |
| `nld/docs/site/assets/` | The buildless HTML/CSS/JS template, shipped as package data |
| `nld/docs/server/docs_server.py` | The stdlib server and the read-only API |
| `nld/docs/state/collector.py` | `LiveStateCollector` — reads the running system |
| `nld/docs/state/models.py` | `DocsLiveState` and its per-section models |
| `nld/docs/state/cache.py` | `CachedStateProvider` |
| `nld/docs/state/errors.py` | Classifies a backend error into a section status and message |
| `nld/docs/task/docs_tasks.py` | The tasks behind the commands |
| `nld/cli/docs/` | `main_docs.py`, `catalog_docs.py`, `state_docs.py`, `params_docs.py` |
