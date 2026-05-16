---
name: guide-data-layers
description: >
  NLD data layer architecture — raw (JSON staging, flattening, deduplication),
  refinement (typed columns, semantic naming), business/Gold (joins, business
  rules), and consumer/Platinum (datamarts, BI-ready tables). Covers layer
  responsibilities, input/output conventions, and flow patterns.
user-invocable: false
---

# Guide: Data Layers

Reference for the NLD lakehouse data layer architecture — the four-layer
pipeline from raw ingestion through to consumer-ready data products.

## When to Use

Activate this guide when the agent is:
- Creating or modifying flows that move data between layers
- Designing a new data product (acquisition, business, or consumer)
- Working with raw JSON staging (`raw_json_*`) or flattening flows
- Creating refined structures from raw data
- Building business or consumer layer tables/views
- Understanding the data pipeline topology

## Documentation

| Document | Path |
|----------|------|
| Raw layer | `${CLAUDE_PLUGIN_ROOT}/docs/data-layers/raw.md` |
| Refinement layer | `${CLAUDE_PLUGIN_ROOT}/docs/data-layers/refinement.md` |
| Business layer (Gold) | `${CLAUDE_PLUGIN_ROOT}/docs/data-layers/business.md` |
| Consumer layer (Platinum) | `${CLAUDE_PLUGIN_ROOT}/docs/data-layers/consumer.md` |

### Layer Overview

```
S3 Landing Zone
  ↓ ingestion (DLT)
raw_json_*          (jsonb staging)
  ↓ flatten (SQL flow)
raw_*               (flat typed columns)
  ↓ v_raw_*_latest  (deduplicated view)
refined_*           (clean, semantic naming)
  ↓
business_*          (Gold — joins, business rules)
  ↓
consumer_*          (Platinum — datamarts, BI-ready)
```

### Key Topics per Layer

**Raw** — JSON staging via DLT, flattening SQL flows, `v_raw_*_latest`
deduplicated views, raw structure conventions.

**Refinement** — reads from `v_raw_*_latest`, semantic column naming with
standard prefixes, proper SQL typing, primary key matching functional key.

**Business (Gold)** — consumes refined data, applies business rules, joins
across data products, exposes business-meaningful entities.

**Consumer (Platinum)** — topmost layer, serves BI tools/APIs/ML, builds
dimension and datamart tables on top of business layer.

## Cross-References

- For field naming conventions and characterisations, see `guide-field-conventions`.
- For structure conventions and characterisations, see `guide-structure-conventions`.
