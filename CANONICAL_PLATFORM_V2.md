# CANONICAL PLATFORM CONTRACT (V2)

This document is the authoritative platform contract for the Econiq Core behavioral intelligence runtime. It outlines the state of every signal, feature, dimension, score, recommendation, and prediction, clarifying whether they are implemented, planned, deprecated, or removed.

---

## 1. Canonical Signals

Signals represent raw ingested metrics from transaction databases or external telemetry sources.

| Signal ID | Signal Name | Data Origin | Status | Consumer | Note / Status Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PUR_REC** | Purchase Recency | event_ledger | **Implemented** | Feature Store | Handled via transaction dates |
| **PUR_FRQ** | Purchase Frequency | event_ledger | **Implemented** | Feature Store | Count of sale events |
| **PUR_VOL** | Order Volatility | event_ledger | **Implemented** | Feature Store | StdDev of sales / Mean sales |
| **PUR_VAL_MDN**| Median Order Value | event_ledger | **Implemented** | Feature Store | Median net invoice value |
| **PAY_DPD_AVG** | Average Days Past Due | event_ledger | **Implemented** | Feature Store | Mean settlement delay |
| **PAY_DPD_MAX** | Maximum Days Past Due | event_ledger | **Implemented** | Feature Store | Max settlement delay |
| **PAY_CR_UTIL** | Credit Utilization | event_ledger / config | **Implemented** | Feature Store | Outstanding / Credit Limit |
| **PAY_FRG_IDX** | Payment Fragmentation | event_ledger | **Implemented** | Feature Store | Payment tx count per invoice |
| **OPR_RET_VOL** | Return Value Ratio | event_ledger | **Implemented** | Feature Store | Return amount / gross sales |
| **OPR_RET_FLT** | Customer Fault Return Rate| event_ledger | **Implemented** | Feature Store | Fault classification proportion |
| **OPR_ORD_CAN** | Order Cancellation Rate | event_ledger | **Implemented** | Feature Store | Ratio of cancelled orders |
| **NET_LOY_AGE** | Relationship Longevity | event_ledger | **Implemented** | Feature Store | Days since first transaction |
| **NET_PEER_RNK** | Peer Performance Rank | event_ledger | **Future Only** | None | Excluded from active scoring |
| **ENG_POR_LGN** | Portal Login Frequency | Telemetry (None) | **Future Only** | None | Excluded from active scoring |
| **ENG_CRT_ABD** | Cart Abandonment Rate | Telemetry (None) | **Future Only** | None | Excluded from active scoring |

---

## 2. Canonical Features

Features represent aggregates calculated over rolling temporal windows.

| Feature Name | Primary Origin Signal(s) | Status | Consumer | Note / Status Details |
| :--- | :--- | :--- | :--- | :--- |
| `sales_window` | PUR_FRQ, PUR_VAL_MDN | **Implemented** | Dimensions Engine | Rolling sales sum |
| `payments_window` | PAY_DPD_AVG, PAY_FRG_IDX | **Implemented** | Dimensions Engine | Rolling payments sum |
| `returns_value_window` | OPR_RET_VOL | **Implemented** | Dimensions Engine | Rolling returns sum |
| `events_window` | All | **Implemented** | Dimensions Engine | Event record count |
| `sales_events_window` | PUR_FRQ | **Implemented** | Dimensions Engine | Sale event count |
| `payments_events_window`| PAY_FRG_IDX | **Implemented** | Dimensions Engine | Payment event count |
| `returns_events_window` | OPR_RET_VOL | **Implemented** | Dimensions Engine | Return event count |
| `category_diversity_count`| PUR_VAL_MDN | **Implemented** | Dimensions Engine | Distinct category count |
| `product_diversity_count`| PUR_VAL_MDN | **Implemented** | Dimensions Engine | Distinct SKU count |
| `payment_modes_window` | PAY_FRG_IDX | **Refactored** | Dimensions Engine | Payment types (under Discipline) |
| `registration_date` | NET_LOY_AGE | **Implemented** | Dimensions Engine | Customer static registration date |
| `business_type` | NET_PEER_RNK | **Implemented** | Dimensions Engine | Customer type metadata |
| `credit_limit_window` | PAY_CR_UTIL | **Implemented** | Dimensions Engine | Active credit limit boundary |
| `purchase_days` | PUR_FRQ | **Implemented** | Dimensions Engine | Days with sale events |
| `active_duration_days` | All | **Implemented** | Dimensions Engine | Timespan between first/last event |
| `last_purchased_at` | PUR_REC | **Implemented** | Dimensions Engine | Timestamp of latest sale |
| `log_sales_scale` | PUR_VAL_MDN | **Implemented** | Dimensions Engine | Log-scaled sales volume |
| `participation_density` | PUR_FRQ | **Implemented** | Dimensions Engine | Trading day density ratio |
| `net_revenue_window` | PUR_FRQ, OPR_RET_VOL | **Refactored** | Dimensions Engine | Consolidated under Activity |
| `business_age_days` | NET_LOY_AGE | **Refactored** | Dimensions Engine | Consolidated under Stability |
| `sales_recent` | PUR_FRQ | **Implemented** | Dimensions Engine | Recent sales velocity |
| `events_recent` | All | **Implemented** | Dimensions Engine | Recent event activity |
| `sales_events_recent` | PUR_FRQ | **Implemented** | Dimensions Engine | Recent sale event count |
| `penalty_window` | OPR_RET_VOL | **Deprecated** | None | Aliased to `returns_value_window` |

---

## 3. Canonical Dimensions

Dimensions are the intermediate internal pillars of behavioral intelligence.

| Dimension Name | Underlying Features | Status | Scope |
| :--- | :--- | :--- | :--- |
| **Activity** | `sales_window`, `sales_events_window`, `log_sales_scale`, `purchase_days`, `participation_density`, `last_purchased_at` | **Implemented** | Internal |
| **Discipline** | `payments_window`, `payments_events_window`, `payment_modes_window` | **Implemented** | Internal |
| **Credit** | `credit_limit_window`, `payments_window` | **Implemented** | Internal |
| **Relationship** | `active_duration_days` | **Implemented** | Internal |
| **Product** | `product_diversity_count`, `category_diversity_count` | **Implemented** | Internal |
| **Friction** | `returns_value_window`, `returns_events_window`, `penalty_window` | **Implemented** | Internal |
| **Growth** | `sales_recent`, `events_recent`, `sales_events_recent` | **Implemented** | Internal |
| **Stability** | `events_window`, `participation_density`, `business_age_days`, `registration_date`, `business_type` | **Implemented** | Internal |

*Note: The legacy dimensions Value, Concentration, Payment Mode, and Maturity have been consolidated into the 8 canonical pillars to increase interpretability, resolve redundancies, and reduce overlap.*

---

## 4. Canonical Scores

Scores are the authoritative external metrics exposed to client APIs.

| Score Name | Database Field | Status | Exposure | Formula | Business Decision Supported |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Health** | `health_score` | **Implemented** | API | $0.40 \cdot \text{Activity} + 0.35 \cdot \text{Friction} + 0.25 \cdot \text{Stability}$ | Customer engagement & retention planning |
| **Risk** | `risk_score` | **Implemented** | API | $0.40 \cdot (1 - \text{Credit}) + 0.40 \cdot (1 - \text{Discipline}) + 0.20 \cdot (1 - \text{Stability})$ | Credit limits, collections prioritization |
| **Growth** | `growth_score` | **Implemented** | API | $0.50 \cdot \text{Growth} + 0.30 \cdot \text{Product} + 0.20 \cdot \text{Activity}$ | Upselling, cross-selling opportunity mapping |
| **Trust** | `trust_score` | **Implemented** | API | $0.50 \cdot \text{Discipline} + 0.30 \cdot \text{Relationship} + 0.20 \cdot \text{Stability}$ | Contractual terms extension, pricing tiers |
| **Opportunity**| `opportunity_score` | **Implemented** | API | $0.50 \cdot (1 - \text{Product}) + 0.30 \cdot \text{Growth} + 0.20 \cdot \text{Relationship}$ | Priority business development outreach |
| **Credit** | `credit_score` | **Implemented** | API | $0.40 \cdot \text{Trust} + 0.40 \cdot (1 - \text{Risk}) + 0.20 \cdot \text{Activity}$ | Approved credit line limit assignments |
| **Collection** | `collection_score` | **Implemented** | API | $0.50 \cdot (1 - \text{Discipline}) + 0.30 \cdot \text{Risk} + 0.20 \cdot \text{Activity}$ | Aging receivable collection priorities |
| **Relationship**| `relationship_score` | **Implemented** | API | $0.40 \cdot \text{Relationship} + 0.40 \cdot \text{Stability} + 0.20 \cdot \text{Activity}$ | Partnership program inclusions |

*Note: Legacy metrics `purchase_score`, `payment_score`, and `rg_score` have been fully removed from both DB and API.*

---

## 5. Canonical Recommendations

Standardized outputs mapping score thresholds to automated actions.

| Rec ID | Recommended Action | Type | Trigger Conditions | Status |
| :--- | :--- | :--- | :--- | :--- |
| **REC_CR_INC** | `INCREASE_CREDIT_LIMIT` | CREDIT_LIMIT | Trust $\ge 0.75$ & Risk $\le 0.25$ | **Implemented** |
| **REC_CR_DEC** | `DECREASE_CREDIT_LIMIT` | CREDIT_LIMIT | Risk $\ge 0.60$ | **Implemented** |
| **REC_PT_TGT** | `TIGHTEN_PAYMENT_TERMS` | PAYMENT_TERMS | Collection $\le 0.40$ or Risk $\ge 0.50$ | **Implemented** |
| **REC_PT_EXT** | `EXTEND_PAYMENT_TERMS` | PAYMENT_TERMS | Trust $\ge 0.70$ & Collection $\ge 0.80$| **Implemented** |
| **REC_RT_PRO** | `PROACTIVE_RETENTION` | RETENTION_STRATEGY | Health $\le 0.45$ & Relationship $\ge 0.60$| **Implemented** |
| **REC_CL_ACC** | `ACCELERATED_COLLECTION`| COLLECTION_STRATEGY| Collection $\le 0.50$ & Outstanding $> 0$| **Implemented** |

---

## 6. Canonical Prediction Outputs

ML Target formats that estimators must yield.

| Target Output Name | Status | Model Engine | Output Labels / Range |
| :--- | :--- | :--- | :--- |
| `RiskPrediction` | **Implemented** | DefaultRiskEstimator | LOW, MEDIUM, HIGH, CRITICAL |
| `GrowthPrediction` | **Implemented** | DefaultGrowthEstimator | CONTRACTION, STABLE, EXPANSION, ACCELERATING |
| `HealthPrediction` | **Implemented** | DefaultHealthEstimator | A, B, C, D, F |
| `ChurnPrediction` | **Implemented** | DefaultChurnEstimator | boolean (is_churn_risk) |
| `CollectionPrediction`| **Implemented** | DefaultCollectionEstimator | Expected delay days, probability |
| `OpportunityPrediction`| **Implemented** | DefaultOpportunityEstimator | LOW, MEDIUM, HIGH, STIMULUS |
