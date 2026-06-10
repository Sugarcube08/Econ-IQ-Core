# Econiq Alert Engine Architecture

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Principal Product Architect & Lead Backend Engineer  
**Owner:** Product & Security Team

---

## 1. Alert Classification Model

Econiq classifies alerts into three functional tiers to prioritize analyst workflows:

```
                  ┌───────────────────────────────┐
                  │         ALERT ENGINE          │
                  └───────────────┬───────────────┘
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│ Static Alert │           │  Predictive  │           │   AI Alert   │
│(Overdue Invc)│           │ (Default P)  │           │  (Anomalies) │
└──────────────┘           └──────────────┘           └──────────────┘
```

1.  **Static Alerts (Risk & Collection Warnings):** Triggered by simple threshold violations (e.g. invoice payment remains unpaid $> 15$ days past due date).
2.  **Predictive Alerts (Default & Churn Warnings):** Triggered by model output deviations (e.g. default probability $P_{\text{default}}$ increases by $> 30\%$ inside a 7-day window).
3.  **AI Alerts (Anomaly Warnings):** Triggered by statistical anomaly models (e.g., purchase volume Z-score $> 3.0$ or Isolation Forest flags transaction anomalies).

---

## 2. Priority, Escalation, and Suppression Rules

*   **Priority Matrix:** Categorizes warnings into Critical (action needed within 4 hours), High, Medium, and Low levels.
*   **Deduplication (Debouncing):** Throttles duplicate alerts for the same customer and rule within 12 hours to prevent alert fatigue.
*   **Active Dispute Suppression:** If an invoice is flagged in the database as `DISPUTED`, it is excluded from payment delay calculations, suppressing false-positive delinquent alarms.
*   **Database Schema:**
```sql
CREATE TABLE triggered_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    rule_type VARCHAR(64) NOT NULL, -- 'STATIC', 'PREDICTIVE', 'ANOMALY'
    priority_level VARCHAR(32) NOT NULL, -- 'CRITICAL', 'HIGH', 'MEDIUM'
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'RESOLVED'
    trigger_reason VARCHAR(255) NOT NULL,
    trigger_metrics JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

---

## 3. Example Alert Trigger (Go Implementation)

The alert evaluator runs as a background task evaluating metrics and prediction values:

```go
func EvaluatePredictiveAlerts(ctx context.Context, customerID string, currentScore int, previousScore int) {
    // Check if score degradation exceeds threshold
    if currentScore - previousScore >= 25 {
        db.Exec(ctx, `
            INSERT INTO triggered_alerts (tenant_id, customer_id, rule_type, priority_level, trigger_reason, trigger_metrics)
            VALUES ($1, $2, 'PREDICTIVE', 'HIGH', 'Risk score increased by 25+ points in a single sync execution.', $3)
        `, tenantID, customerID, json.RawMessage(`{"current":`+strconv.Itoa(currentScore)+`,"previous":`+strconv.Itoa(previousScore)+`}`))
    }
}
```
