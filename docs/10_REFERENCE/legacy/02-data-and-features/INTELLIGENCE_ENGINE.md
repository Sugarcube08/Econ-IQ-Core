# Econiq Intelligence Engine Specification

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Principal Product Architect & Data Science Lead  
**Owner:** Analytics & ML Team

---

## 1. Credit Scoring Matrix

Econiq translates raw metrics into six intelligence scores. Every score ranges from `0` to `100`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SCORING ENGINE                                │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│  Risk Score  │ Health Score │ Trust Score  │ Opportunity  │ Growth/Stab │
├──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│   Influence  │ Collection P │  Explainable │ Drivers      │ Auditable   │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

---

## 2. Score Formulations and Interpretations

### 2.1. Risk Score (Default Risk Index)
*   **Formula:**
    $$\text{Risk Score} = 0.45 \cdot f(\text{WDPD}_{30}) + 0.25 \cdot \text{CUR} + 0.15 \cdot \text{CTDI} + 0.15 \cdot (100 - \text{CEI}_{90})$$
    Where:
    *   $f(\text{WDPD}_{30}) = \min(100, \text{WDPD} \times 3.33)$ *(Max penalty at 30 days past due)*.
    *   $\text{CUR}$ is the Credit Utilization Ratio.
    *   $\text{CTDI}$ is the Credit Term Deviation Index.
    *   $\text{CEI}_{90}$ is the Collection Efficiency Index.
*   **Interpretation:** `> 75`: High default risk. Hold orders.
*   **Refresh Strategy:** Daily batch job.

### 2.2. Health Score (Overall Retailer Viability)
*   **Formula:**
    $$\text{Health Score} = 0.35 \cdot (100 - \text{Risk Score}) + 0.25 \cdot \text{Stability Score} + 0.20 \cdot \text{Growth Score} + 0.20 \cdot \text{Trust Score}$$
*   **Interpretation:** `> 80`: Outstanding, stable retailer. Eligible for automatic credit expansions.
*   **Refresh Strategy:** Daily batch.

### 2.3. Trust Score (Payment Behavior Integrity)
*   **Formula:**
    $$\text{Trust Score} = 0.50 \cdot \text{SCI} + 0.30 \cdot (100 - \min(100, \text{Return Rate} \times 5)) + 0.20 \cdot \text{Payment punctuality}$$
*   **Interpretation:** Low score indicates inconsistent payments or high return rates.
*   **Refresh Strategy:** Weekly batch.

### 2.4. Opportunity Score (Credit Expansion Match)
*   **Formula:**
    $$\text{Opportunity Score} = 0.40 \cdot \text{Growth Score} + 0.35 \cdot \text{CUR} + 0.25 \cdot \text{Trust Score}$$
*   **Interpretation:** High score indicates a growing retailer constrained by their credit limit.
*   **Refresh Strategy:** Daily batch.

### 2.5. Collection Priority Score (Collection Queue Router)
*   **Formula:**
    $$\text{Collection Priority Score} = 0.40 \cdot \text{Invoice Amount} + 0.35 \cdot (1.0 - P_{\text{collection}}) + 0.25 \cdot \text{Days Overdue}$$
    Where:
    *   $P_{\text{collection}}$ is the ML-predicted recovery probability.
*   **Interpretation:** High score prioritizes the retailer on the collection route.
*   **Refresh Strategy:** Real-time on sync run.

---

## 3. Explainability & Storage

To satisfy the **Complete Explainability** principle, calculations are logged with their input components:

```sql
CREATE TABLE customer_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    score_type VARCHAR(32) NOT NULL, -- 'RISK', 'HEALTH', 'OPPORTUNITY', 'COLLECTION'
    score_value INT NOT NULL,
    
    -- Explainability Payloads
    input_metrics JSONB NOT NULL, -- Metrics snapshot
    score_drivers JSONB NOT NULL, -- Human-readable explanations
    
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

### Sample Explainability JSON:
```json
{
  "score_type": "RISK",
  "score_value": 78,
  "score_drivers": [
    {"metric": "wdpd_30", "impact": "+33.6", "reason": "Weighted Days Past Due is 22.4 days."},
    {"metric": "credit_utilization", "impact": "+23.0", "reason": "Credit line is 92% utilized."}
  ]
}
```
