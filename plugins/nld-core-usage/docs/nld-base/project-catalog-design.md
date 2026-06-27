# NLD Project Catalog — Multi-Project Model

This document describes `NldProjectCatalog`, the nld-core model that sits **above**
individual projects (`project-design.md`): a platform-level catalogue recording
every nld project, where it lives on disk, and the dependency links between them.

It is the cross-project layer that gives meaning to cross-product references —
for example a scheduling `FlowPrecondition` with `external: true` names an upstream
by its `nld_project`, which must be a catalogued project (see `guide-scheduling`).

---

## 1. What it models

A single platform is usually several nld projects (e.g. one per data product):
an acquisition project feeds a business project, which feeds a consumer project.
Each project on its own only sees its own registry; it cannot resolve another
project's entities. `NldProjectCatalog` is the place those cross-project
dependencies are declared, so a consumer (a deploy orchestrator, a Kestra
scheduling generator, …) can wire them up.

**File:** `core/nld/project/project_catalog.py`

## 2. Models

### `NldProjectCatalogEntry(NldNamedBaseModel)`

A single catalogued project.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Project name (inherited; folded from the mapping key — see below). |
| `path` | `str` | Project root **relative to the catalog file** (the folder holding that project's `nld_project.yml`). Required. |
| `predecessors` | `list[str]` | Names of the other catalogued projects this one depends on. |

### `NldProjectCatalog(NldBaseModel)`

| Field | Type | Purpose |
|-------|------|---------|
| `projects_base_path` | `str \| None` | Base dir, relative to the catalog file, that each entry's `path` resolves against. When unset, paths resolve relative to the catalog file's own directory. |
| `projects` | `dict[str, NldProjectCatalogEntry]` | Catalogued projects, **keyed by project name**. |

**Loading conventions** (mirrors `Project`):

- `NLD_PROJECT_CATALOG_FILENAME = "nld_project_catalog.yml"`.
- `NldProjectCatalog.from_yaml(root_path)` joins that fixed filename onto the
  folder and loads it.

**Validation & normalisation:**

- A `model_validator(mode="before")` (`_inject_project_names`) folds each
  `projects` mapping key into the entry's `name` field, so the YAML keys the
  project by name and the entry never repeats it.
- A `field_validator` (`_validate_predecessors_exist`) rejects any `predecessor`
  that is not itself a catalogued project — the catalogue is self-contained.

## 3. YAML shape

```yaml
# nld_project_catalog.yml
projects_base_path: ops/nld/data_products   # optional; default = catalog file's dir
projects:
  clh_acquisition_opendata:
    path: clh/acquisition/opendata           # folder holding that project's nld_project.yml
    predecessors: []
  clh_acquisition_web_hr:
    path: clh/acquisition/web_hr
    predecessors: []
  clh_business_dwh:
    path: clh/business/dwh
    predecessors:
      - clh_acquisition_opendata             # each must itself be a catalogued project
      - clh_acquisition_web_hr
```

The `predecessors` links form the **cross-project dependency DAG** (a business
project runs after the acquisition projects feeding it).

## 4. Python API

```python
catalog = NldProjectCatalog.from_yaml("ops/scheduling")

catalog.entry_names                 # ['clh_acquisition_opendata', ..., 'clh_business_dwh']
catalog.get_entry("clh_business_dwh")          # NldProjectCatalogEntry | None
catalog.get_entry("clh_business_dwh").path     # 'clh/business/dwh'
catalog.predecessors_of("clh_business_dwh")    # ['clh_acquisition_opendata', 'clh_acquisition_web_hr']
```

Catalog-driven project loaders let nld-core load each catalogued `Project` from
its resolved `path` (a generic nld-core concern, not platform-specific).

## 5. Relationship to other concepts

- **Project** (`project-design.md`) — the catalogue points at one `nld_project.yml`
  per entry via `path`; each project keeps its own registry.
- **Scheduling** (`guide-scheduling`) — a per-flow `FlowPrecondition` with
  `external: true` + `nld_project: <name>` expresses the same dependency at the
  flow grain that the catalogue expresses at the project grain.
- **Platform registry** — on a full data platform, the platform's own registry
  (`ops/nld/config/org/nld_<platform>.yaml`) is the operational analogue of this
  generic core catalogue; the platform docs cover how the two relate.
