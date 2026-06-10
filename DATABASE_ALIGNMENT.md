# Econiq Core: Database Alignment & Schema Mapping Specification

This document defines the schema compatibility and database mapping rules between the legacy VGIS SQLAlchemy models and the target **Econiq Core** PostgreSQL datasets (`customers`, `raw_sales`, `raw_payments`, and `raw_returns`).

---

## 1. Table Mapping & Relations

The ingestion pipeline maps raw data source tables into the standardized event ledger format:

```text
Target Raw Data Tables                 Econiq Core Event Ledger
┌─────────────────────┐                ┌──────────────────────────────────┐
│ customers           │ ─────────────> │ event_ledger (OPENING_BALANCE)   │
├─────────────────────┤                ├──────────────────────────────────┤
│ raw_sales           │ ─────────────> │ event_ledger (SALE)              │
├─────────────────────┤                ├──────────────────────────────────┤
│ raw_payments        │ ─────────────> │ event_ledger (PAYMENT, DISCOUNT) │
├─────────────────────┤                ├──────────────────────────────────┤
│ raw_returns         │ ─────────────> │ event_ledger (RETURN)            │
└─────────────────────┘                └──────────────────────────────────┘
```

---

## 2. Model Compatibility & Mapping Analysis

### 2.1 `customers` $\rightarrow$ `event_ledger` (Opening Balance)
*   **Target Fields:** `customer_id` (String), `customer_name` (String), `opening_balance` (Float).
*   **Ledger Materialization:** When a new customer is sync'd, the ingestion pipeline inserts an `OPENING_BALANCE` event in the `event_ledger` table anchored at date `2000-01-01` with `amount = opening_balance` to initialize their financial history.
*   **Compatibility Gaps:** The legacy system joined `raw_cities` to populate the customer city name in `orchestrator.py` (L311-318). If `raw_cities` is missing in the target database, this join will fail, causing recomputations to crash.
*   **Alignment Strategy:** Inspect database metadata dynamically at startup. If `raw_cities` does not exist in the database, fallback to setting `city = None` in the customer intelligence record.

### 2.2 `raw_sales` $\rightarrow$ `event_ledger` (Sale Events)
*   **Target Fields:** `customer_id` (String), `bill_date` (Date/String), `net_amount` (Float), `dis_amt` (Float), `is_ok` (Integer).
*   **Ledger Materialization:** Normalizes records to type `SALE` in the ledger, mapping `net_amount` to `amount` and `dis_amt` to `discount_amount` in metadata.
*   **Compatibility Gaps:** None.
*   **Alignment Strategy:** Maintain standard normalization.

### 2.3 `raw_payments` (formerly `raw_receipts`) $\rightarrow$ `event_ledger` (Payment Events)
*   **Target Fields:** `customer_id` (String), `receipt_date` (Date/String), `amount` (Float), `discount` (Float), `receipt_type` (String), `bank_name` (String), `is_ok` (Integer).
*   **Ledger Materialization:** Normalizes records to type `PAYMENT` in the ledger. If `discount` is $> 0.0$, it automatically materializes a corresponding `DISCOUNT` event in the ledger to reconcile settled outstanding debt.
*   **Compatibility Gaps:** The legacy backend maps from the table named `raw_receipts`. The target database table is named `raw_payments`.
*   **Alignment Strategy:** Rename database table target inside `DBIngestionProvider` and `SyncPipeline` queries from `raw_receipts` to `raw_payments`.

### 2.4 `raw_returns` (formerly `raw_rg`) $\rightarrow$ `event_ledger` (Return Events)
*   **Target Fields:** `customer_id` (String), `rg_date` / `bill_date` (Date/String), `amount` (Float), `rgtype` (String).
*   **Ledger Materialization:** Maps returns to type `RETURN` in the ledger. Uses the returns type (`rgtype`) to determine return responsibility (Genuine vs. Customer fault).
*   **Compatibility Gaps:**
    1.  The legacy VGIS backend queries `raw_rg`. The target dataset table is named `raw_returns`.
    2.  `raw_returns` may not contain the `rgtype` column (representing returns classification). If missing, the return fault weight defaults to `1.0` (penalizing the customer for all returns).
*   **Alignment Strategy:**
    1.  Rename database target queries inside ingestion from `raw_rg` to `raw_returns`.
    2.  Implement a fallback check: if `rgtype` column does not exist on the target table, default the responsibility mapping to `GENUINE` (exempting the customer from credit rating penalties) or load a dynamic mapping table.

---

## 3. Data Processing Pipeline Compatibility

*   **Ledger Generation:** Aligned. The sequence number generation and daily outstanding compiling works on standard `event_ledger` records and is fully compatible.
*   **Feature Generation:** Aligned. The Polars rolling expression aggregate chains query `event_ledger` event types directly, meaning schema updates do not affect calculation pipelines.
*   **Scoring Compatibility:** Aligned. Once features are generated in the feature store, the scoring orchestrator runs calculations without querying raw tables.

---

## 4. Master Schema Gap Checklist

> [!WARNING]
> Prior to executing the migration script, verify the following database table conditions:

- [ ] Rename table query identifiers from `raw_receipts` to `raw_payments` inside `core/ingestion/db_provider.py` and `core/ingestion/sync_pipeline.py`.
- [ ] Rename table query identifiers from `raw_rg` to `raw_returns` inside `core/ingestion/db_provider.py` and `core/ingestion/sync_pipeline.py`.
- [ ] Rename table query identifiers from `raw_customers` to `customers` inside `core/ingestion/db_provider.py` and `core/ingestion/sync_pipeline.py`.
- [ ] Implement city metadata fallback check in `core/intelligence/orchestrator.py` to check for `raw_cities` presence before joining.
- [ ] Implement dynamic fallback check in `core/ingestion/db_provider.py` for `rgtype` presence in `raw_returns` (default to `GENUINE` returned goods weight if column does not exist).
- [ ] Ensure all target tables contain a primary key or sequential timestamp index (e.g. `raw_id` or `created_at`) to enable incremental synchronization; if absent, execute fallback to full sync updates in `SyncPipeline`.
