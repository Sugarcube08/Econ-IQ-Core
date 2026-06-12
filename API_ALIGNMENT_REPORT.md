# API CONTRACT VALIDATION & ALIGNMENT REPORT

This report validates that every backend endpoint conforms exactly to its DTO schemas, and verifies that no deprecated, legacy, undocumented, or hidden fields leak through API responses.

---

## 1. Mismatch Log & Status Tracker

| File | Location | Issue | Fix | Status |
| :--- | :--- | :--- | :--- | :--- |
| `core/schemas/recommendation.py` | `ActionRecommendation` | Missing fields: `priority`, `affected_score`, `expected_impact`, `action_category`, `reason`. Legacy field names: `recommendation_type`, `action`, `rationale`. | Updated `ActionRecommendation` schema model to include canonical fields (`type`, `priority`, `reason`, `affected_score`, `expected_impact`, `confidence`, `action_category`, `value`). | **RESOLVED** |
| `core/recommendation/service.py` | `generate_recommendations` | Output format did not match the corrected schema (was setting `action`, `rationale` and missing priority metrics). | Updated generation logic to output all required recommendation properties dynamically. | **RESOLVED** |
| `core/schemas/prediction.py` | `BasePrediction` | Missing consistent model metadata versioning schema on prediction outputs. | Added `model_version: str` to `BasePrediction` pydantic model. | **RESOLVED** |
| `core/prediction/service.py` | Estimators `predict()` | Estimator outputs did not populate the model version in their returned predictions. | Updated all default heuristic model estimators to dynamically output `model_version="1.0.0"`. | **RESOLVED** |
| `core/customers/routes.py` | `list_customers_datatable` | Verify that the page size and pagination metadata do not leak raw features or raw dataframes. | Audited payload to ensure only the 8 canonical scores and summary metadata are returned. | **VERIFIED** |

---

## 2. Validation Audit Details

### 2.1 Customer Profile Endpoint (`GET /customer/{id}`)
* **Schema Target**: `CustomerProfileResponseData`
* **Audit Verdict**: **PASS**
* **Verification Details**:
  * Response only contains canonical intelligence components (`health_score`, `risk_score`, `growth_score`, `trust_score`, `opportunity_score`, `credit_score`, `collection_score`, `relationship_score`) and their previous period offsets.
  * No legacy states or raw Polars Dataframe records are serialized.
  * Graceful degradation handles database starvation using resilient snapshot/degradation logic without leakage.

### 2.2 Customer List Endpoint (`GET /customers`)
* **Schema Target**: `CustomerDatatableResponseData`
* **Audit Verdict**: **PASS**
* **Verification Details**:
  * Exposes summary data matching the 8 canonical scores.
  * No heavy metrics calculation details, predictions, or recommendations are present in the list response payload.
  * Paginated queries filter directly on PostgreSQL indices for high performance.

### 2.3 Predictions Endpoint (`GET /customer/{id}/predictions`)
* **Schema Target**: Dictionary mapping prediction types to `BasePrediction` subclasses.
* **Audit Verdict**: **PASS**
* **Verification Details**:
  * Consistent structure across all prediction dimensions (Risk, Churn, Growth, Collection, Health, Opportunity).
  * Exposes `score`, `confidence`, `model_version`, `features_snapshot`, and `key_drivers`.

### 2.4 Recommendations Endpoint (`GET /customer/{id}/recommendations`)
* **Schema Target**: `CustomerRecommendations`
* **Audit Verdict**: **PASS**
* **Verification Details**:
  * Corrected model ensures every recommendation lists its `type`, `priority`, `reason`, `affected_score`, `expected_impact`, `confidence`, and `action_category`.
  * All items contain explanations (reasons).

### 2.5 Explainability Payloads
* **Audit Verdict**: **PASS**
* **Verification Details**:
  * Prediction outputs expose `key_drivers` (e.g. SHAP / feature importance proxies) and `features_snapshot`.
  * Score deltas are explicitly exposed as difference intervals (current - previous) so the frontend can display exact change indicators.
