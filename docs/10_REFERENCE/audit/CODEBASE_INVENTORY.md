# Econiq Codebase Inventory: Forensic Audit

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Technical Due Diligence Audit Team  
**Owner:** Startup CTO & Hackathon Lead  

---

## 1. Directory Tree & Module Map

Below is the physical directory map of the reference codebase located in `/ref`:

```text
ref/
├── app/
│   ├── api/                   # API Endpoints (FastAPI Routers)
│   │   ├── auth.py            # User Login/Logout/OTP REST endpoints
│   │   ├── users.py           # User CRUD & Status modifications
│   │   ├── api_keys.py        # System-to-system HMAC API key CRUD
│   │   ├── customers.py       # Retailer listing & details endpoints
│   │   └── dashboard.py       # Aggregate metrics endpoints
│   ├── config/                # Environment and app config
│   │   └── settings.py        # Settings validation (Pydantic)
│   ├── core/                  # Core Middlewares & Core Utils
│   │   ├── security.py        # JWT generation, hashing, encryption
│   │   ├── permissions.py     # Role and permission registries (RBAC)
│   │   ├── rate_limit.py      # Burst / sustained limits (Redis-backed)
│   │   └── dependencies.py    # FastAPI dependencies & guards
│   ├── features/              # Feature Engineering
│   │   └── engineer.py        # Polars sliding window feature compiler
│   ├── ingestion/             # raw data ingestion provider
│   │   └── db_provider.py     # Database scraper extracting raw inputs
│   ├── intelligence/          # The scoring and state engines
│   │   ├── cadence/           # Customer ordering intervals (consistency)
│   │   ├── causal/            # Diagnosis explanations of state changes
│   │   ├── confidence/        # Data volume weight multipliers
│   │   ├── exposure/          # Debt pressure and persistence indices
│   │   ├── ledger/            # Reconstruct exposure & balance sheets
│   │   ├── payment/           # Payment delays & consistency rules
│   │   ├── rg/                # Return goods friction calculators
│   │   ├── settlement/        # FIFO matching of bills to receipts
│   │   ├── states/            # Transition classifications (Elite, Active)
│   │   ├── stress/            # Volatility indicators (payment rhythm)
│   │   ├── trade/             # Buying consistencies & trade potential
│   │   ├── transitions/       # Chronological delta state changes
│   │   ├── trust/             # Non-linear trust score fusion engine
│   │   ├── queue_worker.py    # Background worker scheduler task
│   │   └── orchestrator.py    # Core intelligence manager
│   ├── ledger/                # Transaction structures
│   │   ├── ledger.py          # ledger log builders & appenders
│   │   └── context.py         # Longitudinal context validation service
│   ├── middleware/            # Security filters
│   │   └── security.py        # Hardened headers, rate limiter interceptor
│   ├── models/                # Database ORM classes (SQLAlchemy)
│   │   ├── auth_models.py     # Users, APIKeys, OTPChallenges
│   │   └── state_models.py    # EventLedger, SyncState, SyncLock, IngestBatch
│   ├── normalization/         # raw parsing
│   │   └── __init__.py        # Date formats & string standardizations
│   ├── observability/         # Monitoring
│   │   └── logger.py          # Loguru structured formats configuration
│   ├── pipelines/             # Ingestion pipelines
│   │   └── ingestion_pipeline.py # raw parser sync logic
│   ├── repositories/          # Database queries encapsulation
│   │   ├── auth.py            # User & Key Postgres operations
│   │   ├── dashboard.py       # Metrics aggregation queries
│   │   └── intelligence.py    # upsert metrics & read profiles
│   ├── schemas/               # Pydantic serialization models
│   │   ├── auth.py, customers.py, dashboard.py, events.py, responses.py
│   ├── storage/               # Persistence gateways
│   │   ├── postgres.py        # Connection pools (SQLAlchemy Async)
│   │   └── redis.py           # Key-value clients (Redis)
│   ├── utils/                 # Utilities
│   │   ├── lock_manager.py, temporal.py, ip.py
│   ├── main.py                # FastAPI webserver configuration
│   └── sync_main.py           # Sync and recomputation daemon launcher
├── migrations/                # Alembic migration scripts
├── scripts/                   # CLI maintenance scripts
└── tests/                     # Unit and verification tests
```

---

## 2. Core Dependencies & Libraries

*   **FastAPI (0.136.1):** High-performance ASGI web gateway.
*   **SQLAlchemy (2.0.49) & asyncpg (0.31.0):** Async connection pool and ORM queries to PostgreSQL.
*   **Polars (1.40.1) & PyArrow (24.0.0):** Rust-backed, vectorized feature and scoring pipeline.
*   **Redis (5.3.0):** Distributed lock manager and rate limiting cache.
*   **PyJWT (2.12.1) & Cryptography (48.0.0):** EdDSA token signing and encryption.
*   **DuckDB (1.5.2):** High-performance analytical querying over local Parquet cache (unused in actual Postgres path, but present).
*   **loguru (0.7.3) & prometheus-client (0.21.1):** Operational telemetry.

---

## 3. Core Component Audits

### 3.1. Intelligence Orchestrator (`app/intelligence/orchestrator.py`)
*   **Purpose:** Coordinates the execution of 12 distinct scoring engines, feature extraction, and state transitions.
*   **Dependencies:** `polars`, `app/features/engineer.py`, `app/intelligence/*`.
*   **Consumers:** `app/intelligence/queue_worker.py`, `app/api/customers.py`.
*   **Complexity:** Critical (522 lines of complex Polars join logic).
*   **Risk Level:** High (Inverted `is_ok` logic causes data corruption).
*   **Reuse Potential:** Very High. Can be used as-is for the scoring calculations after correcting `is_ok`.

### 3.2. Sync Pipeline (`app/services/sync_pipeline.py`)
*   **Purpose:** Pulls data from raw staging tables into the canonical `event_ledger`.
*   **Dependencies:** `sqlalchemy`, `app/ingestion/db_provider.py`, `app/ledger/ledger.py`.
*   **Consumers:** `app/main.py` (when workers enabled), `app/sync_main.py`.
*   **Complexity:** High (Handles Postgres session-level advisory locks).
*   **Risk Level:** Medium (Prone to connection timeouts under lock contention).
*   **Reuse Potential:** High. Keep for sync logs but modify to load raw tables directly.

### 3.3. DB Ingestion Provider (`app/ingestion/db_provider.py`)
*   **Purpose:** Fetches raw transactional rows and cleans schema object types.
*   **Dependencies:** `polars`, `sqlalchemy`.
*   **Consumers:** `app/services/sync_pipeline.py`.
*   **Complexity:** Medium (Reflects tables on-the-fly).
*   **Risk Level:** Low.
*   **Reuse Potential:** High. Keep as the database scraper.

### 3.4. Feature Engineer (`app/features/engineer.py`)
*   **Purpose:** Vectorized extraction of payment delay, averages, and utilization.
*   **Dependencies:** `polars`.
*   **Consumers:** `app/intelligence/orchestrator.py`.
*   **Complexity:** Medium (Calculates longitudinal rolling window metrics).
*   **Risk Level:** Low.
*   **Reuse Potential:** High. Serves as the ML feature generator.

### 3.5. Security & Authentication (`app/core/dependencies.py` & `app/core/security.py`)
*   **Purpose:** Generates JWT tokens and validates HMAC headers.
*   **Dependencies:** `pyjwt`, `cryptography`, `passlib`.
*   **Consumers:** `app/main.py`, `app/api/*`.
*   **Complexity:** Medium.
*   **Risk Level:** Low.
*   **Reuse Potential:** Absolute (100% reusable).
