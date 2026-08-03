# Connection & Connector Architecture

## Part 1: Multi-Source Connection Configuration

### Overview

The connection configuration system supports loading configurations from multiple sources with configurable precedence. This enables flexible configuration management where sensitive values can be overridden via environment variables, while keeping base configurations in TOML files.

## Architecture Components

### 1. ConnectionConfigSource (Abstract Base Class)

Located in: `core/nld/connector/base/config_source.py`

Base class defining the interface for all configuration sources:

```python
import abc
from typing import Optional

from nld.connector.base.config_source import ConnectionConfigs

class ConnectionConfigSource(abc.ABC):
    @abc.abstractmethod
    def load(self) -> Optional[ConnectionConfigs]:
        """Load connection configurations from this source."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if this source is available."""
        pass

    @abc.abstractmethod
    def get_priority(self) -> int:
        """Get the priority of this source (higher = higher priority)."""
        pass
```

### 2. TomlConnectionConfigSource

Loads configurations from TOML files (typically `secrets.toml`).

**Features:**
- Parses TOML structure with connections and profiles
- Supports file existence checking
- Configurable priority (default: 10)
- Optional `required` flag to enforce file existence

**TOML Format:**
```toml
[connection_name]
type = "connection_type"
param1 = "value1"
param2 = "value2"

[profile_name.connection_name]
param1 = "override_value1"
```

### 3. EnvironmentConnectionConfigSource

Loads configurations from environment variables.

**Features:**
- Configurable prefix (default: `NLD__DATA_CONNECTION`)
- Higher default priority (20) to override TOML
- Case-insensitive parameter names (converted to lowercase)

**Environment Variable Format:**
```bash
# Default profile parameters
NLD__DATA_CONNECTION__<CONNECTION_NAME>__<PARAM>=value

# Profile-specific parameters
NLD__DATA_CONNECTION__<CONNECTION_NAME>__<PROFILE_NAME>__<PARAM>=value

# Special parameters
NLD__DATA_CONNECTION__<CONNECTION_NAME>__TYPE=connection_type
NLD__DATA_CONNECTION__<CONNECTION_NAME>__CUSTOM_CONNECTOR=path.to.CustomClass
```

**Examples:**
```bash
# Snowflake connection
NLD__DATA_CONNECTION__SNOW_OPENDATA__TYPE=snowflake
NLD__DATA_CONNECTION__SNOW_OPENDATA__ACCOUNT=dummy.eu-west-3.aws
NLD__DATA_CONNECTION__SNOW_OPENDATA__USER=OPENDATA_USER
NLD__DATA_CONNECTION__SNOW_OPENDATA__PASSWORD=OPENDATA_PASSWORD

# Staging profile override
NLD__DATA_CONNECTION__SNOW_OPENDATA__STAGING__DATABASE_NAME=OPENDATA_STAGING

# Azure connection
NLD__DATA_CONNECTION__AZURE_OPENDATA__TYPE=azure_blob_storage
NLD__DATA_CONNECTION__AZURE_OPENDATA__STORAGE_ACCOUNT_NAME=dummy_storage
```

### 4. ConnectionConfigLoader

Manages multiple sources and merges configurations with precedence.

**Features:**
- Accepts list of sources
- Automatically sorts sources by priority (lowest to highest)
- Merges configurations with higher priority sources overriding lower
- Separate merging for default profiles and named profiles

**Merging Behavior:**
1. Process sources in priority order (lowest to highest)
2. For each connection:
   - Type and custom_connector: Overridden if provided by higher priority
   - Default profile: Parameters merged, higher priority overrides
   - Profiles: Each profile merged separately, higher priority adds/overrides parameters

## Usage

### Basic Usage with from_sources()

The simplest way to use multi-source loading:

```python
from nld.connector.base.config import ConnectionConfigs

# Load from all available sources (TOML + environment variables)
configs = ConnectionConfigs.from_sources("/path/to/config/directory")

# Use the configs
connection = configs.get_connection_config("snow_opendata")
params = connection.get_parameters_for_profile("staging")
```

### Custom Source Configuration

For more control, create sources and loader manually:

```python
from nld.connector.base.config_loader import ConnectionConfigLoader
from nld.connector.base.config_source import (
    TomlConnectionConfigSource,
    EnvironmentConnectionConfigSource,
)

# Create sources with custom priorities
sources = [
    TomlConnectionConfigSource(
        file_path="/path/to/secrets.toml",
        priority=10,
        required=True  # Fail if file doesn't exist
    ),
    EnvironmentConnectionConfigSource(
        prefix="NLD__DATA_CONNECTION",
        priority=20
    ),
]

# Load and merge
loader = ConnectionConfigLoader(sources)
configs = loader.load()
```

### Adding Custom Sources

Implement the `ConnectionConfigSource` interface:

```python
from typing import Optional
from nld.connector.base.config_source import ConnectionConfigSource, ConnectionConfigs

class CustomConfigSource(ConnectionConfigSource):
    def __init__(self, priority: int = 15):
        self.priority = priority

    def is_available(self) -> bool:
        # Check if source is available
        return True

    def get_priority(self) -> int:
        return self.priority

    def load(self) -> Optional[ConnectionConfigs]:
        # Load and return ConnectionConfigs
        # Return None if source is unavailable
        pass
```

## Default Configuration in NldExecutionContext

The execution context wires the sources automatically
(`core/nld/task/context/context.py`): `NldExecutionContext.__init__` calls
`ConnectionConfigs.from_sources(nld_config_folder_path)`, which builds exactly
two sources — `TomlConnectionConfigSource(<config folder>/secrets.toml,
priority=10, required=False)` and
`EnvironmentConnectionConfigSource("NLD__DATA_CONNECTION", priority=20)`.

The config folder resolves in order: `task_request.nld_config_folder_path` →
env `NLD__CONFIG_FOLDER_PATH` → `<cwd>/.nld`. So the default connection file
is `.nld/secrets.toml`. The context also loads `.nld/.env` with
`override=False` — variables already exported (CI, pod secrets) always beat
the file.

## Precedence Rules

### Priority Values

- **Lower number** = Lower priority (loaded first)
- **Higher number** = Higher priority (overrides lower)

**Default Priorities:**
- TOML files: **10**
- Environment variables: **20**

### Merging Examples

#### Example 1: Simple Override

**secrets.toml:**
```toml
[myconn]
type = "snowflake"
account = "toml_account"
user = "toml_user"
password = "toml_password"
```

**Environment variables:**
```bash
NLD__DATA_CONNECTION__MYCONN__ACCOUNT=env_account
```

**Result:**
```python
config.type = "snowflake"           # From TOML
config.default_profile = {
    "account": "env_account",       # Overridden by env
    "user": "toml_user",            # From TOML
    "password": "toml_password"     # From TOML
}
```

#### Example 2: Profile Merging

**secrets.toml:**
```toml
[myconn]
type = "snowflake"
account = "base_account"

[staging.myconn]
database_name = "staging_db"
warehouse = "staging_wh"
```

**Environment variables:**
```bash
NLD__DATA_CONNECTION__MYCONN__STAGING__WAREHOUSE=env_wh
NLD__DATA_CONNECTION__MYCONN__STAGING__ROLE=env_role
```

**Result:**
```python
# Default profile
config.default_profile = {
    "account": "base_account"
}

# Staging profile
config.profiles["staging"] = {
    "database_name": "staging_db",       # From TOML
    "warehouse": "env_wh",          # Overridden by env
    "role": "env_role"              # Added by env
}

# When getting staging profile parameters (merged with default):
staging_params = {
    "account": "base_account",      # Inherited from default
    "database_name": "staging_db",       # From staging profile
    "warehouse": "env_wh",          # From staging profile
    "role": "env_role"              # From staging profile
}
```

## Per-Connector Credential Fields

TOML keys and env-var parameters must match the credential model fields of the
connection's `type`:

| `type` | Fields |
|--------|--------|
| `postgresql` | `host`, `port`, `user`, `password`, `database_name`, `schema_name`, `sslmode` (`disable`/`allow`/`prefer`/`require`/`verify-ca`/`verify-full`), `sslrootcert` |
| `bigquery` | `project_id` (required), `dataset_id`, `schema_name`, `location`, `credentials_path`, `api_endpoint`. Auth: service-account JSON via `credentials_path`; Application Default Credentials when unset; anonymous against `api_endpoint` (emulator) |
| `snowflake` | `account`, `user`, `authenticator` (`snowflake` → requires `password`; `snowflake_jwt` → requires `private_key_path` [+ `private_key_passphrase`]; `programmatic_access_token` → requires `token`), `role`, `warehouse`, `database_name`, `schema_name` |
| `duckdb` | `database_name` (the database file path — DuckDB is file-based), `schema_name` (default `main`) |
| `azure_blob_storage` | `storage_account_name`, `sas_token` |
| `s3_blob_storage` | `endpoint_url`, `region_name`, `access_key_id`, `secret_access_key`, `bucket_name` |
| `local` | `base_path` |

`schema_name` is the canonical cross-connector field for the active schema
(`get_active_schema()`); on BigQuery it designates the dataset, falling back
to `dataset_id`.

## Selecting a Profile at Connection Time

A profile is resolved when a connector is opened, not only when reading
raw parameters. `NldExecutionContext.get_data_connector` and
`load_connector` accept an optional `profile_name`:

```python
# Default profile — parameters declared directly on the connection
connector = execution_context.get_data_connector("my_postgres")

# Named profile, merged over the default profile (named values win)
connector = execution_context.get_data_connector(
    "my_postgres", profile_name="staging"
)
```

When `profile_name` is omitted, the connector opens with
`default_profile`. When supplied, the named profile is merged over
`default_profile` via `ConnectionConfig.get_parameters_for_profile`, so
named values override the defaults. An unknown profile name raises
`UnavailableConnectionProfileException`.

The first `get_data_connector` call for a connection lazy-loads it under
the requested profile; the profile is fixed for the lifetime of that
loaded connector.

### Enumerating Selectable Profiles

`ConnectionConfig.get_available_profile_names()` returns every profile a
caller can select:

- `"default"` whenever the connection declares parameters directly (a
  non-empty `default_profile`),
- each named profile from `profiles`,
- `"default"` as the sole fallback when the connection declares neither.

This differs from `get_profile_names()`, which returns only the named
profiles. Use `get_available_profile_names()` for listings that must
surface the implicit default alongside named profiles.

### CLI Surface

`--profile-name` selects the profile on the subcommands that open a
connector:

- `nld connection debug`, `nld connection export-env-var`,
  `nld connection get-structure`, and `nld connection export-query-csv`
  open the named connection under the selected profile.
- `nld flow state` read subcommands (`execution get-state`,
  `execution get-history`, `execution get-steps`,
  `incremental get-state`, `incremental get-planned`) select the
  credential profile of the state backend connection they read from.

Omitting the flag uses the default profile. `nld connection list` takes
no `--profile-name`; it reports each connection's selectable profiles
via `get_available_profile_names()`.

### Exporting Query Results to CSV

`nld connection export-query-csv` executes a read-only SELECT against a
named connection and writes the result to a CSV file:

```bash
nld connection export-query-csv --connection-name my_conn \
    --query "SELECT * FROM users" --output-file users.csv

nld connection export-query-csv --connection-name my_conn \
    --query-file users.sql --delimiter ";"
```

The query is passed inline (`--query`) or read from a `.sql` file
(`--query-file`); `--output-file` defaults to `query_result.csv`,
`--delimiter` to a comma, and `--no-header` suppresses the header row.
Only SELECT (or WITH) statements are accepted — statement type is
checked via the sqlglot utils (`assert_select_query`), so the command
cannot mutate the connected database.

The command is backed by `export_query_to_csv` on the connector base —
an abstract method each connector implements with its native export
path for efficiency: psycopg2 `COPY` for PostgreSQL, Arrow fetch for
Snowflake, native `COPY TO` for DuckDB, and the client's
`to_dataframe` materialization for BigQuery.

## Testing

Comprehensive tests are available in `tests/unit/connector/base/test_config_sources.py`:

- `test_toml_source_basic`: Basic TOML loading
- `test_environment_source_basic`: Basic environment variable loading
- `test_loader_with_precedence`: Multi-source precedence
- `test_loader_merge_profiles`: Profile merging from different sources

Run tests:
```bash
pytest tests/unit/connector/base/test_config_sources.py -v
```

## Part 2: Connector Engine Architecture

### Terminology

| Term | Definition |
|------|-----------|
| **Engine** | The driver/protocol used to connect to a backend. Examples: psycopg2, DuckDB, snowflake-connector-python. Each engine has its own connection wrapper and connector implementation. |
| **Adapter** | A data interface layer that translates between Python data structures and backend operations. Examples: Pandas (DataFrames), Pydantic (models). Adapters are scoped to a specific engine because they depend on engine-specific APIs. |
| **Connector** | The high-level interface for interacting with a backend. A connector type (e.g., PostgreSQL) can have multiple engines. |

### Base Layer

The base connector layer supports multi-engine patterns through generic type parameters:

```python
DataConnector[CONNECTION_WRAPPER: ConnectionWrapper[Any, Any]]
SQLDataConnector[CONNECTION_WRAPPER: ConnectionWrapper[Any, Any]]
ConnectionWrapper[CREDENTIAL_TYPE, CONNECTION_TYPE]
```

Each engine produces a different `ConnectionWrapper` specialization, and the
connector is parameterized by it. The `ConnectorPlugin` supports a
`custom_connector_class` parameter for engine selection.

### Directory Convention

Connectors follow this directory structure:

```
connector/<type>/
├── __init__.py                      → Plugin (default engine), package exports
├── <type>_credential.py             → shared across all engines
├── <type>_structure.py              → connector-specific Structure subclass
├── connector_definition.py          → data type enum + ConnectorDefinition singleton
├── engine/
│   └── <engine-name>/
│       ├── __init__.py
│       ├── connector.py             → engine-specific connector
│       ├── connection.py            → engine-specific connection wrapper
│       ├── query_wrapper.py         → engine-specific query handling
│       ├── utils.py                 → engine-specific utilities
│       └── adapter/
│           ├── pandas/              → DataFrame adapter (engine-specific)
│           └── pydantic/            → NldBaseModel manager (engine-specific)
├── service/
│   ├── structure_reader.py          → catalog extraction (engine-agnostic)
│   ├── data_profiler.py             → audit-query profiling
│   ├── deploy_capabilities.py       → ConnectorDeployCapabilities profile
│   └── structure_diff_ddl_statement_builder.py → deploy DDL statements
└── sqlglot/
    ├── ddl.py                       → dialect DDL builder (owns catalog queries)
    └── dml.py                       → dialect DML builder
```

### Connector Definitions

Each connector exposes a `ConnectorDefinition` singleton — its static engine
facts — via `DataConnector.get_connector_definition()`. The definition lives
in the connector's `connector_definition.py` together with the engine's data
type enum (`PostgreSQLDataTypes`, `BigQueryDataTypes`, `SnowflakeDataTypes`,
`DuckDBDataTypes`) and carries:

- `name` — the connector type string.
- `accepted_data_types` — the engine type spellings a structure definition may
  declare (empty means unrestricted).
- `comparable_data_type_aliases` — engine spellings mapped to their canonical
  comparable form (consumed by deploy diff/drift type normalization).
- `fixed_precision_data_types` — types whose precision is fixed by the engine
  and never reported by the structure readers.

Deployment-specific engine behavior lives separately in
`ConnectorDeployCapabilities` (`service/deploy_capabilities.py`), reached via
`get_deploy_capabilities()` — see `structure-deployment.md` for the
capability matrix. Services consult the definition and capabilities instead
of hardcoding engine knowledge locally, and structure readers never write
SQL: every catalog query a reader runs is built by the connector's sqlglot
DDL builder.

### PostgreSQL Connector Structure

```
nld/connector/postgresql/
├── __init__.py                      → Plugin (default: psycopg2 engine)
├── postgresql_credential.py         → PostgreSQLCredential
├── postgresql_structure.py          → PostgreSQLStructure
├── connector_definition.py          → PostgreSQLDataTypes + PostgreSQLConnectorDefinition
├── engine/
│   └── psycopg2/
│       ├── __init__.py
│       ├── connector.py             → Psycopg2SQLConnector
│       ├── connection.py            → Psycopg2SQLConnectionWrapper
│       ├── query_wrapper.py         → engine query handling
│       ├── utils.py                 → engine utilities
│       └── adapter/
│           ├── pandas/
│           │   └── dataframe_manager.py → PandasPostgreSQLManager
│           └── pydantic/
│               └── model_manager.py     → NldBaseModelPostgreSQLManager
├── service/
│   ├── structure_reader.py          → PostgreSQLStructureReader
│   ├── data_profiler.py
│   ├── deploy_capabilities.py       → POSTGRESQL_DEPLOY_CAPABILITIES
│   └── structure_diff_ddl_statement_builder.py → PostgreSQLStructureDiffDDLStatementBuilder
└── sqlglot/
    ├── ddl.py
    └── dml.py
```

### DuckDB Connector

DuckDB is a full connector type (`type = "duckdb"`, file-based: the
`database_name` credential is the database file path) following the standard
layout, with its engine under `engine/duckdb_native/`. The package also
exposes `DuckDBEngine` (`duckdb_engine.py`) — an embedded in-memory SQL
engine usable for Parquet file operations independently of any named
connection:

```
nld/connector/duckdb/
├── __init__.py                      → Plugin (default: duckdb_native engine)
├── duckdb_credential.py             → DuckDBCredential (database_name, schema_name="main")
├── duckdb_structure.py
├── connector_definition.py          → DuckDBDataTypes + DuckDBConnectorDefinition
├── duckdb_engine.py                 → DuckDBEngine (embedded Parquet/SQL engine)
├── constants.py                     → DUCKDB_DIALECT
├── engine/duckdb_native/            → DuckDBSQLConnector, wrapper, adapters
├── service/                         → reader, profiler, capabilities, deploy DDL builder
└── sqlglot/                         → dialect DDL/DML builders
```

### Adapter Scoping

Adapters are scoped to a specific engine because they depend on engine-specific APIs:

| Adapter | Engine dependency | Specific API used |
|---------|------------------|-------------------|
| `PandasPostgreSQLManager` | psycopg2 | `psycopg2.extras.execute_values()` for batch inserts |
| `NldBaseModelPostgreSQLManager` | psycopg2 | `psycopg2.sql.SQL()`, `sql.Identifier()`, `sql.Literal()` |

If a new engine needs DataFrame or Pydantic model support, it must provide its
own adapter implementations using that engine's API. Adapters live under the
engine they depend on:

```
connector/<type>/engine/<engine>/adapter/<adapter-name>/
```

### Class Hierarchy

```mermaid
classDiagram
    direction TB

    class ConnectionWrapper~CRED, CONN~ {
        <<abstract>>
        +name: str
        +credentials: CRED
        +connection: CONN
        +open() Self
        +close() Self
        +type: str
    }

    class DataConnector~CW~ {
        +connection_wrapper: CW
        +open_connection()
        +close_connection()
    }

    class SQLDataConnector~CW~ {
        <<abstract>>
        +execute_query()
        +create_table()
        +drop_table()
    }

    class ConnectorPlugin~DC, CW, CRED~ {
        +connector_class: type
        +connection_wrapper_class: type
        +credentials_class: type
        +create_new_connector()
    }

    DataConnector <|-- SQLDataConnector
    SQLDataConnector <|-- Psycopg2SQLConnector

    ConnectionWrapper <|-- Psycopg2SQLConnectionWrapper

    class Psycopg2SQLConnector {
        psycopg2 implementation
    }

    class Psycopg2SQLConnectionWrapper {
        ConnectionWrapper~PGCredential, Psycopg2Conn~
    }

    class PandasPostgreSQLManager {
        +connector: Psycopg2SQLConnector
        +insert_dataframe()
        +fetch_table()
    }

    class NldBaseModelPostgreSQLManager {
        +connector: Psycopg2SQLConnector
        +create_table()
        +insert_model()
        +upsert_model()
        +read_models()
    }

    Psycopg2SQLConnector --> PandasPostgreSQLManager : used by
    Psycopg2SQLConnector --> NldBaseModelPostgreSQLManager : used by
```

### Engine Selection

Engine selection happens at the plugin level: each connector package's
`__init__.py` exposes a `Plugin` whose `connector_class` is the default
engine's connector (psycopg2 for PostgreSQL, duckdb_native for DuckDB).

A connection substitutes its own connector class through the
`custom_connector` config key — a dotted class path that must subclass the
plugin's connector class:

```toml
[my_postgres]
type = "postgresql"
custom_connector = "my_package.connectors.MyTunneledPostgreSQLConnector"
host = "..."
```

`ConnectorFactory` resolves the path at creation time (env-var form:
`NLD__DATA_CONNECTION__MY_POSTGRES__CUSTOM_CONNECTOR=...`). Additional plugin
search packages come from `ConnectorFactory(allowed_connector_paths=[...])`.
