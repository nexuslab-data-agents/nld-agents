# Business Layer ("Gold")

## Overview

The **business layer** — also referred to as the **Gold** layer or **Business
Data Store** — contains data that has been cleaned, conformed and joined
according to business rules. It consumes refined data produced by acquisition
products and exposes business-meaningful entities (reference data, facts) ready
to be aggregated by the consumer layer.

```
Refined (acquisition)  →  Business (Gold)  →  Consumer (Platinum)
```

Business products in this repository live under `<domain>/business/<product>/`
and follow the layout described in
[Data Product Structures §3](../general-design/product-structures.md#3-data-business-product-structure).

## Position in the Pipeline

- **Inputs**: refined entities exposed by upstream acquisition products
  (referenced via the `predecessors` section of each business flow YAML).
- **Outputs**: business tables (reference / fact) and their display views,
  consumed by Platinum-layer datamarts and dimensions.
- **Implementation**: pure SQL flows (`assets/flows/<sub_product>/*.{sql,yaml}`).
  No Python code runs in the business layer.

## Table Naming

The standard business-layer table naming rule — one prefix per table kind:

| Prefix        | Kind                   | Description                                                                                                          |
|---------------|------------------------|------------------------------------------------------------------------------------------------------------------------|
| `R_`          | Referential table      | State information: business entities and classification codes — *what things are*. One row per current entity state, updated in place. |
| `R_*_HISTORY` | Historical referential | Every past state of a referential entity (SCD type 2), validity-bounded; additive to the `R_` table.                    |
| `F_`          | Fact table             | Transactional data: purchase orders, sales orders, account lines, events, observations — *what happened, when, how much*. |
| `M_`          | Mart table             | Aggregated data derived from referential and fact tables, losing the source granularity (pre-aggregated business datasets). |
| `W_`          | Working table          | Temporary table used during processing. **Optional**: transient, never exposed or consumed downstream.                  |
| `P_`          | Parameter table        | Manually-maintained data: curated master data, seeds carrying a fixed referential, or calculation parametrization.      |
| `T_`          | Technical table        | Logging / monitoring tables.                                                                                             |
| `V_<TABLE>`   | Display view           | Exposure surface of a table to the next layer (`V_R_*`, `V_F_*`, `V_M_*`).                                               |

Full naming pattern: `{PREFIX}_{DOMAIN}_{DESCRIPTION}`. `{DOMAIN}` is a short
business sub-domain identifier (e.g. `FR_LEGAL_UNIT`, `HR`, `GEO`,
`VIDEO_GAME`). `{DESCRIPTION}` is a concise, business-meaningful name. The
**root entity of a domain may omit `{DESCRIPTION}`** (`r_video_game`);
satellite tables extend the root name (`r_video_game_genre`,
`r_video_game_platform`). Formulas are written in uppercase for readability;
physical PostgreSQL objects are lowercase (`r_fr_legal_unit_activity`).

Display views, working tables, parameter tables and technical tables are also
listed in
[Structure Convention — Auxiliary Structures](../structure/structure-convention.md#auxiliary-structures-business--consumer),
shared with the consumer layer.

## Table Kinds: How to Choose

Choosing between `R_`, `F_` and `M_` is primarily a question of **what the
rows describe**, not of size or refresh cadence.

### Referential Table (`R_`)

A referential (reference) table answers the question **"what is this
thing?"**. Each row
describes a business **entity or concept** that exists independently of any
event, and that other tables point at to give themselves meaning.

**Use a reference table when**:

- Rows represent stable business **entities** (a company, a job offer, a
  postal code, a person) or **classification codes** (an activity code, a
  legal category, a staff-range bucket).
- The table is the **authoritative source of truth** for that entity within
  the domain — other tables join to it rather than redefining its attributes.
- The natural key is a **business identifier** (SIREN, ISO code, slug, …),
  not a timestamp or an event id.
- A row's attributes describe **what the entity is**, not **what happened**:
  name, label, description, category, geography, validity dates, status.
- Updates happen **in place** (slowly-changing): the row already exists, you
  refresh its attributes when the source changes.
- The table is typically **joined** by downstream consumers (datamarts and
  dimensions) to enrich facts, rather than aggregated.

**Typical signals you are looking at a reference table**:

- The row count is roughly bounded by the cardinality of a real-world
  population (≈ N companies, ≈ M postal codes), not by the passage of time.
- Removing the time dimension does not make the table meaningless.
- A consumer asking *"give me the list of all X"* expects this table.

**Examples**:

- `R_FR_LEGAL_UNIT` — the canonical list of French legal units, one row per
  SIREN, attributes describe the company itself.
- `R_FR_LEGAL_UNIT_ACTIVITY` — reference list of legal-unit activity codes
  (NAF/APE), one row per code with its label.
- `R_FR_LEGAL_UNIT_STAFF_RANGE` — reference list of staff-range buckets.
- `R_GEO_FR_POSTAL_CODE` — reference list of French postal codes with their
  city / department.

#### Historical Reference Tables (`_history` suffix)

A reference table holds the **current** state of each entity (one row per
business key). When the successive states of an entity over time also need to
be persisted, a companion **historical reference table** is added, suffixed by
`_history`.

**Naming**: `R_{DOMAIN}_{DESCRIPTION}_HISTORY`

**Use a historical reference table when**:

- Consumers need to answer point-in-time questions such as
  *"what was the activity code of this legal unit on 2024-06-30?"*.
- The entity's descriptive attributes evolve over time and the platform must
  preserve every past state, not only the latest one.
- Slowly-changing-dimension semantics (SCD type 2) are required: each row
  represents one **state** of the entity, bounded by validity dates.

**Conventions**:

- Each row represents **one state** of the entity. The natural key is the
  business identifier **plus** a validity discriminator (typically a
  `dt_valid_from` / `dt_valid_to` pair, or a snapshot date).
- The current state of every entity must remain available in the regular
  `R_…` reference table; the `_history` table is additive, not a replacement.
- The historical table references the same entity identifier as its
  non-historical counterpart so the two can be joined.
- Display views follow the same rule as other tables: a view exposing the
  historical table prefixes the underlying name with `V_` (e.g.
  `V_R_FR_LEGAL_UNIT_HISTORY`).

**Examples**:

- `R_FR_LEGAL_UNIT` — current state of each French legal unit.
- `R_FR_LEGAL_UNIT_HISTORY` — every past state of each legal unit, with
  validity dates, allowing point-in-time reconstruction.
- `R_FR_LEGAL_UNIT_ACTIVITY_HISTORY` — every past state of the activity-code
  reference list (e.g. label changes, retired codes).

### Fact Table (`F_`)

A fact table answers the question **"what happened, when, and how much?"**.
Each row records a **business event, observation or measurement** tied to a
specific point in time, and references reference tables to give that event
context.

**Use a fact table when**:

- Rows represent **events**, **transactions**, **observations** or
  **state snapshots** captured at a given moment.
- The natural key contains (or is derived from) a **timestamp**, an
  **event id**, or a `(reference_id, date)` pair.
- The row's main payload is **measurements**: counts, amounts, durations,
  flags, statuses-at-a-point-in-time.
- The table grows **monotonically** as time passes: yesterday's rows do not
  change, today's rows are appended.
- Foreign keys point to **reference tables** that describe the actors of the
  event (which company, which job offer, which activity code).
- Downstream consumers typically **aggregate** this table (sum, count,
  average over a time window) rather than just join to it.

**Typical signals you are looking at a fact table**:

- The row count grows roughly linearly with time.
- The same business entity can appear many times, once per event.
- A consumer asking *"how many X happened between date A and date B"*
  expects this table.

**Examples** (illustrative — actual names depend on the product):

- `F_HR_JOB_APPLICATION` — one row per job application event, with applicant
  id, job offer id, application timestamp.
- `F_HR_JOB_OFFER_PUBLICATION` — one row each time a job offer is published
  or republished, with the source, the publication timestamp.
- `F_FR_LEGAL_UNIT_STATUS_CHANGE` — one row per change of administrative
  status of a legal unit, with the new status and the change date.

### Mart Table (`M_`)

A mart table answers the question **"what does the data say once aggregated?"**.
It is derived from referential and fact tables by aggregation and **loses the
source granularity**: a row no longer maps 1:1 to a source entity or event but
to a group (a time bucket, a category, a geography, …).

**Use a mart table when**:

- The table is built by **aggregating** referentials and/or facts (sums,
  counts, averages, ratios, rankings) and the source-level rows are not
  reconstructible from it.
- The result is a **business-ready dataset** shared inside the domain — the
  business layer's own aggregates, as opposed to Platinum `DTM_` datamarts
  which are purpose-built for one specific consumer or use case.

**Examples** (illustrative):

- `M_VIDEO_GAME_GENRE_YEAR` — games released per canonical genre per year.
- `M_FR_LEGAL_UNIT_ACTIVITY_STAFF` — legal-unit counts aggregated by activity
  code and staff range.

### Working Table (`W_`)

A working table is a **temporary table used during processing** — an
intermediate materialisation a flow needs between two steps. Working tables
are **not mandatory**: most flows go straight from sources to target.

**Conventions**:

- Transient: may be truncated or rebuilt at every run; its content carries no
  retention guarantee.
- Never exposed: no display view, no consumer grant, no downstream flow may
  read it.
- Excluded from structure audits and business documentation duties.

### Parameter Table (`P_`)

A parameter table holds **manually-maintained data** owned by Data Engineers,
in one of three shapes:

- **Curated master data** — e.g. a manually-maintained unit-of-measure list.
- **Seeds carrying a fixed referential** — small, versioned-in-git reference
  data that no source system provides (e.g. a canonical genre mapping seed).
- **Calculation parametrization** — thresholds, rates and mapping values that
  drive flow logic (e.g. `P_CUS_TENANT_DATA_RANGE`).

### Borderline Cases

- **Daily snapshots of an entity** (e.g. "company state on day D") are
  **facts**, not references: each row is tied to a date, the table grows over
  time, and consumers will typically filter by date or aggregate.
- **A list that happens to change often** is still a reference if each row
  describes an entity rather than an event (e.g. a frequently-updated catalog
  of products).
- **Mappings / cross-references** between two reference entities (e.g.
  company ↔ activity code) are reference tables: they describe a relationship
  that exists, not an event that occurred.
- If a table mixes the two — descriptive attributes **and** event measures —
  split it: keep the descriptive part as `R_…` and emit the events as
  `F_…` rows referencing it.

### Examples in This Repository

- `R_FR_LEGAL_UNIT_ACTIVITY` — referential list of legal-unit activity codes.
- `R_FR_LEGAL_UNIT_STAFF_RANGE` — referential list of staff-range buckets.
- `R_FR_LEGAL_UNIT_CATEGORY` — referential list of legal-unit categories.
- `R_VIDEO_GAME` — unified video game referential (domain root entity, no
  description part); satellites `R_VIDEO_GAME_GENRE`, `R_VIDEO_GAME_PLATFORM`.
- `F_FR_PROPERTY_VALUES` — property transaction facts (DVF).
- `V_R_FR_LEGAL_UNIT_ACTIVITY` — display view exposing the referential table.

## Display Views

Each business table (except working tables) is typically paired with a
display view that exposes it to the next layer. The view prefixes the
underlying table name with `V_` (e.g. `V_R_FR_LEGAL_UNIT_ACTIVITY` for
`R_FR_LEGAL_UNIT_ACTIVITY`). When the view filters or derives from the data, a
more specific name may be defined (e.g. the audit view
`V_R_VIDEO_GAME_UNMATCHED_HLTB`).

## Templates

Business tables use the `nld_standard_tracking` template (see
[Structure Convention — Templates by Layer](../structure/structure-convention.md#templates-by-layer)).

## Files Required

For each business entity:

| File          | Path                                                          | Purpose              |
|---------------|---------------------------------------------------------------|----------------------|
| Flow YAML     | `assets/flows/<sub_product>/r_<entity>.yaml`                  | Flow configuration   |
| SQL           | `assets/flows/<sub_product>/r_<entity>.sql`                   | Transformation SQL   |
| Structure     | `assets/structure/<sub_product>/r_<entity>.yml`               | Table schema         |
| View flow YAML| `assets/flows/<sub_product>/v_r_<entity>.yaml` *(optional)*   | Display view config  |
| View SQL      | `assets/flows/<sub_product>/v_r_<entity>.sql` *(optional)*    | Display view SQL     |
