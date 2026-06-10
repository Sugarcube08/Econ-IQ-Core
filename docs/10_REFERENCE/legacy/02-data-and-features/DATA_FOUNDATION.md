# Econiq Data Foundation & Feature Map

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Data Science Lead & Startup CTO  
**Owner:** Core Engineering Team

---

## 1. Relational Database Schema

Econiq relies on the transactional tables inside our PostgreSQL database:

```
                  ┌───────────────────────────────┐
                  │          CUSTOMERS            │
                  └───────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│    INVOICES     │      │    PAYMENTS     │      │    RETURNS      │
│ (Sales debits)  │      │ (Cash credits)  │      │ (Credit notes)  │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### 1.1. Customer Metadata (`customers`)
```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    erp_ledger_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    tax_identifier VARCHAR(64),
    credit_limit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    credit_period_days INT NOT NULL DEFAULT 30,
    outstanding_balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
```

### 1.2. Invoices (`invoices`)
```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    invoice_number VARCHAR(128) NOT NULL,
    issued_date DATE NOT NULL,
    due_date DATE NOT NULL,
    net_amount NUMERIC(15, 2) NOT NULL,
    paid_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(64) NOT NULL DEFAULT 'UNPAID'
);
```

### 1.3. Payments (`payments`)
```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    receipt_number VARCHAR(128) NOT NULL,
    payment_date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    payment_mode VARCHAR(64) NOT NULL
);
```

### 1.4. Returns (`returns`)
```sql
CREATE TABLE returns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    credit_note_number VARCHAR(128) NOT NULL,
    return_date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL
);
```

---

## 2. Synthetic Data Simulation Assumptions

To deliver a compelling hackathon demonstration, we seed PostgreSQL with synthetic ledger records:
1.  **Time Depth:** Simulate 12 months of daily transactions per customer.
2.  **Risk Scenarios:**
    *   *Cohort A (Healthy):* Constant purchases, average payment delay $< 5$ days past due.
    *   *Cohort B (Delinquent/Risky):* Increasing payment delay variance, utilization $> 95\%$.
    *   *Cohort C (Churning):* Purchasing frequency drops to zero over the last 60 days.
3.  **Data Inconsistencies:** 5% of records are generated with typos (e.g. "Sharma Tex" vs "Sharma Textiles") to demonstrate fuzzy resolution.

---

## 3. Data Quality Score Heuristics

Econiq calculates a Data Quality Score (DQS) during sync runs:

$$\text{DQS} = \frac{\text{Vouchers successfully matched to canonical models}}{\text{Total sync rows}} \times 100$$

*   *DQS < 90%:* Generates an operational warning.
*   *DQS < 70%:* Pauses downstream ML scoring updates for that customer.

---

## 4. Feature Generation Blueprint

The database state is compiled into numerical inputs for modeling:

```
[Raw SQL Queries on PostgreSQL] ──(Hourly cron task)──► [Redis Feature Cache]
                                                               │
                                                               ├─► serve API
                                                               └─► serve ML Models
```

1.  **Payment Delay:** Average difference between payment date and invoice due date.
2.  **Average Outstanding:** Mean balance carried over a 90-day window.
3.  **Order Frequency:** Invoice count per month.
4.  **Credit Utilization:** `outstanding_balance / credit_limit`.
5.  **Return Ratio:** `returns_amount / sales_amount`.
