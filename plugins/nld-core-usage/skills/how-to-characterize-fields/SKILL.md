---
name: how-to-characterize-fields
description: >
  Propose field characterisations for one structure. For every field that has no
  characterisation yet, pick a pertinent one from the common characterisations set
  by combining the characterisation rules, the structure's current state (keys,
  data types, characterisations already present) and the structure's data profile
  (its StructureAudit). Where the evidence contradicts an existing characterisation,
  challenge it. Fields supplied by a field template are considered already valid and
  are skipped. Produce a full per-field report and confirm with the user before
  updating the structure. Use when a structure has uncharacterised (or questionable)
  fields and you want a reasoned, checkable characterisation proposal.
user-invocable: true
---

# How to Characterize the Fields of a Structure

**Classification**: Atomic Skill | Structure Analysis

---

## Definition

- **What**: For a **single** structure, examine every field that carries **no
  characterisation yet** and propose a pertinent characterisation drawn from the
  **common characterisations** set. Where the data profile **contradicts** a
  characterisation a field already carries, challenge it rather than leave it.
  Then emit a full report and ask the user to confirm before writing the
  characterisations back to the structure YAML.
- **When**: A structure exists, but some of its fields have no semantic role
  attached. You want each such field characterised so the framework (SQL
  rendering, upsert, lineage, reporting) can act on it — and you want the
  proposal reasoned from evidence, not guessed.
- **Why**: A characterisation unlocks behavior across the stack without ad-hoc
  flags (see `field-characterisation.md`, §1). Proposing them from the
  characterisation rules **plus** the measured data profile (the audit) keeps the
  choice grounded: a `cd_`-prefixed, fully-distinct, 100%-covered column reads as
  a reference; a low-cardinality coded column reads differently from a free-text
  one.

For the entity internals and the catalogue of characterisation names, read the
`guide-structures` skill and `field-characterisation.md` (§3 default/in-code
names, §4 **common characterisations**). For naming-prefix conventions, see the
`nld-data-conventions` `guide-field-conventions` skill.

---

## Prerequisites

- Run from a directory with `nld_project.yml`.
- The structure to characterise already exists under the entity path
  (`<entity_path>/structure/<ns>/...`).
- **Strongly recommended**: a `StructureAudit` for the same structure exists
  (`assets/audits/structure/<ns>/<structure>.yml`). The audit is the data
  profile that turns guesses into evidence-based proposals. An **agent-authored
  analysis markdown** — a separate report someone produced by analysing the audit,
  carrying additional information beyond the raw measured facts (field-selection
  notes, anomalies, interpretation) — is also sometimes available next to it; when
  present, read it for that extra context. (This is **not** the mechanical
  `nld structure audit render` output, which only reformats the audit YAML.) If no
  audit exists, profile the structure first with the `how-to-profile-a-structure`
  skill, or proceed on the rules + current state alone and **say so** in the report.

---

## Inputs the proposal is built from

The characterisation for a field is decided by combining **three** sources. Never
use only one.

| # | Source | How to obtain it | What it tells you |
|---|--------|------------------|-------------------|
| 1 | **The rule** | `field-characterisation.md` §3–§4; `guide-field-conventions` prefixes | Which characterisation a field's name/type/role maps to (the candidate set). |
| 2 | **Current structure state** | `nld structure info --name <s> --namespace <ns>` | Existing characterisations, keys, data types, field order — what is already covered and must not be duplicated. |
| 3 | **Data profile (audit)** | `nld structure audit info --name <audit> --namespace <ns>`, plus any agent-authored analysis markdown next to the audit | Coverage %, distinct count, min/max, value distributions — the evidence that confirms or rejects a candidate; the analysis markdown adds interpretation beyond the raw facts. |

---

## The decision framework

For each field, walk these in order:

1. **Skip fields supplied by a field template.** Fields contributed by a field
   template (the technical tracking columns — `ts_inserted_at`, `ts_updated_at`,
   `fl_deleted`, `ts_src_*`, the DLT/ingestion fields, …) are considered to carry
   **valid** characterisations by definition. Do **not** check, re-propose, or
   challenge them. Only the structure's **own** fields are in scope. (Identify
   template fields from the structure templates it includes — see
   `guide-field-conventions` "Distribution by Structure Template".)

2. **Skip keys.** A primary / functional key field needs no functional
   characterisation; leave it untouched.

3. **Decide per own-field by state:**
   - **No characterisation yet** → propose one (steps below).
   - **Already characterised** → accept it silently **unless** the data profile
     contradicts it (see step 6, *Challenge*). Do not restate confirmations as
     proposals.

4. **Read the rule from name + type.** Use the naming prefix and data type to
   form the candidate characterisation(s):
   - `cd_` / `id_` code or identifier → a reference (`tec_external_reference` /
     `func_external_reference`) or `reporting_technical_info` if it is just a
     stable id exposed for reporting.
   - `ds_` description / free text → `free_text`.
   - amount / `nb_` / numeric measure → `amount_in_uom` or `quantity`
     (with a paired `uom`), or `amount_in_cur` (with a paired `currency`).
   - currency / unit code column → `currency` / `uom`.
   - length-of-time measure (months, years, days) → `duration` with a
     `unit_of_measure` attribute (and `aggregation_applied_rule` when the value is
     pre-aggregated, e.g. a min / max / average duration).
   - ratio / proportion → `percentage` with a `base` attribute (`100` for a
     0–100 scale, `1` for a 0–1 fraction); the audit `min`/`max` bounds confirm
     the base.
   - value drawn from a controlled list / enumeration / nomenclature →
     `referential_value` (with an optional `referential` attribute naming the list,
     and `multi_value: true` when several codes are concatenated).
   - language code → `language` (`standard: iso_639`); country code → `country`
     (`standard: iso_3166`).
   - `dt_` / `ts_` business time not already a `rec_*` technical timestamp →
     `functional_timestamp`, `snapshot_date`, `validity_start/end_*`.
   - string/int encoded date or time (`YYYYMMDD`, `HHMMSS`, …) → `functional_date`
     / `functional_time` with a `format` attribute (e.g. `yyyymmdd`, `ddmmyyyy`,
     `hhmmss`, `hhmm`).
   - integer year on its own (e.g. `yr_`, a creation year) → `functional_year`.
   - period / granularity of time (e.g. `monthly`, `yearly`) → `time_period`.
   - geographic coordinate column → `latitude` / `longitude`; postal / ZIP code →
     `zip_code` (GEO category).
   - web URL → `url`; URL slug / opaque web identifier → `slug` (WEB category).
   - stable identifier issued by the source system → `source_identifier`.
   - parent/child link column → `hierarchy_parent_info` /
     `hierarchy_child_info` (HIERARCHY category).
   - strictly-positive ranking integer → `priority`.

5. **Confirm or reject with the data profile.** Use the audit to choose between
   candidates and to set confidence:
   - **Reference vs. not** — `distinct == row_count` and high coverage support a
     reference / identifier; many repeats argue against it.
   - **Code vs. free text** — low distinct count (a small enumerated set, often
     with a `distribution` block) supports a coded role; high distinct + long
     values support `free_text`.
   - **Format characterisations** — `min`/`max` and sample values confirm an
     encoded date/time (`functional_date` / `functional_time` with the matching
     `format` attribute, e.g. `yyyymmdd`, `hhmmss`) or `epoch_ms`.
   - **Amount vs. quantity vs. currency** — numeric range plus a sibling
     unit/currency column decides `amount_in_uom` vs `amount_in_cur` vs
     `quantity`.
   - **Coverage caveats** — note low coverage; a sparsely populated column gets a
     lower-confidence proposal.

6. **Wire amount ↔ currency / uom links.** A `currency` (or `uom`) field carries
   a `linked_fields` attribute listing **every** amount it qualifies; each
   `amount_in_cur` (or `amount_in_uom`) carries a `linked_field` attribute naming
   its **single** currency / unit field. Propose both ends together and resolve
   the link by sibling-column name; flag any amount with no resolvable
   currency / unit in the report. See `field-characterisation.md` §4 MEASURE /
   CURRENCY for the exact YAML.

7. **Prefer the common set, then the in-code set.** Draw names from §4 **common
   characterisations** first; fall back to §3 in-code names where they fit
   (`mandatory`, `unique`). If nothing fits, propose **no characterisation** and
   say why — an empty proposal is a valid, honest outcome.

8. **Challenge a characterisation the evidence contradicts.** For an own-field
   that is **already** characterised, if the data profile disagrees with it
   (e.g. a field tagged `free_text` whose audit shows only 8 distinct values; an
   `amount_in_cur` with no resolvable `currency`; a `unique`/reference tag on a
   column with heavy repeats), raise a **challenge** row: state the current
   characterisation, the contradicting evidence, and the better candidate. Never
   silently overwrite — surface it for the user to decide.

9. **Respect single-per-structure rules.** Characterisations marked *single per
   structure* (e.g. each `rec_*` timestamp, `snapshot_date`) may be proposed for
   at most one field; if two fields compete, pick the better-supported one and
   note the runner-up.

---

## The report

Produce one report for the whole structure. It is the deliverable the user
confirms against.

```
# Field characterisation proposal — <namespace>.<structure>

Audit: <audit name> (audited_at <ts>, row_count <n>)   |   or: NO AUDIT — rules + current state only

| Field | Data type | Current | Action | Proposed | Category | Confidence | Evidence |
|-------|-----------|---------|--------|----------|----------|-----------|----------|
| ts_inserted_at   | TIMESTAMP_TZ      | rec_insert_tst | skip (template) | — | — | — | template field, valid by definition |
| cd_job_reference | CHARACTER VARYING | primary_key | skip (key) | — | — | — | — |
| contract_type    | CHARACTER VARYING | —          | propose | referential_value (referential: contract_type) | CODE | high | distinct=8, has distribution → value from a controlled list, not free text |
| ds_salary        | NUMERIC           | —          | propose | amount_in_cur | CURRENCY | medium | numeric, 17% coverage; no resolvable currency sibling → flag |
| dt_published     | CHARACTER VARYING | —          | propose | functional_date (format: yyyymmdd) | DATETIME | high | values like 20251019, min/max are 8-digit ints |
| ds_comment       | CHARACTER VARYING | free_text  | challenge | (keep / coded?) | DATA_ENTRY | medium | tagged free_text but distinct=5 → evidence contradicts |

## Summary
- Own fields: P; template/key fields skipped: S.
- Proposals: M; challenges: C; left uncharacterised: K (reason).
- Amount ↔ currency/uom links to confirm: <currency.linked_fields ↔ amount.linked_field>.
- Single-per-structure conflicts: <field A vs field B for snapshot_date>.
- Caveats: <no audit / low coverage / drifted column>.
```

Rules for the report:
- **One row per own field**, plus skipped template/key rows marked as such, so
  coverage is auditable. Template fields are listed only to show they were
  deliberately skipped — never proposed or challenged.
- `Action` is one of `skip (template)`, `skip (key)`, `propose`, `challenge`.
- Every proposal/challenge cites **evidence** from the audit (or states none was
  available).
- Confidence is `high` / `medium` / `low`; never present a guess as certain.
- List unresolved **amount↔currency/uom links** and **single-per-structure
  conflicts** explicitly.

---

## Process

1. **Confirm the structure** exists and read its fields:
   `nld structure info --name <s> --namespace <ns>`. Note keys, data types, and
   every field that already carries a characterisation.
2. **Separate own fields from template fields.** Identify which fields come from
   an included field template (technical tracking, DLT, ingestion) and exclude
   them from analysis — they are valid by definition. Only the structure's own
   fields are in scope.
3. **Load the data profile**:
   `nld structure audit info --name <audit> --namespace <ns>`, and read any
   agent-authored analysis markdown next to the audit for extra context. If no
   audit exists, offer to run `how-to-profile-a-structure` first, or continue
   without it and flag every proposal as evidence-light.
4. **For each own field**, apply the decision framework (rule → data profile →
   link wiring → common set → challenge → single-per-structure check), producing
   a `propose`, `challenge`, or no-op outcome.
5. **Assemble the report** in the format above — one row per own field (plus
   skipped template/key rows), with evidence and confidence on every
   proposal/challenge.
6. **Confirm with the user.** Present the report and **ask explicitly** whether to
   apply the proposed characterisations and act on the challenges. Do not edit the
   YAML before the user agrees. Let them accept all, a subset, or none.
7. **Apply the confirmed subset** to the structure YAML — add/adjust the
   `characterisations:` entries on each field (string shorthand or full object;
   see `structure-design.md` "Field Characterisations"). Wire paired
   characterisations together: the `currency`/`uom` field's `linked_fields` and
   each amount's `linked_field`.
8. **Verify** the edited structure still loads:
   `nld structure info --name <s> --namespace <ns>`. If the structure layers map
   onto another structure, re-validate with `nld structure model validate`.

---

## Cross-references

- Characterisation catalogue & rules: `field-characterisation.md`
  (§3 in-code, §4 **common characterisations**) via the `guide-structures` skill.
- The data profile this skill consumes: `how-to-profile-a-structure` and
  `guide-structure-audit` skills.
- Writing characterisations in YAML: `structure-design.md`
  "Field Characterisations".
- Naming prefixes (`cd_`, `ds_`, `dt_`, `ts_`, …): `nld-data-conventions`
  `guide-field-conventions` skill.
