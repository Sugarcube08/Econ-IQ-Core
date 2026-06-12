# CANONICAL SCORE MODEL (V2)

This document establishes the frozen scoring formulations for the Econiq Core platform. All calculations are executed strictly within `core/intelligence/meta/scores.py` and served via the `/api/v1` serving layer.

---

## 1. Consolidated B2B Dimensions

To optimize interpretability and reduce overlap, the legacy 12 dimensions have been consolidated into 8 intermediate pillars:

1. **Activity (`dim_activity`)**: Rolling sales volume and frequency.
2. **Discipline (`dim_discipline`)**: Timeliness of payments and average days past due.
3. **Credit (`dim_credit`)**: Credit utilization relative to limits.
4. **Relationship (`dim_relationship`)**: Customer lifetime longevity and interaction cadence.
5. **Product (`dim_product`)**: SKU diversity and product category concentration (merged).
6. **Friction (`dim_friction`)**: Returns ratio and customer-fault log rates.
7. **Growth (`dim_growth`)**: Purchase velocity trend lines.
8. **Stability (`dim_stability`)**: Consistency of transaction frequency (Stability + Maturity merged).

---

## 2. Canonical Score Formulations & Mappings

The 8 public canonical scores are calculated as weighted averages of the 8 B2B dimensions:

```
+------------------+     +------------------------+     +---------------------+
|  B2B Dimensions  | --> | Weight Assignment Map  | --> |  8 Canonical Scores |
+------------------+     +------------------------+     +---------------------+
```

### A. Health Score (`health_score`)
* **Formula**:
  $$\text{Health} = 0.40 \cdot \text{Activity} + 0.35 \cdot (1 - \text{Friction}) + 0.25 \cdot \text{Stability}$$
* **Purpose**: Identifies customers showing signs of operational drop-off or logistical strain.
* **Decision Supported**: Proactive customer success interventions.

### B. Risk Score (`risk_score`)
* **Formula**:
  $$\text{Risk} = 0.40 \cdot \text{Credit} + 0.40 \cdot (1 - \text{Discipline}) + 0.20 \cdot (1 - \text{Stability})$$
* **Purpose**: Evaluates credit default and operational trade risks.
* **Decision Supported**: Adjusting credit limits, credit hold triggers.

### C. Growth Score (`growth_score`)
* **Formula**:
  $$\text{Growth} = 0.50 \cdot \text{Growth} + 0.30 \cdot \text{Product} + 0.20 \cdot \text{Activity}$$
* **Purpose**: Identifies account expansion signals.
* **Decision Supported**: Upsell and marketing campaigns.

### D. Trust Score (`trust_score`)
* **Formula**:
  $$\text{Trust} = 0.50 \cdot \text{Discipline} + 0.30 \cdot \text{Relationship} + 0.20 \cdot \text{Stability}$$
* **Purpose**: Measures trade consistency and agreement compliance.
* **Decision Supported**: Extension of payment terms (e.g., Net 30 to Net 60).

### E. Opportunity Score (`opportunity_score`)
* **Formula**:
  $$\text{Opportunity} = 0.50 \cdot (1 - \text{Product}) + 0.30 \cdot \text{Growth} + 0.20 \cdot \text{Relationship}$$
* **Purpose**: Pinpoints high-potential gap analysis opportunities.
* **Decision Supported**: Targeted sales outreach.

### F. Credit Score (`credit_score`)
* **Formula**:
  $$\text{Credit} = 0.40 \cdot \text{Trust} + 0.40 \cdot (1 - \text{Risk}) + 0.20 \cdot \text{Activity}$$
* **Purpose**: Assigns dynamic internal credit rankings.
* **Decision Supported**: Setting auto-approval thresholds for transaction financing.

### G. Collection Score (`collection_score`)
* **Formula**:
  $$\text{Collection} = 0.50 \cdot (1 - \text{Discipline}) + 0.30 \cdot \text{Risk} + 0.20 \cdot \text{Activity}$$
* **Purpose**: Scores collection urgency.
* **Decision Supported**: Allocating debt collections resources.

### H. Relationship Score (`relationship_score`)
* **Formula**:
  $$\text{Relationship} = 0.40 \cdot \text{Relationship} + 0.40 \cdot \text{Stability} + 0.20 \cdot \text{Activity}$$
* **Purpose**: Measures lifetime commercial affinity.
* **Decision Supported**: Strategic partner program inclusion.
