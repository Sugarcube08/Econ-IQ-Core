# Database Alignment Specification

This document defines the schema compatibility and database mapping rules between the legacy VGIS SQLAlchemy models and the target **Econiq Core** PostgreSQL datasets (`customers`, `raw_sales`, `raw_payments`, and `raw_returns`).

---

## 1. Table Mapping & Relations

The ingestion pipeline maps the incoming target tables into the standardized core database ledger format:

```text
Econiq Source Tables                Econiq Core Ledger Models
┌─────────────────┐                 ┌────────────────────────────────┐
│ customers       │ ──────────────> │ event_ledger (OPENING_BALANCE) │
├─────────────────┤                 ├────────────────────────────────┤
│ raw_sales       │ ──────────────> │ event_ledger (SALE)            │
├─────────────────┤                 ├────────────────────────────────┤
│ raw_payments    │ ──────────────> │ event_ledger (PAYMENT)         │
├─────────────────┤                 ├────────────────────────────────┤
│ raw_returns     │ ──────────────> │ event_ledger (RETURN)          │
└─────────────────┘                 └────────────────────────────────┘
```

---

## 2. Model Compatibility Analysis

### 2.1 `customers` $\rightarrow$ `event_ledger` (Opening Balance)
*   **Source Fields:** `customer_id` (String), `customer_name` (String), `opening_balance` (Float).
*   **Logic:** When a new customer is processed, the pipeline materializes an `OPENING_BALANCE` event in the `event_ledger` anchored at date `2000-01-01` with `amount = opening_balance` to initialize their financial history.
*   **Compatibility Gaps:** The legacy system joined `raw_cities` to populate the customer city name in [orchestrator.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/orchestrator.py#L318). If `raw_cities` is not populated in the target database, this join will fail or return `None`.
*   **Action:** Flatten `city_name` directly into the `customers` database model or check for the existence of `raw_cities` first, handling failures gracefully.

### 2.2 `raw_sales` $\rightarrow$ `event_ledger` (Sale Events)
*   **Source Fields:** `customer_id` (String), `bill_date` (String/Date), `net_amount` (Float), `dis_amt` (Float), `is_ok` (Integer).
*   **Logic:** Normalizes records to type `SALE` in the ledger, mapping `net_amount` to `amount` and `dis_amt` to `discount_amount`.
*   **Compatibility Gaps:** None.
*   **Action:** Maintain as-is.

### 2.3 `raw_payments` (formerly `raw_receipts`) $\rightarrow$ `event_ledger` (Payment Events)
*   **Source Fields:** `customer_id` (String), `receipt_date` (String/Date), `amount` (Float), `discount` (Float), `receipt_type` (String), `bank_name` (String), `is_ok` (Integer).
*   **Logic:** Normalizes records to type `PAYMENT` in the ledger. If `discount` is $> 0$, it also generates a side-effect `DISCOUNT` event to account for settled credit.
*   **Compatibility Gaps:** The VGIS backend maps from the table named `raw_receipts`. The target table is named `raw_payments`.
*   **Action:** Rename database table target inside `DBIngestionProvider` and `SyncPipeline` queries from `raw_receipts` to `raw_payments`.

### 2.4 `raw_returns` (formerly `raw_rg`) $\rightarrow$ `event_ledger` (Return Events)
*   **Source Fields:** `customer_id` (String), `rg_date` / `bill_date` (String/Date), `amount` (Float), `rgtype` (String).
*   **Logic:** Maps returns to type `RETURN` in the ledger. Evaluates `rgtype` to determine return responsibility (company vs. customer fault).
*   **Compatibility Gaps:**
    1.  The legacy VGIS backend queries `raw_rg`. The target dataset table is named `raw_returns`.
    2.  `raw_returns` may not contain the `rgtype` column (represented as return goods type). If missing, the return fault weight defaults to `1.0` (penalizing the customer for all returns).
*   **Action:**
    1.  Rename database target queries inside ingestion from `raw_rg` to `raw_returns`.
    2.  Implement a fallback checks: if `rgtype` column does not exist on the target table, default the responsibility mapping to `GENUINE` (exempting the customer) or write a config script to add `rgtype` to the schema.

---

## 3. Data Processing Pipeline Compatibilities

*   **Ledger Generation:** Aligned. The sequence number generation and daily outstanding compiling works seamlessly on standard `event_ledger` records.
*   **Feature Generation:** Aligned. The Polars rolling expression aggregate chains query `event_ledger` event types directly, meaning schema updates do not affect calculation pipelines.
*   **Scoring Compatibility:** Aligned. Once features are generated in the feature store, the scoring orchestrator runs calculations without querying raw tables.

---

## 4. Key Schema Alignment Gaps Checklist

- [ ] Update table identifier `raw_receipts` $\rightarrow$ `raw_payments` inside `app/services/sync_pipeline.py` and `app/ingestion/db_provider.py`.
- [ ] Update table identifier `raw_rg` $\rightarrow$ `raw_returns` inside `app/services/sync_pipeline.py` and `app/ingestion/db_provider.py`.
- [ ] Verify `rgtype` column presence inside the database table `raw_returns`.
- [ ] Implement city flattening inside the bulk query lookup in `orchestrator.py` to prevent crashes when `raw_cities` is missing.
