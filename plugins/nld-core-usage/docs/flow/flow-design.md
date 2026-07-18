# NLD Flow Design

This document describes the architecture of the NLD Flow system. It covers the
implementation and the design decisions that guide development. The flow system
is the core engine that powers automated data pipelines in nld-core.

---

## 1. Purpose: SQL Query Automation

The primary focus of the NLD Flow system is the automation of SQL-based data
transformations. While the framework supports arbitrary Python task classes via
`DataFlowTask`, the main use case is `SQLFlowTask`: a task that reads a SQL SELECT
query from a co-located `.sql` file and materializes its result as a table.

- **SQL-first approach:** Most data flows are expressed as SQL SELECT statements.
  The framework reads a `.sql` file and applies a configurable **write strategy**
  (OVERWRITE, VIEW, INSERT, UPSERT, DELETE_INSERT, or UPSERT_LOGICAL_DELETE) to
  materialize the result. Execution, state tracking, and incremental logic are
  handled transparently.
- **SQLFlowTask** (`core/nld/flow/sql/sql_flow_task.py`) extends `DataFlowTask` and
  resolves its SQL file from the project entities root using the flow namespace and
  name (e.g. namespace `source.raw`, name `my_flow` resolves to
  `entities_root/flows/source/raw/my_flow.sql`). The write strategy is determined
  from the flow definition's `write_strategy` field (defaults to `OVERWRITE`).
- **DataFlowTask** (`core/nld/flow/task/data_flow_task.py`) provides the base
  lifecycle: pre-processing (state retrieval, source state, processing state
  determination) -> `run_flow()` -> post-processing (state saving, execution status).

---

## 2. Core Principles

### 2.1 Easy Flow Development

Developers define data flows as YAML definitions (`flows/<namespace>/<flow>.yml`) paired
with Python task classes extending `DataFlowTask`. The framework handles:
- Connector resolution and injection via `data_connectors` mapping
- Parameter management (init vs run separation)
- State manager creation via factories with pluggable backends and engines
- **Task auto-resolution:** When the `task` field is omitted from the YAML definition,
  the framework auto-resolves the task module from the entity path, namespace, and
  flow name (e.g. `<entity_path>.flows.<namespace>.<flow_name>`) and searches for a
  `DataFlowTask` subclass in that module using `find_subclass_in_module`.

Flow definitions support both explicit `task` module paths and auto-resolution
from the entity path. The `DataFlowTask` lifecycle (pre-processing -> run_flow
-> post-processing) is well established with hooks at every stage.

### 2.2 Automatic Data Updates on Deployment

When deploying a data asset, the system automatically handles:
- **DDL changes** (CREATE TABLE, ALTER TABLE for new columns and declared renames)
- **Data directives** (one-shot `backfill_default` fills, planned `reload`
  full refreshes consumed by the next execution)
- **Structure synchronization** (asset definition vs actual database state)

DDL is generated per connector (PostgreSQL, Snowflake, BigQuery, DuckDB) by the
structure diff DDL statement builder. The deploy planner detects changed flows
by definition-hash comparison and changed structures by live schema diff.

### 2.3 Autonomous Execution Perimeter Determination

The framework autonomously determines what needs to be processed:
- **Partition determination** via `by_key` incremental (key-level granularity with
  statuses: NOT_PROCESSED, SUCCEEDED, FAILED, DELETED)
- **Incremental time frames** via `by_source_tst` (timestamp-based pull ranges)
- **Scope filtering** via loading strategies (FULL, DELTA, UNIT, BACKFILL, BACKFILL_DELTA)

Three incremental types are supported (by_key, by_source_tst, no_increment)
with multiple backend/engine combinations:

| Backend | Engine | Supported Incremental Types |
|---------|--------|-----------------------------|
| S3 blob storage | pydantic, duckdb | by_key, by_source_tst, no_increment |
| PostgreSQL | pydantic | by_key, by_source_tst |
| Snowflake | pydantic | by_key, by_source_tst |
| Local filesystem | pydantic, duckdb | by_key, no_increment |

The `update_processing_state()` method in each manager determines the processing
perimeter based on strategy and historical state. UTC timezone is enforced on
`by_source_tst` incremental logic.

### 2.4 Separation of Run vs Deploy Concerns

- **Automatic runs** (scheduled/triggered): Execute flows with incremental logic only.
  Never perform structure changes.
- **Deployment**: Handles structure DDL updates and flow version recording,
  triggered by schema or logic changes.

The `nld flow deploy` command handles structure DDL and flow version
recording. The `nld flow execute` command runs flows with incremental logic
only (no DDL changes). The deploy planner computes an in-memory change set by
comparing asset definitions against the live database state, and the executor
applies DDL and records flow versions in dependency order. Deployment never
executes flows; a full refresh is requested through a `reload` change-file
directive, which plans it for the next `nld flow execute`. See
`flow-deployment.md`.

---

## 3. SQLFlowTask

### 3.1 Target Management

Each `DataFlowTask` has a target representing the destination where the flow
materializes its output.

**`target_structure` entity reference**

`DataFlowDefinition` has an optional `target_structure` field typed as
`NldEntityReference[Structure] | None`. This links a flow to its target
structure definition by name, using the generic entity reference system.

**`write_strategy` field**

`DataFlowDefinition` has an optional `write_strategy` field (string). This
specifies which SQL write strategy `SQLFlowTask` uses to materialize the query
result. Defaults to `OVERWRITE` when not specified.

**`predecessors` field**

`DataFlowDefinition` has a `predecessors` dictionary mapping names to
`DataFlowStructurePredecessor` (each containing a `full_path` entity reference
to a `Structure`). This declares which upstream structures the flow depends on,
enabling dependency graph resolution.

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
data_connectors:
  target: my_postgres
target_structure: staging.customer_summary
write_strategy: UPSERT
predecessors:
  raw_customers:
    full_path: source.raw_customers
```

At runtime, calling `definition.resolve_target_structure()` resolves the
reference through the entity registry and returns a deep-copied `Structure`
instance. The result is cached for repeated access.

Target information beyond the structure (schema, table name) is resolved at
runtime from connector credentials or explicit `target_schema` parameter.

### 3.1b SQL Write Strategies

`SQLFlowTask` delegates data materialization to pluggable `SQLWriteStrategy`
implementations (`core/nld/flow/sql/sql_write_strategy.py`). Six strategies are
available:

| Strategy | DDL/DML | Requires Structure | Requires PK |
|----------|---------|-------------------|-------------|
| `OVERWRITE` | TRUNCATE + INSERT INTO ... SELECT | Yes | No |
| `VIEW` | CREATE OR REPLACE VIEW | No | No |
| `INSERT` | INSERT INTO ... SELECT (append) | Yes | No |
| `UPSERT` | INSERT ... ON CONFLICT DO UPDATE | Yes | Yes |
| `DEL_INS` | DELETE matching PKs + INSERT | Yes | Yes |
| `UPSERT_LOG_DEL` | UPSERT + mark absent rows as logically deleted | Yes | Yes |

Strategies that require a target structure resolve it from the flow definition's
`target_structure` entity reference. Strategies that require primary keys read
them from the structure's field characterisations.

### 3.2 Incremental SQL Filtering

`SQLFlowTask.run_flow()` includes a filtering phase between SQL loading and
execution. The `_apply_incremental_filter()` method delegates to the incremental
state manager's `apply_sql_filter()`, which uses a strategy-specific
`IncrementalSqlFilterManager` to inject WHERE clauses into the base SQL query
via sqlglot AST manipulation.

**`run_flow()` lifecycle:**

```
1. Load base SQL from .sql file
2. Apply incremental filter (inject WHERE clauses based on strategy)
3. Execute final SQL via write strategy
```

**Injection method per incremental type:**

| Incremental Type | Injection |
|------------------|-----------|
| `by_source_tst` | Adds `WHERE` clause on source timestamp column |
| `by_key` | Adds `WHERE` clause on key column |
| `no_increment` | Leaves SQL as-is |

**Example: `by_source_tst` injection**

Base SQL:
```sql
SELECT id, name, updated_at
  FROM raw.customers
```

After parsing phase (DELTA strategy, pulling from `2024-01-15` to `2024-01-16`):
```sql
SELECT id, name, updated_at
  FROM raw.customers
 WHERE updated_at >= '2024-01-15T00:00:00Z'
   AND updated_at < '2024-01-16T00:00:00Z'
```

**Example: `by_key` injection**

Base SQL:
```sql
SELECT order_id, product, quantity
  FROM raw.orders
```

After parsing phase (processing keys `['2024-01', '2024-02']`):
```sql
SELECT order_id, product, quantity
  FROM raw.orders
 WHERE partition_key IN ('2024-01', '2024-02')
```

---

## 4. Development Lifecycle

The flow system supports a 3-environment, 5-step development lifecycle.

| Step | Environment | Description |
|------|-------------|-------------|
| 1. Development | Dev | Developer makes changes, tracking possible |
| 2. Deployment to Staging | Staging | `nld flow deploy` computes the change set, applies DDL, records versions |
| 3. Staging Testing | Staging | Processes execute automatically |
| 4. Deployment to Prod | Prod | Same deploy process as staging |
| 5. Production | Prod | Processes execute automatically |

**Environment flow:**

```
        DEV                    STAGING                   PROD
 ┌───────────────┐     ┌───────────────────┐     ┌───────────────────┐
 │               │     │                   │     │                   │
 │  1. Develop   │────►│  2. Deploy        │     │  4. Deploy        │
 │     flows     │     │     + Apply DDL   │     │     + Apply DDL   │
 │               │     │     + Record      │     │     + Record      │
 │               │     │       versions    │     │       versions    │
 │  (tracking    │     │  3. Automatic     │────►│  5. Automatic     │
 │   optional)   │     │     execution     │     │     execution     │
 │               │     │                   │     │                   │
 └───────────────┘     └───────────────────┘     └───────────────────┘
```

**Key design decisions:**

- The deployment change set is computed by comparing asset definitions against
  the live database schema. The same logic runs for staging and production.
- Automatic execution in staging and production uses incremental logic only
  (no DDL changes); deploy-requested reloads are consumed as planned
  incremental state.

---

## 5. Flow Dependency Graph

The `DataFlowDependencyGraphTask` (`core/nld/flow/task/data_flow_dependency_graph.py`)
builds a dependency graph from all registered flow definitions and outputs it as
JSON. It is accessible via the `nld flow deps` CLI command.

The graph is built by:
1. Creating **nodes** from all registered flow definitions (with id, namespace,
   name, and optional target_structure).
2. Creating **edges** by matching each flow's `predecessors` structure references
   against other flows' `target_structure` values. If flow B declares a predecessor
   structure that flow A produces (via `target_structure`), an edge is created from
   A to B.

```
Flow Definitions ──► DataFlowDependencyGraphTask ──► JSON (nodes + edges)
```

---

## 6. Change Use Cases for Deployment

The deployment system detects and handles these categories of changes:

| Change Type | DDL Action | Data Action |
|-------------|-----------|------------|
| **New table/view** | CREATE TABLE (views via VIEW flow execution) | None (population is a flow run) |
| **Column renaming** (declared via `rename_field`) | ALTER TABLE RENAME COLUMN | None |
| **New column** | ALTER TABLE ADD COLUMN | `backfill_default` directive if requested |
| **Column rule change** | None | `reload` directive → planned full refresh |
| **General selection change** (filter, ...) | None | `reload` directive → planned full refresh |
| **Additional data loaded** (new UNION, ...) | None | `reload` directive → planned full refresh |

This is supported by:
1. **Structure diff engine** - Compares asset definitions against live database
   schemas to detect structural changes (new tables, new columns, type changes)
2. **Change files** - Declare the intentions a diff cannot infer (renames,
   reloads, one-shot backfill defaults) in `.deployments/`, applied exactly once
3. **DDL statement builder** - Generates CREATE/ALTER/REBUILD statements with
   connector-specific implementations (PostgreSQL, Snowflake, BigQuery, DuckDB)
4. **Planner** - Computes the in-memory change set (flows + structures + links)
5. **Executor** - Applies it in dependency order with cascade-skip on failure

---

## 7. Backend Database for Operations Tracking

A centralized backend database tracks:

| Data | Purpose | Implementation |
|------|---------|----------------|
| **Flow execution history** | Track every run with timing, status, metrics | `FlowExecutionInfo` with S3/PostgreSQL/Local backends. All metadata tables include `ts_inserted_at` and `ts_updated_at` audit fields. |
| **Incremental state** | Track what was processed per flow (keys, timestamps) | Incremental state managers (S3/PostgreSQL/Local backends) |
| **Deployment history** | Track deployments, what changed, what was applied | `FlowDeployMetadataManager` with `_nld_flow_state`, `_nld_flow_history`, `_nld_flow_deployment` and per-run change tables |
| **Structure versions** | Track structure definitions over time for diff | `StructureMetadataBackendManager` with `_nld_structure_state` and `_nld_structure_history` tables |
| **Flow dependency graph** | Track flow-to-flow and flow-to-structure relationships | `DataFlowDependencyGraphTask` (JSON output) |

---

## 8. CLI Commands

### `nld flow deps`

Determine the full dependency tree of a flow or set of flows.

- Uses `DataFlowDependencyGraphTask`
- Builds a graph of nodes (flows) and edges (predecessor-to-successor through shared structures)
- Outputs a JSON file with `nodes` and `edges` arrays via `FileOutputService`
- Resolves flow-to-flow dependencies (which flows produce structures consumed by other flows)
- Resolves flow-to-structure dependencies (which structures a flow reads/writes)

### `nld flow deploy`

Deploy changed flows and their target structures:
- Detect changed flows via their definition hashes (YAML, SQL, task Python)
  and compute an in-memory change set against the live database schema
- Preview with `--preview` (exit code 2 when changes are pending, `--output`
  for JSON); apply with an interactive confirmation or `--no-interactive`
- Deploy structures in dependency order (CREATE / ALTER / REBUILD), execute
  pre/post deployment SQL hooks, recreate dependent views via VIEW flows
- Resolve pending `.deployments/` change files (flow renames, planned reloads)
- Track every run and flow version in the metadata backend via
  `FlowDeployMetadataManager`

See `flow-deployment.md` for the full architecture.

---

## 9. Architecture Overview

```
CLI Layer (nld flow info, nld flow execute, nld flow deps)
    │
    ▼
Flow Definition (YAML) ──► DataFlowTask (Python)
    │                           │
    │  target_structure ◄───────┤
    │  predecessors             │
    │  write_strategy           ▼
    │  task (explicit or    SQLFlowTask ──► SQL Write Strategies
    │   auto-resolved)         (OVERWRITE, VIEW, INSERT, UPSERT,
    │                           DEL_INS, UPSERT_LOG_DEL)
    ▼                           │
Entity Registry            State Management
    │                      (Execution + Incremental)
    ▼                           │
Connectors ◄────────────────────┘
(PostgreSQL, S3,           Backends
 Local, Snowflake)      (S3, PostgreSQL, Local)
                        Engines
                        (pydantic, duckdb)
                              │
Dependency Graph              │
(DataFlowDependencyGraphTask) │
    ▼                         │
JSON output (nodes + edges) ◄─┘
```

---

## 10. Key Files Reference

| Component | Path |
|-----------|------|
| CLI entry point | `core/nld/cli/main.py` |
| Flow CLI commands | `core/nld/cli/flow/main_flow.py` |
| Flow definition model | `core/nld/flow/definition/flow_definition.py` |
| Flow config | `core/nld/flow/config/flow_config.py` |
| DataFlowTask base | `core/nld/flow/task/data_flow_task.py` |
| DataFlowStep base | `core/nld/flow/task/data_flow_step.py` |
| Flow executor | `core/nld/flow/task/data_flow_executor.py` |
| Flow execution task | `core/nld/flow/task/data_flow_exec_task.py` |
| Flow info task | `core/nld/flow/task/data_flow_info.py` |
| Flow dependency graph task | `core/nld/flow/task/data_flow_dependency_graph.py` |
| SQLFlowTask | `core/nld/flow/sql/sql_flow_task.py` |
| SQL file resolver | `core/nld/flow/sql/sql_file_resolver.py` |
| SQL write strategies | `core/nld/flow/sql/sql_write_strategy.py` |
| State factory | `core/nld/flow/state/factory.py` |
| Flow state managers | `core/nld/flow/state/manager/` |
| Execution factory | `core/nld/flow/execution/factory.py` |
| Execution state manager | `core/nld/flow/execution/manager.py` |
| Execution tracking | `core/nld/flow/execution/execution_info.py` |
| Execution decorator | `core/nld/flow/execution/decorator.py` |
| Incremental factory | `core/nld/flow/incremental/services/factory.py` |
| Incremental logic (by_source_tst) | `core/nld/flow/incremental/impl/by_source_tst/logic.py` |
| Incremental logic (by_key) | `core/nld/flow/incremental/impl/by_key/logic.py` |
| Incremental logic (no_increment) | `core/nld/flow/incremental/impl/no_increment/logic.py` |
| Loading strategies | `core/nld/flow/utils/flow_loading_strategy.py` |
| Update strategies | `core/nld/flow/utils/flow_update_strategy.py` |
| Backend mixins (local) | `core/nld/flow/backend/local/backend_mixin.py` |
| Backend mixins (PostgreSQL) | `core/nld/flow/backend/postgresql/backend_mixin.py` |
| Backend mixins (S3) | `core/nld/flow/backend/s3_blob_storage/backend_mixin.py` |
| Structure model | `core/nld/structure/structure/structure.py` |
| Structure reader (PG) | `core/nld/connector/postgresql/service/structure_reader.py` |
| DDL operations (PG) | `core/nld/connector/postgresql/engine/psycopg2/connector.py` |
| DDL operations (PG, sqlglot) | `core/nld/connector/postgresql/sqlglot/ddl.py` |
| DML operations (PG, sqlglot) | `core/nld/connector/postgresql/sqlglot/dml.py` |
| SQL renderer | `core/nld/structure/service/structure_sql_renderer.py` |
| Entity registry | `core/nld/service/nld_entity_registry.py` |
| Backend mixins (Snowflake) | `core/nld/flow/backend/snowflake/backend_mixin.py` |
| Flow deploy planner | `core/nld/flow/deploy/flow_deploy_planner.py` |
| Flow deploy executor | `core/nld/flow/deploy/flow_deploy_executor.py` |
| Flow deploy metadata manager | `core/nld/flow/deploy/flow_deploy_metadata_manager.py` |
| Flow deploy metadata models | `core/nld/flow/deploy/flow_deploy_metadata_models.py` |
| SQL transformation registry | `core/nld/flow/sql/transformation/registry.py` |
| SQL transformation base resolver | `core/nld/flow/sql/transformation/base_resolver.py` |
| SQL glot utils | `core/nld/flow/sql/sql_glot_utils.py` |
