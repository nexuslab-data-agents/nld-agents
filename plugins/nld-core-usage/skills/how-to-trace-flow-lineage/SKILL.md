---
name: how-to-trace-flow-lineage
description: >
  Trace the upstream and downstream flow lineage of a structure (or a flow) from
  the shell with `nld flow deps`. The command builds the flow dependency graph — a
  directed, bipartite graph of flow nodes and structure nodes — and scopes it to
  the lineage around one node. Use when you need to know what feeds a structure,
  what consumes it, or the structure-to-structure lineage across the project.
user-invocable: true
---

# How to Trace Flow Lineage

**Classification**: Atomic Skill | Structure Analysis

---

## Definition

- **What**: Use `nld flow deps` to extract the **upstream** (what feeds it) and
  **downstream** (what it feeds) links of a chosen structure or flow, scoped to
  that node's lineage, as JSON or a Mermaid diagram.
- **When**: You need to answer "where does this table come from?", "what breaks
  if I change it?", "which flows read or write it?", or "what is the
  structure-to-structure lineage in this namespace?".
- **Why**: The links are not declared on the structures themselves — they are
  **derived from the flow definitions** (each flow's `target_structure` and its
  `predecessors`). `nld flow deps` reads every flow definition, assembles the
  graph, and filters it to the lineage you ask for, so you get the real wiring
  instead of guessing from names.

For explicit, hand-declared field-level links between two structures (mappings,
cardinality), that is a different mechanism — see the `how-to-model-structure-layers`
and `guide-structure-model` skills. This skill is about the **lineage derived
from flows**.

---

## Mental model: a bipartite flow graph

The dependency graph has **two kinds of node** and edges always run **in the
direction the data flows**:

- `structure.<namespace>.<name>` — a structure node.
- `flow.<namespace>.<name>` — a flow node.
- **Edge `structure → flow`**: the flow reads that structure (it is a
  **predecessor** of the flow).
- **Edge `flow → structure`**: the flow writes that structure (it is the flow's
  **target structure**).

Consequences:

- **Structures never link to structures directly.** A structure-to-structure
  link is always **two hops** through the flow that connects them:

  ```
  structure A  ──►  flow X  ──►  structure B
  (X reads A)              (X writes B)
  ```

  So "B depends on A" means *some flow reads A and writes B*.
- **Upstream** of a node = follow edges **backwards** (its sources).
  **Downstream** = follow edges **forwards** (its consumers).
- A structure only appears in the graph if **some flow references it** as a
  target or predecessor. A structure no flow touches has no derivable links.

---

## The command

```
nld flow deps [--structure-name <s> | --flow-name <f>] [--namespace <ns>]
              [--upstream] [--downstream] [--format json|mermaid]
              [--override-output-folder-path <dir>]
```

| Option | Purpose |
|--------|---------|
| `--structure-name <s>` | Focus the lineage on this structure. **Mutually exclusive** with `--flow-name`. |
| `--flow-name <f>` | Focus the lineage on this flow. Mutually exclusive with `--structure-name`. |
| `--namespace <ns>` | Namespace the focus node resolves in. With **no** `--structure-name`/`--flow-name`, scopes the graph to the whole namespace. |
| `--upstream` | Keep only the **upstream** lineage of the focus node (its sources). |
| `--downstream` | Keep only the **downstream** lineage (its consumers). |
| `--format json\|mermaid` | Output format. `json` (default) for machine reading; `mermaid` for a diagram. |
| `--override-output-folder-path <dir>` | Write the graph file into this folder instead of a timestamped folder under `output/`. Gives programmatic callers a deterministic path. |

Direction rules:

- Pass **neither** `--upstream` nor `--downstream` → you get **both** directions
  (the full lineage around the node).
- Pass **one** → only that side.
- `--upstream` / `--downstream` require a focus: one of `--structure-name`,
  `--flow-name`, or `--namespace`.

Output: the command **writes a file** to a timestamped folder under `output/`
(`output/<timestamp>/flow_dependency_graph.json` or `.mmd`) and logs the exact
path. There is no stdout dump — open the written file to read the graph.
Pass `--override-output-folder-path <dir>` to choose the folder yourself
(the file name stays fixed) — useful when a script consumes the graph and
must not parse the logged path or glob for the newest folder.

---

## Reading the JSON output

```json
{
  "nodes": [
    { "id": "structure.refined.refined_orders", "type": "structure" },
    { "id": "flow.refined.refined_orders",
      "type": "flow", "namespace": "refined", "name": "refined_orders",
      "target_structure": "refined.refined_orders" },
    { "id": "structure.raw.raw_orders", "type": "structure" }
  ],
  "edges": [
    { "source": "structure.raw.raw_orders", "target": "flow.refined.refined_orders" },
    { "source": "flow.refined.refined_orders", "target": "structure.refined.refined_orders" }
  ]
}
```

- `nodes[].type` is `structure` or `flow`; the `flow.`/`structure.` prefix on
  `id` says the same thing.
- Each `edge` is `source → target` in data-flow direction.
- **To read structure-to-structure links, collapse the flow nodes.** For a focus
  structure `S`:
  - **Immediate upstream structures** = the predecessor structures of the
    flow(s) whose `target_structure` is `S` (i.e. `structure → flow(→S)`).
  - **Immediate downstream structures** = the `target_structure` of the flow(s)
    that read `S` (i.e. `(S→)flow → structure`).
  - Repeat across hops for full transitive lineage.

For a quick visual instead of parsing JSON, re-run with `--format mermaid` and
paste the `.mmd` into any Mermaid viewer.

---

## Process

1. **Pick the focus** — a structure (`--structure-name`) or a flow
   (`--flow-name`), plus its `--namespace`.
2. **Choose the direction**:
   - What feeds it → `--upstream`.
   - What it feeds / what would break downstream → `--downstream`.
   - The full neighborhood → omit both flags.
3. **Run it**, e.g.:
   ```
   # upstream sources of a refined table
   nld flow deps --structure-name refined_orders --namespace refined --upstream

   # downstream consumers of a raw table
   nld flow deps --structure-name raw_orders --namespace raw --downstream

   # full lineage around a flow
   nld flow deps --flow-name refined_orders --namespace refined

   # the whole namespace graph as a diagram
   nld flow deps --namespace refined --format mermaid
   ```
4. **Open the written file** at the logged `output/<timestamp>/…` path.
5. **Read the links** from `edges`, collapsing flow nodes to get
   structure-to-structure lineage (see above). For a picture, use
   `--format mermaid`.

---

## Cross-references

- Architectural reference for the graph and flow lifecycle: `guide-flows` skill
  (section "Flow Dependency Graph").
- Explicit, declared field-level links between two structures (not derived from
  flows): `how-to-model-structure-layers` and `guide-structure-model` skills.
- The structures that appear as nodes: `guide-structures` skill.
