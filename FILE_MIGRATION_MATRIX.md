# Econiq Core: Master File Migration Matrix

This document defines the migration path for all source files in the reference backend (`ref/app/`) to their target locations under the generalized `core/` package layout. It controls the migration execution.

---

## 1. Master File Migration Matrix

| Source File Location | Target File Location | Migration Strategy | Complexity | Risk | Priority | Reuse % |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `ref/app/api/api_keys.py` | `core/auth/api_keys.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/api/auth.py` | `core/auth/routes.py` | **REFACTOR**<br>(Align imports to new module paths). | Low | Low | High | 95% |
| `ref/app/api/customers.py` | `core/customers/routes.py` | **REFACTOR**<br>(Inject dynamic policy state bounds, add dynamic credit grade checks, add export controls). | Medium | Medium | Critical | 80% |
| `ref/app/api/dashboard.py` | `core/dashboard/routes.py` | **GENERALIZE**<br>(Verify queries compatibility with target table names). | Medium | Low | Critical | 90% |
| `ref/app/api/users.py` | `core/auth/users.py` | **KEEP** | Low | Low | Medium | 100% |
| `ref/app/config/settings.py` | `core/config/settings.py` | **REFACTOR**<br>(Integrate dynamic policy configuration model parser). | Medium | Low | Critical | 85% |
| `ref/app/features/engineer.py` | `core/feature_store/engineer.py` | **KEEP** | High | Low | Critical | 100% |
| `ref/app/ingestion/db_provider.py` | `core/ingestion/db_provider.py` | **GENERALIZE**<br>(Map raw tables: `raw_receipts` $\rightarrow$ `raw_payments`, `raw_rg` $\rightarrow$ `raw_returns`. Handle missing `rgtype` column gracefully). | Medium | Medium | Critical | 90% |
| `ref/app/intelligence/orchestrator.py` | `core/intelligence/orchestrator.py` | **GENERALIZE**<br>(Inject settings policy profile; retrieve features from Redis online cache). | High | High | Critical | 85% |
| `ref/app/intelligence/queue_worker.py` | `core/intelligence/queue_worker.py` | **KEEP** | High | Medium | High | 95% |
| `ref/app/intelligence/resilience.py` | N/A | **DELETE**<br>(Redundant, unused error handler logic). | Low | Low | Low | 0% |
| `ref/app/intelligence/validator.py` | `core/intelligence/validator.py` | **KEEP** | Medium | Low | High | 95% |
| `ref/app/intelligence/cadence/engine.py` | `core/intelligence/cadence/engine.py` | **GENERALIZE**<br>(Load parameters from settings policy object). | Low | Low | High | 90% |
| `ref/app/intelligence/causal/engine.py` | `core/explainability/drivers.py` | **GENERALIZE**<br>(Rename to compile warning indicators context for Gemini). | Low | Low | Medium | 95% |
| `ref/app/intelligence/confidence/engine.py`| `core/intelligence/confidence/engine.py`| **REFACTOR**<br>(Parameterize density confidence thresholds). | Low | Low | High | 90% |
| `ref/app/intelligence/exposure/pressure.py` | `core/intelligence/exposure/pressure.py` | **KEEP** | Medium | Low | High | 100% |
| `ref/app/intelligence/ledger/reconstruction.py`| `core/ledger/reconstruction.py` | **KEEP** | High | Low | Critical | 100% |
| `ref/app/intelligence/payment/behavior.py` | `core/intelligence/payment/behavior.py` | **REFACTOR**<br>(Parameterize delay scale decay limits and subfactor weights into policy settings). | High | High | Critical | 80% |
| `ref/app/intelligence/payment/rhythm.py` | `core/intelligence/payment/rhythm.py` | **KEEP** | Medium | Low | High | 100% |
| `ref/app/intelligence/rg/engine.py` | `core/intelligence/rg/engine.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/intelligence/settlement/engine.py` | `core/ledger/settlement.py` | **KEEP** | High | Low | Critical | 100% |
| `ref/app/intelligence/states/engine.py` | `core/intelligence/states/engine.py` | **REFACTOR**<br>(Extract state inference rules, velocity thresholds, and class limits to Policy Engine). | Medium | High | Critical | 50% |
| `ref/app/intelligence/stress/engine.py` | `core/intelligence/stress/engine.py` | **REFACTOR**<br>(Parameterize return goods weights). | Low | Low | High | 75% |
| `ref/app/intelligence/transitions/engine.py` | `core/intelligence/transitions/engine.py` | **KEEP** | Medium | Low | High | 100% |
| `ref/app/intelligence/trust/engine.py` | `core/intelligence/trust/engine.py` | **REFACTOR**<br>(Parameterize purchase/payment fusion weights coefficient). | Low | Low | High | 50% |
| `ref/app/ledger/context.py` | `core/ledger/context.py` | **KEEP** | Medium | Low | High | 95% |
| `ref/app/ledger/ledger.py` | `core/ledger/ledger.py` | **GENERALIZE**<br>(Ensure returned goods penalty weight is 0.0 for genuine).| High | Medium | Critical | 90% |
| `ref/app/models/auth_models.py` | `core/models/auth_models.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/models/state_models.py` | `core/models/state_models.py` | **KEEP** | Low | Low | Critical | 100% |
| `ref/app/observability/logger.py` | `core/observability/logger.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/pipelines/ingestion_pipeline.py` | N/A | **DELETE**<br>(Duplicate ingestion implementation). | Low | Low | Low | 0% |
| `ref/app/repositories/auth.py` | `core/repositories/auth.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/repositories/dashboard.py` | `core/repositories/dashboard.py` | **KEEP** | Medium | Low | High | 100% |
| `ref/app/repositories/intelligence.py` | `core/repositories/intelligence.py` | **KEEP** | Low | Low | High | 95% |
| `ref/app/services/auth_service.py` | `core/services/auth_service.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/services/email_service.py` | `core/services/email_service.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/services/sync_pipeline.py` | `core/ingestion/sync_pipeline.py` | **GENERALIZE**<br>(Map raw tables: `raw_receipts` $\rightarrow$ `raw_payments`, `raw_rg` $\rightarrow$ `raw_returns`. Integrate advisory locking). | High | High | Critical | 95% |
| `ref/app/services/user_service.py` | `core/services/user_service.py` | **KEEP** | Low | Low | High | 100% |
| `ref/app/storage/postgres.py` | `core/storage/postgres.py` | **KEEP** | Low | Low | Critical | 100% |
| `ref/app/storage/redis.py` | `core/storage/redis.py` | **KEEP** | Low | Low | Critical | 100% |
| `ref/app/utils/lock_manager.py` | `core/utils/lock_manager.py` | **KEEP** | Low | Low | High | 100% |

---

## 2. Migration Phase Roadmap

To ensure zero downtime and code safety, the migration is planned in four logical phases:

```
[Phase 1: Foundation Setup] ──▶ [Phase 2: Ingestion & Ledger] ──▶ [Phase 3: Math & Policy] ──▶ [Phase 4: API & Explainer]
- Setup core/ directory        - Move Ingestion Providers       - Implement Policy Engine    - Move Route Gateway
- Migrate Storage adapters     - Move Settlement & Reconstruction - Refactor Scoring Engines   - Integrate Gemini Copilot
```

*   **Phase 1: Foundation Setup**
    *   Create packages structure under `core/`.
    *   Migrate `storage/`, `config/`, and `observability/`. Validate SQLAlchemy and Redis pools connection.
*   **Phase 2: Ingestion & Ledger**
    *   Migrate `ingestion/` provider and sync pipelines. Apply renaming rules for PostgreSQL target tables.
    *   Migrate `ledger/` reconstruction and settlement. Validate daily outstanding materialization.
*   **Phase 3: Mathematical Scoring & Policy**
    *   Migrate and refactor scoring engines.
    *   Implement Pydantic schemas validating YAML configuration files inside `core/policy/`.
    *   Inject configuration schemas into scoring engines runtime variables.
*   **Phase 4: API & Explainer Gateway**
    *   Migrate routers to `core/auth/`, `core/customers/`, and `core/dashboard/`.
    *   Integrate XGBoost/LightGBM inference loaders and Gemini conversational explainer.
