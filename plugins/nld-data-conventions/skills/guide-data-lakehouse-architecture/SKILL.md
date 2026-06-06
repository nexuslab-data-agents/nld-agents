---
name: guide-data-lakehouse-architecture
description: >
  NLD data lakehouse architecture guide — covers both single-product repositories
  (simple projects, tests) and full multi-domain data platform architectures.
  Defines data domains, product types, data layers, processes, repository structure,
  and data access rules.
user-invocable: false
---

# Guide: Data Lakehouse Architecture

Architectural reference for NLD data repositories. Use this guide to understand
how data repositories are organized, how data flows between layers, and how to
structure new data products.

## Table of Contents

1. [Two Repository Models](#two-repository-models)
   - [Model 1: Single Data Product](#model-1-single-data-product)
   - [Model 2: Full Data Platform (Lakehouse)](#model-2-full-data-platform-lakehouse)
2. [Core Concepts](#1-core-concepts)
   - [Data Domain](#11-data-domain)
   - [Data Product Type](#12-data-product-type)
   - [Data Product](#13-data-product)
   - [Scopes](#14-scopes)
3. [Data Layers and Processes](#2-data-layers-and-processes)
   - [Data Layers](#21-data-layers)
   - [Data Processes](#22-data-processes)
4. [Repository Structure (Full Platform)](#3-repository-structure-full-platform)
5. [Cross-References](#cross-references)

## When to Use

Activate this guide when the agent is:
- Setting up a new data repository or data product
- Understanding the data platform architecture and layer pipeline
- Deciding on repository structure (single-product vs full platform)
- Working with data domains, product types, or scopes
- Understanding data access rules between products
- Creating or modifying Kestra scheduling flows

## Two Repository Models

NLD data repositories come in two forms depending on the project's scope:

### Model 1: Single Data Product

Used for **tests, POCs, and simple projects** where only one data product is
needed. The repository contains a single product with a flat structure:

```
my-data-product/
├── .agents/
├── acquisition/          # or business/ or consumer/
│   ├── .dlt/
│   ├── .nld/
│   ├── assets/
│   └── refinement/
├── scheduling/
└── README.md
```

**When to use**:
- Proof of concept or experimental projects
- Single-source data ingestion pipelines
- Learning and testing environments
- Standalone data products not part of a larger platform

**Characteristics**:
- No domain folder — the product sits at the root
- Simplified scheduling structure
- No cross-product data access concerns
- Can be promoted to a full platform repository later

### Model 2: Full Data Platform (Lakehouse)

Used when **multiple data products across domains** are needed. This is the
standard architecture for production data platforms.

```
nld-lakehouse-<name>/
├── .agents/
├── ops/                        # Operations (Docker, K8s, DB, versioning)
├── <domain>/                   # Data domains (e.g., clh/, sales/)
│   ├── acquisition/            # Acquisition products
│   ├── business/               # Business products
│   ├── consumer/               # Consumer products
│   └── workspace/              # Workspace products (optional)
├── scheduling/                 # Kestra workflow definitions
│   ├── <domain>/
│   └── org/                    # Org-level base flows
└── README.md
```

**When to use**:
- Production data platforms with multiple data sources
- Multi-domain organizations
- When data products need to share and compose data

The remainder of this guide covers the full platform architecture in detail.

---

## 1. Core Concepts

### 1.1 Data Domain

A **data domain** represents a specific area of business or knowledge within the organization. It groups related data products and provides clear ownership boundaries.

**Examples**:
- `clh` - Core business domain (company, HR, real estate data)
- `sales` - Sales and market analysis domain

**Characteristics**:
- Clear business ownership
- Independent from other domains
- Contains multiple data products
- Self-contained data governance

### 1.2 Data Product Type

A **data product type** is an organizational layer between the data domain and individual data products. It categorizes data products based on their role in the data flow architecture.

**Standard Product Types**:
- `acquisition` - Data acquisition products (extract and refine data from external sources)
- `business` - Data business products (apply business logic and transformations)
- `consumer` - Data consumer products (serve data to specific consumers)

**Characteristics**:
- Defines the repository folder structure: `<domain>/<product_type>/<product>/`
- Determines applicable data layers and processes
- Establishes data access rules between products

**Non-Standard Product Types**:

While the standard architecture defines `acquisition`, `business`, and `consumer` product types with specific layers and processes, other product types can exist with completely different data flow patterns. These non-standard types have access to **all processes** from acquisition, business, and consumer, but only activate and implement the ones they need.

#### Project Product Type

**Purpose**: Independent, self-contained data products for specific initiatives, experiments, or temporary use cases.

**Characteristics**:
- Full autonomy - can implement any combination of acquisition, business, and consumer processes
- Project-specific lifecycle - may be temporary or experimental
- Complete process availability - has access to extraction, ingestion, refinement, business logic, and consumption processes
- Selective activation - only implements and activates the processes actually needed

**Structure**:
```
<domain>/projects/<project_name>/
├── acquisition/           # Optional - only if ingesting external data
│   ├── .dlt/
│   ├── .nld/
│   ├── assets/
│   └── refinement/
├── business/              # Optional - only if applying business logic
│   └── transformation/
├── consumer/              # Optional - only if serving data
│   └── api/ or reports/
└── README.md
```

**Process Activation Rules**:
- If no external data ingestion is needed, `acquisition/` folder can be empty or contain only placeholder structure
- If no business transformations are needed, `business/` folder remains empty
- If no specific consumption layer is needed, `consumer/` folder remains empty
- Empty folders indicate available but inactive processes

**Use Cases**:
- POC (Proof of Concept) projects
- Data science experiments
- One-time analytical projects
- Migration or integration projects
- Temporary data pipelines

#### Workspace Product Type

**Purpose**: Shared, collaborative environments for teams to develop, test, and iterate on data work.

**Characteristics**:
- Team collaboration - multiple users working in shared environment
- Development and experimentation - sandbox for testing before production
- Full process availability - has access to all acquisition, business, and consumer processes
- Flexible structure - adapts to team needs and workflows
- No strict data access rules - can access any data product

**Structure**:
```
<domain>/workspaces/<team_or_purpose>/
├── acquisition/           # Optional - for team-specific data sources
│   ├── .dlt/
│   ├── .nld/
│   ├── assets/
│   └── refinement/
├── business/              # Optional - for team transformations
│   └── transformation/
├── consumer/              # Optional - for team dashboards/reports
│   └── reports/ or notebooks/
├── shared/                # Optional - shared utilities
│   ├── notebooks/
│   └── scripts/
└── README.md
```

**Key Differences Between Project and Workspace**:

| Aspect | Project | Workspace |
|--------|---------|-----------|
| **Purpose** | Specific deliverable or initiative | Team collaboration environment |
| **Lifecycle** | Defined start/end, may be temporary | Ongoing, persistent |
| **Ownership** | Single owner or small team | Shared team ownership |
| **Scope** | Focused, specific objective | Broad, multiple activities |
| **Promotion Path** | May graduate to standard product type | Develops work for promotion elsewhere |

**Important Notes**:
- Both types have **no data access restrictions** - can access any other data product
- Both types have **all processes available** - but only implement what's needed
- **Empty folders are acceptable** - they indicate capabilities available but not activated
- Both types can **evolve** - successful projects/workspaces may be refactored into standard product types

**Data Access Rules**:

By default, any data product can access data from any other data product within the platform. However, specific restrictions apply to the standard product types to enforce architectural boundaries:

| Product Type | Allowed Data Access |
|--------------|---------------------|
| **Acquisition** | No access to other data products (source data only) |
| **Business** | Access to Acquisition and Business products only |
| **Consumer** | Access to all product types (Acquisition, Business, Consumer) |
| **Non-Standard** | No restrictions (can access any product type) |

These access rules ensure clean data lineage and prevent circular dependencies in the standard data flow architecture.

### 1.3 Data Product

A **data product** is a self-contained unit that provides curated, high-quality data assets to consumers. It encapsulates all components needed to extract, transform, and serve data.

A data product is always of a specific data product type. In the standard architecture, a data product is either a data acquisition product, data business product, or data consumer product.

**Characteristics**:
- Self-contained codebase
- Clear ownership and responsibility
- Documented data assets
- Versioned and deployable
- Contains the appropriate extraction, ingestion and/or refinement logic depending on its type

#### Data Acquisition Product

A **data acquisition product** is responsible for retrieving entities from external sources and making them available in the platform.

**Entity Retrieval Patterns**:
- **Direct Ingestion**: Entity data is retrieved directly from the source to the Raw layer in a single step
- **Two-Step Process**: Entity data is first extracted from the source to the Landing layer, then ingested from Landing to Raw

**Core Responsibilities**:
- Extracting/ingesting entity data from external sources (APIs, databases, files)
- Landing raw entity data in the platform
- Refining entity data through standardization and quality checks
- Exposing curated data assets for downstream consumption

#### Data Business Product

A **data business product** transforms refined data into business-ready datasets by:
- Implementing business logic and calculations
- Creating aggregations and metrics
- Joining data from multiple acquisition products
- Producing business KPIs and analytical datasets

#### Data Consumer Product

A **data consumer product** serves data to specific consumers:
- API endpoints
- Reports and dashboards
- Data exports
- ML models

### 1.4 Scopes

**Scopes** define the level at which configuration, infrastructure, and data apply:

| Scope              | Description                | Example Entities                    |
|--------------------|----------------------------|-------------------------------------|
| **Organization**   | Platform-wide              | Shared utilities, org-level flows   |
| **Domain**         | Within a data domain       | Domain-specific configs             |
| **Product**        | Within a data product      | Product-specific assets             |
| **Environment**    | Per deployment environment | dev, stg, prd configurations        |

---

## 2. Data Layers and Processes

### 2.1 Data Layers

The platform organizes data into distinct layers based on transformation maturity:

| Layer         | Description                                               | Owner                 | Schema Naming       |
|---------------|-----------------------------------------------------------|-----------------------|---------------------|
| **Landing**   | Temporary storage for raw data extracted from the source  | Acquisition Product   | `{domain}_landing`  |
| **Raw**       | Complete raw data after ingestion                         | Acquisition Product   | `{domain}_raw`      |
| **Refined**   | Cleaned, standardized, quality-checked                    | Acquisition Product   | `{domain}_refined`  |
| **Business**  | Business logic applied                                    | Data Business Product | `{domain}_business` |
| **Consumer**  | Ready for consumption                                     | Data Consumer Product | `{domain}_consumer` |

### 2.2 Data Processes

Each process type governs how data moves between layers:

| From Layer | To Layer  | Process Name       | Description                               |
|------------|-----------|--------------------|-------------------------------------------|
| Source     | Landing   | `extraction`       | Extract data from external sources        |
| Source     | Raw       | `direct_ingestion` | Directly ingest data without landing      |
| Landing    | Raw       | `ingestion`        | Move data from landing to raw             |
| Raw        | Refined   | `refinement`       | Clean, standardize, and validate data     |
| Refined    | Refined   | `refinement`       | Further refine already refined data       |
| Refined    | Business  | `business`         | Apply business logic and transformations  |
| Business   | Business  | `business`         | Further business transformations          |
| Business   | Consumer  | `consumption`      | Prepare data for end-user consumption     |
| Consumer   | Consumer  | `consumption`      | Further consumer-specific transformations |

**Important Notes**:
- Process names are **case-sensitive** and must be used exactly as listed
- Use these names in Kestra flow definitions, NLD flow definitions, data lineage metadata, and documentation
- Any transition not listed in this table is **not authorized** and should raise an architectural review

---

## 3. Repository Structure (Full Platform)

The repository follows a **domain-centric** structure where all components of a data product are co-located.

**Root-level folder ordering**: .agents (documentation), ops (operations), data domains (alphabetically), scheduling, and README.
**Within folders**: All items are sorted alphabetically.

```
nld-lakehouse-<name>/
├── .agents/                    # AI agent documentation, skills, and rules
│   ├── docs/                   # Architecture documentation
│   ├── rules/                  # Agent rules
│   └── skills/                 # Claude Code skills
├── ops/                        # Operations (deployment, CI/CD)
│   ├── docker/                 # Docker configurations
│   ├── kestra/                 # Kestra configurations
│   ├── kubes/                  # Kubernetes manifests
│   ├── postgresql/             # Database setup and migrations
│   └── version/                # Version management scripts
├── <domain>/                   # Data domains (e.g., clh/, sales/)
│   ├── acquisition/            # Data acquisition products
│   ├── business/               # Business products
│   ├── consumer/               # Consumer products
│   └── workspace/              # Workspace products (optional)
├── scheduling/                 # Orchestration (Kestra flows)
│   ├── <domain>/
│   │   ├── acquisition/
│   │   ├── business/
│   │   └── consumer/
│   └── org/                    # Org-level base flows
└── README.md
```

### Top-Level Directories

#### `ops/` (Operations)
Contains all operational code for deploying and managing the platform:
- Docker image configurations
- Kubernetes deployment manifests
- Kestra orchestration setup
- Database migration scripts (Flyway)
- Version management utilities

#### `<domain>/` (Data Domains)
Each data domain (e.g., `clh/`, `sales/`) contains:
- `acquisition/` - Data acquisition products
- `business/` - Business transformation products
- `consumer/` - Consumer-facing products
- `workspace/` - Collaborative workspace products (optional)

#### `scheduling/` (Orchestration)
Contains Kestra workflow definitions organized by domain and product type.

## Cross-References

- For data layer details (raw, refinement, business, consumer), see `guide-data-layers`.
- For field naming and characterisations, see `guide-field-conventions`.
- For structure conventions and characterisations, see `guide-structure-conventions`.
