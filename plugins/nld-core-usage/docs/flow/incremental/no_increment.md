# no_increment — backend availability

Pass-through strategy for full-load flows that track no historical
state. State classes are empty. See the
[incremental availability overview](./README.md) for the command axes
and legend, and `guide-incremental` for the architecture.

## Availability by engine

`no_increment` has a single connector-agnostic backend implemented on
the shared base (`core/nld/flow/incremental/impl/no_increment/backend/`):
`base_with_pydantic.py` and `base_with_duckdb.py` (the DuckDB engine
inherits the pydantic pass-through).

| Engine | Flow execution | `get-state` | `compute` | `compute --persist` |
|--------|:--------------:|:-----------:|:---------:|:-------------------:|
| `pydantic` | ✅ (no-op) | ❌ | ✅ (empty) | — |
| `duckdb` | ✅ (no-op) | ❌ | ✅ (empty) | — |

## Notes

- **Flow execution** — `retrieve_current_state` returns an empty
  `NoIncrementState`; `write_processing_state` and
  `write_post_processing_state` are no-ops. A `no_increment` flow runs
  on any connector.
- **`get-state`** — `no_increment` persists no incremental state, so
  the read accessors raise `NotImplementedError`.
- **`compute`** — runs and resolves to an empty processing state; the
  CLI reports that there is nothing to compute.
- **`compute --persist`** — `no_increment` keeps
  `supports_planned_state=False`, so the strategy never persists a
  plan. `--persist` returns `persisted=False` and `get-planned` prints
  "Planned states are not supported for this flow" — for both the live
  CLI and the equivalent `nld flow execute --state-compute-only`
  short-circuit.

For the connector-by-connector view, see
[`../backends/`](../backends/README.md).
