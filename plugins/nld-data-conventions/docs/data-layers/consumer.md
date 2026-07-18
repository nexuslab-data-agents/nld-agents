# Consumer Layer ("Platinum")

## Overview

The **consumer layer** — also referred to as the **Platinum** layer or
**Data Product** layer — is the topmost layer of the lakehouse. It serves data
to end consumers (BI tools, APIs, ML models, exports) by exposing
dimension-style and datamart-style tables built on top of the business layer.

```
Refined (acquisition)  →  Business (Gold)  →  Consumer (Platinum)
```

Consumer products in this repository live under `<domain>/consumer/<product>/`
and follow the layout described in
[Data Product Structures §4](../general-design/product-structures.md#4-data-consumer-product-structure).

## Position in the Pipeline

- **Inputs**: business tables exposed by upstream business products
  (referenced via the `predecessors` section of each consumer flow YAML).
- **Outputs**: dimension and datamart tables, plus their display views, ready
  for direct consumption by downstream tools.
- **Implementation**: pure SQL flows (`assets/flows/<sub_product>/*.{sql,yaml}`).
  No Python code runs in the consumer layer.

## Table Naming

The consumer layer distinguishes two main kinds of tables:

| Kind             | Description                                                                                  | Naming convention              |
|------------------|----------------------------------------------------------------------------------------------|--------------------------------|
| Dimension table  | Descriptive context entity used to slice/filter facts in BI tools.                          | `DIM_{DOMAIN}_{DESCRIPTION}`   |
| Datamart table   | Pre-aggregated, query-ready dataset purpose-built for a specific consumer or use case.       | `DTM_{DOMAIN}_{DESCRIPTION}`   |

`{DOMAIN}` is a short business sub-domain identifier (e.g. `FR_LEGAL_UNIT`,
`HR`). `{DESCRIPTION}` is a concise, business-meaningful name.

Auxiliary tables (display views, temporary work tables, parameter tables,
technical tables) follow the rules listed in
[Structure Convention — Auxiliary Structures](../structure/structure-convention.md#auxiliary-structures-business--consumer).

### Examples

- `DIM_FR_LEGAL_UNIT_ACTIVITY` — dimension table of legal-unit activities.
- `DIM_FR_LEGAL_UNIT_STAFF_RANGE` — staff-range dimension.
- `DTM_HR_JOB_OFFER_DAILY` — daily job-offer datamart (illustrative).
- `V_DIM_FR_LEGAL_UNIT_ACTIVITY` — display view exposing the dimension.

## Display Views

Consumer products typically expose their tables through display views. The
view prefixes the underlying table name with `V_` (e.g.
`V_DIM_FR_LEGAL_UNIT_ACTIVITY` for `DIM_FR_LEGAL_UNIT_ACTIVITY`); when it
filters or derives from the data, a more specific name may be defined.

## Templates

Consumer views use the `nld_standard_tracking` template (see
[Structure Convention — Templates by Layer](../structure/structure-convention.md#templates-by-layer)).

## Files Required

For each consumer entity:

| File         | Path                                                       | Purpose             |
|--------------|------------------------------------------------------------|---------------------|
| Flow YAML    | `assets/flows/<sub_product>/v_<entity>.yaml`               | Flow configuration  |
| SQL          | `assets/flows/<sub_product>/v_<entity>.sql`                | View / table SQL    |
| Structure    | `assets/structure/<sub_product>/v_<entity>.yml`            | Table / view schema |
