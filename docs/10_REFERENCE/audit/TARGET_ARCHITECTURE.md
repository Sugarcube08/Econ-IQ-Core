# Econiq Target Architecture Blueprint

**Version:** 1.0.0  
**Status:** Approved  
**Author:** Principal Software Architect & Startup CTO  
**Owner:** Core Engineering Team

---

## 1. System Pipeline Layout

This section details the system architecture designed for our hackathon demonstration:

```
[PostgreSQL Database: Customers, Invoices, Payments, Returns] (Baseline Tables)
                                │
                                ▼ (Hourly Go Schedulers)
[Redis Online Feature Cache] (Hydrates sliding feature variables)
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼ (Inference API)                               ▼ (Decision Rules)
[Python FastAPI Service]                        [Recommendation Engine]
- XGBoost Default & Churn Predictors            - Suggests Credit Limit Changes
- CatBoost Collection Priority                  - Groups Collections Queue
- SHAP Feature Drivers                          - Logs Explainability Traces
        │                                               │
        └───────────────────────┬───────────────────────┘
                                ▼
                   [GraphQL API Gateway / Router]
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼ (Dashboard Widgets)                           ▼ (Conversational Assistant)
[React Frontend Client]                         [Gemini Copilot Sidebar]
- Prediction Cards                              - Why is customer risky?
- Prioritized Collection Lists                  - Why did score change?
- Credit Override Actions                       - What actions should I take?
```

---

## 2. Implementation Priority & Path

Below is the chronological order of implementation tasks to transition the reference codebase to the target Econiq platform:

### 2.1. Task 1: Correct the Ingestion Mapper & Database (Day 1)
*   **Action:** Modify the mapping logic in `dbupdater` to write valid transactions as `is_ok = 0`. Execute the SQL update script to swap `is_ok` values in database tables.
*   **Complexity:** Low.
*   **Risk:** Low.
*   **Impact:** Critical (Populates outstanding balances and risk indicators correctly).

### 2.2. Task 2: Implement Redis Feature Cache (Day 1)
*   **Action:** Setup the Redis feature cache structure. Update Go workers to write calculated features to Redis after sync runs.
*   **Complexity:** Medium.
*   **Risk:** Low.
*   **Impact:** High (Enables low-latency feature serving).

### 2.3. Task 3: Deploy FastAPI Python Inference Service (Day 2)
*   **Action:** Package FastAPI container running pre-trained XGBoost and CatBoost models. Define model endpoints (`/run-inference`) that fetch features from Redis.
*   **Complexity:** High.
*   **Risk:** Medium (Model drift and cold start latencies).
*   **Impact:** Critical (Delivers default and churn predictions).

### 2.4. Task 4: Integrate Recommendations & Alerts (Day 2)
*   **Action:** Write decision rules translating probabilities into action recommendations. Integrate warnings into the Alert Engine.
*   **Complexity:** Medium.
*   **Risk:** Low.
*   **Impact:** High (Provides credit overrides and collection priority lists).

### 2.5. Task 5: Deploy Copilot Gateway (Day 2)
*   **Action:** Set up the Copilot Gateway, formatting customer metrics and predictions into a JSON context payload passed to the LLM (Gemini Flash).
*   **Complexity:** High.
*   **Risk:** Medium (Hallucination risk).
*   **Impact:** High (Provides natural-language explanations).
