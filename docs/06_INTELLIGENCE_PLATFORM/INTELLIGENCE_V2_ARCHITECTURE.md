# Intelligence V2 Architecture Plan: Universal Commercial Intelligence

## 1. Executive Summary
The current Intelligence engine (`core/intelligence/`) is heavily overfitted to a specific organizational model, relying on hardcoded states ("Elite", "Declining") and interconnected scores that penalize the same signals multiple times. 
The **Intelligence V2 Generalization** shifts the paradigm from a state-based penalization model to a **multidimensional vector model**.

The new execution pipeline is strictly linear and decoupled:
`Transactions → Features → Dimensions (8) → Meta Scores (4) → Predictions`

## 2. Core Dimensions (The 12 Pillars)
Each dimension is independent, normalized (0.0 to 1.0), and strictly describes one aspect of the entity's behavior.

### Dimension 1: Commercial Activity
*Focus: Buying velocity and consistency.*
- **Signals:** Invoice count, purchase dates.
- **Features:** `purchase_frequency`, `purchase_recency`, `purchase_volume`, `purchase_consistency`.

### Dimension 2: Financial Discipline
*Focus: Payment reliability and promptness.*
- **Signals:** Payment dates vs Due dates.
- **Features:** `average_delay`, `delay_variance`, `clearance_rate`, `on_time_rate`.

### Dimension 3: Credit Behavior
*Focus: Leverage and exposure management.*
- **Signals:** Outstanding balance, credit limit.
- **Features:** `credit_utilization`, `credit_pressure`, `limit_breach_rate`.

### Dimension 4: Relationship Quality
*Focus: Longevity and mutual engagement.*
- **Signals:** First/Last purchase, engagement events.
- **Features:** `engagement_consistency`, `retention_strength`.

### Dimension 5: Product Behavior (Portfolio Concentration)
*Focus: Catalog penetration and diversification.*
- **Signals:** `product_category`, `product_name`.
- **Features:** `category_diversity`, `product_diversity`, `concentration_risk`.

### Dimension 6: Operational Friction
*Focus: Exception rates and dispute frequency.*
- **Signals:** Returns, `return_reason`.
- **Features:** `return_rate`, `return_value_ratio`, `return_reason_distribution`.

### Dimension 7: Growth Dynamics
*Focus: Trajectory and improvement vectors.*
- **Signals:** Delta in sales/volume.
- **Features:** `revenue_growth`, `volume_growth`, `frequency_growth`.

### Dimension 8: Stability & Predictability
*Focus: Variance and operational cadence.*
- **Signals:** Temporal variance in behavior.
- **Features:** `volatility`, `seasonality`, `cadence_stability`.

### Dimension 9: Commercial Value
*Focus: Absolute importance to the business.*
- **Signals:** `gross_revenue`, `net_revenue`, `margin_proxy`.
- **Features:** `total_revenue`, `revenue_share`, `margin_contribution`.

### Dimension 10: Portfolio Concentration (Expanded)
*Focus: Diversified buying vs single-product dependency.*
- **Features:** `category_entropy`, `basket_complexity`.

### Dimension 11: Payment Method Behavior
*Focus: Payment mode signals (Cash vs Digital vs Cheque).*
- **Signals:** `payment_mode`.
- **Features:** `digital_payment_ratio`, `cash_ratio`, `mode_volatility`.

### Dimension 12: Business Maturity
*Focus: Operational age and stage.*
- **Signals:** `registration_date`.
- **Features:** `business_age`, `growth_stage`.

## 3. Meta Scores (Business-Oriented)
Meta scores are business-oriented aggregates derived *only* from dimensions.

- **Risk Score:** `F(Discipline, Credit, Friction, Stability)` -> Decision: Credit limit adjustments.
- **Growth Score:** `F(Activity, Product, Growth, Value)` -> Decision: Marketing investment.
- **Health Score:** `F(Discipline, Activity, Friction, Stability)` -> Decision: Overall account health.
- **Strategic Value Score:** `F(Value, Relationship, Maturity)` -> Decision: Priority servicing.
- **Trust Score:** `F(Discipline, Stability, Relationship)` -> Decision: Terms & conditions.
- **Opportunity Score:** `F(Growth, Activity, Value)` -> Decision: Upsell potential.
- **Stability Score:** `F(Stability, Maturity, Discipline)` -> Decision: Forecast reliability.

## 4. Extraction & Policy Strategy
- **Every Signal -> One Feature:** No signal should be counted twice in the feature layer.
- **Every Feature -> One Dimension:** Clear ownership of behavior.
- **Every Dimension -> One Purpose:** No overlapping dimension mechanics.
- **Every Score -> One Business Decision:** Alignment with executive logic.
## 5. Migration Execution Steps
1. **Feature Engineering Expansion:** Update `core/feature_store/engineer.py` to produce the extended set of features (e.g., product diversity, return reasons).
2. **Dimension Engine Creation:** Replace the fragmented engines (`stress/`, `states/`, `rg/`, etc.) with 8 clear dimension calculators (`core/intelligence/dimensions/`).
3. **Meta Score Engine Creation:** Implement engines that linearly combine dimension scores into the 4 Meta Scores.
4. **Orchestrator Refactor:** Update `IntelligenceOrchestrator` to flow through the new DAG: Features → Dimensions → Meta Scores.
5. **Policy YAML Update:** Move all categorization thresholds (Elite, etc.) into `policy.yaml`.
