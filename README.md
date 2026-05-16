# nld-agents

Claude Code plugin marketplace for the NLD ecosystem — architectural
guides, how-to skills, and data conventions.

## Plugins

- **nld-core-usage** — Architectural and how-to skills for using the
  nld-core library (base model, connections, structures, flows,
  incremental processing, business dictionary, execution/incremental
  info accessors, incremental-strategy decision guide).
- **nld-data-conventions** — NLD data conventions (field naming,
  structure characterisations, data-layer architecture, lakehouse
  architecture).

## Installation

### 1. Add the marketplace

```
/plugin marketplace add nexuslab-data-agents/nld-agents
```

### 2. Install plugins

```
/plugin install nld-core-usage@nld-agents
/plugin install nld-data-conventions@nld-agents
```

### 3. Team setup

To make the marketplace automatically available for everyone on a project, add it to your project's `.claude/settings.json`:

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
