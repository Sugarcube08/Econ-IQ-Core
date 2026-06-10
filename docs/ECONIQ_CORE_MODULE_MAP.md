# Econiq Core Module & Package Directory Map

This document defines the final module map, directory layout, input/output contracts, and dependencies for the **Econiq Core Platform** backend.

---

## 1. Directory Layout

The codebase is refactored into a clean, modular structure under `core/` (replacing legacy `app/` folder packages):

```text
core/
├── auth/                 # Identity, JWT verify, EdDSA sessions, and rate limiting
├── organizations/        # Tenant configuration, profiles, and organization contexts
├── customers/            # Customer detail directories and dynamic lists
├── Ingestion/            # Ingestion providers mapping raw data to standard buffers
├── ledger/               # event_ledger timeline builder and FIFO settlements
├── feature_store/        # Rolling features calculation (Polars) and Redis caching
├── intelligence/         # scoring computation engines
│   ├── exposure/         # outstanding balances pressure
│   ├── payment/          # delay, fragment, and aging indicators
│   ├── stress/           # returns ratio and debt deficiency
│   ├── trade/            # buying regularity and profile matching
│   └── orchestrator.py   # Sequenced pipeline orchestrator
├── policy/               # Pydantic schemas validating YAML configurations
├── prediction/           # XGBoost / LightGBM model loading and inference wrappers
├── recommendation/       # Credit limits adjustments suggestions logic
├── explainability/       # Natural language explanations driver generator (Gemini)
└── observability/        # Loguru structured traces and Prometheus endpoints
```

---

## 2. Detailed Module Specifications

### 2.1 `core/auth/`
*   **Purpose:** Enforces token verification, session tracking, and user RBAC controls.
*   **Inputs:** HTTP Auth headers (`Authorization: Bearer <EdDSA Token>`).
*   **Outputs:** Verified user identity contexts; token validation status.
*   **Dependencies:** `core/core/security.py`, `core/models/auth_models.py`.
*   **Ownership:** Infrastructure Team.

### 2.2 `core/ingestion/`
*   **Purpose:** Reads new raw transaction changes, normalizes structures, and materializes logs.
*   **Inputs:** Rows from raw transactional tables (`raw_sales`, `raw_payments`, `raw_returns`).
*   **Outputs:** Normalized records appended to `event_ledger`; customer recomputation tasks queued.
*   **Dependencies:** `core/ledger/`, `core/storage/postgres.py`.
*   **Ownership:** Ingestion & Data Platform Team.

### 2.3 `core/ledger/`
*   **Purpose:** Reconstructs exposure balances and calculates repayments using FIFO settlement logic.
*   **Inputs:** Chronological array of sales, payments, and return events.
*   **Outputs:** Daily outstanding balances; average repayment durations.
*   **Dependencies:** `Polars`, `AnalysisContext`.
*   **Ownership:** Analytics Core Team.

### 2.4 `core/feature_store/`
*   **Purpose:** Computes rolling window statistics and caches feature matrices.
*   **Inputs:** Chronological arrays from the ledger.
*   **Outputs:** Feature matrices (`sales_window`, `debit_persistence_days`, etc.) stored in Redis.
*   **Dependencies:** `Polars`, `core/storage/redis.py`.
*   **Ownership:** ML Platform Team.

### 2.5 `core/policy/`
*   **Purpose:** Decouples dynamic scoring thresholds from calculations code.
*   **Inputs:** YAML configuration files or PostgreSQL configuration columns.
*   **Outputs:** Validated Pydantic models containing weights and thresholds.
*   **Dependencies:** `Pydantic`.
*   **Ownership:** Architecture & Systems Team.

### 2.6 `core/intelligence/`
*   **Purpose:** Runs subfactor scoring engines and infers risk states.
*   **Inputs:** Features matrix; dynamic policy parameters.
*   **Outputs:** `customer_intelligence` status database records.
*   **Dependencies:** `core/policy/`, `core/feature_store/`.
*   **Ownership:** Systems & Math Team.

### 2.7 `core/prediction/`
*   **Purpose:** Serves real-time ML inferences (risk default, churn, recovery prioritization).
*   **Inputs:** Redis cached feature vectors.
*   **Outputs:** ML model predictions ($0.00\text{--}1.00$).
*   **Dependencies:** `XGBoost`, `LightGBM`, `core/feature_store/`.
*   **Ownership:** ML Platform Team.

### 2.8 `core/explainability/`
*   **Purpose:** Converts predictive outcomes and feature store metrics into credit summaries.
*   **Inputs:** Target customer metrics; Gemini prompt templates.
*   **Outputs:** conversational risk explanation text.
*   **Dependencies:** `Google Gemini SDK`.
*   **Ownership:** AI Platform Team.

### 2.9 `core/recommendation/`
*   **Purpose:** Generates credit decisions based on predictive outputs.
*   **Inputs:** predicted default risk; churn indicators.
*   **Outputs:** credit adjustment actions (adjust terms, flags).
*   **Dependencies:** `core/policy/`.
*   **Ownership:** Commercial Operations Team.
