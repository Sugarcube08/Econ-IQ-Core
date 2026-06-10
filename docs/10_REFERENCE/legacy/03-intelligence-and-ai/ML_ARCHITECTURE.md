# Econiq Practical ML Architecture

**Version:** 2.1.0  
**Status:** Approved  
**Author:** ML Architect & Data Science Lead  
**Owner:** Analytics & ML Team

---

## 1. Practical ML Pipeline

To hit our 2-week hackathon target, we avoid complex deep learning and deploy a lightweight Python FastAPI service that executes pre-trained tabular models:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FEATURE STORE                                 │
│                   (Redis Online Feature Cache)                          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI ML SERVICE                            │
│                                                                         │
│  ┌─────────────────────────┐                 ┌───────────────────────┐  │
│  │ XGBoost Classifier      │                 │ CatBoost Regressor    │  │
│  │ (Default, Churn, Risk)  │                 │ (Collection Prob)     │  │
│  └────────────┬────────────┘                 └───────────┬───────────┘  │
└───────────────┼──────────────────────────────────────────┼──────────────┘
                │ (Probabilities & SHAP Attribution Maps)   │
                ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      POSTGRES PREDICTION CACHE                          │
│            (Read by GraphQL API Gateway for dashboard UI)               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Model Configurations

### 2.1. Default Risk Model (XGBoost)
*   **Objective:** Predict default probability within 90 days of an invoice due date.
*   **Features:** `wdpd_30`, `credit_utilization`, `delay_variance`, `collection_efficiency`.
*   **Output:** $P_{\text{default}} \in [0.0, 1.0]$.

### 2.2. Churn Risk Model (LightGBM)
*   **Objective:** Predict probability of the customer ceasing purchases (no invoice within 60 days).
*   **Features:** `days_since_last_purchase`, `order_frequency_slope`, `sales_vol_ratio`.
*   **Output:** $P_{\text{churn}} \in [0.0, 1.0]$.

### 2.3. Collection Probability (CatBoost)
*   **Objective:** Predict probability of recovering an invoice within 15 days.
*   **Features:** `invoice_amount`, `days_overdue`, `customer_historical_payment_cycle`.
*   **Output:** $P_{\text{collection}} \in [0.0, 1.0]$.

### 2.4. Anomaly & Fraud Detection (Isolation Forest)
*   **Objective:** Flag unusual transaction spikes or strange return ratios.
*   **Features:** `amount`, `payment_mode_variance`, `return_to_sales_ratio`.
*   **Output:** Outlier flag (`1` = normal, `-1` = anomaly).

---

## 3. Explainability Integration (SHAP)

Every inference run calls `shap.TreeExplainer` on the input features to extract local feature contributions. These contributions are saved in the database to explain predictions:

```json
{
  "prediction_type": "DEFAULT_RISK",
  "probability": 0.72,
  "shap_drivers": {
    "credit_utilization": 0.35,  // Highly utilizes credit limit
    "wdpd_30": 0.22,             // Late payments
    "order_frequency": -0.05     // Steady purchasing frequency reduces risk
  }
}
```

---

## 4. Model Registry and Lifecycle

*   **Registry:** Models are versioned and stored as serialized pickle files in the `/ml_models` folder.
*   **Retraining:** Retrained weekly in a cron task. Hyperparameters and test performance metrics (AUC, F1-Score) are logged to local markdown files inside `/ml_runs` (simple, no MLflow overhead for the demo).
*   **Database Schema:**
```sql
CREATE TABLE customer_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    prediction_type VARCHAR(64) NOT NULL,
    predicted_value NUMERIC(10, 4) NOT NULL,
    confidence_score NUMERIC(3, 2) NOT NULL,
    shap_drivers JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```
