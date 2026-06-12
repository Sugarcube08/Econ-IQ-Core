# FRONTEND CONTEXT HANDBOOK & SERVICE INTEGRATION GUIDE

This document serves as the absolute, authoritative source of truth for frontend development and integration with the Econiq Core backend service. 

---

## SECTION 1: PROJECT OVERVIEW

Econiq is a stateful commercial intelligence and risk propagation platform. It enables financial institutions and enterprises to monitor partnership health, evaluate default risk, forecast customer churn, optimize payment collections, and allocate credit limits dynamically based on transaction behaviors recorded in the event ledger.

### Core Business Objectives:
1. **Deterioration Mitigation**: Proactively identify degrading customer accounts before default occurs.
2. **Collection Optimization**: Target collection efforts based on probability scores and expected settlement delays.
3. **Credit Limit Rationalization**: Automatically recommend limit expansions/reductions depending on trade consistency.
4. **Retention Maximization**: Identify inactive commercial windows and trigger proactively managed workflows.

---

## SECTION 2: CANONICAL INTELLIGENCE MODEL

The Econiq Core architecture encapsulates data flows into distinct abstractions. The frontend must consume these precomputed results directly from the serving layer without attempting to re-calculate them:

1. **Signals**: Raw, discrete business events (e.g., individual invoice sales, invoice payments, credit returns).
2. **Features**: Rolling aggregates over temporal windows (e.g., total sales volume, count of returns, average payment delays).
3. **Dimensions**: High-level behavioral aspects evaluated by 8 specialized dimension engines:
   * `Activity`: Volume frequency and density.
   * `Discipline`: Payment rhythm and compliance delay.
   * `Credit`: Receivables pressure and limit utilization.
   * `Relationship`: Partnership consistency and variety.
   * `Product`: SKU/category diversity.
   * `Friction`: Disputed returns and void frequencies.
   * `Growth`: Revenue velocity.
   * `Stability`: Rhythm baseline variance.
4. **Scores**: The 8 Canonical Meta Scores derived purely from the 8 consolidated dimensions:
   * **Health Score**: Overall condition index.
   * **Risk Score**: Default and trading risk probability.
   * **Growth Score**: Commercial scaling potential.
   * **Trust Score**: Compliance and payment reliability.
   * **Opportunity Score**: Upsell space.
   * **Credit Score**: Limit allocation safety rating.
   * **Collection Score**: Settlement recovery priority index.
   * **Relationship Score**: Partnership value index.
5. **Predictions**: Advanced model heuristics forecasting future occurrences (Risk, Churn, Growth, Health Grade, Collection delay, Opportunity tier).
6. **Recommendations**: Automated next-best-actions (Credit limits, Payment terms, Retention, Collections) triggered by policy parameters.
7. **Explainability**: Decoded SHAP features, positive/negative drivers, and score change offsets.

---

## SECTION 3: API INVENTORY

All backend routes are prefixed with `/api/v1`.

### 1. Authentication Endpoints
* `POST /auth/request-otp`: Sends OTP to user email.
* `POST /auth/verify-otp`: Exchange email/OTP/device ID for Access/Refresh tokens.
* `POST /auth/refresh`: Refresh expired Access tokens.
* `POST /auth/logout`: Revoke active refresh session.
* `GET /auth/me`: Current user session credentials.

### 2. Customers Endpoints
* `GET /customers`: Paginated list datatable payload.
* `GET /customers/export/csv`: Streaming CSV file download.
* `GET /customer/{id}`: Detailed customer profile.
* `GET /customer/{id}/predictions`: Predictive metrics block.
* `GET /customer/{id}/recommendations`: Next-best-action recommendations block.

### 3. Graphs Endpoints
* `GET /customer/{id}/purchase-graph`: Sales invoice timeline.
* `GET /customer/{id}/payment-graph`: Settlement payment timeline.
* `GET /customer/{id}/rg-graph`: Returns/credits timeline.
* `GET /customer/{id}/outstanding-graph`: Account balance/exposure movements.

### 4. Dashboard Endpoints
* `GET /dashboard/overview`: High-level executive KPI cards.
* `GET /dashboard/commercial-flow`: Longitudinal collection vs sales timeline.
* `GET /dashboard/aging-distribution`: Receivables aging buckets.
* `GET /dashboard/state-distribution`: Health states count.
* `GET /dashboard/deteriorating-customers`: Top account drops queue.
* `GET /dashboard/improving-customers`: Top account gains queue.
* `GET /dashboard/high-risk-customers`: Critical credit risk list.
* `GET /dashboard/activity-summary`: Daily summary alert strips.
* `GET /dashboard/top-contributors`: Customer concentration list.

---

## SECTION 4: CUSTOMER LIST CONTRACT

The `GET /customers` endpoint serves an optimized payload intended specifically for tabular presentation.

### Datatable Fields
* `customer_id` (`string`): Unique identifier.
* `customer_name` (`string`): Registered business name.
* `city` (`string`): Business node city.
* `health_score` (`float`): Current health [0.0 - 1.0].
* `risk_score` (`float`): Current risk [0.0 - 1.0].
* `growth_score` (`float`): Current growth [0.0 - 1.0].
* `trust_score` (`float`): Current trust [0.0 - 1.0].
* `opportunity_score` (`float`): Current opportunity [0.0 - 1.0].
* `credit_score` (`float`): Current credit capacity [0.0 - 1.0].
* `collection_score` (`float`): Current collection priority [0.0 - 1.0].
* `relationship_score` (`float`): Current relationship index [0.0 - 1.0].
* `state` (`string`): Behavioral segment (e.g. `healthy`, `monitor`, `contract`, `liquidity_stress`).
* `outstanding_current` (`float`): Active outstanding balance.
* `outstanding_previous` (`float`): Previous period outstanding balance.
* `contribution_current` (`float`): Sales volume percentage contribution.
* `contribution_previous` (`float`): Previous period contribution.
* `last_purchase_date` (`string`): Date YYYY-MM-DD.
* `deltas` (`object`):
  * Difference metrics computed as: `current_score - previous_score` (except `outstanding_delta` which represents percentage growth).

### Query Modifiers
* **Sorting**: `sort_by` (default: "trust_score"), `sort_order` ("asc" | "desc").
* **Filtering**: `current_state` (comma-separated list), score ranges (e.g. `health_score_min`).
* **Search**: `search` (fuzzy search string).
* **Pagination**: `page` (default 1), `limit` (default 10).

---

## SECTION 5: CUSTOMER PROFILE CONTRACT

The `GET /customer/{id}` endpoint provides the canonical intelligence profile for detail cards.

### Payload Structure
```json
{
  "customer": {
    "customer_id": "string",
    "customer_name": "string",
    "city": "string",
    "scores": {
      "health_score": 0.8521,
      "risk_score": 0.1245,
      "growth_score": 0.7512,
      "trust_score": 0.9102,
      "opportunity_score": 0.6514,
      "credit_score": 0.8201,
      "collection_score": 0.8951,
      "relationship_score": 0.8804,
      "outstanding_current": 145000.0,
      "outstanding_previous": 120000.0
    },
    "deltas": {
      "health_score": 0.025,
      "risk_score": -0.015,
      "growth_score": 0.05,
      "trust_score": 0.01,
      "opportunity_score": 0.02,
      "credit_score": 0.03,
      "collection_score": 0.015,
      "relationship_score": 0.02,
      "outstanding_delta": 20.83
    },
    "behavior_state": "healthy",
    "organization_contribution": {
      "current_percentage": 2.45,
      "delta": 0.3
    },
    "last_purchased_at": "2026-06-10",
    "updated_at": "2026-06-12T18:00:00Z"
  }
}
```

---

## SECTION 6: DASHBOARD CONTRACTS

Dashboard metrics represent aggregated metrics across the organization context:

### 1. Overview Cards (`/dashboard/overview`)
* Contains active customer counts, sales totals, collections totals, outstanding, overdue, health index, and comparison deltas.

### 2. Commercial Flow (`/dashboard/commercial-flow`)
* Longitudinal series of points: `[{"period_start": "string", "period_end": "string", "sales_volume": float, "collection_volume": float, "outstanding_exposure": float}]`.

### 3. Aging Receivables Distribution (`/dashboard/aging-distribution`)
* Maps receivables total dollars into overdue buckets: `current`, `overdue_30`, `overdue_60`, `overdue_90`, `overdue_120`, `overdue_120_plus`.

### 4. Behavioral States Distribution (`/dashboard/state-distribution`)
* Distribution counts and percentages across: `HEALTHY`, `MONITOR`, `CONTRACT`, `LIQUIDITY_STRESS`.

---

## SECTION 7: PREDICTIONS CONTRACT

Retrieved via `GET /customer/{id}/predictions`. Returns a uniform structure for all predictive dimensions:

```json
{
  "customer_id": "string",
  "prediction_date": "YYYY-MM-DD",
  "score": 0.7245,
  "confidence": 0.95,
  "model_version": "1.0.0",
  "features_snapshot": { ... },
  "key_drivers": ["string"],
  "prediction_class_label": "string"
}
```

### Dimensions Definitions & Confidence Enums:
1. **Risk**: `risk_level` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
2. **Growth**: `growth_potential` (`CONTRACTION`, `STABLE`, `EXPANSION`, `ACCELERATING`).
3. **Health**: `health_grade` (`A`, `B`, `C`, `D`, `F`).
4. **Churn**: `is_churn_risk` (`true` | `false`).
5. **Collection**: `repayment_probability` (`float`), `expected_delay_days` (`integer`).
6. **Opportunity**: `opportunity_tier` (`LOW`, `MEDIUM`, `HIGH`, `STIMULUS`), `expected_upsell_value` (`float`).

---

## SECTION 8: RECOMMENDATIONS CONTRACT

Retrieved via `GET /customer/{id}/recommendations`. Returns actionable proposals triggered by backend policies.

### Payload Schema
```json
{
  "customer_id": "string",
  "generated_date": "YYYY-MM-DD",
  "recommendations": [
    {
      "type": "CREDIT_LIMIT | PAYMENT_TERMS | RETENTION_STRATEGY | COLLECTION_STRATEGY",
      "priority": "LOW | MEDIUM | HIGH | CRITICAL",
      "reason": "Explanatory rationale text.",
      "affected_score": "credit_score | collection_score | relationship_score",
      "expected_impact": "LOW | MEDIUM | HIGH",
      "confidence": 0.90,
      "action_category": "INCREASE_CREDIT_LIMIT | TIGHTEN_PAYMENT_TERMS | PROACTIVE_RETENTION_REACH_OUT | ACCELERATED_COLLECTION",
      "value": "Quantitative parameter (e.g. '20% Increase')"
    }
  ]
}
```

---

## SECTION 9: EXPLAINABILITY CONTRACT

Every canonical score contains positive/negative drivers, and score change differences.

### 1. Score Lineage Drivers
* The frontend must present positive deltas as green progress indicators and negative deltas as amber/red warning indicators.
* **Positive Drivers** (Examples): `HIGH_TRADE_REGULARITY`, `FAST_SETTLEMENT`, `ELITE_LIQUIDITY`, `STRONG_DEBT_CLEARANCE`, `LOW_CUSTOMER_RG`, `STABLE_PARTICIPATION`.
* **Negative Drivers** (Examples): `SLOW_SETTLEMENT`, `HIGH_OPERATIONAL_FRICTION`, `LIQUIDITY_STRESS`, `CHRONIC_DEBT_PRESSURE`, `WEAK_CLEARANCE_STRENGTH`, `INCONSISTENT_TRADING`, `CRITICAL_BEHAVIORAL_STRESS`.

---

## SECTION 10: UI MAPPING GUIDE

Map backend telemetry directly to suggested UI components for premium UX:

| Backend Concept | Suggested UI Component | Visual Indicator Strategy |
| :--- | :--- | :--- |
| **Health Score** | `Health Card / Radial Gauge` | Color spectrum green-to-red based on [0.0 - 1.0] range. |
| **Risk Score** | `Risk Indicator / Badge` | Red for CRITICAL/HIGH, yellow for MEDIUM, green for LOW. |
| **Recommendations** | `Action Queue / Cards` | Sortable queue grouped by priority level. Include a "Reasoning Details" expander. |
| **Predictions** | `Forecast Cards / Sparklines` | Timeline projections showing Churn Risk, Expected Delay Days, and Upsell Values. |
| **Score Delta** | `Delta Trend Indicator` | Chevron up (green) for positive, chevron down (red) for negative. |
| **Behavioral State** | `Status Ribbon` | High-visibility status badge in page headers. |
| **Explainability Drivers** | `Why Panel / Drivers List` | Side-by-side list of positive (green check) vs negative (red hazard) factors. |

---

## SECTION 11: DO NOT ASSUME

To maintain system integrity and prevent architectural drift, the frontend must strictly adhere to these constraints:

* 🚫 **Do Not Calculate Scores**: The frontend must never try to calculate, compute, average, or blend dimensions/scores. The backend formulas are the sole source of truth.
* 🚫 **Do Not Derive Dimensions**: Never infer high-level dimensions (like activity or friction) from ledger items on client runtime.
* 🚫 **Do Not Recreate Business Logic**: Policies, limit changes, and terms extensions are generated on the server. Do not write local rule evaluations.
* 🚫 **Do Not Cache/Synthesize Transitions**: Let the server record and flag state changes (e.g., transitions from healthy to stress).

---

## SECTION 12: FRONTEND IMPLEMENTATION READINESS

### Backend Status
* **API Serving Layer**: **PRODUCTION ALIGNED** (Exposes only 8 canonical scores; returns clean structured JSONs).
* **DTO Models**: **FROZEN** (Validated schemas, all fields matching contract).
* **Heuristics / Predictions**: **OPERATIONAL (V1)** (Default heuristic models serving predictable baseline arrays).
* **Recommendations Engine**: **OPERATIONAL (V1)** (Policy rules output compliant properties).
* **Explainability Engine**: **OPERATIONAL (V1)** (Drivers and delta calculations integrated).

### Known Limitations
* Custom date ranges (different from default 365d) trigger dynamic database queries which can increase latency. The frontend should display a loading spinner for custom date filters.

### Future Enhancements
* Transition from heuristic rules-based estimators (Version 1.0.0) to trained machine learning models (Version 2.0.0+) without API signature modifications.
