---
name: guide-connections
description: >
  Architectural guide for the nld-core connection and connector system. Covers
  ConnectionConfigSource, TomlConnectionConfigSource, credential management,
  connector engine architecture, and connector usage patterns for PostgreSQL,
  BigQuery, Snowflake, and DuckDB.
user-invocable: false
---

# Guide: Connections & Connectors

Architectural reference for the nld-core connection configuration and connector
engine system. Use this guide when working on connector code, connection config,
or any code that initializes database connections.

## When to Use

Activate this guide when the agent is working on:
- Connector code in `nld/connector/`
- Connection configuration (TOML config files, `ConnectionConfigSource` subclasses)
- Database connection initialization or credential management
- Adding support for a new database backend

## Document Resolution

The full architectural reference is at
`${CLAUDE_PLUGIN_ROOT}/docs/connection/connection-config.md`.

### Key Sections

When reading the reference doc, focus on the section relevant to your task:

| Task | Section |
|------|---------|
| Understanding config source precedence | Part 1: "Precedence Rules" |
| Adding a new config source | Part 1: "Adding Custom Sources" |
| Writing a `secrets.toml` / env vars for a connection type | Part 1: "Per-Connector Credential Fields" |
| Understanding connector class hierarchy | Part 2: "Class Hierarchy" |
| Working with PostgreSQL connectors | Part 2: "PostgreSQL Connector Structure" |
| Static engine facts (data type enums, comparable aliases, fixed precision) | Part 2: "Connector Definitions" |
| DuckDB connector and the embedded `DuckDBEngine` | Part 2: "DuckDB Connector" |
| Understanding engine selection (`custom_connector`) | Part 2: "Engine Selection" |
| Selecting a profile when opening a connector (`get_data_connector` / `--profile-name`) | "Selecting a Profile at Connection Time" |
| Writing tests for connection code | Part 1: "Testing" |

## Critical Rules

### Query Execution with execute_query

When calling `execute_query` with a query that has no `name` and no `params`,
pass the query string directly instead of wrapping it in a `QueryWrapper`.

```python
# Good - plain string when no name or params needed
connector.execute_query("SELECT * FROM my_table")

# Bad - unnecessary QueryWrapper
connector.execute_query(QueryWrapper(query="SELECT * FROM my_table"))
```

Use `QueryWrapper` only when you need its additional features such as `name`,
`params`, or `runtime_exception_message`.

## Cross-References

- For structures that connectors read/write, see the `guide-structures` skill.
