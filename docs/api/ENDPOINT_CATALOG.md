# API Endpoint Catalog

This catalog documents every active endpoint exposed by the EconIQ core service.

---

## 1. Intelligence Endpoints

### 1.1 `GET /api/v1/dashboard`
- **Description:** Retrieves aggregate KPIs for the system landing page, including total credit exposure, aging distributions, high risk counts, and improving trends.
- **Required Permission:** `Permission.INTEL_READ`
- **Query Parameters:** None
- **Response Format:** `StandardResponse[DashboardOverview]`

### 1.2 `GET /api/v1/customer/{id}`
- **Description:** Returns the complete longitudinal customer profile containing the 8 Canonical scores, percentage contributions, and trends.
- **Required Permission:** `Permission.INTEL_READ`
- **Query Parameters:**
  - `window_days` (*integer, default 365*): Analysis time horizon.
- **Response Format:** `StandardResponse[CustomerProfileResponseData]`

### 1.3 `GET /api/v1/customer/{id}/timeline`
- **Description:** Client-constructed timeline query. Reconstructs historical customer events by querying collections, commitments, and sales ledgers.
- **Required Permission:** `Permission.INTEL_READ`
- **Query Parameters:** None
- **Response Format:** Array of unified timeline objects.

### 1.4 `GET /api/v1/customer/{id}/alerts`
- **Description:** Retrieves all active and acknowledged alerts registered specifically for the specified customer.
- **Required Permission:** `Permission.INTEL_READ`
- **Query Parameters:**
  - `status` (*string, default ACTIVE*): Filter alert status.
- **Response Format:** `StandardResponse[list[Alert]]`

### 1.5 `GET /api/v1/customer/{id}/recommendations`
- **Description:** Returns automated commercial priority actions generated for a single customer.
- **Required Permission:** `Permission.INTEL_READ`
- **Query Parameters:** None
- **Response Format:** `StandardResponse[CustomerRecommendations]`

---

## 2. Collections Endpoints

### 2.1 `POST /api/v1/collections/activity`
- **Description:** Logs a customer outreach action performed by a credit analyst.
- **Required Permission:** `Permission.INTEL_READ`
- **Body Schema:**
  - `customer_id` (*string*): Unique customer account identifier.
  - `activity_type` (*string - e.g. CALL, EMAIL, VISIT*): Type of interaction.
  - `notes` (*string*): Detailed notes.
  - `outcome` (*string - e.g. CONTACTED, PROMISE_MADE, NO_RESPONSE*): Outreach outcome.
- **Response Format:** `StandardResponse[CollectionActivity]`

### 2.2 `POST /api/v1/collections/commitment`
- **Description:** Registers a formal payment promise from a customer to pay a specific amount on a given date.
- **Required Permission:** `Permission.INTEL_READ`
- **Body Schema:**
  - `customer_id` (*string*): Unique customer account identifier.
  - `amount` (*float*): Promised payment amount.
  - `promised_date` (*string, YYYY-MM-DD*): Expected payment settlement date.
- **Response Format:** `StandardResponse[PaymentCommitment]`

---

## 3. Decisioning Endpoints

### 3.1 `POST /api/v1/decisions/action`
- **Description:** Logs an override decision action by a credit analyst (approving, overriding, or rejecting an automated recommended action).
- **Required Permission:** `Permission.INTEL_READ`
- **Body Schema:**
  - `customer_id` (*string*): Unique customer identifier.
  - `recommendation_id` (*string*): Associated recommendation UUID.
  - `action_taken` (*string - APPROVED, REJECTED, OVERRIDDEN*): Action type.
  - `reason` (*string*): Justification reason notes.
- **Response Format:** `StandardResponse[DecisionAudit]`

---

## 4. Machine Learning (ML) Endpoints

### 4.1 `GET /api/v1/ml/models`
- **Description:** Lists metadata for all registered models inside the system registry.
- **Required Permission:** Public / API Key
- **Response Format:** `list[ModelMetadataDTO]`

### 4.2 `GET /api/v1/ml/calibration`
- **Description:** Computes and retrieves reliability metrics, Brier scores, and calibration evaluations.
- **Required Permission:** Public / API Key
- **Response Format:** Calibration JSON.

### 4.3 `GET /api/v1/ml/explanation/{id}`
- **Description:** Computes SHAP value explanations for a customer prediction (churn, distress, or delinquency).
- **Required Permission:** Public / API Key
- **Query Parameters:**
  - `model_type` (*string, default churn*): Model name.
- **Response Format:** SHAP explanation JSON.

### 4.4 `POST /api/v1/ml/simulate`
- **Description:** Performs a what-if counterfactual scenario simulation to assess how changes (e.g. extending credit terms, logging calls) alter a customer's default/distress risk profile.
- **Required Permission:** Public / API Key
- **Body Schema:**
  - `customer_id` (*string*): Customer ID.
  - `actions` (*list[string]*): Applied simulation actions.
- **Response Format:** `SimulationResponse`

---

## 5. Advisor Endpoints

### 5.1 `GET /api/v1/advisor/customer/{id}`
- **Description:** Integrates current state, SHAP explanations, and simulations to generate a prioritized recommended list of actions.
- **Required Permission:** Public / API Key
- **Response Format:** Unified Advice payload.

---

## 6. Health & Infrastructure Endpoints

### 6.1 `GET /api/v1/system/capabilities`
- **Description:** Evaluates the functional health status of all 8 core platform capabilities by running table counts against their respective SQL entities.
- **Required Permission:** None
- **Response Format:** Capability health checklist dictionary.

### 6.2 `GET /api/v1/health` (or `GET /health`)
- **Description:** General system heartbeat for orchestration layers.
- **Required Permission:** None
- **Response Format:** `StandardResponse[Heartbeat]`
