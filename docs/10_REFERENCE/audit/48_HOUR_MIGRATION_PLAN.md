# Econiq 48-Hour Migration Action Plan

**Version:** 1.0.0  
**Status:** Approved  
**Author:** Startup CTO & Technical Lead  
**Owner:** Core Engineering Team

---

## 1. Day 1: Code Cleanups & Database Realignment

```
[08:00 - 12:00: Schema Migration] ──► [12:00 - 16:00: Mapper Correction] ──► [16:00 - 20:00: API Realignment]
```

### Hour 08:00 - 12:00: Database Schema & Index Upgrades
*   **Task 1:** Execute DDL migrations on the DEV database (`econiq_db`) to add the `is_ok` column and index `idx_ledger_customer_date` to `event_ledger`, correcting the recomputation queue crash.
*   **Task 2:** Run SQL update script on both databases to swap the inverted `is_ok` values:
    *   `UPDATE event_ledger SET is_ok = CASE WHEN is_ok = 1 THEN 0 ELSE 1 END;`
*   **Target Files:** `migrations/versions/add_is_ok_to_dev.py`, `scripts/realignment_migration.sql`.

### Hour 12:00 - 16:00: Correct the Ingestion Mapper
*   **Task 3:** Modify the mapping logic in `dbupdater/src/mdb_sync/application/mapper.py` to write valid transactions as `is_ok = 0`.
*   **Task 4:** Refactor the sync pipeline (`app/services/sync_pipeline.py`) to reduce database lock periods by running loops sequentially.
*   **Target Files:** `dbupdater/src/mdb_sync/application/mapper.py`, `app/services/sync_pipeline.py`.

### Hour 16:00 - 20:00: API Schema Realignment
*   **Task 5:** Update FastAPI customer schemas (`app/schemas/customers.py`) to include predictions, scores, and active recommendations.
*   **Task 6:** Prune unused dependencies (`duckdb`, `pyarrow`) from `pyproject.toml` to optimize container sizes.
*   **Target Files:** `app/schemas/customers.py`, `pyproject.toml`.

---

## 2. Day 2: Scoring, Features, and AI Integrations

```
[08:00 - 12:00: Feature Cache] ──► [12:00 - 16:00: Score Refactor] ──► [16:00 - 20:00: Copilot RAG Gateway]
```

### Hour 08:00 - 12:00: Deploy Redis Feature Cache
*   **Task 7:** Write Redis cache client wrappers in Go/Python to store customer features as serialized JSON strings.
*   **Task 8:** Configure Go ingestion workers to update the Redis cache after sync jobs.
*   **Target Files:** `app/storage/redis.py`, `app/features/engineer.py`.

### Hour 12:00 - 16:00: Refactor Scoring Rules
*   **Task 9:** Refactor composite calculations in `app/intelligence/orchestrator.py` to save input snapshot metrics and drivers inside the JSON explainability columns.
*   **Task 10:** Create the target `customer_recommendations` table in PostgreSQL.
*   **Target Files:** `app/intelligence/orchestrator.py`, `app/models/state_models.py`.

### Hour 16:00 - 20:00: Deploy Copilot RAG Gateway
*   **Task 11:** Implement the Copilot Gateway, writing context query helpers that fetch metrics, active predictions, and recommendations for the prompt payload.
*   **Task 12:** Set up system instructions to restrict conversation topics to explaining pre-computed customer credit metrics.
*   **Target Files:** `app/api/copilot.py`, `app/core/dependencies.py`.
