# FEATURE LINEAGE MATRIX (V2)

This matrix defines the end-to-end lineage flow of Econiq Core. It certifies trace paths from raw database signal inputs to features, consolidated dimensions, canonical scores, automated recommendations, and model predictions.

---

## 1. Flow Trajectory Diagram

```
[ Raw Database Signals ]
         |
         v
[ Rolling Features ]
         |
         v
[ 8 Consolidated B2B Dimensions ]
         |
         v
[ 8 Public Canonical Scores ]
         +-------------------+--------------------+
         |                                        |
         v                                        v
[ ML Predictions ]                      [ Action Recommendations ]
```

---

## 2. End-to-End Lineage Matrix

This matrix maps all 24 canonical features to their consolidated dimensions, score influence, and downstream outputs:

| Signal (Input) | Feature (Store) | Dimension (Internal) | Score (Serving) | Recommendation (Output) | Prediction (Target) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PUR_REC** | `last_purchased_at` | Activity | Health, Growth | `PROACTIVE_RETENTION` | Churn |
| **PUR_FRQ** | `sales_window` | Activity | Health, Growth, Credit, Collection, Relationship | `INCREASE_CREDIT_LIMIT` | Growth |
| **PUR_FRQ** | `sales_events_window` | Activity | Health, Growth, Relationship | `INCREASE_CREDIT_LIMIT` | Growth |
| **PUR_FRQ** | `purchase_days` | Activity | Health, Growth, Relationship | None | Growth |
| **PUR_FRQ** | `participation_density` | Activity, Stability | Health, Trust, Relationship | `PROACTIVE_RETENTION` | Churn |
| **PUR_FRQ** | `sales_recent` | Growth | Growth, Opportunity | `INCREASE_CREDIT_LIMIT` | Growth |
| **PUR_FRQ** | `sales_events_recent` | Growth | Growth, Opportunity | None | Growth |
| **PUR_VAL_MDN**| `log_sales_scale` | Activity | Growth, Credit | `INCREASE_CREDIT_LIMIT` | Opportunity |
| **PUR_VAL_MDN**| `category_diversity_count`| Product | Growth, Opportunity | `INCREASE_CREDIT_LIMIT` | Opportunity |
| **PUR_VAL_MDN**| `product_diversity_count` | Product | Growth, Opportunity | `INCREASE_CREDIT_LIMIT` | Opportunity |
| **PAY_DPD_AVG**| `payments_window` | Discipline | Risk, Trust, Credit, Collection, Health | `EXTEND_PAYMENT_TERMS` | Collection |
| **PAY_FRG_IDX**| `payments_events_window`| Discipline | Trust, Collection | `EXTEND_PAYMENT_TERMS` | Collection |
| **PAY_FRG_IDX**| `payment_modes_window` | Discipline | Trust | `EXTEND_PAYMENT_TERMS` | Collection |
| **PAY_CR_UTIL**| `credit_limit_window` | Credit | Risk, Credit, Collection | `DECREASE_CREDIT_LIMIT` | Risk |
| **OPR_RET_VOL**| `returns_value_window` | Friction | Health, Risk | `TIGHTEN_PAYMENT_TERMS` | Risk |
| **OPR_RET_VOL**| `returns_events_window` | Friction | Health, Risk | `TIGHTEN_PAYMENT_TERMS` | Risk |
| **OPR_RET_VOL**| `penalty_window` (Alias) | Friction | Health, Risk | `TIGHTEN_PAYMENT_TERMS` | Risk |
| **NET_LOY_AGE**| `business_age_days` | Stability | Health, Risk, Trust, Relationship | `PROACTIVE_RETENTION` | Churn |
| **NET_LOY_AGE**| `registration_date` | Stability | Relationship | `PROACTIVE_RETENTION` | Churn |
| **NET_PEER_RNK**| `business_type` | Stability | Relationship, Growth | None | Opportunity |
| **All Active** | `events_window` | Stability | Health, Risk, Trust, Relationship | `PROACTIVE_RETENTION` | Churn |
| **All Active** | `events_recent` | Growth | Growth, Opportunity | None | Churn |
| **All Active** | `active_duration_days` | Relationship, Stability| Health, Trust, Relationship | `PROACTIVE_RETENTION` | Churn |

---

## 3. Architecture Lineage Certifications

We certify that the following assertions are true:
* **No Orphan Features**: Every feature computed in the feature store is mapped to at least one consolidated dimension and participates in score generation.
* **No Duplicate Paths**: Each feature contributes to a unique subset of scores; no identical parallel pipelines exist.
* **No Circular Influence**: The graph flows strictly from Raw Signals $\to$ Features $\to$ Dimensions $\to$ Scores $\to$ Recommendations/Predictions. No score feedback loops back to modify features.
* **No Hidden Scoring**: No ad-hoc or hardcoded score modifiers exist outside of the dimensions and meta-score configurations.
* **No Undocumented Transformations**: All mathematical transformations (e.g., logarithmic scaling, min-max normalization) are explicit in feature formulas and engineered code.
