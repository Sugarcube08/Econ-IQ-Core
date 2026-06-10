# Econiq Core: Module Map & Package Directory Layout

This document defines the final module map, directory layout, input/output contracts, and dependencies for the **Econiq Core Platform** backend.

---

## 1. Directory Layout

The codebase is refactored into a clean, modular structure under `core/` (replacing legacy `ref/app/` folder packages):

```text
core/
├── auth/                 # Identity, JWT verify, EdDSA sessions, and rate limiting
├── organizations/        # Tenant configuration, profiles, and organization contexts
├── customers/            # Customer detail directories, routes, and dynamic lists
├── Ingestion/            # Ingestion providers mapping raw data to standard buffers
├── ledger/               # event_ledger timeline builder and FIFO settlements
├── feature_store/        # Rolling features calculation (Polars) and Redis caching
├── intelligence/         # Scoring computation engines
│   ├── exposure/         # Outstanding balances pressure calculations
│   ├── payment/          # Delay, rhythm, fragmentation, and aging indicators
│   ├── stress/           # Returns ratio and debt deficiency calculations
│   ├── trade/            # Buying regularity and profile matching
│   └── orchestrator.py   # Sequenced pipeline orchestrator
├── policy/               # Pydantic schemas validating configuration profiles
├── prediction/           # XGBoost / LightGBM model loading and inference wrappers
├── recommendation/       # Credit limits adjustments suggestions logic
├── explainability/       # Natural language explanations driver generator (Gemini)
├── observability/        # Loguru structured traces and Prometheus endpoints
├── models/               # SQLAlchemy persistence models (auth and state)
├── repositories/         # Database persistence query adapters
├── services/             # Core business service logic (users, auth)
└── storage/              # Database adapter drivers (Postgres, Redis)
```

---

## 2. Detailed Module Specifications

### 2.1 `core/auth/`
*   **Purpose:** Enforces token verification, session tracking, and user RBAC controls.
*   **Inputs:** HTTP Authentication Headers (`Authorization: Bearer <EdDSA JWT Token>`).
*   **Outputs:** Verified user identity contexts; token validation status.
*   **Dependencies:** `core/models/auth_models.py`, `core/services/auth_service.py`, `core/storage/redis.py`.
*   **Ownership:** Infrastructure Team.

### 2.2 `core/organizations/`
*   **Purpose:** Manages multi-tenant configuration profiles and dynamic settings.
*   **Inputs:** Organization IDs, tenant scopes.
*   **Outputs:** Validated organization metadata and configurations.
*   **Dependencies:** `core/storage/postgres.py`.
*   **Ownership:** Systems & Multi-Tenancy Team.

### 2.3 `core/customers/`
*   **Purpose:** Serves customer profiles, histories, behavioral states, and lists.
*   **Inputs:** Customer identifier strings, pagination query parameters, date ranges.
*   **Outputs:** JSON customer payloads, paginated customer lists, CSV metrics export.
*   **Dependencies:** `core/repositories/intelligence.py`, `core/policy/`.
*   **Ownership:** Features & Core API Team.

### 2.4 `core/ingestion/`
*   **Purpose:** Asynchronously synchronizes raw transaction changes, normalizes structures, and appends records.
*   **Inputs:** New rows in PostgreSQL raw tables (`raw_sales`, `raw_payments`, `raw_returns`).
*   **Outputs:** Normalized records appended to `event_ledger`; customer recomputation tasks queued in `customer_recomputation_queue`.
*   **Dependencies:** `core/storage/postgres.py`, `core/storage/redis.py` (advisory locking).
*   **Ownership:** Ingestion & Data Platform Team.

### 2.5 `core/ledger/`
*   **Purpose:** Reconstructs exposure balances and calculates repayments using FIFO settlement logic.
*   **Inputs:** Chronological array of sales, payments, and return events.
*   **Outputs:** Daily outstanding exposure balances; average repayment durations; settlement maps.
*   **Dependencies:** `Polars`, `core/ledger/context.py`.
*   **Ownership:** Financial Engineering Team.

### 2.6 `core/feature_store/`
*   **Purpose:** Computes rolling window statistics and caches feature matrices.
*   **Inputs:** Chronological event ledger records.
*   **Outputs:** Feature matrices (`sales_window`, `debit_persistence_days`, etc.) cached in Redis.
*   **Dependencies:** `Polars`, `core/storage/redis.py`.
*   **Ownership:** ML Platform Team.

### 2.7 `core/policy/`
*   **Purpose:** Decouples dynamic scoring thresholds, weights, and classifications from calculation code.
*   **Inputs:** YAML configuration profiles or dynamic PostgreSQL configuration columns.
*   **Outputs:** Validated Pydantic models containing weights, bands, decay parameters, and thresholds.
*   **Dependencies:** `Pydantic`.
*   **Ownership:** Architecture & Systems Team.

### 2.8 `core/intelligence/`
*   **Purpose:** Runs individual scoring engines and infers longitudinal risk states.
*   **Inputs:** Features matrix, dynamic policy configurations.
*   **Outputs:** `customer_intelligence` status database records, calculated subfactor scores.
*   **Dependencies:** `core/policy/`, `core/feature_store/`, `core/ledger/`.
*   **Ownership:** Financial Math & Systems Team.

### 2.9 `core/prediction/`
*   **Purpose:** Serves real-time ML inferences (Default Risk, Churn probability, recovery prioritization).
*   **Inputs:** Redis cached feature vectors.
*   **Outputs:** ML model inference values ($0.00\text{--}1.00$).
*   **Dependencies:** `XGBoost`, `LightGBM`, `core/feature_store/`.
*   **Ownership:** Data Science & ML Team.

### 2.10 `core/recommendation/`
*   **Purpose:** Generates credit terms adjustments based on predictive outputs and policy rules.
*   **Inputs:** Predicted default risk, churn indicators, customer billing history, policy parameters.
*   **Outputs:** Credit adjustment actions (adjust terms, adjust limits, flag account).
*   **Dependencies:** `core/policy/`, `core/prediction/`.
*   **Ownership:** Commercial Operations Team.

### 2.11 `core/explainability/`
*   **Purpose:** Generates natural language explanations of predictive scores.
*   **Inputs:** Target customer metrics, prompt templates, Google Gemini API.
*   **Outputs:** Conversational risk explanation text.
*   **Dependencies:** `Google Gemini SDK`, `core/feature_store/`.
*   **Ownership:** AI Platform Team.

### 2.12 `core/observability/`
*   **Purpose:** System metrics collection, structured logging, and performance telemetry.
*   **Inputs:** Internal execution logs, response durations.
*   **Outputs:** Rotated log files, Prometheus scraper metrics (`/metrics`).
*   **Dependencies:** `Loguru`, `Prometheus Client`.
*   **Ownership:** SRE & DevOps Team.

---

## 3. Package Communication Protocols

To maintain high throughput and microsecond latency targets, communications between modules follow standard contracts:

*   **Ingestion $\rightarrow$ Queue Worker:** Ingestion adds tasks asynchronously. The queue worker picks them up using a background daemon thread running `FOR UPDATE SKIP LOCKED`.
*   **Orchestrator $\rightarrow$ Feature Store:** Orchestrator reads raw ledger records and runs Polars vectorized operations, writing computed features to Redis.
*   **Prediction $\rightarrow$ Explainer:** Prediction outputs (PD float) are paired with feature vectors and passed to the explainer's Gemini prompt templates.
*   **Policy $\rightarrow$ Scoring Engines:** Policies are injected as parameter context objects when invoking `.compute_score()` or `.compute()` methods on scoring engines.
