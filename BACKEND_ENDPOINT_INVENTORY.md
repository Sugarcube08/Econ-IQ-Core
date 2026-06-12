# BACKEND ENDPOINT INVENTORY

This document provides a master registry of all API endpoints implemented in the Econiq Core backend system. It details the HTTP methods, paths, purpose, authentication/permissions, request schemas, response formats, dependencies, and example responses/errors for each serving route.

---

## 1. Authentication Endpoints

### POST /api/v1/auth/request-otp
* **Method**: `POST`
* **Route**: `/api/v1/auth/request-otp`
* **Purpose**: Initiates user sign-in by generating and dispatching a one-time password (OTP) to the specified email address if the account exists.
* **Authentication**: None (Public)
* **Request Schema**:
  ```json
  {
    "email": "string"
  }
  ```
* **Response Schema**: `StandardResponse[dict[str, str]]`
* **Dependencies**: `AuthService`, `AuthRepository`
* **Serving Source**: PostgreSQL (`users` database lookup)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "If an account exists, an OTP has been sent.",
    "data": {
      "email": "user@example.com"
    },
    "metadata": {}
  }
  ```
* **Example Errors**:
  * **400 Bad Request** (Invalid email format)
  * **429 Too Many Requests** (OTP request rate limit exceeded)

### POST /api/v1/auth/verify-otp
* **Method**: `POST`
* **Route**: `/api/v1/auth/verify-otp`
* **Purpose**: Verifies the OTP sent to the user's email and returns a pair of Access and Refresh tokens on success.
* **Authentication**: None (Public)
* **Request Schema**:
  ```json
  {
    "email": "string",
    "otp": "string",
    "device_id": "string (optional)"
  }
  ```
* **Response Schema**: `StandardResponse[TokenResponseSchema]`
* **Dependencies**: `AuthService`, `AuthRepository`
* **Serving Source**: Redis (OTP storage) & PostgreSQL (`users` and `audit_logs` tables)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Authentication successful",
    "data": {
      "access_token": "eyJhbGciOiJSUzI1NiIsIn...",
      "refresh_token": "eyJhbGciOiJSUzI1NiIsIn...",
      "token_type": "bearer",
      "expires_in": 3600
    },
    "metadata": {}
  }
  ```
* **Example Errors**:
  * **401 Unauthorized** (Invalid or expired OTP)
  * **403 Forbidden** (Account locked due to too many failed attempts)

### POST /api/v1/auth/refresh
* **Method**: `POST`
* **Route**: `/api/v1/auth/refresh`
* **Purpose**: Exchanges a valid Refresh Token for a new pair of Access and Refresh tokens.
* **Authentication**: Bearer token signature validation
* **Request Schema**:
  ```json
  {
    "refresh_token": "string",
    "device_id": "string (optional)"
  }
  ```
* **Response Schema**: `StandardResponse[TokenResponseSchema]`
* **Dependencies**: `AuthService`, `AuthRepository`
* **Serving Source**: PostgreSQL (`user_sessions` and `users` tables)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Token refreshed successfully",
    "data": {
      "access_token": "eyJhbGciOiJSUzI1NiIsIn...",
      "refresh_token": "eyJhbGciOiJSUzI1NiIsIn...",
      "token_type": "bearer",
      "expires_in": 3600
    },
    "metadata": {}
  }
  ```
* **Example Errors**:
  * **401 Unauthorized** (Invalid or expired refresh token)

### POST /api/v1/auth/logout
* **Method**: `POST`
* **Route**: `/api/v1/auth/logout`
* **Purpose**: Invalidates the active user session and revokes the provided Refresh Token.
* **Authentication**: Bearer Token
* **Request Schema**:
  ```json
  {
    "refresh_token": "string"
  }
  ```
* **Response Schema**: `StandardResponse[None]`
* **Dependencies**: `AuthService`, `AuthRepository`
* **Serving Source**: PostgreSQL (`user_sessions` soft deletion)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Successfully logged out.",
    "data": null,
    "metadata": {}
  }
  ```
* **Example Errors**:
  * **401 Unauthorized** (Missing or invalid authorization header)

### GET /api/v1/auth/me
* **Method**: `GET`
* **Route**: `/api/v1/auth/me`
* **Purpose**: Retrieves details of the currently authenticated user session.
* **Authentication**: Bearer Token
* **Request Schema**: None
* **Response Schema**: `StandardResponse[UserResponseSchema]`
* **Dependencies**: `get_current_user` dependency
* **Serving Source**: JWT token payload extraction & PostgreSQL verification
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "User profile retrieved successfully",
    "data": {
      "id": "d134b22c-a2b1-4c12-9c1b-e5012a9c1404",
      "email": "analyst@econiq.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "ANALYST",
      "is_active": true
    },
    "metadata": {}
  }
  ```
* **Example Errors**:
  * **401 Unauthorized** (Invalid or expired token)

### GET /api/v1/auth/debug/ip
* **Method**: `GET`
* **Route**: `/api/v1/auth/debug/ip`
* **Purpose**: diagnostic endpoint to inspect and verify client IP extraction rules and proxy headers.
* **Authentication**: None (Public - should be restricted in production config)
* **Request Schema**: None
* **Response Schema**: `StandardResponse[dict]`
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Client IP diagnostic info",
    "data": {
      "detected_ip": "192.168.1.50",
      "request_client_host": "127.0.0.1",
      "headers": {
        "x-forwarded-for": "192.168.1.50",
        "user-agent": "Mozilla/5.0..."
      },
      "environment": "development"
    },
    "metadata": {}
  }
  ```

---

## 2. Customer Endpoints

### GET /api/v1/customers
* **Method**: `GET`
* **Route**: `/api/v1/customers`
* **Purpose**: Paginated, sortable, and filterable listing of business customers with summary intelligence payloads.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)
* **Request Schema (Query Parameters)**:
  * `page` (default: 1): integer
  * `limit` (default: 10): integer
  * `sort_by` (default: "trust_score"): string
  * `sort_order` (default: "desc"): string
  * `search`: string (fuzzy search on ID, name, city)
  * `current_state`: string (comma-separated list, e.g., "healthy,monitor")
  * Scores range filters (e.g. `health_score_min`, `health_score_max`)
* **Response Schema**: `StandardResponse[CustomerDatatableResponseData]`
* **Dependencies**: `get_db`
* **Serving Source**: PostgreSQL (`customer_intelligence` materialized table)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Customers retrieved successfully",
    "data": {
      "customers": [
        {
          "customer_id": "CUST-001",
          "customer_name": "Acme Industrial Corp",
          "city": "Mumbai",
          "health_score": 0.8521,
          "risk_score": 0.1245,
          "growth_score": 0.7512,
          "trust_score": 0.9102,
          "opportunity_score": 0.6514,
          "credit_score": 0.8201,
          "collection_score": 0.8951,
          "relationship_score": 0.8804,
          "state": "healthy",
          "outstanding_current": 145000.00,
          "outstanding_previous": 120000.00,
          "contribution_current": 2.45,
          "contribution_previous": 2.15,
          "last_purchase_date": "2026-06-10",
          "deltas": {
            "health_score": 0.025,
            "risk_score": -0.015,
            "growth_score": 0.05,
            "trust_score": 0.01,
            "opportunity_score": 0.02,
            "credit_score": 0.03,
            "collection_score": 0.015,
            "relationship_score": 0.02,
            "contribution_score": 0.3,
            "outstanding_delta": 20.83
          }
        }
      ]
    },
    "metadata": {
      "pagination": {
        "page": 1,
        "limit": 1,
        "total_records": 124,
        "total_pages": 124,
        "has_next": true,
        "has_previous": false
      },
      "sorting": {
        "sort_by": "trust_score",
        "sort_order": "desc"
      },
      "filters": {
        "current_state": null,
        "health_score_range": [null, null]
      },
      "search": null,
      "processing_time_ms": 12
    }
  }
  ```

### GET /api/v1/customer/{id}
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}`
* **Purpose**: Retrieves a comprehensive commercial profile containing the 8 canonical intelligence scores and deltas.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)
* **Request Schema (Query Parameters)**:
  * `window_days` (default: 365): integer
  * `start_date`: string (date YYYY-MM-DD)
  * `end_date`: string (date YYYY-MM-DD)
* **Response Schema**: `StandardResponse[CustomerProfileResponseData]`
* **Dependencies**: `IntelligenceRepository`, `ResilientIntelligenceOrchestrator`
* **Serving Source**: PostgreSQL (`customer_intelligence` for default window, or dynamic aggregation from `event_ledger` for custom periods)
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Customer profile retrieved successfully (materialized cache)",
    "data": {
      "customer": {
        "customer_id": "CUST-001",
        "customer_name": "Acme Industrial Corp",
        "city": "Mumbai",
        "scores": {
          "health_score": 0.8521,
          "risk_score": 0.1245,
          "growth_score": 0.7512,
          "trust_score": 0.9102,
          "opportunity_score": 0.6514,
          "credit_score": 0.8201,
          "collection_score": 0.8951,
          "relationship_score": 0.8804,
          "outstanding_current": 145000.00,
          "outstanding_previous": 120000.00
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
    },
    "metadata": {
      "mode": "materialized",
      "window_days": 365,
      "processing_time_ms": 5
    }
  }
  ```

---

## 3. Predictions and Recommendations Endpoints

### GET /api/v1/customer/{id}/predictions
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/predictions`
* **Purpose**: Retrieves all predictive analytics outputs (Risk, Growth, Health, Churn, Collection, Opportunity) for the given customer.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)
* **Request Schema (Query Parameters)**:
  * `version`: string (model version string, optional)
* **Response Schema**: `StandardResponse[dict]`
* **Dependencies**: `PredictionService`, `ModelRegistry`
* **Serving Source**: Dynamic inference using registered estimators and customer transaction aggregates
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "All predictions retrieved successfully",
    "data": {
      "risk": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.1245,
        "confidence": 0.95,
        "model_version": "1.0.0",
        "features_snapshot": {
          "sales_window": 145000.0,
          "payments_window": 120000.0
        },
        "key_drivers": ["payment_regularity"],
        "risk_level": "LOW"
      },
      "growth": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.7512,
        "confidence": 0.88,
        "model_version": "1.0.0",
        "features_snapshot": {
          "sales_window": 145000.0,
          "sales_recent": 45000.0
        },
        "key_drivers": ["sales_recent_velocity"],
        "growth_potential": "EXPANSION"
      },
      "health": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.8521,
        "confidence": 0.92,
        "model_version": "1.0.0",
        "features_snapshot": {},
        "key_drivers": ["payment_ratio"],
        "health_grade": "B"
      },
      "churn": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.05,
        "confidence": 0.90,
        "model_version": "1.0.0",
        "features_snapshot": {},
        "key_drivers": ["days_since_last_purchase"],
        "is_churn_risk": false
      },
      "collection": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.8951,
        "confidence": 0.85,
        "model_version": "1.0.0",
        "features_snapshot": {},
        "key_drivers": ["historical_repayment_ratio"],
        "repayment_probability": 0.8951,
        "expected_delay_days": 9
      },
      "opportunity": {
        "customer_id": "CUST-001",
        "prediction_date": "2026-06-12",
        "score": 0.6514,
        "confidence": 0.82,
        "model_version": "1.0.0",
        "features_snapshot": {},
        "key_drivers": ["sales_vs_category_diversity"],
        "opportunity_tier": "HIGH",
        "expected_upsell_value": 21750.00
      }
    },
    "metadata": {}
  }
  ```

### GET /api/v1/customer/{id}/recommendations
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/recommendations`
* **Purpose**: Generates automated next-best-action recommendations for a customer.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)
* **Request Schema**: None
* **Response Schema**: `StandardResponse[CustomerRecommendations]`
* **Dependencies**: `RecommendationService`, `PredictionService`
* **Serving Source**: Policy rules triggered by active predictive metrics and thresholds
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "Recommendations generated successfully",
    "data": {
      "customer_id": "CUST-001",
      "generated_date": "2026-06-12",
      "recommendations": [
        {
          "type": "CREDIT_LIMIT",
          "priority": "MEDIUM",
          "reason": "Customer exhibits low payment default risk coupled with expanding trading volume.",
          "affected_score": "credit_score",
          "expected_impact": "HIGH",
          "confidence": 0.90,
          "action_category": "INCREASE_CREDIT_LIMIT",
          "value": "20% Increase"
        },
        {
          "type": "PAYMENT_TERMS",
          "priority": "LOW",
          "reason": "Highly reliable payment discipline supports extended terms to capture trading growth.",
          "affected_score": "collection_score",
          "expected_impact": "MEDIUM",
          "confidence": 0.85,
          "action_category": "EXTEND_PAYMENT_TERMS",
          "value": "Net-60"
        }
      ]
    },
    "metadata": {}
  }
  ```

---

## 4. Analytical Graphs Endpoints

### GET /api/v1/customer/{id}/purchase-graph
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/purchase-graph`
* **Purpose**: Provides periodic sales/billing trends reconstructed from the ledger.
* **Request Schema (Query Parameters)**:
  * `window_days` (default: 365): integer
  * `granularity` (default: "weekly"): string (`daily`, `weekly`, `monthly`, `yearly`)

### GET /api/v1/customer/{id}/payment-graph
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/payment-graph`
* **Purpose**: Provides periodic payment collection flows.

### GET /api/v1/customer/{id}/rg-graph
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/rg-graph`
* **Purpose**: Provides returns and credits timeline.

### GET /api/v1/customer/{id}/outstanding-graph
* **Method**: `GET`
* **Route**: `/api/v1/customer/{id}/outstanding-graph`
* **Purpose**: Provides opening, additions, settlements, and closing outstanding receivables balances.

---

## 5. Dashboard Endpoints

### GET /api/v1/dashboard/overview
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/overview`
* **Purpose**: Key executive KPI metrics and comparative period deltas.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)

### GET /api/v1/dashboard/commercial-flow
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/commercial-flow`
* **Purpose**: Longitudinal commercial billing vs collection vs outstanding timeline.

### GET /api/v1/dashboard/aging-distribution
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/aging-distribution`
* **Purpose**: Receivable exposure grouped by overdue buckets.

### GET /api/v1/dashboard/state-distribution
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/state-distribution`
* **Purpose**: Customer segmentation count across behavioral states.

### GET /api/v1/dashboard/deteriorating-customers
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/deteriorating-customers`
* **Purpose**: Immediate attention queue of accounts with largest score drops.

### GET /api/v1/dashboard/improving-customers
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/improving-customers`
* **Purpose**: Opportunity queue of accounts with largest score gains.

### GET /api/v1/dashboard/high-risk-customers
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/high-risk-customers`
* **Purpose**: Credit risk queue ranked by exposure and stress indicators.

### GET /api/v1/dashboard/activity-summary
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/activity-summary`
* **Purpose**: Summary strip of newly active/inactive, trust gain/loss, and overdue accounts.

### GET /api/v1/dashboard/top-contributors
* **Method**: `GET`
* **Route**: `/api/v1/dashboard/top-contributors`
* **Purpose**: Concentration analysis listing top sales volume accounts.

---

## 6. Exports & System Endpoints

### GET /api/v1/customers/export/csv
* **Method**: `GET`
* **Route**: `/api/v1/customers/export/csv`
* **Purpose**: Export custom filtered list of customers as a CSV file.
* **Authentication**: Bearer Token or API Key (`Permission.INTEL_READ`)

### GET /api/v1/health
* **Method**: `GET`
* **Route**: `/api/v1/health`
* **Purpose**: Lightweight service health check.
* **Authentication**: None
* **Example Response**:
  ```json
  {
    "success": true,
    "message": "System healthy",
    "data": {
      "status": "healthy",
      "environment": "production",
      "version": "2.0.0"
    },
    "metadata": {}
  }
  ```
