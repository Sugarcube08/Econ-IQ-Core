# API Request & Response Examples

This catalog contains concrete examples of payloads for primary endpoints.

---

## 1. Get Customer Profile
### `GET /api/v1/customer/CUST-901`
#### Response (200 OK)
```json
{
  "success": true,
  "message": "Customer profile retrieved successfully (materialized cache)",
  "data": {
    "customer": {
      "customer_id": "CUST-901",
      "customer_name": "Acme Industrial Distributors",
      "city": "Mumbai",
      "scores": {
        "health_score": 0.83,
        "risk_score": 0.17,
        "growth_score": 0.88,
        "trust_score": 0.91,
        "opportunity_score": 0.74,
        "credit_score": 0.85,
        "collection_score": 0.12,
        "relationship_score": 0.9
      },
      "deltas": {
        "health_score": 0.02,
        "risk_score": -0.01,
        "growth_score": 0.04,
        "trust_score": 0.01,
        "opportunity_score": -0.02,
        "credit_score": 0.0,
        "collection_score": -0.03,
        "relationship_score": 0.02
      },
      "behavior_state": "elite",
      "organization_contribution": {
        "current_percentage": 14.2,
        "delta": 1.15
      },
      "last_purchased_at": "2026-06-18",
      "updated_at": "2026-06-19T11:45:00Z"
    }
  },
  "metadata": {
    "mode": "materialized",
    "window_days": 365,
    "processing_time_ms": 3
  }
}
```

---

## 2. Simulate Customer Intervention
### `POST /api/v1/ml/simulate`
#### Request Body
```json
{
  "customer_id": "CUST-404",
  "actions": [
    "LOG_OUTREACH_CALL",
    "REVISE_CREDIT_Horiz_60D"
  ]
}
```
#### Response (200 OK)
```json
{
  "current": {
    "distress": 0.74,
    "health": 0.38
  },
  "simulated": {
    "distress": 0.41,
    "health": 0.62
  },
  "delta": {
    "distress": -0.33,
    "health": 0.24
  },
  "simulation_source": "HEURISTIC"
}
```

---

## 3. Retrieve Advisor Recommendations
### `GET /api/v1/advisor/customer/CUST-404`
#### Response (200 OK)
```json
{
  "customer_id": "CUST-404",
  "current_state": "declining",
  "churn_risk": 0.78,
  "delinquency_risk": 0.82,
  "distress_risk": 0.74,
  "prioritized_actions": [
    {
      "action_type": "LOG_OUTREACH_CALL",
      "impact_score": 0.45,
      "urgency": "HIGH",
      "confidence": 0.88,
      "reason": "Direct contact is shown to mitigate distress signals by establishing immediate communication channels."
    },
    {
      "action_type": "CREATE_PAYMENT_PLAN",
      "impact_score": 0.38,
      "urgency": "MEDIUM",
      "confidence": 0.81,
      "reason": "Outstanding exposure requires formal commitments to reduce collection queues."
    }
  ]
}
```

---

## 4. Log Outreach Activity
### `POST /api/v1/collections/activity`
#### Request Body
```json
{
  "customer_id": "CUST-404",
  "activity_type": "CALL",
  "notes": "Followed up on invoice INV-2026-990. Customer promised payment next Tuesday.",
  "outcome": "PROMISE_MADE"
}
```
#### Response (200 OK)
```json
{
  "success": true,
  "message": "Activity logged successfully",
  "data": {
    "id": "e0b1c20e-fcb0-464a-adfe-a28a1c97a5b6",
    "customer_id": "CUST-404",
    "activity_type": "CALL",
    "notes": "Followed up on invoice INV-2026-990. Customer promised payment next Tuesday.",
    "outcome": "PROMISE_MADE",
    "created_at": "2026-06-19T17:40:12.435Z"
  },
  "metadata": {
    "processing_time_ms": 8
  }
}
```

---

## 5. Get System Capabilities
### `GET /api/v1/system/capabilities`
#### Response (200 OK)
```json
{
  "ledger": {
    "healthy": true
  },
  "intelligence": {
    "healthy": true
  },
  "alerts": {
    "healthy": true
  },
  "collections": {
    "healthy": true
  },
  "decisioning": {
    "healthy": true
  },
  "feature_store": {
    "healthy": true
  },
  "ml": {
    "healthy": true,
    "models": 6
  },
  "advisor": {
    "healthy": true
  }
}
```
