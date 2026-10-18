# nld-agents

For engineers building data pipelines on top of the nld-core Python library — a Claude Code plugin marketplace with architectural guides, how-to skills, and data conventions for the NLD ecosystem.

## 30-second quickstart

```
/plugin marketplace add nexuslab-data-agents/nld-agents
/plugin install nld-core-usage@nld-agents
/plugin install nld-data-conventions@nld-agents
```

Then ask Claude *"how do I make this flow incremental?"* and it routes to the right skill automatically.

## Plugins

### `nld-core-usage`

**When to install:** you are writing code against the `nld-core` library and want Claude to understand its architecture (flow lifecycle, incremental processing, structures, connections) without you pasting docs into the chat.

**Example trigger:** *"I want to add a new SQL flow that pulls daily orders from a REST API — what's the right incremental strategy?"* → Claude invokes `how-to-determine-incremental-strategy`, then `guide-flows` for the implementation pattern.

| Skill | What it does |
|---|---|
| `guide-base-model` | Core Pydantic layer — NldBaseModel hierarchy, namespaces, entity references, serialization |
| `guide-entity-registry` | Entity definitions, providers, NldEntityRegistry accessors, same-name entities across namespaces, filesystem, namespace-folder & selective loading |
| `guide-project` | Project container, execution context, TaskRequest, StandardTask, what every command logs, task→entity access |
| `guide-project-catalog` | `NldProjectCatalog` — multi-project catalogue and cross-project predecessor DAG |
| `guide-project-docs` | `nld docs` — the project's own back + front UI: repository snapshot, documentation coverage, live state |
| `guide-business-dictionary` | Namespaced business vocabulary for naming tables/fields |
| `guide-connections` | Connector engine architecture (PostgreSQL, BigQuery, Snowflake, DuckDB, SQLite) |
| `guide-flows` | SQLFlowTask/DataFlowTask lifecycle, write strategies, dependency graph |
| `guide-incremental` | `by_key` / `by_source_tst` / `by_target_period` / `no_increment` strategies, state management |
| `guide-data-quality` | Post-write quality checks — the `quality_checks` block, the built-in rules, severities, result persistence |
| `guide-structures` | Structure definitions, field characterisations, deployment, view structures generated from their flow, Pydantic model export |
| `guide-structure-model` | StructureModel entity — same-layer join links, field mappings, cardinality |
| `guide-structure-audit` | StructureAudit entity — per-structure coverage and value-distribution audits |
| `guide-deployment` | The deploy system — structure and flow deploy paths, drift gate, change files, namespace deploys and the deploy lock |
| `guide-governance` | Ownership entities — `structure_owner` (data) / `flow_owner` (technical), lineage resolution, `nld ownership` CLI |
| `guide-scheduling` | Environment-aware `FlowTask` scheduling — triggers, predecessors, environments, `nld scheduling` CLI |
| `how-to-set-up-a-project` | Initialize a project or audit an existing one: every `nld_project.yml` key and namespace facet, connections, environments, entity layout, deployment/alerting, guardrails, then verify |
| `how-to-check-connections` | Discover and verify project connections with `nld connection list` / `debug` / `export-env-var` |
| `how-to-document-a-structure` | Create or refresh a Structure YAML from a real table, nested JSON columns included, then validate it |
| `how-to-profile-a-structure` | Profile (or hand-author), validate, and render a StructureAudit with `nld structure audit` |
| `how-to-characterize-fields` | Propose field characterisations for one structure from the rules + its audit, report, and confirm before updating |
| `how-to-model-structure-layers` | Record a structure's same-layer join links as a StructureModel, then validate them |
| `how-to-trace-flow-lineage` | Trace upstream/downstream structure and flow lineage with `nld flow deps` |
| `how-to-execute-a-flow` | Run a flow with `nld flow execute` — the runtime options each incremental type accepts |
| `how-to-determine-incremental-strategy` | Decision walkthrough for picking `by_key` vs `by_source_tst` vs `by_target_period` vs `no_increment` |
| `how-to-get-execution-info` | Retrieving flow execution metadata from state backends |
| `how-to-get-incremental-info` | Retrieving incremental state from state backends, and excluding `by_key` keys |
| `how-to-use-business-dictionary` | `nld business dict find` / `list` CLI usage |
| `how-to-check-deploy-impact` | Compute a change's deployment blast radius with `nld deploy impact --git-base` (no database) |
| `how-to-deploy-a-project` | Deploy flows and structures with `nld flow deploy` — preview, scoping, drift reconciliation |
| `how-to-bootstrap-deployment-backend` | Stand up the deployment metadata backend of a database that already exists |
| `how-to-create-a-new-incremental-type` | Author and register an external incremental type |
| `how-to-create-a-new-data-quality-check` | Author and register an external data quality rule |

### `nld-data-conventions`

**When to install:** you are naming new tables, columns, or layers in an NLD-style data lakehouse and want the project's agreed conventions instead of guessing.

**Example trigger:** *"What should I prefix this column with?"* → Claude consults `guide-field-conventions` and tells you the right prefix and shape.

| Skill | What it does |
|---|---|
| `guide-data-lakehouse-architecture` | Repository structure, domain layout, single-product vs multi-domain |
| `guide-data-layers` | raw / refinement / business / consumer layer responsibilities |
| `guide-field-conventions` | Column naming prefixes and field characterisations |
| `guide-structure-conventions` | Structure characterisations, ordering rules, layer-specific templates |

## What a skill invocation looks like

```
You     › I'm writing a new flow that pulls daily orders from a REST API.
          What incremental strategy should I use?

Claude  › [invokes how-to-determine-incremental-strategy]
          For a REST API exposing recently-modified orders, by_source_tst is
          the right fit — it tracks the last successful pull timestamp and
          only requests data updated since then. See guide-incremental for
          the state machine. Here is the IncrementalConfig…
```

## Team setup

To make the marketplace available for everyone on a project, add it to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": ["nexuslab-data-agents/nld-agents"],
  "enabledPlugins": [
    "nld-core-usage@nld-agents",
    "nld-data-conventions@nld-agents"
  ]
}
```

## License

Apache-2.0. See [LICENSE](./LICENSE).
