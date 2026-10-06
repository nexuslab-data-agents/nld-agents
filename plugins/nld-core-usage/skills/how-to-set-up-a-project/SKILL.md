---
name: how-to-set-up-a-project
description: >
  Initialize a new nld project, or audit and update an existing one, by walking
  every configuration point nld-core reads: the `nld_project.yml` keys and its
  namespace facets (structure, flow, scheduling/alerting, folder, deploy), connections
  and profiles in `.nld/`, environments and variables, the entity tree and
  namespace folders, extension points, the deployment metadata backend, and the
  commit/CI guardrails. Reports each point as set, missing or invalid, proposes
  the changes, applies them once confirmed, and verifies the result with the
  read-only `nld` commands. Use when the user asks to create, initialize or set
  up an nld project, to check, review or update a project's configuration, or
  before a project's first deploy.
user-invocable: true
---

# How to Set Up an nld Project

**Classification**: Composite Skill | Project Setup

---

## Definition

- **What**: Bring a directory to a working nld project, or bring an existing
  project's configuration up to date, point by point, then prove it loads and
  validates.
- **When**: A new repository or data product adopts nld; an existing project
  needs a review (after an nld-core upgrade, before a first deploy, before
  adding scheduling or alerting); a project fails to load.
- **Modes**:
  - **Initialize**: no `nld_project.yml` in the project root. Build the skeleton
    (Step 2), then fill the checklist.
  - **Update**: a `nld_project.yml` exists. Start from what `nld project info`
    resolves, audit every point, and change only what the audit flags.
- **Ground rules**:
  - Never write a secret into `nld_project.yml` or into a committed file.
    Secrets live in `.nld/secrets.toml` or in environment variables.
  - Present the full report (see "Report") and get the user's confirmation
    before writing any file.
  - Ask only for what cannot be read from the repository: the project name,
    the engines and their connections, the namespace plan, whether flows are
    deployed, scheduled and alerted.

For the meaning of every key, read
`${CLAUDE_PLUGIN_ROOT}/docs/nld-base/project-design.md` → "4. Project" (the
`nld_project.yml` reference, the `namespaces` block and the `scheduling`
facet). This skill is the procedure; that document is the reference.

## Step 1: Locate the project and take a baseline

The project root is the directory holding `nld_project.yml`. Commands resolve
it from `--root-folder-path`, then `NLD__ROOT_FOLDER_PATH`, then the current
directory. The config folder (connections, `.env`) is `NLD__CONFIG_FOLDER_PATH`
when set, otherwise `.nld` under the **current directory** — not under
`--root-folder-path` — so run the commands from the project root, or export
`NLD__CONFIG_FOLDER_PATH`.

In **Update** mode, start with:

```bash
nld project info          # resolved configuration + namespaces + entity counts
```

It prints the metadata backend, properties, namespace folders, deployable
namespaces and deploy groups, Python additional paths, additional entities,
variables, environments, the `flow` block's task types, incremental types and
quality rules, and each namespace's structure, flow and scheduling settings,
then the namespaces and entity counts. Keep it as the baseline of the report;
read `additional_entity_paths` and `flow.additional_alert_transports` from the
file itself.

A project that fails to load names its problem. The usual causes:

| Error mentions | Cause | Fix |
|---|---|---|
| `Unknown facets` for a namespace | Typo, or a facet that does not exist | Facets are `structure`, `flow`, `scheduling`, `folder`, `deploy` |
| `cannot be declared as a namespace folder` | `folder: true` on `.` or on a wildcard key | Only exact, non-root keys can be folders |
| `uses the segment ... reserved for an entity folder` | A namespace folder named like `flows`, `structure`, `templates`... | Rename the namespace |
| `cannot declare a 'deploy' facet` / `declares nothing` / `is declared by a single namespace` | `deploy` on a wildcard key, without `unit: true` nor `group`, or a group with one member | `deploy` only on exact keys, with `unit: true` and/or a `group` shared by at least two namespaces |
| `names an unknown transport` / `does not accept settings` | Alerting typo | Built-in transports: `slack` (`channel`), `telegram` (`chat_id`) |
| `Invalid path ... in python_additional_paths` | A path with `/` | Use dotted module notation |
| `Additional entity path ... does not exist` / `is not importable` | A wrong `additional_entity_paths` entry, or its package not installed | Fix the path, or install the package in the project environment |
| `Additional entity name ... conflicts with a built-in entity type` | An `additional_entities` entry reusing a built-in name | Rename the entity type |
| `must contain 'name' field` | Missing `name` | Add it |

## Step 2: Project skeleton

```
<project root>/
├── nld_project.yml
├── .nld/
│   ├── secrets.toml            # connections — never committed
│   ├── secrets.toml.example    # same shape, no secret values — committed
│   └── .env                    # optional environment variables — never committed
└── <entity_path>/              # e.g. assets/ — every entity lives under it
    ├── __init__.py             # when flows carry Python code (see below)
    ├── structure/              # Structure YAML, one sub-folder per namespace
    ├── flows/                  # flow YAML (+ .sql / .py next to it)
    ├── seeds/                  # CSV seed files
    ├── scheduling/             # FlowTask (per-environment scheduling)
    ├── structure_model/        # same-layer join models
    ├── audits/structure/       # StructureAudit data profiles
    ├── templates/              # field, field_template, field_adapter,
    │                           # field_format_adapter, structure_adapter,
    │                           # structure_template
    ├── characterisations/field/  # project field characterisation definitions
    ├── business/dictionary/    # business vocabulary
    └── governance/             # structure/ and flow/ ownership
```

Inside each entity folder, a namespace is a sub-path (`structure/sales/raw/`
holds namespace `sales.raw`). **Namespace folders** invert that layout for
chosen namespaces: with `namespaces.sales.folder: true`, the sales entities
live under `<entity_path>/sales/structure/`, `<entity_path>/sales/flows/`...,
which keeps one source's assets together. Shared entities (templates,
characterisations, governance) usually stay at the top of `entity_path`. A
namespace lives in exactly one place: once it is a folder, any of its files left
in the type-first tree fails the load (`NamespaceFolderConflictException`), so
move all its entity types together.

Python flows resolve their task class from
`<entity_path>.flows.<namespace>.<flow_name>` (or
`<entity_path>.<folder namespace>.flows...`), so `entity_path` must then be an
importable package (`__init__.py`) and the project root must be on
`PYTHONPATH` (`PYTHONPATH=$PWD` next to `NLD__ROOT_FOLDER_PATH=$PWD`).
SQL-only projects need neither.

## Step 3: `nld_project.yml` checklist

Starter file (**Initialize** mode), valid on its own:

```yaml
name: my_project
version: '0.0.1'
entity_path: assets
namespaces:
  .:
    structure:
      default_connection_name: dwh      # a connection of .nld/secrets.toml
      database_name: my_db
      schema_name: public
    flow:
      default_state_backend_connector: dwh
environments:
  default: prd
  values:
    prd: {}
```

`nld scheduling validate` refuses to run without an environment, so the
`environments` block belongs in the starter even before any scheduling.

Audit every key, set or not:

| Key | Needed when | Check | Default when absent |
|---|---|---|---|
| `name` | always | Present, stable (deployment metadata and catalogs key on it) | load fails |
| `version` | recommended | Bumped with releases of the project | none |
| `entity_path` | entities are not at the root | Directory exists; a package when flows carry Python | `.` |
| `properties` | platform tooling reads them | Free-form strings only; the core ignores them | none |
| `namespaces` | always in practice | See the facet checklist below | no defaults: deploying, profiling or SQL-reading a structure fails with `Namespace '<ns>' not found in structure config`, and a flow without its own `state_backend_connector` has no state backend |
| `environments` | always (scheduling), several targets | `default` names a declared value; each `connection_profile` exists for the connections it uses | no environment |
| `variables` | SQL hooks use `{{ var }}` | Every variable a hook references is declared, or provided as `NLD__VAR__<NAME>` | none |
| `metadata_backend_connector` | `nld flow deploy`, change files | Names a connection; its schema exists (the tables are created, not the schema) | deploy cannot record state |
| `flow.additional_flow_task_types` | custom task types (`task_type: <name>`) | Each class path importable | built-ins `sql`, `seed` |
| `flow.additional_incremental_types` | custom incremental types | `name`, `logic_module`, `state_manager_module`, `backend_package` importable; no name collision | built-ins only |
| `flow.additional_quality_rules` | custom data quality rules | `name`, `rule_class` importable; no name collision | built-in rules only |
| `flow.additional_alert_transports` | alert transports beyond slack/telegram | `name`, `transport_class` importable | `slack`, `telegram` |
| `python_additional_paths` | shared Python code outside the flow modules | Keys only `flows`, `sql_transformations`; dotted paths | none |
| `additional_entity_paths` | entities shipped in a package or another folder | `pkg://<package>[/<subdir>]` installed (not zipped), or an existing directory, absolute or relative to the root; project entities override them | none |
| `additional_entities` | project-defined entity types | `name` not a built-in type; `model_type` importable; `folder_name` exists | none |

### Namespace facets

Keys are namespaces (`.` = root) or wildcard patterns (`"*.extraction"`).
A namespace resolves to its nearest declared level, so declare the common
settings at `.` and override only where a layer differs.

| Facet | Check |
|---|---|
| `structure` | `default_connection_name`, `database_name`, `schema_name` set for every namespace whose structures are deployed or read by SQL flows; `tags` only for tags every structure of the namespace must carry |
| `flow` | `default_state_backend_connector` set wherever flows run (or each flow declares its own `state_backend_connector`) |
| `scheduling` | `max_attempts` (1-10, default 1): give retries only to flows calling unreliable external systems. `alerting`: see Step 6 |
| `folder` | `true` only on exact, non-root namespaces whose assets are grouped in their own folder; the folder actually exists on disk |
| `deploy` | Only when a namespace is deployed on its own (`--namespace <ns>` on `nld flow deploy` / `nld structure deploy`): `unit: true`, or a `group` shared by the namespaces that must deploy together. Exact keys only; the declaration applies to that namespace alone, a descendant needing its own to be deployable on its own. Without any, the project deploys as a whole (`guide-deployment`) |

## Step 4: Connections

`.nld/secrets.toml` declares each connection once, with optional profiles
overriding some parameters:

```toml
[dwh]
type = "postgresql"        # postgresql, snowflake, bigquery, duckdb, sqlite, s3_blob_storage...
host = "localhost"
port = 5432
user = "nld"
password = "..."
database_name = "my_db"
schema_name = "public"

[staging.dwh]              # profile "staging" of connection "dwh"
database_name = "my_db_staging"
```

`NLD__DATA_CONNECTION__<CONNECTION>__<PARAM>` (and
`NLD__DATA_CONNECTION__<CONNECTION>__<PROFILE>__<PARAM>`) override the file,
which is how CI and orchestrators inject credentials. `.nld/.env` is loaded
without overriding variables already exported.

Checks:

1. Collect every connection the project names: `default_connection_name` and
   `default_state_backend_connector` of each namespace,
   `metadata_backend_connector`, and the `data_connectors` /
   `state_backend_connector` of the flows.
2. Each one is declared: `nld connection list` (name, type, profiles).
3. Each `environments.values.<env>.connection_profile` exists as a profile of
   the connections that environment uses.
4. Each one opens: `nld connection debug --connection-name <name>
   [--profile-name <profile>]`. Run it only with the user's agreement when it
   targets a shared or production system.
5. `.nld/secrets.toml` and `.nld/.env` are git-ignored; a
   `secrets.toml.example` with empty secret values documents the shape.

Details: `guide-connections`, `how-to-check-connections`.

## Step 5: Environments and variables

- The active environment comes from `--env`, then `NLD__ENVIRONMENT`, then
  `environments.default`.
- Each environment selects a `connection_profile` (absent = default profile)
  and may override `variables`.
- Hook variables resolve from `variables`, overridden by `NLD__VAR__<NAME>`.
  Variables differing per target belong to the environments or to the
  environment variables, never hard-coded in hooks.

Details: `guide-scheduling` (environments, FlowTask scheduling).

## Step 6: Deployment, scheduling and alerting (when used)

- **Deployment**: `metadata_backend_connector` set, its schema created.
  - New database: the first `nld structure deploy` / `nld flow deploy` builds
    it (`how-to-deploy-a-project`).
  - Database already live: seed the metadata with
    `how-to-bootstrap-deployment-backend` instead of redeploying.
  - Parts of the project released separately (one source, one schema):
    declare them as deploy units or groups (`namespaces.<ns>.deploy`, see the
    facet checklist); a project deployed as a whole needs no `deploy` facet.
- **Scheduling**: one FlowTask per flow and environment under `scheduling/`
  (`guide-scheduling`); `nld scheduling validate --env <env>` for each
  environment.
- **Alerting**: declare it once at `.` and override per namespace:

  ```yaml
  namespaces:
    .:
      scheduling:
        alerting:
          transports: [slack]
          alert_on: [FAILED, WARNING]     # default [FAILED]
          slack:
            channel: data-alerts
  ```

  The secrets come from the environment only
  (`NLD__ALERTING__SLACK__WEBHOOK_URL`, `NLD__ALERTING__TELEGRAM__BOT_TOKEN`).
  A missing secret silently disables the transport, so check that the runtime
  environment provides it. `enabled: false` is the explicit opt-out of a
  namespace.

## Step 7: Commit and CI guardrails

Run the offline validations on every commit touching the entities, and in CI.
None of them needs a database:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: nld-validate
      name: NLD validate
      entry: bash -c 'export NLD__ROOT_FOLDER_PATH=$PWD PYTHONPATH=$PWD &&
        uv run nld structure validate && uv run nld structure model validate &&
        uv run nld structure audit validate &&
        uv run nld structure generate --check'
      language: system
      files: ^(assets/|nld_project\.yml)
      pass_filenames: false
```

Drop `uv run` when `nld` is installed directly in the active environment. In
a repository holding several projects, add one hook per project that `cd`s
into it and narrows `files` to its own folder.

- `nld structure generate --check` fails when a generated view structure is
  stale (`structure-design.md` → "Generated Structures").
- `nld deploy impact --git-base origin/main` lists the assets a branch
  changes, from the repository alone; useful as a CI summary
  (`how-to-check-deploy-impact`).
- Add `.nld/secrets.toml` and `.nld/.env` to `.gitignore`.

## Step 8: Verify

After applying the changes, run the read-only sequence. Every command must
exit 0:

```bash
nld project info                    # loads, shows the intended configuration
nld connection list                 # every named connection is declared
nld structure validate              # field characterisations (+ STALE warnings)
nld structure model validate        # structure model links
nld structure audit validate        # structure audits
nld structure generate --check      # generated structures up to date
nld flow list                       # every flow loads
nld scheduling validate --env <env> # once per environment
```

Then, only against a reachable metadata backend and with the user's
agreement, preview the first deployment: `nld flow deploy --preview` (exit 2
means changes are pending, which is expected on a first deploy).

## Report

Before writing anything, present one table covering every point of Steps 2-7:

| Area | Item | Status | Proposed action |
|---|---|---|---|
| Project file | `metadata_backend_connector` | MISSING | Set to `dwh` (flows are deployed) |
| Namespaces | `.` → `structure` | OK | — |
| Connections | `dwh` profile `staging` | INVALID | `environments.values.stg.connection_profile` names it but `secrets.toml` lacks it |
| Guardrails | `generate --check` in pre-commit | MISSING | Add to the NLD validate hook |

Statuses: `OK`, `MISSING` (needed but absent), `INVALID` (present but wrong),
`UNUSED` (optional and not needed: leave it out rather than add empty keys).
Apply the confirmed actions, then run Step 8 and report its results.

## Cross-References

- `nld_project.yml` reference: `guide-project` (`project-design.md` → "4. Project").
- Entity folders, namespace folders, additional entity roots: `guide-entity-registry`.
- Connections and profiles: `guide-connections`, `how-to-check-connections`.
- Environments and scheduling: `guide-scheduling`.
- Deployment: `guide-deployment`, `how-to-deploy-a-project`,
  `how-to-bootstrap-deployment-backend`, `how-to-check-deploy-impact`.
- Several projects on one platform: `guide-project-catalog`.
