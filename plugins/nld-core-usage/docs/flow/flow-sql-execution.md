## SQL Flow Execution

This document describes how to execute an `SQLFlowTask` from an nld project.

### Table of Contents

1. [Overview](#1-overview)
   - 1.1 [What SQLFlowTask Does](#11-what-sqlflowtask-does)
   - 1.2 [Class Hierarchy](#12-class-hierarchy)
2. [Project Setup](#2-project-setup)
   - 2.1 [Project Structure](#21-project-structure)
   - 2.2 [Project File](#22-project-file)
   - 2.3 [Connection Configuration](#23-connection-configuration)
   - 2.4 [Flow Definition YAML](#24-flow-definition-yaml)
   - 2.5 [SQL File](#25-sql-file)
3. [Write Strategies](#3-write-strategies)
   - 3.1 [Overview](#31-overview)
   - 3.2 [OVERWRITE (default)](#32-overwrite-default)
   - 3.3 [VIEW](#33-view)
   - 3.4 [INSERT](#34-insert)
   - 3.5 [UPSERT](#35-upsert)
   - 3.6 [DELETE_INSERT](#36-delete_insert)
   - 3.7 [UPSERT_LOGICAL_DELETE](#37-upsert_logical_delete)
   - 3.8 [Strategy Pattern Architecture](#38-strategy-pattern-architecture)
4. [Incremental Filtering](#4-incremental-filtering)
   - 4.1 [Overview](#41-overview)
   - 4.2 [MASTER Predecessor Resolution](#42-master-predecessor-resolution)
   - 4.3 [Filtering Rules](#43-filtering-rules)
   - 4.4 [YAML Examples](#44-yaml-examples)
5. [Execution](#5-execution)
   - 5.1 [CLI Command](#51-cli-command)
   - 5.2 [Programmatic Execution](#52-programmatic-execution)
6. [Execution Flow](#6-execution-flow)
   - 6.1 [High-Level Sequence](#61-high-level-sequence)
   - 6.2 [Initialization Phase](#62-initialization-phase)
   - 6.3 [Pre-Processing Phase](#63-pre-processing-phase)
   - 6.4 [SQL Execution Phase](#64-sql-execution-phase)
   - 6.5 [Post-Processing Phase](#65-post-processing-phase)
7. [SQL File Resolution](#7-sql-file-resolution)
   - 7.1 [Path Convention](#71-path-convention)
   - 7.2 [Namespace Mapping](#72-namespace-mapping)
8. [Configuration Reference](#8-configuration-reference)
   - 8.1 [Flow Definition Fields](#81-flow-definition-fields)
   - 8.2 [Parameter Formats](#82-parameter-formats)
9. [Error Handling](#9-error-handling)
10. [File Reference](#10-file-reference)

---

## 1. Overview

### 1.1 What SQLFlowTask Does

`SQLFlowTask` reads a `.sql` file containing a SELECT query and executes it on a target
database using a configurable write strategy. By default, the OVERWRITE strategy performs
a `TRUNCATE TABLE` followed by `INSERT INTO ... SELECT`. Other strategies support
incremental patterns such as INSERT, UPSERT, DELETE_INSERT, and UPSERT_LOGICAL_DELETE.

### 1.2 Class Hierarchy

```
BaseTask (abstract)
  └─ DataFlowTask (abstract)
       └─ SQLFlowTask (concrete)
            └─ delegates to SQLWriteStrategy (abstract)
                 ├─ OverwriteStrategy
                 ├─ ViewStrategy
                 ├─ InsertStrategy
                 ├─ UpsertStrategy
                 ├─ DeleteInsertStrategy
                 └─ UpsertLogicalDeleteStrategy
```

| Class | Location | Purpose |
|-------|----------|---------|
| `BaseTask` | `nld/task/base.py` | Execution UUID, logging, parameter validation |
| `DataFlowTask` | `nld/flow/task/data_flow_task.py` | Pre/post-processing lifecycle, state management |
| `SQLFlowTask` | `nld/flow/sql/sql_flow_task.py` | SQL-specific execution logic, strategy delegation |
| `SQLWriteStrategy` | `nld/flow/sql/sql_write_strategy.py` | Abstract base for write strategies |

`SQLFlowTask` defaults to the `NO_INCREMENT` incremental logic (only `FULL` loading
strategy). When the flow definition sets the `incremental` field (e.g. `by_source_tst`
or `by_key`), the incremental logic is resolved dynamically at init time and the SQL
query is automatically filtered based on the loading strategy. The `write_strategy`
parameter controls how data is written to the target table.

---

## 2. Project Setup

### 2.1 Project Structure

A minimal nld project for running an SQL flow requires:

```
my_project/
├── nld_project.yml
├── .nld/
│   └── secrets.toml
└── entities/
    └── flows/
        ├── my_flow.yml
        └── my_flow.sql
```

With a namespace:

```
my_project/
├── nld_project.yml
├── .nld/
│   └── secrets.toml
└── entities/
    └── flows/
        └── staging/
            ├── customer_summary.yml
            └── customer_summary.sql
```

For strategies that require a `target_structure` (OVERWRITE, INSERT, UPSERT, DELETE_INSERT,
UPSERT_LOGICAL_DELETE), a Structure entity must also be defined:

```
my_project/
├── nld_project.yml
├── .nld/
│   └── secrets.toml
└── entities/
    ├── structure/
    │   └── staging/
    │       └── customer_summary.yml
    └── flows/
        └── staging/
            ├── customer_summary.yml
            └── customer_summary.sql
```

### 2.2 Project File

The `nld_project.yml` file declares the project metadata:

```yaml
name: 'my_project'
version: '0.0.1'
entity_path: .
```

The `entity_path` field tells the framework where to find entities relative to the
project root. When set to `.`, the entities directory is at the project root level.

### 2.3 Connection Configuration

Connections are defined in `.nld/secrets.toml`:

```toml
[my_postgres]
type = "postgresql"
host = "localhost"
port = 5432
user = "postgres"
password = "secret"
database_name = "mydb"
schema_name = "staging"
```

The connection name (`my_postgres` here) is what the flow definition references in its
`data_connectors` mapping. The `schema_name` field is used as the default target schema
when `target_schema` is not explicitly set in the flow definition params.

### 2.4 Flow Definition YAML

The flow definition YAML file declares which task to run, which connectors to use,
and configuration parameters.

**Minimal definition (schema from connector credentials):**

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
data_connectors:
  target: my_postgres
```

When `target_schema` is omitted, the schema is resolved from the target connector's
`schema_name` credential field (e.g. `schema_name` in `secrets.toml`).

**With explicit schema override:**

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
data_connectors:
  target: my_postgres
params:
  target_schema: "analytics"
```

**With update strategy (e.g. UPSERT):**

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
target_structure: staging.customer_summary
write_strategy: UPSERT
data_connectors:
  target: my_postgres
params:
  target_schema: "analytics"
```

**Key fields:**

- `name`: the flow name, which also determines the target table name and the SQL
  file to look for
- `task`: the Python class path to `SQLFlowTask`
- `data_connectors.target`: maps the `target` connector role to a connection name
  from `secrets.toml`
- `target_structure`: entity reference to a Structure definition (required for
  INSERT, UPSERT, DELETE_INSERT, UPSERT_LOGICAL_DELETE strategies)
- `params.target_schema`: the database schema where the table will be created
  (optional, resolved from the connector's `schema_name` credential when omitted)
- `write_strategy`: the write strategy to use (default: `OVERWRITE`)
- `incremental`: the incremental strategy name (e.g. `by_source_tst`, `by_key`).
  When set, `SQLFlowTask` dynamically resolves the incremental logic and applies
  automatic WHERE clause filtering on the SQL query.
- `predecessors.<name>.role`: `MASTER` or `SECONDARY`. When no role is set, the
  first predecessor defaults to MASTER.
- `predecessors.<name>.key_field`: column name for `by_key` filtering on the
  MASTER predecessor.

**With incremental filtering (by_source_tst):**

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
incremental: by_source_tst
predecessors:
  customers:
    full_path: staging.customers
    role: MASTER
  orders:
    full_path: staging.orders
    role: SECONDARY
target_structure: warehouse.customer_summary
write_strategy: INSERT
data_connectors:
  target: my_postgres
```

**With incremental filtering (by_key):**

```yaml
name: customer_summary
task: nld.flow.sql.SQLFlowTask
incremental: by_key
predecessors:
  customers:
    full_path: staging.customers
    role: MASTER
    key_field: customer_id
target_structure: warehouse.customer_summary
write_strategy: UPSERT
data_connectors:
  target: my_postgres
```

### 2.5 SQL File

The SQL file must contain a SELECT query (without a trailing semicolon). The framework
wraps it according to the configured write strategy:

```sql
SELECT
    customer_id,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount
FROM source_schema.orders
GROUP BY customer_id
```

The file must be co-located with the YAML definition and share the same base name
(e.g. `customer_summary.yml` and `customer_summary.sql`).

---

## 3. Write Strategies

### 3.1 Overview

The `write_strategy` parameter controls how the SQL flow writes data to the target
table. This uses a Strategy pattern where each strategy is a concrete implementation
of the `SQLWriteStrategy` abstract class.

| Strategy | SQL Pattern | Requires target_structure | Requires PK |
|----------|-------------|--------------------------|-------------|
| `OVERWRITE` (default) | TRUNCATE + INSERT INTO ... SELECT | Yes | No |
| `VIEW` | CREATE OR REPLACE VIEW AS | No | No |
| `INSERT` | INSERT INTO ... SELECT | Yes | No |
| `UPSERT` | INSERT ... ON CONFLICT DO UPDATE | Yes | Yes |
| `DELETE_INSERT` | DELETE matching + INSERT | Yes | Yes |
| `UPSERT_LOGICAL_DELETE` | UPSERT + mark absent rows | Yes | Yes |

### 3.2 OVERWRITE (default)

Truncates the existing table and reloads it from the query result. This is the default
strategy. The target table must already exist (managed by structure deploy).

```sql
TRUNCATE TABLE schema.table;
INSERT INTO schema.table (col1, col2, ...) SELECT ...;
```

Requires: `target_structure` on the flow definition.

### 3.3 VIEW

Creates or replaces a database view. The view executes the query at read time, so
the data is always up to date. No physical table is created.

```sql
CREATE OR REPLACE VIEW schema.table AS (SELECT ...);
```

### 3.4 INSERT

Appends all rows from the query result to the existing target table. The table must
already exist with a compatible structure. No deduplication is performed.

```sql
INSERT INTO schema.table (col1, col2, ...) SELECT ...;
```

Requires: `target_structure` on the flow definition.

### 3.5 UPSERT

Inserts new rows and updates existing ones when a primary key conflict is detected.

**PostgreSQL** uses `INSERT ... ON CONFLICT DO UPDATE SET` with a `WHERE` clause
using `IS DISTINCT FROM` to skip no-op updates:

```sql
INSERT INTO schema.table (col1, col2, ...)
SELECT ...
ON CONFLICT (pk_col) DO UPDATE SET col2 = EXCLUDED.col2, ...
WHERE (table.col2 IS DISTINCT FROM EXCLUDED.col2 OR ...);
```

**Snowflake** uses `MERGE INTO ... WHEN MATCHED AND` with the same change-detection:

```sql
MERGE INTO schema.table AS target
USING (...) AS source
ON target.pk_col = source.pk_col
WHEN MATCHED AND (target.col2 IS DISTINCT FROM source.col2 OR ...)
  THEN UPDATE SET col2 = source.col2, ...
WHEN NOT MATCHED THEN INSERT (col1, col2, ...) VALUES (source.col1, source.col2, ...);
```

The `IS DISTINCT FROM` condition ensures rows are only updated when at least one
data column has actually changed. This prevents unnecessary writes, WAL entries,
index updates, and false `ts_updated_at` changes.

#### Field Characterisation-Based Exclusions

Two field characterisations control which columns participate in the upsert:

| Characterisation | UPDATE SET | WHERE match | Use case |
|---|---|---|---|
| `exclude_from_upsert_update` | No | No | Insert-only fields (e.g., `REC_INSERT_TST`) |
| `exclude_from_upsert_match` | Yes | No | Updated but shouldn't trigger diff (e.g., `REC_LAST_UPDATE_TST`, `REC_SOURCE_EXTRACTION_TST`) |

These characterisations are resolved in `_get_upsert_field_params()` and threaded
through the connector's `upsert_from_query()` method via the `exclude_from_update`,
`expression_overrides`, and `exclude_from_match` parameters.

Requires: `target_structure` with a primary key defined.

### 3.6 DELETE_INSERT

Deletes rows from the target table whose primary key values match those in the query
result, then inserts all rows from the query. This ensures a clean replacement of
the matched subset while preserving unmatched rows.

```sql
DELETE FROM schema.table WHERE (pk_col) IN (SELECT pk_col FROM (SELECT ...) AS _subq);
INSERT INTO schema.table (col1, col2, ...) SELECT ...;
```

Requires: `target_structure` with a primary key defined.

### 3.7 UPSERT_LOGICAL_DELETE

Performs an upsert (same as UPSERT strategy, including `IS DISTINCT FROM`
change-detection and characterisation-based exclusions), then marks rows
present in the target table but absent from the query result as logically
deleted by setting the deletion flag column to `TRUE`. The deletion flag
column is resolved dynamically from the target structure using the
`rec_deletion_flag` field characterisation.

```sql
-- Step 1: Upsert with change detection (same as UPSERT strategy)
INSERT INTO schema.table (col1, col2, ...)
SELECT ...
ON CONFLICT (pk_col) DO UPDATE SET col2 = EXCLUDED.col2, ...
WHERE (table.col2 IS DISTINCT FROM EXCLUDED.col2 OR ...);

-- Step 2: Mark absent rows as deleted
UPDATE schema.table SET <deletion_flag_column> = TRUE
WHERE (pk_col) NOT IN (SELECT pk_col FROM (SELECT ...) AS _src);
```

Requires: `target_structure` with a primary key defined and exactly one field with
the `rec_deletion_flag` characterisation.

### 3.8 Strategy Pattern Architecture

The strategy selection is handled by the `get_write_strategy()` factory function in
`nld/flow/sql/sql_write_strategy.py`. The `SQLFlowTask.run_flow()` method:

1. Resolves the write strategy from the flow definition's `write_strategy` via `get_write_strategy()`
2. Resolves the `target_structure` from the flow definition if the strategy requires it
3. Delegates execution to `write_strategy.execute(connector, table_path, sql_query, target_structure)`

The connector methods used by the strategies are defined on `SQLDataConnector`:

| Method | Used by | Description |
|--------|---------|-------------|
| `truncate_table` | OVERWRITE | Truncate a table |
| `insert_into_from_query` | OVERWRITE, INSERT, DELETE_INSERT | Insert from SELECT |
| `create_or_replace_view` | VIEW | Create or replace a view |
| `upsert_from_query` | UPSERT, UPSERT_LOGICAL_DELETE | Insert or update from SELECT |
| `delete_from_query` | DELETE_INSERT | Delete matching keys from subquery |
| `execute_query` | UPSERT_LOGICAL_DELETE | Execute raw SQL for logical delete |

---

## 4. Incremental Filtering

### 4.1 Overview

When a flow definition sets the `incremental` field, `SQLFlowTask` resolves the
incremental logic through `DataFlowDefinition.resolve_incremental_logic()` and
automatically injects WHERE clauses into the SQL query before execution. The
filtering targets MASTER predecessor tables and is based on the incremental
strategy and loading strategy.

`DataFlowDefinition.resolve_incremental_logic(task_class=None)` is the single
entry point for resolving the runtime logic. Resolution priority (cached on
the definition):

1. The strategy declared on the flow's ``incremental`` YAML config, looked up
   through `IncrementalStateManagerFactory.get_incremental_logic()` at
   `nld/flow/incremental/services/factory.py`.
2. The task class ``_INCREMENTAL_LOGIC`` ClassVar (when set).
3. ``NO_INCREMENT_FLOW_INCREMENTAL_LOGIC`` as a safe default.

`DataFlowTask` exposes the resolved value via the `incremental_logic` instance
property, which call sites (`__init__`, `init_state_manager`,
`incremental_definition`) read from instead of `_INCREMENTAL_LOGIC` directly.
`SQLFlowTask` no longer overwrites its ClassVar at construction time — the
resolver does that work in one place.

`SQLFlowTask._apply_incremental_filter()` delegates to
`IncrementalStateManager.apply_sql_filter()`, which calls the `sql_filter_manager` property
to obtain the strategy-specific `IncrementalSqlFilterManager` instance. Each manager exposes
its own SQL filter via this property:

- `BySourceTstStateManager.sql_filter_manager` returns a `BySourceTstSqlFilterManager` that injects timestamp-based WHERE clauses
- `ByKeyStateManager.sql_filter_manager` returns a `ByKeySqlFilterManager` that injects key-based IN clauses
- `NoIncrementStateManager.sql_filter_manager` returns a `NoIncrementSqlFilterManager` that returns the query unchanged

The SQL filter classes are defined in dedicated `sql_filter_manager.py` files within each
incremental module (`nld/flow/incremental/impl/by_source_tst/sql_filter_manager.py`, etc.).
The abstract base class `IncrementalSqlFilterManager` is defined in
`nld/flow/incremental/base/sql_filter_manager.py`.

Generic sqlglot helper functions (`find_table_reference`, `get_table_alias_or_name`) are
located in `nld/utils/sqlglot/utils.py`, while DML helpers (`build_timestamp_condition`,
`build_key_in_condition`) are in `nld/utils/sqlglot/base_dml.py`. Both are exported from
the `nld/utils/sqlglot/` package and used by the SQL filter implementations.

### 4.2 CLI parameter plumbing

CLI flags such as `--full`, `--with-delta`, `--pull-from`, and `--pull-to` reach
`SQLFlowTask.__init__` via `DataFlowExecutor.init_data_flow`, which filters
`task_request.get_parameters()` by `DataFlowDefinition.get_init_params_keys()`.

`DataFlowDefinition.get_init_params_keys()` returns the task class's
own init keys (via the standard `BaseTask.get_init_params_keys()`)
plus the param names from
`resolve_incremental_logic().definition.param_definitions`. The class
itself never appends incremental params: `DataFlowTask.get_init_params()`
is just the inherited `BaseTask` method. This makes the resolver the
single source of truth for "which CLI flags does this flow accept" —
the per-flow `incremental` strategy wins over the task class default,
and dropping it would silently fall back to `DELTA` even when `--full`
is passed.

`DataFlowExecutor.init_data_flow()` therefore performs **two**
mandatory-key checks before constructing the task:
- `task_type.check_init_params_dict(init_params)` — covers the
  task-class init params.
- `self._check_incremental_init_params(init_params)` — covers
  mandatory params from the resolved incremental logic.

When adding a new CLI flag for an incremental strategy, register it in **both**:
- the strategy's `param_definitions` list (e.g. `BY_SOURCE_TST_INCREMENTAL_DEFINITION` in
  `nld/flow/incremental/impl/by_source_tst/logic.py`), and
- the Click option in `nld/cli/flow/params_flow.py` plus the command decorator
  in `nld/cli/flow/main_flow.py`.

### 4.2 MASTER Predecessor Resolution

MASTER predecessors are resolved via `DataFlowDefinition.resolve_master_predecessors()`:

1. All predecessors with `role: MASTER` are returned.
2. If no predecessor has an explicit MASTER role, an empty list is returned (no filtering applied).
3. If no predecessors exist, an empty list is returned (no filtering applied).

Each MASTER predecessor's `full_path` is resolved to a `Structure` entity, which provides
field metadata needed for filtering (e.g. the `REC_LAST_UPDATE_TST` characterised field
for `by_source_tst`). Multiple MASTER predecessors are supported, allowing filtering
on multiple source tables in a single query.

### 4.3 Filtering Rules

| Incremental | Loading Strategy | Filter Applied |
|-------------|-----------------|----------------|
| `no_increment` | FULL | None |
| `by_source_tst` | FULL | None |
| `by_source_tst` | DELTA | `master.tst_col >= start AND master.tst_col < end` |
| `by_source_tst` | BACKFILL | Same as DELTA |
| `by_key` | FULL | None |
| `by_key` | DELTA | `master.key_field IN ('key1', 'key2', ...)` |
| `by_key` | BACKFILL | Same as DELTA |

For `by_source_tst`, the timestamp column is resolved from each MASTER predecessor
structure's `REC_LAST_UPDATE_TST` characterised field. The start and end timestamps
come from the `BySourceTstProcessingState` set during pre-processing.

For `by_key`, the key column is specified by the `key_field` attribute on each MASTER
predecessor. The keys come from `ByKeyProcessingState.get_keys_to_process()`.

The filter is injected using sqlglot: the SQL query is parsed, each MASTER table is
found by name matching, and the WHERE condition is AND'ed with any existing WHERE clause.
If the table has an alias (e.g. `FROM customers AS c`), the alias is used to qualify
the column reference.

### 4.4 YAML Examples

**by_source_tst with DELTA:**

Given this SQL file:

```sql
SELECT c.customer_id, c.name, o.total
FROM customers AS c
JOIN orders AS o ON c.customer_id = o.customer_id
WHERE o.status = 'completed'
```

With `incremental: by_source_tst` and `strategy: DELTA`, the query becomes:

```sql
SELECT c.customer_id, c.name, o.total
FROM customers AS c
JOIN orders AS o ON c.customer_id = o.customer_id
WHERE o.status = 'completed'
  AND c.last_update_tst >= '2025-01-01T00:00:00+00:00'
  AND c.last_update_tst < '2025-01-02T00:00:00+00:00'
```

**by_key with DELTA:**

```sql
SELECT customer_id, name, email
FROM customers
```

With `incremental: by_key`, `key_field: customer_id`, and `strategy: DELTA`:

```sql
SELECT customer_id, name, email
FROM customers
WHERE customers.customer_id IN ('cust_001', 'cust_002', 'cust_003')
```

---

## 5. Execution

### 5.1 CLI Command

Execute an SQL flow from the project root:

```bash
nld flow execute --flow-name customer_summary
```

With a namespace:

```bash
nld flow execute --flow-name customer_summary --flow-namespace staging
```

With a specific strategy:

```bash
nld flow execute --flow-name customer_summary --strategy FULL
```

**CLI Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--flow-name` | Yes | Name of the flow to execute |
| `--flow-namespace` | No | Dot-separated namespace (e.g. `staging`, `source.raw`) |
| `--strategy` | No | Loading strategy (FULL, DELTA, BACKFILL). Available strategies depend on the `incremental` configuration. |
| `--nld-root-folder-path` | No | Override the project root path |

The `write_strategy` (write strategy) is configured as a top-level field in the flow
definition YAML, not as a CLI parameter or flow parameter.

### 5.2 Programmatic Execution

From within a Python context where `NldExecutionContext` is already initialized:

```python
from nld.flow.task.executor import execute_data_flow

result = execute_data_flow(
    data_flow_name="customer_summary",
    namespace_name="staging",
)
```

---

## 6. Execution Flow

### 6.1 High-Level Sequence

```
CLI: nld flow execute --flow-name <name>
 │
 ▼
DataFlowExecutionTask.__init__()
 ├─ Load project entities
 ├─ Retrieve flow definition from entity registry
 ├─ Initialize DataFlowExecutor
 │   ├─ Initialize NldExecutionContext
 │   ├─ Validate flow definition coherence
 │   └─ Check connector availability
 └─ DataFlowExecutor.init_data_flow()
     ├─ Load data connectors (open connections)
     ├─ Build init parameters
     ├─ Validate init parameters
     └─ Instantiate SQLFlowTask
 │
 ▼
DataFlowExecutionTask.run()
 └─ DataFlowExecutor.execute_data_flow()
     ├─ Build run parameters
     ├─ Validate run parameters
     └─ SQLFlowTask.run()
         ├─ Pre-processing (state retrieval)
         ├─ run_flow() (strategy-based SQL execution)
         └─ Post-processing (state persistence)
 │
 ▼
FlowExecutionInfo (result)
```

### 6.2 Initialization Phase

**Entry point:** `DataFlowExecutionTask.__init__()` at `nld/flow/task/data_flow_exec_task.py:27`

1. **Load entities:** the execution context scans the `entities/flows/` directory
   for YAML definitions and registers them in the entity registry.

2. **Retrieve definition:** the flow definition is fetched by name and namespace
   from the entity registry.

3. **DataFlowExecutor initialization** at `nld/flow/task/data_flow_executor.py:29`:
   - Creates or reuses the `NldExecutionContext`
   - Calls `DataFlowDefinition.check_coherence()` to validate the task module
     can be loaded and parameters are valid
   - Verifies that all connectors referenced in `data_connectors` exist in
     the connection configuration

4. **Task instantiation** via `DataFlowExecutor.init_data_flow()` at `nld/flow/task/data_flow_executor.py:82`:
   - Loads the task class (already validated)
   - Opens database connections for all referenced connectors
   - Builds init parameters by merging flow definition params with CLI params
   - Injects the `namespaced_data_flow_definition` so the task has access to its
     own flow definition and namespace at runtime
   - Maps connector role names to actual connector instances
     (e.g. `target` + `_connector` suffix → `target_connector`)
   - Instantiates `SQLFlowTask` with the merged parameters
   - During `SQLFlowTask.__init__()`:
     - The parent `DataFlowTask.__init__()` reads `self.incremental_logic`,
       which delegates to `DataFlowDefinition.resolve_incremental_logic()` —
       the per-flow `incremental` config wins over the task class
       `_INCREMENTAL_LOGIC` ClassVar, with `NO_INCREMENT` as the fallback.
     - The target schema is resolved: if `target_schema` is provided explicitly it is
       used as-is, otherwise it falls back to the connector's `schema_name` credential.
       A `ValueError` is raised if neither is available.

### 6.3 Pre-Processing Phase

**Method:** `DataFlowTask.pre_processing()` at `nld/flow/task/data_flow_task.py:182`

The pre-processing runs three sub-phases in order:

1. **`pre_processing_at_start()`**: hook for custom initialization (no-op by default)
2. **`pre_processing_for_execution()`**: retrieves the latest execution state from
   the backend
3. **`pre_processing_for_state()`**: retrieves incremental state, source state,
   determines logically deleted entries, and determines processing state

For `SQLFlowTask` with `NO_INCREMENT` logic (default), these state operations are
mostly no-ops since there is no incremental tracking. When `incremental` is set on the
flow definition, the pre-processing phase retrieves incremental state from the backend
and computes the processing state (e.g. timestamps for `by_source_tst`, keys for
`by_key`), which is then used by `_apply_incremental_filter()` during `run_flow()`.

### 6.4 SQL Execution Phase

**Method:** `SQLFlowTask.run_flow()` at `nld/flow/sql/sql_flow_task.py:62`

1. **Assert connection:** verifies the target connector has an open connection
2. **Resolve SQL file:** finds the `.sql` file from the project entities structure
3. **Load SQL content:** reads and validates the file is not empty
4. **Apply incremental filter:** if the flow definition has an `incremental` strategy
   and the loading strategy is `DELTA` or `BACKFILL`, the SQL query is modified using
   sqlglot to add a WHERE clause on the MASTER predecessor table(s). The filtering logic
   is delegated by `_apply_incremental_filter()` to the incremental state manager's
   `apply_sql_filter()` method, which obtains the strategy-specific `IncrementalSqlFilterManager`
   via the `sql_filter_manager` property. Each SQL filter class is defined in a dedicated
   `sql_filter_manager.py` within its incremental module and uses helpers from
   `nld/utils/sqlglot/`. For `FULL` strategy or when no
   `incremental` is set, the query is returned unchanged.
5. **Build table path:** constructs `{target_schema}.{flow_name}`
   (e.g. `staging.customer_summary`), where `target_schema` was resolved during
   initialization from the explicit parameter or the connector's `schema_name` credential
6. **Resolve write strategy:** maps `write_strategy` to a `SQLWriteStrategy` instance
   via `get_write_strategy()`
7. **Resolve target structure:** if the strategy requires it, resolves the
   `target_structure` from the flow definition using `resolve_target_structure()`
8. **Execute strategy:** delegates to `strategy.execute(connector, table_path,
   sql_query, target_structure)` which performs the appropriate SQL operations

### 6.5 Post-Processing Phase

**Method:** `DataFlowTask.post_processing()` at `nld/flow/task/data_flow_task.py:246`

1. **`post_processing_for_state()`**: saves processing state and creates/saves
   post-processing state
2. **`post_processing_for_execution()`**: updates and saves the global execution
   state. Skipped on failure or for the UNIT strategy. For BACKFILL strategy,
   the execution history is updated but the execution state record is left
   unchanged so that the next regular run still sees the previous timestamps.
3. **`post_processing_at_end()`**: hook for custom cleanup (no-op by default)

The execution status is set to `SUCCEEDED` or `FAILED` based on whether `run_flow()`
raised a `RuntimeError`.

---

## 7. SQL File Resolution

### 7.1 Path Convention

SQL files are resolved using the function `resolve_sql_file_path()` at
`nld/flow/sql/sql_file_resolver.py:6`:

```
{entities_root}/flows/{namespace_as_path}/{flow_name}.sql
```

### 7.2 Namespace Mapping

| Namespace | SQL File Path |
|-----------|---------------|
| `.` (root) | `entities/flows/my_flow.sql` |
| `staging` | `entities/flows/staging/my_flow.sql` |
| `source.raw` | `entities/flows/source/raw/my_flow.sql` |

Dots in the namespace are converted to directory separators. The root namespace
(`.`) means the SQL file is placed directly under `entities/flows/`.

---

## 8. Configuration Reference

### 8.1 Flow Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Flow name (determines table name and SQL file name) |
| `task` | `str` | Yes | Python class path (use `nld.flow.sql.SQLFlowTask`) |
| `data_connectors` | `dict[str, str]` | Yes | Maps connector roles to connection names |
| `incremental` | `str` | No | Incremental strategy name (e.g. `by_source_tst`, `by_key`). When set, enables automatic SQL query filtering based on the loading strategy. |
| `predecessors` | `dict[str, DataFlowStructurePredecessor]` | No | Maps predecessor names to structure references. Used for incremental filtering. |
| `predecessors.<name>.full_path` | `NldEntityReference[Structure]` | Yes | Dot-separated reference to the predecessor structure entity. |
| `predecessors.<name>.role` | `str` | No | `MASTER` or `SECONDARY`. First predecessor defaults to MASTER when no role is set. |
| `predecessors.<name>.key_field` | `str` | No | Column name for `by_key` incremental filtering on the MASTER predecessor. |
| `state_backend_connector` | `str` or `StateBackendConnector` | No | Connector(s) for persisting execution/incremental state. Accepts a bare connection-name string (legacy form, coerced to `primary`) or a mapping with `primary` (required) and optional `secondary`. Each side may itself be a bare string or the typed `StateBackendConnectorConfig` (`connector` + free-form `params` dict — e.g. `file_format` for S3). The primary backend is authoritative for all reads and for the consolidated execution history; the secondary receives a dual-write copy of per-run execution info, step info and incremental processing state, with failures logged and swallowed (post-processing incremental state stays primary-only). |
| `target_structure` | `NldEntityReference[Structure]` | No | Dot-separated reference to a target structure entity (e.g. `staging.my_table`). Required for OVERWRITE, INSERT, UPSERT, DELETE_INSERT, and UPSERT_LOGICAL_DELETE strategies. |
| `write_strategy` | `str` | No | Write strategy: OVERWRITE, VIEW, INSERT, UPSERT, DELETE_INSERT, or UPSERT_LOGICAL_DELETE (default: OVERWRITE) |
| `params` | `list` or `dict` | No | Flow parameters |
| `params.target_schema` | `str` | No | Database schema for the target table |

### 8.2 Parameter Formats

Parameters can be provided in two formats.

**Dict format (simple key-value):**

```yaml
params:
  target_schema: "staging"
```

**List format (explicit types):**

```yaml
params:
  - name: target_schema
    type: str
    value: "staging"
```

The dict format is automatically normalized to the list format with type `str`.

### 8.3 State Backend Connector Formats

`state_backend_connector` accepts three YAML forms:

**Legacy bare string (single primary backend):**

```yaml
state_backend_connector: postgres_metadata
```

**Mapping with bare-string sides (primary + optional secondary mirror):**

```yaml
state_backend_connector:
  primary: postgres_metadata
  secondary: s3_data_target
```

**Mapping with typed sides (per-side connector + params):**

```yaml
state_backend_connector:
  primary:
    connector: postgres_metadata
  secondary:
    connector: s3_data_target
    params:
      file_format: parquet
```

The bare string at the root is normalized to `{primary: {connector: <value>}}`
and a bare string on a side is normalized to `{connector: <value>}` by
`field_validator`s on `StateBackendConnector` and `DataFlowDefinition`
(see `core/nld/flow/definition/state_backend_connector.py`).

`StateBackendConnectorConfig` carries the per-side `connector` name and a
free-form `params` dict. Backend-specific knobs (e.g. `file_format` for the
S3 backend) live in `params` so they can differ between primary and secondary
without polluting the shared model.

**Project + flow merging.** When a project-wide default and a flow-level value
both declare `state_backend_connector`, `merge_state_backend_connectors`
applies the flow value on top of the project default: the flow's `connector`
wins on each side, and `params` are merged field-by-field with flow params
overriding project params (so a project-wide `file_format` default still
applies unless the flow overrides it).

**Derivation from typed structures.**
`determine_parameters_for_flow_definition` is declared on the execution
and incremental backend base classes and overridden by each backend
class that needs typed-context derivation. The S3 mixin
(`S3BackendMixin`) resolves `s3_root_path` from `S3Structure.s3_root_path`
(composed `s3_root_prefix` + `s3_folder_path`, defaulting to the
structure name), and the override is inherited by both the execution
and `by_key` incremental S3 state backends. Derived values are merged
with per-side YAML `params` and explicit kwargs in that precedence:
**derived < `config.params` < explicit kwargs**. The read-only
`nld flow state` CLI uses the same code path to construct a backend
manager without going through the full executor, so values like
`s3_root_path` do not need to be repeated under `params:` when the
flow's target is an `S3Structure`.

When `secondary` is set, each side is built independently: each
resolves its own backend class, derives its own parameters from the
typed context, and merges its own `params`. The two sides do not share
`params`, so an S3 secondary can declare its own `file_format` next to
a PostgreSQL primary without polluting the shared model.

---

## 9. Error Handling

Errors are handled at three levels:

1. **Schema resolution** (`nld/flow/sql/sql_flow_task.py:98`): during task
   initialization, if no `target_schema` is provided and the connector credentials
   do not have a `schema_name`, a `ValueError` is raised.

2. **Strategy validation** (`nld/flow/sql/sql_flow_task.py:86`): if a strategy
   requires `target_structure` and none is set on the flow definition, a
   `ValueError` is raised. If a strategy requires a primary key and the structure
   has none, a `ValueError` is raised.

3. **SQLWriteStrategy level** (`nld/flow/sql/sql_write_strategy.py`): each strategy
   checks the `QueryExecResult` of every SQL operation. If any fails, a
   `RuntimeError` is raised with the error message from the connector.

4. **DataFlowTask level** (`nld/flow/task/data_flow_task.py:283`): the `run()` method
   catches `RuntimeError` from `run_flow()` and updates the execution status to
   `FAILED`. Post-processing always runs regardless of success or failure.

The `FlowExecutionInfo` returned by `run()` contains the final execution status
(`SUCCEEDED`, `SUCCEEDED_WITH_WARNING`, or `FAILED`) and any error message.

---

## 10. File Reference

| File | Purpose |
|------|---------|
| `nld/flow/sql/sql_flow_task.py` | SQLFlowTask implementation |
| `nld/utils/sqlglot/utils.py` | Generic sqlglot helper functions for SQL AST manipulation |
| `nld/utils/sqlglot/base_dml.py` | DML helper functions (timestamp conditions, key-in conditions) |
| `nld/flow/sql/sql_write_strategy.py` | Write strategy pattern (6 strategies) |
| `nld/flow/sql/sql_file_resolver.py` | SQL file path resolution and content loading |
| `nld/flow/utils/flow_update_strategy.py` | FlowUpdateStrategies enum |
| `nld/flow/task/data_flow_task.py` | DataFlowTask base class with lifecycle |
| `nld/flow/task/data_flow_exec_task.py` | CLI task runner for data flows |
| `nld/flow/task/data_flow_executor.py` | DataFlowExecutor orchestration |
| `nld/flow/definition/flow_definition.py` | DataFlowDefinition YAML model (predecessors, incremental) |
| `nld/flow/execution/execution_info.py` | FlowExecutionInfo and step tracking |
| `nld/flow/config/flow_config.py` | FlowConfig runtime model |
| `nld/flow/incremental/impl/no_increment/logic.py` | NO_INCREMENT incremental logic |
| `nld/flow/incremental/impl/by_source_tst/logic.py` | BY_SOURCE_TST incremental logic (FULL, DELTA, BACKFILL) |
| `nld/flow/incremental/impl/by_source_tst/manager.py` | BY_SOURCE_TST state manager |
| `nld/flow/incremental/impl/by_source_tst/sql_filter_manager.py` | BY_SOURCE_TST SQL filter (timestamp-based) |
| `nld/flow/incremental/impl/by_key/logic.py` | BY_KEY incremental logic (FULL, DELTA, BACKFILL) |
| `nld/flow/incremental/impl/by_key/sql_filter_manager.py` | BY_KEY SQL filter (key-based IN clause) |
| `nld/flow/incremental/services/factory.py` | IncrementalStateManagerFactory |
| `nld/flow/incremental/services/registry.py` | FlowIncrementalTypeRegistry for built-in and external types |
| `nld/flow/incremental/impl/no_increment/sql_filter_manager.py` | NO_INCREMENT SQL filter (no-op) |
| `nld/flow/incremental/base/sql_filter_manager.py` | IncrementalSqlFilterManager abstract base class |
| `nld/flow/incremental/services/factory.py` | IncrementalStateManagerFactory |
| `nld/cli/flow/main_flow.py` | CLI command definitions |
| `nld/connector/base/connector.py` | SQLDataConnector with DDL/DML methods |
| `nld/connector/base/config.py` | ConnectionConfig model for secrets.toml |
| `nld/connector/postgresql/engine/psycopg2/connector.py` | PostgreSQL connector implementation |
| `nld/connector/postgresql/engine/psycopg2/query_builder.py` | PostgreSQL query builder for INSERT/UPSERT |
