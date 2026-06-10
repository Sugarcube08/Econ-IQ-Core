# Econiq Recommendation Engine Specification

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Principal Product Architect & Startup CTO  
**Owner:** Product & Security Team

---

## 1. Role of the Recommendation Engine

Econiq is a **Decision-Centric** platform. Instead of forcing users to analyze data manually, the system evaluates model predictions and metrics to generate explicit, explainable recommendations for credit limits, collection schedules, and risk hedging.

```
[Metrics & Model Predictions] ──► [Decision Rules Engine] ──► [Audit Log Payload]
                                                                     │
                                                                     ▼
                                                        [Target: Wholesaler Dashboard]
                                                          - "Reduce credit limit to $300k"
                                                          - "Prioritize call: high recovery prob"
```

---

## 2. Core Recommendation Rules

### 2.1. Credit Limit Recommendations
*   **Expansion Recommendation:**
    *   *Conditions:* Opportunity Score $> 80$ AND Credit Utilization $> 90\%$.
    *   *Action:* `INCREASE_CREDIT_LIMIT` by $+25\%$ of current limit.
*   **Contraction Recommendation:**
    *   *Conditions:* Risk Score $> 70$ OR Default Probability $P_{\text{default}} > 0.65$.
    *   *Action:* `DECREASE_CREDIT_LIMIT` to match outstanding balance (preventing new sales credit).

### 2.2. Collection Prioritization Recommendations
*   **Call Priority Routing:**
    *   *Conditions:* Customer has overdue invoices AND Collection Priority Score is in the top 10% of the active tenant queue.
    *   *Action:* `PRIORITIZE_COLLECTION_CALL`.

### 2.3. Risk Mitigation Recommendations
*   **Hedging Decisions:**
    *   *Conditions:* Default Probability $P_{\text{default}} > 0.75$.
    *   *Action:* `TRANSITION_TO_COD` (Cash on Delivery) or `REQUEST_BANK_GUARANTEE`.

### 2.4. Growth Opportunities
*   **Sales Incentives:**
    *   *Conditions:* Growth Score $> 80$ and Default Probability $P_{\text{default}} < 0.15$.
    *   *Action:* `OFFER_VOLUME_DISCOUNT`.

---

## 3. Database Schema & Explainability Logs

Recommendations must be explainable. Wholesalers will not act on recommendations unless they can audit the underlying metrics:

```sql
CREATE TABLE customer_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    category VARCHAR(64) NOT NULL, -- 'CREDIT', 'COLLECTION', 'RISK_MITIGATION'
    action_type VARCHAR(64) NOT NULL, -- 'INCREASE_LIMIT', 'HOLD_SHIPMENT', 'CALL'
    recommended_value NUMERIC(15, 2), -- Target credit limit
    confidence_score NUMERIC(3, 2) NOT NULL,
    
    -- Explainability Payloads
    rationale_text TEXT NOT NULL,
    input_indicators JSONB NOT NULL, -- Snapshot of input features
    
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'ACCEPTED', 'REJECTED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

### Sample Recommendations Record (JSON):
```json
{
  "category": "CREDIT",
  "action_type": "DECREASE_LIMIT",
  "recommended_value": 300000.00,
  "confidence_score": 0.92,
  "rationale_text": "Reduce credit limit to prevent further exposure. Retailer shows high default risk (78) driven by a 22-day increase in average payment delays.",
  "input_indicators": {
    "risk_score": 78,
    "p_default": 0.72,
    "wdpd_30": 22.4,
    "credit_utilization": 0.92
  }
}
```
