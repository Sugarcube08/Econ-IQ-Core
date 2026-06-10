# Econiq Technical Debt Forensic Audit

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Technical Due Diligence Auditor  
**Owner:** Core Engineering Team

---

## 1. Summary of Identified Technical Debt

This audit documents code issues, architectural bottlenecks, and security bugs present in the reference codebase.

---

## 2. Detailed Findings

### 2.1. Inverted `is_ok` Semantic logic (CRITICAL)
*   **Context:** In the ingestion pipeline (`dbprovider` & `sync_pipeline`), valid transactions are written with `is_ok = 1`. However, the scoring models (`app/intelligence/orchestrator.py` and downstream engines) filter for `is_ok == 0` for financial calculations.
*   **Impact:** All valid invoices and receipts are filtered out, leaving financial metrics (Outstanding, Repayment health, Credit Limits) at zero.
*   **Severity:** `CRITICAL`
*   **Remediation:** Modify the mapping logic to write valid transactions as `is_ok = 0` and invalid ones as `is_ok = 1`. Run a migration SQL script to swap `is_ok` values in `event_ledger`, `raw_sales`, `raw_receipts`, and `raw_rg`.

### 2.2. Development Schema Discrepancy (HIGH)
*   **Context:** The Development database (`vgis_db`) was never upgraded to include the `is_ok` column in `event_ledger`.
*   **Impact:** The recomputation queue worker crashed on every cycle, flooding the queue with failed tasks.
*   **Severity:** `HIGH`
*   **Remediation:** Execute a DDL migration adding the `is_ok` column and its composite index (`idx_ledger_customer_date`) to the DEV database.

### 2.3. Unused Analytical Engine (DuckDB / Parquet Cache) (MEDIUM)
*   **Context:** The codebase includes references to DuckDB and Parquet caching (`ref/app/pipelines/ingestion_pipeline.py`), but the actual endpoints and worker services query PostgreSQL directly.
*   **Impact:** Dead code and unused dependencies (`duckdb`, `pyarrow`, `fastexcel`) bloat the project image size.
*   **Severity:** `MEDIUM`
*   **Remediation:** Prune DuckDB and Parquet libraries from `pyproject.toml` and remove dead imports to optimize container footprints.

### 2.4. Synchronous Email Dispatcher (MEDIUM)
*   **Context:** `app/services/email_service.py` connects to SMTP servers synchronously inside API execution paths.
*   **Impact:** API threads will block for several seconds while SMTP handshakes resolve, creating latency spikes.
*   **Severity:** `MEDIUM`
*   **Remediation:** Route email triggers to background queues or mock them out for the hackathon demo.

### 2.5. Connection Pool Starvation & N+1 Queries (HIGH)
*   **Context:** Database sessions in workers retrieve customer lists and query metrics sequentially in loops.
*   **Impact:** Can cause PostgreSQL connection pool starvation and timeout errors.
*   **Severity:** `HIGH`
*   **Remediation:** Implement batch queries (e.g. using `IN` filters or SQL joins) instead of fetching customer rows individually in loops.

### 2.6. Hardcoded Environment Settings (LOW)
*   **Context:** Port configurations and database keys are occasionally hardcoded in settings fallbacks.
*   **Impact:** Configuration leakage risk.
*   **Severity:** `LOW`
*   **Remediation:** Enforce strict env validations using Pydantic Settings.
