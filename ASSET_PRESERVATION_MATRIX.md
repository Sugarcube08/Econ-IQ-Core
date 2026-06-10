# Econiq Core: Asset Preservation & Backend Reuse Matrix

This document maps all legacy VGIS backend files and assets, evaluating their business value, replacement cost, reuse percentage, and migration actions. The primary goal is to maximize code reuse, minimizing implementation risk during the Econiq transition.

---

## 1. Core Asset Evaluation Matrix

### 1.1 Ingestion & Storage Core Assets

| Legay File Location | Purpose | Business Value | Replacement Cost | Reuse % | Target Action | Details & Migration Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ref/app/storage/postgres.py` | Postgres pooling adapter and session management. | **Critical** | Low | 100% | **KEEP** | Move to `core/storage/postgres.py`. Unchanged. |
| `ref/app/storage/redis.py` | Redis connection manager. | **Critical** | Low | 100% | **KEEP** | Move to `core/storage/redis.py`. Unchanged. |
| `ref/app/utils/lock_manager.py` | Context manager wrapper executing Redis locks. | **High** | Low | 100% | **KEEP** | Move to `core/utils/lock_manager.py`. Unchanged. |
| `ref/app/services/sync_pipeline.py` | Syncs records from raw tables to event ledger. | **Critical** | High | 95% | **GENERALIZE** | Move to `core/ingestion/sync_pipeline.py`. Map table targets `raw_receipts` $\rightarrow$ `raw_payments`, `raw_rg` $\rightarrow$ `raw_returns`. |
| `ref/app/ingestion/db_provider.py` | Normalizes database records into the ledger format. | **Critical** | High | 90% | **GENERALIZE** | Move to `core/ingestion/db_provider.py`. Map table names, and handle missing `rgtype` column gracefully. |
| `ref/app/pipelines/ingestion_pipeline.py`| Older, duplicated ingestion sync code path. | Low | Low | 0% | **DELETE** | Legacy file. Redundant and replaced by `sync_pipeline.py`. |

### 1.2 Ledger & Feature Store Core Assets

| Legacy File Location | Purpose | Business Value | Replacement Cost | Reuse % | Target Action | Details & Migration Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ref/app/intelligence/ledger/reconstruction.py` | Double-entry ledger reconstruction engine. | **Critical** | High | 100% | **KEEP** | Move to `core/ledger/reconstruction.py`. Retain accounting math intact. |
| `ref/app/intelligence/settlement/engine.py` | Chronologically matches payments against sales. | **Critical** | High | 100% | **KEEP** | Move to `core/ledger/settlement.py`. FIFO settlement logic remains unchanged. |
| `ref/app/ledger/context.py` | Compiles analysis context metadata for ledger. | **High** | Medium | 95% | **KEEP** | Move to `core/ledger/context.py`. Retain. |
| `ref/app/ledger/ledger.py` | Ledger query interface layer. | **Critical** | High | 90% | **GENERALIZE** | Move to `core/ledger/ledger.py`. Standardize queries; default returned goods penalty weight to 0.0 for genuine. |
| `ref/app/features/engineer.py` | Vectorized aggregates using Polars. | **Critical** | High | 100% | **KEEP** | Move to `core/feature_store/engineer.py`. Math calculations are fully reusable. |

### 1.3 Mathematical Scoring & Intelligence Engines

| Legacy File Location | Purpose | Business Value | Replacement Cost | Reuse % | Target Action | Details & Migration Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ref/app/intelligence/orchestrator.py` | Controls calculation execution sequences. | **Critical** | High | 85% | **GENERALIZE** | Move to `core/intelligence/orchestrator.py`. Load policy configs dynamically; query features from Redis. |
| `ref/app/intelligence/queue_worker.py` | Concurrency worker daemon. | **High** | High | 95% | **KEEP** | Move to `core/intelligence/queue_worker.py`. Retain task claims using `SKIP LOCKED`. |
| `ref/app/intelligence/validator.py` | Intelligence data integrity checks. | **High** | Low | 95% | **KEEP** | Move to `core/intelligence/validator.py`. Retain. |
| `ref/app/intelligence/resilience.py` | Unused or experimental error recovery handlers. | Low | Low | 0% | **DELETE** | Dead code. Error recovery is managed directly in queue worker loops. |
| `ref/app/intelligence/cadence/engine.py` | Measures transaction frequency classes. | **High** | Medium | 90% | **GENERALIZE** | Move to `core/intelligence/cadence/engine.py`. decople threshold constants into the Policy Engine. |
| `ref/app/intelligence/causal/engine.py` | Compiles warning tags and indicators. | **High** | High | 95% | **GENERALIZE** | Move to `core/explainability/drivers.py`. Integrate as a context compiler for Gemini API. |
| `ref/app/intelligence/confidence/engine.py`| Density and transactional depth confidence factor.| **High** | Medium | 90% | **REFACTOR** | Move to `core/intelligence/confidence/engine.py`. Load evidence limits from Policy Engine. |
| `ref/app/intelligence/exposure/pressure.py` | Monitors outstanding debt pressure. | **High** | High | 100% | **KEEP** | Move to `core/intelligence/exposure/pressure.py`. Retain. |
| `ref/app/intelligence/payment/behavior.py` | Computes subfactor scores for payment habits. | **Critical** | High | 80% | **REFACTOR** | Move to `core/intelligence/payment/behavior.py`. decople delay decay limits and subfactor weights. |
| `ref/app/intelligence/payment/rhythm.py` | repyament rhythm analysis. | **High** | Medium | 100% | **KEEP** | Move to `core/intelligence/payment/rhythm.py`. Retain. |
| `ref/app/intelligence/rg/engine.py` | Returns ratio and count tracking. | **High** | Medium | 100% | **KEEP** | Move to `core/intelligence/rg/engine.py`. Retain. |
| `ref/app/intelligence/states/engine.py` | Inferred customer behavioral states machine. | **Critical** | High | 50% | **REFACTOR** | Move to `core/intelligence/states/engine.py`. Extract hardcoded states, velocity bounds, and classes. |
| `ref/app/intelligence/stress/engine.py` | Stress score metrics (returns, deficits). | **High** | Medium | 75% | **REFACTOR** | Move to `core/intelligence/stress/engine.py`. decople returned goods weights to policy configurations. |
| `ref/app/intelligence/transitions/engine.py`| Tracks longitudinal state changes. | **High** | High | 100% | **KEEP** | Move to `core/intelligence/transitions/engine.py`. Retain. |
| `ref/app/intelligence/trust/engine.py` | Combines purchase and payment scores. | **High** | Medium | 50% | **REFACTOR** | Move to `core/intelligence/trust/engine.py`. Parameterize the 50/50 fusion weights. |

### 1.4 API, Identity & Configuration Assets

| Legacy File Location | Purpose | Business Value | Replacement Cost | Reuse % | Target Action | Details & Migration Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ref/app/api/api_keys.py` | Handles API keys validation and security hashing. | **High** | Medium | 100% | **KEEP** | Move to `core/auth/api_keys.py`. Retain. |
| `ref/app/api/auth.py` | User session validation and login. | **High** | Medium | 95% | **REFACTOR** | Move to `core/auth/routes.py`. Align imports. |
| `ref/app/api/customers.py` | Customer endpoints, detail, and timeline. | **High** | High | 80% | **REFACTOR** | Move to `core/customers/routes.py`. Load dynamic states and add export page controls. |
| `ref/app/api/dashboard.py` | Dashboard charts data retrieval. | **High** | High | 90% | **GENERALIZE** | Move to `core/dashboard/routes.py`. Ensure raw queries match target schemas. |
| `ref/app/api/users.py` | User registration and profile management. | **Medium** | Low | 100% | **KEEP** | Move to `core/auth/users.py`. Retain. |
| `ref/app/config/settings.py` | Dynamic environmental settings parser. | **High** | Medium | 85% | **REFACTOR** | Move to `core/config/settings.py`. Add validation mechanisms for policies. |
| `ref/app/models/auth_models.py` | SQLAlchemy database structures for auth/users. | **High** | Medium | 100% | **KEEP** | Move to `core/models/auth_models.py`. Retain. |
| `ref/app/models/state_models.py` | SQLAlchemy structures for ledger, queue, and state. | **Critical** | High | 100% | **KEEP** | Move to `core/models/state_models.py`. Retain. |
| `ref/app/observability/logger.py` | Async structured file logs and telemetry. | **Medium** | Low | 100% | **KEEP** | Move to `core/observability/logger.py`. Retain. |
| `ref/app/repositories/auth.py` | CRUD db adapters for authentication. | **High** | Medium | 100% | **KEEP** | Move to `core/repositories/auth.py`. Retain. |
| `ref/app/repositories/dashboard.py` | Complex database query builder for charts. | **High** | High | 100% | **KEEP** | Move to `core/repositories/dashboard.py`. Retain. |
| `ref/app/repositories/intelligence.py` | Reads and updates computed intelligence metrics. | **High** | High | 95% | **KEEP** | Move to `core/repositories/intelligence.py`. Retain. |
| `ref/app/services/auth_service.py` | Password hashing, verification, MFA services. | **High** | Medium | 100% | **KEEP** | Move to `core/services/auth_service.py`. Retain. |
| `ref/app/services/email_service.py` | SMTP relay dispatch handlers. | **Medium** | Low | 100% | **KEEP** | Move to `core/services/email_service.py`. Retain. |
| `ref/app/services/user_service.py` | CRUD operations for profiles. | **Medium** | Low | 100% | **KEEP** | Move to `core/services/user_service.py`. Retain. |

---

## 2. Generalization Rules & Guidelines

To control execution risk and prevent regression, developers must follow these rules during refactoring:

1.  **Do NOT touch Invariant Math:** The FIFO invoice matching algorithm in `settlement/engine.py` and the double-entry balance compiler in `ledger/reconstruction.py` are mathematically correct and must not be altered.
2.  **decople Configuration Only:** Changes to scoring engines must be strictly limited to replacing hardcoded numbers with variable references passed via a `policy` context object.
3.  **Delete Duplicate/Legacy Code:** Ensure all legacy files mapped to **DELETE** (e.g., `pipelines/ingestion_pipeline.py`) are deleted immediately to avoid syntax conflicts.
