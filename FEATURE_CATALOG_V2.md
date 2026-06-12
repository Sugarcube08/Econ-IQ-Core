# FEATURE CATALOG (V2)

This catalog details all 24 rolling temporal features computed by the feature store engine. Each feature is audited and mapped from raw database signals to consolidated B2B dimensions, canonical scores, ML predictions, and explainability boundaries.

---

## 1. Feature Specifications & Audit Matrix

### 1. `sales_window`
* **Business Purpose**: Measures aggregate commercial trade volume.
* **Formula**: $\sum \text{Amount} \text{ where event\_type} = \text{"SALE"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PUR_FRQ`, `PUR_VAL_MDN`
* **Dimension Mapping**: Activity
* **Score Mapping**: Health, Growth, Credit, Collection, Relationship
* **Prediction Usage**: Risk, Growth, Opportunity, Health, Collection
* **Explainability Usage**: SHAP driver charts, sales scale indicator
* **Status**: **Retain**

### 2. `payments_window`
* **Business Purpose**: Measures cash recovery volume.
* **Formula**: $\sum \text{Amount} \text{ where event\_type} = \text{"PAYMENT"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PAY_DPD_AVG`, `PAY_DPD_MAX`, `PAY_FRG_IDX`
* **Dimension Mapping**: Discipline
* **Score Mapping**: Risk, Trust, Credit, Collection, Health
* **Prediction Usage**: Risk, Health, Collection, Churn
* **Explainability Usage**: Repayment health timelines
* **Status**: **Retain**

### 3. `returns_value_window`
* **Business Purpose**: Measures negative logistics/return volume.
* **Formula**: $\sum \text{Amount} \text{ where event\_type} = \text{"RETURN"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `OPR_RET_VOL`, `OPR_RET_FLT`
* **Dimension Mapping**: Friction
* **Score Mapping**: Health, Risk
* **Prediction Usage**: Risk, Health
* **Explainability Usage**: Dispute and dispute resolution indicators
* **Status**: **Retain**

### 4. `events_window`
* **Business Purpose**: Measures interaction volume and event density.
* **Formula**: $\text{Count}(\text{events})$ over $T=365\text{d}$.
* **Signal Dependencies**: All active signals
* **Dimension Mapping**: Stability
* **Score Mapping**: Health, Risk, Trust, Relationship
* **Prediction Usage**: Risk, Churn
* **Explainability Usage**: Activity density charts
* **Status**: **Retain**

### 5. `sales_events_window`
* **Business Purpose**: Frequency of purchase events indicating order rhythm.
* **Formula**: $\text{Count}(\text{events}) \text{ where event\_type} = \text{"SALE"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PUR_FRQ`
* **Dimension Mapping**: Activity, Product
* **Score Mapping**: Health, Growth, Relationship
* **Prediction Usage**: Growth, Opportunity
* **Explainability Usage**: Ordering rate trends
* **Status**: **Retain**

### 6. `payments_events_window`
* **Business Purpose**: Frequency of repayment actions.
* **Formula**: $\text{Count}(\text{events}) \text{ where event\_type} = \text{"PAYMENT"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PAY_FRG_IDX`
* **Dimension Mapping**: Discipline
* **Score Mapping**: Trust, Collection
* **Prediction Usage**: Collection
* **Explainability Usage**: Repayment cadence charts
* **Status**: **Retain**

### 7. `returns_events_window`
* **Business Purpose**: Return event frequency indicating order execution disputes.
* **Formula**: $\text{Count}(\text{events}) \text{ where event\_type} = \text{"RETURN"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `OPR_RET_VOL`
* **Dimension Mapping**: Friction
* **Score Mapping**: Health, Risk
* **Prediction Usage**: Risk
* **Explainability Usage**: Quality dispute rate
* **Status**: **Retain**

### 8. `category_diversity_count`
* **Business Purpose**: Width of product categories purchased, representing vendor locking.
* **Formula**: $\text{Distinct}(\text{product\_category}) \text{ where event\_type} = \text{"SALE"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PUR_VAL_MDN`
* **Dimension Mapping**: Product (Concentration merged)
* **Score Mapping**: Growth, Opportunity
* **Prediction Usage**: Opportunity
* **Explainability Usage**: Category gap charts
* **Status**: **Retain**

### 9. `product_diversity_count`
* **Business Purpose**: Granular SKU count representing item diversity.
* **Formula**: $\text{Distinct}(\text{product\_name}) \text{ where event\_type} = \text{"SALE"}$ over $T=365\text{d}$.
* **Signal Dependencies**: `PUR_VAL_MDN`
* **Dimension Mapping**: Product (Concentration merged)
* **Score Mapping**: Growth, Opportunity
* **Prediction Usage**: Opportunity
* **Explainability Usage**: SKU diversity indices
* **Status**: **Retain**

### 10. `payment_modes_window`
* **Business Purpose**: Ingested types of payment instruments.
* **Formula**: Array list of payment types (Cash, Bank Draft, Card, etc.) over $T=365\text{d}$.
* **Signal Dependencies**: `PAY_FRG_IDX`
* **Dimension Mapping**: Discipline (Payment Mode dimension consolidated)
* **Score Mapping**: Trust
* **Prediction Usage**: Collection
* **Explainability Usage**: Payment instrument breakdown
* **Status**: **Refactor** (Consolidated under Discipline dimension)

### 11. `registration_date`
* **Business Purpose**: Date the customer account was first registered.
* **Formula**: $\text{First}(\text{registration\_date})$ from static customer profile.
* **Signal Dependencies**: `NET_LOY_AGE`
* **Dimension Mapping**: Stability (Maturity dimension consolidated)
* **Score Mapping**: Relationship
* **Prediction Usage**: Churn
* **Explainability Usage**: Lifetime registration date
* **Status**: **Retain**

### 12. `business_type`
* **Business Purpose**: Customer category tier (e.g., wholesaler, retailer, distributor).
* **Formula**: $\text{First}(\text{business\_type})$ from static customer profile.
* **Signal Dependencies**: `NET_PEER_RNK`
* **Dimension Mapping**: Stability (Maturity dimension consolidated)
* **Score Mapping**: Relationship, Growth
* **Prediction Usage**: Opportunity, Growth
* **Explainability Usage**: Peer segment benchmarks
* **Status**: **Retain**

### 13. `credit_limit_window`
* **Business Purpose**: Approved maximum outstanding exposure boundary.
* **Formula**: Active approved credit limit.
* **Signal Dependencies**: `PAY_CR_UTIL`
* **Dimension Mapping**: Credit
* **Score Mapping**: Risk, Credit, Collection
* **Prediction Usage**: Risk, Collection
* **Explainability Usage**: Limit utilization ratios
* **Status**: **Retain**

### 14. `purchase_days`
* **Business Purpose**: Active trading days inside the window.
* **Formula**: $\text{Count}(\text{unique dates}) \text{ where daily\_sales} > 0.0$ over $T=365\text{d}$.
* **Signal Dependencies**: `PUR_FRQ`
* **Dimension Mapping**: Activity
* **Score Mapping**: Health, Growth, Relationship
* **Prediction Usage**: Growth, Churn
* **Explainability Usage**: Active purchase days count
* **Status**: **Retain**

### 15. `active_duration_days`
* **Business Purpose**: Interval span of customer interaction activity.
* **Formula**: $\text{MaxDate} - \text{MinDate} \text{ in window}$.
* **Signal Dependencies**: All active signals
* **Dimension Mapping**: Relationship, Stability
* **Score Mapping**: Relationship, Trust, Health
* **Prediction Usage**: Churn
* **Explainability Usage**: Historical activity duration span
* **Status**: **Retain**

### 16. `last_purchased_at`
* **Business Purpose**: Date of the latest purchase event.
* **Formula**: $\max(\text{event\_date}) \text{ where event\_type} = \text{"SALE"}$
* **Signal Dependencies**: `PUR_REC`
* **Dimension Mapping**: Activity
* **Score Mapping**: Health, Growth
* **Prediction Usage**: Churn, Risk
* **Explainability Usage**: Recency metrics (days since purchase)
* **Status**: **Retain**

### 17. `log_sales_scale`
* **Business Purpose**: Normalizes sales volume outliers for ML neural feeds.
* **Formula**: $\log_{10}(\text{sales\_window} + 1.0)$
* **Signal Dependencies**: `PUR_VAL_MDN`
* **Dimension Mapping**: Activity
* **Score Mapping**: Credit, Growth
* **Prediction Usage**: Risk, Growth
* **Explainability Usage**: Log-scaled sales volume charts
* **Status**: **Retain**

### 18. `participation_density`
* **Business Purpose**: Proportion of rolling active window days where trading occurred.
* **Formula**: `purchase_days` / max(`active_duration_days`, 1.0)
* **Signal Dependencies**: `PUR_FRQ`
* **Dimension Mapping**: Activity, Stability
* **Score Mapping**: Health, Stability, Trust
* **Prediction Usage**: Churn, Growth
* **Explainability Usage**: Trade frequency density
* **Status**: **Retain**

### 19. `net_revenue_window`
* **Business Purpose**: Standard net revenue after deducting returns.
* **Formula**: `sales_window` - `returns_value_window`
* **Signal Dependencies**: `PUR_FRQ`, `OPR_RET_VOL`
* **Dimension Mapping**: Activity (Value dimension consolidated)
* **Score Mapping**: Growth, Opportunity, Credit, Relationship
* **Prediction Usage**: Growth, Churn
* **Explainability Usage**: Net revenue generation trends
* **Status**: **Refactor** (Consolidated under Activity dimension)

### 20. `business_age_days`
* **Business Purpose**: Total relationship tenure in days.
* **Formula**: $\text{CurrentDate} - \text{registration\_date}$
* **Signal Dependencies**: `NET_LOY_AGE`
* **Dimension Mapping**: Stability (Maturity dimension consolidated)
* **Score Mapping**: Relationship, Trust
* **Prediction Usage**: Churn
* **Explainability Usage**: Relationship lifespan tenure
* **Status**: **Refactor** (Consolidated under Stability dimension)

### 21. `sales_recent`
* **Business Purpose**: Recency sales indicator to evaluate short-term velocity.
* **Formula**: $\sum \text{Amount} \text{ where event\_type} = \text{"SALE"}$ in recent 20% window.
* **Signal Dependencies**: `PUR_FRQ`
* **Dimension Mapping**: Growth
* **Score Mapping**: Growth, Opportunity
* **Prediction Usage**: Growth, Opportunity
* **Explainability Usage**: Short-term sales velocity charts
* **Status**: **Retain**

### 22. `events_recent`
* **Business Purpose**: Recent interaction event volume.
* **Formula**: $\text{Count}(\text{events}) \text{ in recent 20\% window}$.
* **Signal Dependencies**: All active signals
* **Dimension Mapping**: Growth
* **Score Mapping**: Health, Growth
* **Prediction Usage**: Churn
* **Explainability Usage**: Recent interaction frequency
* **Status**: **Retain**

### 23. `sales_events_recent`
* **Business Purpose**: Count of purchase events in the short term.
* **Formula**: $\text{Count}(\text{events}) \text{ where event\_type} = \text{"SALE"}$ in recent 20% window.
* **Signal Dependencies**: `PUR_FRQ`
* **Dimension Mapping**: Growth
* **Score Mapping**: Growth, Opportunity
* **Prediction Usage**: Growth
* **Explainability Usage**: Recent sales count trends
* **Status**: **Retain**

### 24. `penalty_window`
* **Business Purpose**: Outdated name for returns value window (backward compatibility).
* **Formula**: Identical to `returns_value_window`.
* **Signal Dependencies**: `OPR_RET_VOL`
* **Dimension Mapping**: Friction
* **Score Mapping**: Health, Risk
* **Prediction Usage**: Risk
* **Explainability Usage**: Downstream compatibility alias
* **Status**: **Deprecated** (Retained purely for backward-compatibility alias)
