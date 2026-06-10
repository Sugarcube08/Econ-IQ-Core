# System Decomposition & Core Classification

This document decomposes the legacy VGIS backend codebase, classifying every module, model, service, controller, and job into four distinct architecture layers. This classification separates the invariant platform mechanics from the organization-specific business rules and technical debt.

---

## 1. Classification Methodology

To isolate a reusable platform kernel (**Econiq Core**), all codebase elements are classified under one of the following domains:

| Category | Definition | Migration Action |
| :--- | :--- | :--- |
| **INFRASTRUCTURE** | Non-functional support layers: storage interfaces, serialization, authentication protocols, task queues, logging systems, and configurations. | **Keep & Reuse (As-Is)** |
| **COMMERCIAL INTELLIGENCE** | Invariant math operations, ledger timeline reconstruction algorithms, transactional velocity indicators, and rolling statistical aggregate operations. | **Keep & Generalize** |
| **ORGANIZATION LOGIC** | Hardcoded heuristics, grading thresholds, state conditions, scoring weights, label assignments, and domain classifications. | **Extract to Policy Engine** |
| **TECHNICAL DEBT** | Design flaws, performance bottlenecks, code-comment discrepancies, dead code, blocking sync patterns, or lack of proper pagination. | **Refactor, Replace, or Delete** |

---

## 2. Directory Tree & Module Mapping

The VGIS backend is organized as a single FastAPI repository with asynchronous background processing loops. The directory map below identifies the categorization of each primary codebase file:

```text
ref/
├── app/
│   ├── api/
│   │   ├── api_keys.py              --> INFRASTRUCTURE (API Key Management)
│   │   ├── auth.py                  --> INFRASTRUCTURE (JWT & OAuth Flow)
│   │   ├── customers.py             --> COMMERCIAL INTELLIGENCE & TECHNICAL DEBT (Export without Pagination)
│   │   ├── dashboard.py             --> COMMERCIAL INTELLIGENCE (Aggregation Endpoints)
│   │   └── users.py                 --> INFRASTRUCTURE (RBAC & User Controllers)
│   ├── config/
│   │   └── settings.py              --> INFRASTRUCTURE (Config & Env Vars)
│   ├── core/
│   │   ├── security.py              --> INFRASTRUCTURE (Hashing & JWT Tokens)
│   │   └── dependencies.py          --> INFRASTRUCTURE (FastAPI Dependency Injection)
│   ├── features/
│   │   └── engineer.py              --> COMMERCIAL INTELLIGENCE (Polars Rolling Features)
│   ├── ingestion/
│   │   └── db_provider.py           --> COMMERCIAL INTELLIGENCE & ORGANIZATION LOGIC (Parsing & Type Mapping)
│   ├── intelligence/
│   │   ├── cadence/                 --> COMMERCIAL INTELLIGENCE (Purchase Timing Engine)
│   │   ├── causal/                  --> COMMERCIAL INTELLIGENCE (Explainability / Drivers)
│   │   ├── confidence/              --> COMMERCIAL INTELLIGENCE & ORGANIZATION LOGIC (Evidence Weighting Caps)
│   │   ├── exposure/                --> COMMERCIAL INTELLIGENCE (Outstanding Balance Stress)
│   │   ├── ledger/                  --> COMMERCIAL INTELLIGENCE (Ledger Timeline Reconstruction)
│   │   ├── payment/                 --> COMMERCIAL INTELLIGENCE & ORGANIZATION LOGIC (Discipline Scoring Subfactors)
│   │   ├── rg/                      --> COMMERCIAL INTELLIGENCE (Returned Goods Burden Engine)
│   │   ├── settlement/              --> COMMERCIAL INTELLIGENCE (Bill Matching Engine)
│   │   ├── states/                  --> ORGANIZATION LOGIC (Hardcoded Customer States Machine)
│   │   ├── stress/                  --> COMMERCIAL INTELLIGENCE & TECHNICAL DEBT (Weights Mismatch with Comments)
│   │   ├── trade/                   --> COMMERCIAL INTELLIGENCE (Profile & Consistency Engines)
│   │   ├── transitions/             --> COMMERCIAL INTELLIGENCE (Longitudinal Path Shifts)
│   │   ├── trust/                   --> ORGANIZATION LOGIC (50/50 Purchase/Payment Fusion Weighting)
│   │   ├── orchestrator.py          --> COMMERCIAL INTELLIGENCE (Computation Sequence Pipeline)
│   │   ├── queue_worker.py          --> INFRASTRUCTURE (Async Queue Worker)
│   │   └── validator.py             --> COMMERCIAL INTELLIGENCE (Data Entropy & Collapse Validator)
│   ├── ledger/
│   │   ├── context.py               --> INFRASTRUCTURE (Polars History Loader)
│   │   └── ledger.py                --> COMMERCIAL INTELLIGENCE (Ledger Materializer & Sequence Generation)
│   ├── middleware/
│   │   └── auth.py                  --> INFRASTRUCTURE (Request Auth Context Interceptor)
│   ├── models/
│   │   ├── auth_models.py           --> INFRASTRUCTURE (Users, API Keys, Sessions, OTP)
│   │   └── state_models.py          --> INFRASTRUCTURE & COMMERCIAL INTELLIGENCE (DB Schema Definitions)
│   ├── normalization/
│   │   └── normalizer.py            --> COMMERCIAL INTELLIGENCE (Data Type Casting)
│   ├── observability/
│   │   └── logger.py                --> INFRASTRUCTURE (Loguru Structured Telemetry)
│   ├── repositories/
│   │   └── intelligence.py          --> INFRASTRUCTURE (SQLAlchemy Async Repo Queries)
│   ├── schemas/
│   │   └── intelligence.py          --> INFRASTRUCTURE (Pydantic DTOs & Contexts)
│   ├── services/
│   │   └── sync_pipeline.py         --> INFRASTRUCTURE (Raw Ingestion Sync Loop)
│   ├── storage/
│   │   ├── postgres.py              --> INFRASTRUCTURE (PostgreSQL Engine & Session Pool)
│   │   └── redis.py                 --> INFRASTRUCTURE (Redis Connection Manager & Locks)
│   ├── utils/
│   │   └── lock_manager.py          --> INFRASTRUCTURE (Redis Distributed Lock)
│   ├── main.py                      --> INFRASTRUCTURE (FastAPI Main App Entrypoint)
│   └── sync_main.py                 --> INFRASTRUCTURE (Sync Pipeline Daemon Entrypoint)
```

---

## 3. Detailed Module Analysis

### 3.1 `app/api/` (API Controllers)
*   **Purpose:** Expose dashboard statistics, customer tables, auth workflows, user profiles, and key generation.
*   **Dependencies:** `SQLAlchemy`, `FastAPI Security Dependencies`, `IntelligenceRepository`.
*   **Consumers:** Frontend Dashboard application (React/HTML client).
*   **Complexity:** Medium (Contains raw SQL formulations for complex dashboard statistics).
*   **Risk Level:** Medium (Exposes transactional totals; lack of field-level sanitization could leak records).
*   **Reuse Potential:** High (APIs are fully aligned with the frontend schema, needing minimal adjustments).

### 3.2 `app/features/engineer.py` (Rolling Features)
*   **Purpose:** Efficiently aggregate raw events into longitudinal metrics using Polars rolling windows.
*   **Dependencies:** `Polars`, `AnalysisContext`.
*   **Consumers:** `StateEngine`, `ConfidenceEngine`, `StressEngine`, `RGBehaviorEngine`, `PurchaseBehaviorEngine`.
*   **Complexity:** High (Polars expression chains performing rolling sums, counts, and log-scaling).
*   **Risk Level:** Low (Pure compute layer with zero network calls or external state).
*   **Reuse Potential:** Extremely High (Econiq's feature store baseline).

### 3.3 `app/intelligence/states/engine.py` (State Machine)
*   **Purpose:** Classifies customers into behavioral categories (`active`, `elite`, `declining`, `irregular`, `inactive`) and trajectories.
*   **Dependencies:** `Polars`.
*   **Consumers:** `IntelligenceOrchestrator`.
*   **Complexity:** Low (Mainly nested `pl.when().then()` conditions).
*   **Risk Level:** High (Contains hardcoded threshold constants that dictate risk classifications without business config access).
*   **Reuse Potential:** Low as code; High as a blueprint (Must be refactored to read configuration rules dynamically).

### 3.4 `app/services/sync_pipeline.py` (Ingestion pipeline)
*   **Purpose:** Asynchronously fetch unprocessed records from raw databases, normalize them, write to `event_ledger`, and queue customers for scoring.
*   **Dependencies:** `DBIngestionProvider`, `LedgerService`, `SQLAlchemy`, `Polars`.
*   **Consumers:** `sync_main.py` daemon loop.
*   **Complexity:** High (Uses Advisory locks, `FOR UPDATE SKIP LOCKED` database queues, and nested rollback checkpoints).
*   **Risk Level:** High (Performs critical raw write operations; lock leaks can freeze the sync loop).
*   **Reuse Potential:** High (This ingestion architecture is extremely clean and can directly consume the raw transactional PostgreSQL tables).

---

## 4. Key Metrics Summary

*   **Total Infrastructure Modules:** 22 (approx. 50% of files)
*   **Total Commercial Intelligence Modules:** 18 (approx. 40% of files)
*   **Total Organization-Specific Logic Modules:** 2 (approx. 5% of files - primarily `states/engine.py`, `trust/engine.py`)
*   **Technical Debt / Refactor Target Modules:** 3 (approx. 5% of files - primarily `stress/engine.py`, API exports, and DDL checks)

> [!NOTE]
> By separating the **Infrastructure** and **Commercial Intelligence** layers, we preserve over **90%** of the existing engineering investments while extracting the hardcoded business thresholds into a dynamic profile repository.
