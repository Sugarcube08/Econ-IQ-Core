# Econiq AI/ML Readiness Audit

**Version:** 1.0.0  
**Status:** Completed  
**Author:** ML Platform Architect & Data Science Lead  
**Owner:** Core Engineering Team

---

## 1. Core ML Features Availability

The database schema and Polars feature extraction layer (`app/features/engineer.py`) compile key input variables:

| Feature Variable | Source Table | Frequency | Description |
| :--- | :--- | :--- | :--- |
| `payment_delay_mean` | `event_ledger` | Daily | Mean payment delay. |
| `payment_delay_var` | `event_ledger` | Daily | Variance in payment cycles. |
| `outstanding_bal` | `event_ledger` | Real-time | Current outstanding balance. |
| `credit_utilization` | `customers` | Real-time | Balance divided by credit limit. |
| `order_frequency` | `event_ledger` | Monthly | Invoice count. |
| `return_ratio` | `event_ledger` | Weekly | Returns divided by total sales. |

---

## 2. Model Feasibility Matrix

We evaluate our readiness to train and deploy models for the 2-week hackathon:

| Prediction / Model | Readiness Status | Input Features | Target Label Source | Missing Requirements / Actions |
| :--- | :--- | :--- | :--- | :--- |
| **Risk Prediction** | `READY` | `payment_delay_mean`, `credit_utilization`, `delay_variance`. | Customer is tagged `Grade D` or default event occurs ($>90$ days delay). | Correct `is_ok` mapping to populate outstanding balances. |
| **Churn Prediction** | `READY` | `order_frequency_slope`, `days_since_last_purchase`. | No new invoice created in subsequent 60 days. | Seeding synthetic cohort data to train the model. |
| **Growth Prediction** | `PARTIALLY READY`| `sales_volume_growth_90d`, `order_frequency`. | Sales volume increases by $>30\%$ in subsequent 90 days. | Needs historical logs ($>6$ months) to establish growth baselines. |
| **Collection Probability**| `READY` | `invoice_amount`, `days_overdue`, `avg_payment_delay`. | Invoice is settled within 15 days of warning. | Map target labels from payment receipt records. |
| **Health Prediction** | `READY` | Fused score based on risk, stability, and growth. | None (Heuristic combination). | Implement the composite Health scorecard. |
| **Anomaly Detection** | `READY` | `amount`, `payment_mode_variance`, `return_to_sales_ratio`. | Unsupervised (no label needed). | Integrate scikit-learn's `IsolationForest` module. |

---

## 3. Explainability and Telemetry

Econiq model designs enforce **traceable predictions**:
1.  **SHAP Attribution:** FastAPI inference loops evaluate local feature contributions (SHAP values) on-the-fly.
2.  **Explainability Records:** Prediction outputs are stored in `customer_predictions` alongside the SHAP feature contributions, enabling credit analysts to audit why a rating was assigned.
