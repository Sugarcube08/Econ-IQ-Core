# Econiq Feature Store Architecture

**Version:** 2.1.0  
**Status:** Approved  
**Author:** ML Architect & Data Platform Architect  
**Owner:** Analytics & ML Team

---

## 1. Feature Cache Strategy

For the hackathon, we bypass columnar databases (ClickHouse) and manage features in a unified, low-latency **Redis Online Feature Cache**. This ensures that the FastAPI inference service can hydrate feature inputs within milliseconds.

```
[PostgreSQL Database] ──(Go worker calculates aggregates)──► [Redis Cache]
                                                                  │
                                                                  ▼
                                                       [Inference Engine API]
```

---

## 2. Core Feature Catalog

Below are the feature variables registered for the modeling pipeline:

| Feature Key | Type | Description | Target Model |
| :--- | :--- | :--- | :--- |
| `payment_delay_mean` | `FLOAT` | Mean days past due for settled invoices. | Default Risk |
| `payment_delay_variance` | `FLOAT` | Standard deviation of payment delays. | Default Risk, Churn |
| `outstanding_average_90d`| `DECIMAL`| Mean unpaid balance carried over 90 days. | Default Risk, Churn |
| `order_frequency_slope` | `FLOAT` | Linear trend of invoice counts (last 60 days).| Churn, Growth |
| `sales_volume_growth_90d`| `FLOAT` | Percentage change in purchasing volumes. | Growth |
| `return_to_sales_ratio` | `FLOAT` | Returns value divided by total gross sales. | Anomalies, Default |
| `credit_utilization_ratio`| `FLOAT` | Outstanding balance divided by credit limit. | Default Risk |
| `collection_efficiency` | `FLOAT` | Percentage of outstanding debts recovered. | Default Risk, Churn |

---

## 3. Ingestion and Refresh Strategy

*   **Real-time Feature Trigger:** Computed inline when a sync job finishes processing (`sync.jobs.raw` consumer).
*   **Batch Feature Sync:** A scheduler job runs daily at 00:01 local time to update historical metrics (e.g. `order_frequency_slope`).
*   **Data Lineage Schema (Redis Key Structure):**
    *   `Key Name:` `tenant:{tenant_id}:customer:{customer_id}:features`
    *   `TTL:` 48 Hours (automatically re-hydrated on dashboard access or sync runs).
    *   `Value format:` Serialized JSON string of the feature registry mapping.

### Sample Redis Payload:
```json
{
  "customer_id": "a6b7c8d9-e0f1-4a2b-8c3d-4e5f6a7b8c9d",
  "updated_at": "2026-06-10T18:50:00Z",
  "features": {
    "payment_delay_mean": 12.4,
    "payment_delay_variance": 4.1,
    "outstanding_average_90d": 45000.00,
    "order_frequency_slope": -0.12,
    "sales_volume_growth_90d": -0.15,
    "return_to_sales_ratio": 0.02,
    "credit_utilization_ratio": 0.92,
    "collection_efficiency": 0.68
  }
}
```
