# Database Schema Alignment & Ingestion Mapping

This document maps the legacy econiq database models to the actual **Econiq Core** data source tables (`customers`, `raw_sales`, `raw_payments`, and `raw_returns`) and defines the schema conversions required.

---

## 1. Raw Ingestion Mapping Matrix

The ingestion pipeline will shift from the legacy econiq raw tables to the Econiq database schema as follows:

| Legacy econiq Table | Econiq Target Table | Primary Mapping Fields | Action | Semantic Mapping Rule |
| :--- | :--- | :--- | :---: | :--- |
| `raw_customers` | `customers` | `customer_id` $\rightarrow$ `customer_id`<br>`customer_name` $\rightarrow$ `customer_name`<br>`opening_balance` $\rightarrow$ `opening_balance` | **Rename & Flatten** | Flatten city fields; map city name directly if available in the `customers` table instead of joining a separate `raw_cities` lookup. |
| `raw_sales` | `raw_sales` | `customer_id` $\rightarrow$ `customer_id`<br>`bill_date` $\rightarrow$ `event_date`<br>`net_amount` $\rightarrow$ `amount`<br>`dis_amt` $\rightarrow$ `discount_amount`<br>`is_ok` $\rightarrow$ `is_ok` | **Keep & Wrap** | Standardize date parsing format. Ensure `is_ok` is read correctly as transaction state indicator. |
| `raw_receipts` | `raw_payments` | `customer_id` $\rightarrow$ `customer_id`<br>`receipt_date` $\rightarrow$ `event_date`<br>`amount` $\rightarrow$ `amount`<br>`discount` $\rightarrow$ `discount_amount`<br>`receipt_type` $\rightarrow$ `payment_mode`<br>`bank_name` $\rightarrow$ `bank_name` | **Rename & Wrap** | Rename source table to match standard payments naming convention. Maintain mode and bank fields. |
| `raw_rg` | `raw_returns` | `customer_id` $\rightarrow$ `customer_id`<br>`rg_date` / `bill_date` $\rightarrow$ `event_date`<br>`amount` $\rightarrow$ `amount`<br>`rgtype` $\rightarrow$ `rg_responsibility` | **Rename & Wrap** | Map `rgtype` strings: `"genuine"` $\rightarrow$ `GENUINE` (no scoring penalty); `"customer rg"` $\rightarrow$ `CUSTOMER` (scoring penalty). |

---

## 2. Ingestion State Tracking DDL Upgrade

To allow the asynchronous `SyncPipeline` to track row-level ingestion processing without double-counting transactions, the target Econiq raw tables must be upgraded to include metadata state columns.

### DDL Migration SQL Script
Run the following SQL DDL statements on the target PostgreSQL database to prepare the tables:

```sql
-- 1. Upgrade customers
ALTER TABLE customers ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS processing_attempts INTEGER DEFAULT 0;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_processing_error TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;

-- 2. Upgrade raw_sales
ALTER TABLE raw_sales ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE raw_sales ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(255);
ALTER TABLE raw_sales ADD COLUMN IF NOT EXISTS processing_attempts INTEGER DEFAULT 0;
ALTER TABLE raw_sales ADD COLUMN IF NOT EXISTS last_processing_error TEXT;
ALTER TABLE raw_sales ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;

-- 3. Upgrade raw_payments
ALTER TABLE raw_payments ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE raw_payments ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(255);
ALTER TABLE raw_payments ADD COLUMN IF NOT EXISTS processing_attempts INTEGER DEFAULT 0;
ALTER TABLE raw_payments ADD COLUMN IF NOT EXISTS last_processing_error TEXT;
ALTER TABLE raw_payments ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;

-- 4. Upgrade raw_returns
ALTER TABLE raw_returns ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE raw_returns ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(255);
ALTER TABLE raw_returns ADD COLUMN IF NOT EXISTS processing_attempts INTEGER DEFAULT 0;
ALTER TABLE raw_returns ADD COLUMN IF NOT EXISTS last_processing_error TEXT;
ALTER TABLE raw_returns ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;

-- 5. Add performance indexes for processing updates
CREATE INDEX IF NOT EXISTS idx_sales_processed ON raw_sales (is_processed, processing_attempts);
CREATE INDEX IF NOT EXISTS idx_payments_processed ON raw_payments (is_processed, processing_attempts);
CREATE INDEX IF NOT EXISTS idx_returns_processed ON raw_returns (is_processed, processing_attempts);
```

---

## 3. Core Ledger & Intelligence Mapping

Once synced, the ingestion provider normalizes raw records into `EventLedger`, which is subsequently analyzed and persisted in `CustomerIntelligence`. No schema changes are required for these table structures:

```text
raw_sales (Econiq)  ─────┐
raw_payments (Econiq)  ──┼──> Normalized Ingestion ──> event_ledger (Core Table)
raw_returns (Econiq)  ───┘                                   │
                                                          Polars Feature Engineer
                                                             │
                                                             ▼
                                                    customer_intelligence (Core Table)
```

### 3.1 `event_ledger` Core Table Mapping
*   `event_id`: Unique hash generating primary key (`UUIDv4`).
*   `customer_id`: Target customer identifier.
*   `event_type`: Invariant value: `SALE`, `PAYMENT`, `RETURN`, `OPENING_BALANCE`, `DISCOUNT`.
*   `event_date`: Calendar date of execution.
*   `amount`: Transaction worth.
*   `is_ok`: Ingest status flag (retained to maintain historical ledgers).

### 3.2 `customer_intelligence` Scoring Output Table Mapping
This table serves the frontend widgets and APIs:
*   `customer_id`: Primary key.
*   `customer_name` / `city`: Identity details.
*   `trust_score` / `purchase_score` / `payment_score` / `rg_score`: Calculated metrics.
*   `state` / `outstanding_current` / `contribution_current`: Financial status metrics.
*   `trust_previous` / `purchase_previous` / `payment_previous`: Rolling historical comparisons.

> [!IMPORTANT]
> The automatic schema verification hook in [sync_pipeline.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/services/sync_pipeline.py#L29-L54) must be updated to target `raw_payments` and `raw_returns` instead of `raw_receipts` and `raw_rg`.
