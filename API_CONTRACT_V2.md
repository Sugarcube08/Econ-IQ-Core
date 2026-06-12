# API CONTRACT (V2)

This document defines the frozen API schemas and endpoint structures for Econiq Core. In accordance with Phase 7 requirements, all legacy score references (`purchase_score`, `payment_score`, `rg_score`, legacy grades/states) are removed. The API serves only the 8 Canonical Scores.

---

## 1. Encapsulation & Security Boundaries

To prevent private intelligence feature leakage, the platform implements a hard partition:

* **Strictly Internal**: Raw signals, rolling features, and consolidated B2B dimensions.
* **Exposed Publicly**: The 8 Canonical Scores, automated recommendations, and model predictions.

---

## 2. Frozen Endpoint Directory

All routes are prefixed with `/api/v1`.

### A. Customers Listing
* **Path**: `GET /api/v1/customers`
* **Query Parameters**:
  * `page`: Int (Default: 1)
  * `limit`: Int (Default: 10)
  * `sort_by`: Str (Default: `trust_score`)
  * `sort_order`: Str (`asc` or `desc`)
  * `search`: Str (Fuzzy query ID, Name, City)
  * `current_state`: Str (Filter: `active`, `declining`, `dormant`, etc.)
  * Score-range filters: `health_score_min`/`max`, `risk_score_min`/`max`, etc.
* **JSON Response Schema**:
  ```json
  {
    "success": true,
    "message": "Customers retrieved successfully",
    "data": {
      "customers": [
        {
          "customer_id": "uuid-string",
          "customer_name": "Retail Corp",
          "city": "Mumbai",
          "health_score": 0.8543,
          "risk_score": 0.1250,
          "growth_score": 0.6543,
          "trust_score": 0.9123,
          "opportunity_score": 0.4321,
          "credit_score": 0.8912,
          "collection_score": 0.2345,
          "relationship_score": 0.9543,
          "state": "active",
          "outstanding_current": 12450.00,
          "outstanding_previous": 15600.00,
          "contribution_current": 1.45,
          "contribution_previous": 1.25,
          "last_purchase_date": "2026-06-11",
          "deltas": {
            "health_score": 0.0210,
            "risk_score": -0.0120,
            "growth_score": 0.0340,
            "trust_score": 0.0123,
            "opportunity_score": -0.0102,
            "credit_score": 0.0150,
            "collection_score": -0.0230,
            "relationship_score": 0.0050,
            "contribution_score": 0.20,
            "outstanding_delta": -20.19
          }
        }
      ]
    },
    "metadata": {
      "pagination": {
        "page": 1,
        "limit": 10,
        "total_records": 1,
        "total_pages": 1
      }
    }
  }
  ```

---

### B. Customer Profile Snapshots
* **Path**: `GET /api/v1/customer/{id}`
* **Response Schema**:
  ```json
  {
    "success": true,
    "message": "Customer profile retrieved successfully",
    "data": {
      "customer": {
        "customer_id": "uuid-string",
        "customer_name": "Retail Corp",
        "city": "Mumbai",
        "scores": {
          "health_score": 0.8543,
          "risk_score": 0.1250,
          "growth_score": 0.6543,
          "trust_score": 0.9123,
          "opportunity_score": 0.4321,
          "credit_score": 0.8912,
          "collection_score": 0.2345,
          "relationship_score": 0.9543,
          "outstanding_current": 12450.00,
          "outstanding_previous": 15600.00
        },
        "deltas": {
          "health_score": 0.0210,
          "risk_score": -0.0120,
          "growth_score": 0.0340,
          "trust_score": 0.0123,
          "opportunity_score": -0.0102,
          "credit_score": 0.0150,
          "collection_score": -0.0230,
          "relationship_score": 0.0050,
          "outstanding_delta": -20.19
        },
        "behavior_state": "active",
        "organization_contribution": {
          "current_percentage": 1.45,
          "delta": 0.20
        },
        "last_purchased_at": "2026-06-11",
        "updated_at": "2026-06-11T18:45:00Z"
      }
    }
  }
  ```

---

### C. Predictions Endpoint
* **Path**: `GET /api/v1/customer/{id}/predictions`
* **Response Schema**: Exactly matches prediction outputs for risk, growth, health, churn, collection, and opportunity metrics. Exposes SHAP driver names in `key_drivers` but shields core numeric features.
