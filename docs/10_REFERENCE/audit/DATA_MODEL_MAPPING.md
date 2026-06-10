# Econiq Data Model & Contract Mapping

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Data Platform Architect & Startup CTO  
**Owner:** Core Engineering Team

---

## 1. Table and Model Transitions

This section maps the current PostgreSQL tables to their target equivalents in **Econiq**:

| Current Table / Model | Target Table / Model | Action | Detailed Migration Logic |
| :--- | :--- | :--- | :--- |
| `users` | `users` | `KEEP` | Re-use auth properties and password hashes. |
| `api_keys` | `api_keys` | `KEEP` | Re-use API headers and scope access lists. |
| `raw_sales` | `invoices` | `REFACTOR` | Map fields to target invoice structures, resolving dates. |
| `raw_receipts` | `payments` | `REFACTOR` | Map receipt records to payments with clean sign mappings. |
| `raw_rg` | `returns` | `REFACTOR` | Map return transactions, standardizing amounts. |
| `raw_customers` | `customers` | `MODIFY` | Keep metadata, but link customer IDs to unified `economic_identity_id` keys. |
| `event_ledger` | `customer_timeline_events` | `RENAME / REFACTOR` | Rename to `customer_timeline_events`, add bi-temporal columns (`valid_time`, `system_time`), and swap `is_ok` mapping values. |
| `customer_intelligence` | `customer_scores` | `RENAME / REFACTOR` | Split into normalized score history tables, preserving explainability drivers. |
| `sync_state` | `sync_state` | `KEEP` | Keep to track sync job offsets. |

---

## 2. API Schema / DTO Transitions

We transition the endpoints payload structures as follows:

### 2.1. Customer Details Schema
*   **Current Schema (`app/schemas/customers.py`):**
```python
class CustomerResponse(BaseModel):
    customer_id: str
    customer_name: str
    trust_score: float
    state: str
    outstanding_current: float
```
*   **Target Schema (`docs/API_ARCHITECTURE.md`):**
```python
class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    economic_identity_id: str
    outstanding_balance: float
    credit_limit: float
    active_scores: list[ScorePayload]
    active_predictions: list[PredictionPayload]
    active_recommendations: list[RecommendationPayload]
```
*   *Action:* **Refactor**. Update API query layers to join resolved prediction and recommendation tables.

### 2.2. Ingest payload Schema
*   **Current Schema:** Flat imports of voucher sequences.
*   **Target Schema:** Kept as-is to preserve Tally connector integration compatibility, using Go normalizers to populate postgres tables.

---

## 3. Database Updates (PostgreSQL Migration Script)

To fix the critical `is_ok` semantic bug, the database update script must be executed on both DEV and PROD:

```sql
-- 1. Swap is_ok values in raw tables
UPDATE raw_sales SET is_ok = CASE WHEN is_ok = 1 THEN 0 ELSE 1 END;
UPDATE raw_receipts SET is_ok = CASE WHEN is_ok = 1 THEN 0 ELSE 1 END;
UPDATE raw_rg SET is_ok = CASE WHEN is_ok = 1 THEN 0 ELSE 1 END;

-- 2. Swap is_ok values in event_ledger
UPDATE event_ledger SET is_ok = CASE WHEN is_ok = 1 THEN 0 ELSE 1 END;

-- 3. Clear recomputation queue to force fresh runs
TRUNCATE customer_recomputation_queue;
INSERT INTO customer_recomputation_queue (customer_id, priority, status)
SELECT DISTINCT customer_id, 10, 'PENDING' FROM event_ledger;
```
