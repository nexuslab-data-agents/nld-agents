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
| `guide-base-model` | NldBaseModel hierarchy, Pydantic foundations, entity management |
| `guide-business-dictionary` | Namespaced business vocabulary for naming tables/fields |
| `guide-connections` | Connector engine architecture (PostgreSQL, BigQuery, Snowflake, DuckDB) |
| `guide-flows` | SQLFlowTask/DataFlowTask lifecycle, write strategies, dependency graph |
| `guide-incremental` | `by_key` / `by_source_tst` / `no_increment` strategies, state management |
| `guide-structures` | Structure definitions, field characterisations, deployment |
| `guide-structure-audit` | StructureAudit entity — per-structure coverage and value-distribution audits |
| `how-to-profile-a-structure` | Profile (or hand-author), validate, and render a StructureAudit with `nld structure audit` |
| `how-to-characterize-fields` | Propose field characterisations for one structure from the rules + its audit, report, and confirm before updating |
| `how-to-trace-flow-lineage` | Trace upstream/downstream structure and flow lineage with `nld flow deps` |
| `how-to-get-execution-info` | Retrieving flow execution metadata from state backends |
| `how-to-get-incremental-info` | Retrieving incremental state from state backends |
| `how-to-use-business-dictionary` | `nld business dict find` / `list` CLI usage |
| `how-to-determine-incremental-strategy` | Decision walkthrough for picking `by_key` vs `by_source_tst` vs `no_increment` |

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
