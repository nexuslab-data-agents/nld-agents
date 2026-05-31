---
name: how-to-check-connections
description: >
  Discover and verify project connections from the shell using the
  `nld connection` CLI. Use when the user asks "which connections are
  configured?", "what is the exact connection name?", "does this
  connection work?", or "why can't the flow reach the database?".
  Covers `nld connection export-env-var` (emit a connection's resolved
  parameters as `export` statements for `eval` into the current shell),
  `nld connection list` (every connection with its type and profiles),
  and `nld connection debug` (open a named connection and report success
  or the underlying error). All read from the project's resolved
  connection configs (TOML + `NLD__DATA_CONNECTION__*` environment
  sources).
user-invocable: true
---

# How to Check Connections

**Classification**: Atomic Skill | Connection Inspection

---

## Definition

- **What**: Discover the connections a project exposes and confirm a
  specific one can actually be opened, via the `nld connection list`
  and `nld connection debug` subcommands.
- **When**: Before running a flow against an unfamiliar project, when a
  flow fails to reach its source/target, when you need the exact
  `--connection-name` to pass to another command, or when validating
  freshly-supplied credentials.
- **Why**: Both commands resolve the connection through the project's
  `connection_configs` — the same merged view (TOML `secrets.toml`
  plus `NLD__DATA_CONNECTION__*` environment overrides) the executor
  uses at run time. Reaching for a raw `psql`/`bq`/`snowsql` probe
  bypasses that resolution and tests credentials the flow may not even
  see.

For the underlying config-source precedence, credential management, and
connector engine architecture, see the `guide-connections` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- Connections are loaded from the project's configured sources —
  typically a `secrets.toml` file (`TomlConnectionConfigSource`) and
  `NLD__DATA_CONNECTION__*` environment variables
  (`EnvironmentConnectionConfigSource`), with the environment source
  taking precedence. A connection that exists in neither source will
  not appear in `list` and cannot be `debug`-ged.

---

## The commands

```
nld connection export-env-var --connection-name <name> [--profile-name <profile>]

nld connection list

nld connection debug --connection-name <name> [--profile-name <profile>]
```

### Flags

| Command | Flag | Purpose |
|---------|------|---------|
| `export-env-var` | `--connection-name <name>` | Connection whose parameters to emit (required). |
| `export-env-var` | `--profile-name <profile>` | Profile whose resolved values to emit. Optional — omit for the default profile. |
| `list`  | — | None. Lists every connection resolved for the project. |
| `debug` | `--connection-name <name>` | Connection to open (required). |
| `debug` | `--profile-name <profile>` | Profile to open under. Optional — omit to use the connection's default profile. |

---

## Recipes

### 1. Load a connection's credentials into the current shell

```
eval "$(nld connection export-env-var --connection-name my_postgres)"
```

`export-env-var` resolves the connection and prints one `export`
statement per parameter, keyed under
`NLD__DATA_CONNECTION__<NAME>__<PARAM>` (plus a `__TYPE` entry):

```
export NLD__DATA_CONNECTION__MY_POSTGRES__TYPE="postgresql"
export NLD__DATA_CONNECTION__MY_POSTGRES__HOST="db.internal"
export NLD__DATA_CONNECTION__MY_POSTGRES__USER="app"
export NLD__DATA_CONNECTION__MY_POSTGRES__PASSWORD="..."
```

Wrap it in `eval "$(...)"` to load those variables into your current
shell — handy when running an ad-hoc `psql`/`bq`/`snowsql` probe with
the **same** credentials the project resolves. Add `--profile-name` to
emit a specific profile's resolved values:

```
eval "$(nld connection export-env-var --connection-name my_postgres --profile-name staging)"
```

Run without `eval` (interactive terminal) to preview the statements
first — the command prints a `# To load these variables…` helper
comment alongside them. An unknown connection name fails with
`Connection '<name>' not found`.

### 2. Which connections does this project expose?

```
nld connection list
```

Prints one line per connection, sorted by name:

```
Available connections:
  - my_postgres (type: postgresql, profiles: default, staging)
  - snow_opendata (type: snowflake, profiles: default)
```

Each entry shows the connection `name`, its `type` (`postgresql`,
`bigquery`, `snowflake`, `duckdb`, …), and its **selectable** profiles.
The profile list reports `default` whenever the connection declares
parameters directly (the implicit default profile), followed by every
named profile — so a connection with both surfaces `default` *and* its
named profiles (e.g. `default, staging`). A connection that declares
neither is reported as `profiles: default`. When the project resolves no
connections at all, the command logs `No connections found in the
project`.

Use this first to get the **exact** `--connection-name` for any
downstream command — the value is case-sensitive and must match the
config key, not a guess — and to see which `--profile-name` values are
selectable.

### 3. Does a specific connection work?

```
nld connection debug --connection-name my_postgres
```

`debug` resolves the connection and opens it. On success:

```
Connection my_postgres was opened successfully
```

On failure it reports the connection name, the exception class, and the
underlying message:

```
Connection 'my_postgres' could not be opened due to the error:
OperationalError with message 'connection refused'
```

A reachable connection that opens cleanly is the signal that
credentials, host, and network path are all valid for this project's
resolved config.

### 4. Test a non-default profile

```
nld connection debug --connection-name my_postgres --profile-name staging
```

Opens the connection under the named profile. The named profile is
merged over the connection's default parameters, with the named values
winning — so `staging` applies its overrides (e.g. a different database
or account) on top of the shared defaults. Omitting `--profile-name`
opens the default profile. The profile name must be one of those
reported by `nld connection list`; an unknown name fails with an
unavailable-profile error.

`--profile-name` is honoured wherever a connector is opened — the same
flag selects the profile for `nld connection export-env-var` (Recipe 1)
and `nld connection get-structure`, and for the `nld flow state get-*`
read commands it selects the credential profile of the flow's state
backend connection.

### 5. Discover, then verify

The canonical troubleshooting flow when a connection name is unknown or
a flow fails to reach its data:

```
nld connection list
nld connection debug --connection-name <name from the list>
```

List to obtain the exact name and available profiles, then debug to
confirm it opens. If `debug` fails, read the exception class to localise
the fault — an auth error points at credentials, a connection/operational
error at host/port/network, a config error at a missing or misnamed
parameter in the resolved sources.

---

## Guidelines for agents

- **List before you debug.** Connection names are case-sensitive config
  keys; `list` gives you the authoritative value instead of a guess.
- **A missing connection is a config signal, not a CLI failure.** If a
  connection you expected is absent from `list`, it is not present in
  the project's resolved sources — check `secrets.toml` and the
  `NLD__DATA_CONNECTION__*` environment variables, remembering the
  environment source overrides TOML.
- **Read the `debug` error class, not just the text.** The exception
  type (`OperationalError`, an auth error, a config/key error) tells you
  whether to look at the network, the credentials, or the config.
- **`debug` opens a real connection.** It performs an actual handshake
  against the backend; run it when you genuinely want to validate
  reachability, not as a dry config check.

---

## Cross-references

- Architectural reference: `guide-connections` (config-source
  precedence, `TomlConnectionConfigSource` /
  `EnvironmentConnectionConfigSource`, credential management, connector
  engine architecture).
- `nld connection get-structure` extracts a connection's database
  structure (tables, columns, keys) as YAML — a separate `nld
  connection` subcommand outside the scope of this how-to.
