# Econiq Target Architecture: Hackathon Transition Blueprint

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Principal Product Architect & Startup CTO  
**Owner:** Core Engineering Team

---

## 1. System Transition Mapping

To deliver an **AI-first Commercial Decision Infrastructure** within 2 weeks, we categorize every system component as follows:

```
                  ┌────────────────────────────────────────┐
                  │          TRANSITION MAPPING            │
                  └───────────────────┬────────────────────┘
         ┌────────────────┬───────────┴────┬───────────────┐
         ▼                ▼                ▼               ▼
     [KEEP]           [MODIFY]         [REPLACE]        [BUILD NEW]
   Auth, RLS,       Normalizers,     Static alerts   Features, Scores,
   Ingest APIs      Dashboard UI     with ML alerts  ML models, Copilot
```

| Component | Transition | Core Architectural Action | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Authentication & RLS** | `KEEP` | Keep standard JWT validation and Row-Level Security isolation. | `LOW` |
| **Connectors & Ingestion** | `KEEP` | Ingest Tally/BUSY payloads directly to Go parsers. | `LOW` |
| **Normalization Engine** | `MODIFY` | Calculate raw Data Quality Scores (DQS) per sync execution. | `MEDIUM` |
| **Sales Ledger (Invoices)** | `KEEP` | PostgreSQL transactional tables remain the ledger system of record. | `LOW` |
| **Timeline Engine** | `MODIFY` | Read events directly from invoices and payments tables using DB queries instead of event stores. | `MEDIUM` |
| **Feature Store** | `BUILD NEW` | Write a Redis feature cache to serve FastAPI models and UI queries. | `HIGH` |
| **Metrics & Scoring** | `BUILD NEW` | Compute health, risk, growth, and collections scores on sync execution. | `HIGH` |
| **Prediction Engine (ML)**| `BUILD NEW` | Deploy a Python FastAPI container running XGBoost/CatBoost classifiers. | `CRITICAL` |
| **Recommendation Engine** | `BUILD NEW` | Implement decision rules (credit overrides, collection priority). | `CRITICAL` |
| **Alert Engine** | `REPLACE` | Replace static SQL alerts with predictive alerts driven by ML scoring. | `HIGH` |
| **Copilot Layer** | `BUILD NEW` | Build an LLM context compiler loading structured customer metrics. | `HIGH` |
| **Dashboard UI** | `MODIFY` | Overlay ML predictions, recommendations, and the Copilot sidebar. | `HIGH` |

---

## 2. Dynamic Data and Logic Flows

```
[ERP raw sync upload] ──► [Go normalizer parses database fields]
                                      │
                                      ▼
[PostgreSQL: Invoices, Payments, Returns, Customers] (Baseline Tables)
                                      │
                                      ▼
[Go Scheduler/Worker computes metrics & stores in Redis feature cache]
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ▼                                                           ▼
[Python FastAPI Inference API]                              [Recommendation Engine]
(Evaluates XGBoost Default & Churn)                         (Prioritizes Collections)
        │                                                           │
        └─────────────────────────────┬─────────────────────────────┘
                                      ▼
                 [GraphQL API Gateway serves React Client]
                     - Dashboard widgets (ML predictions)
                     - Copilot chat window (LLM explanations)
```

---

## 3. Implementation Priorities & 2-Week Plan

### 3.1. Phase 1 (Days 1–4): Data & Features
*   Define feature aggregations in Go.
*   Setup Redis to serve as the Feature cache.
*   Write scripts to populate Postgres tables with synthetic transaction data (to simulate long-term customer histories for the judges).

### 3.2. Phase 2 (Days 5–8): ML Modeling
*   Build Python FastAPI service container.
*   Train XGBoost models on synthetic data to output default risk, churn risk, and collections recovery probabilities.
*   Integrate SHAP libraries to log feature drivers.

### 3.3. Phase 3 (Days 9–11): Recommendations & Alerts
*   Implement decision rules that translate model probabilities into actions (e.g. `P_default > 0.75` -> `HOLD_SHIPMENT`).
*   Deploy predictive alert rules inside the Go worker thread.

### 3.4. Phase 4 (Days 12–14): Copilot & Dashboard
*   Deploy the Copilot Gateway, routing prompt payloads to the LLM (Gemini Flash).
*   Add prediction summaries, collection queues, and the chat interface to the React frontend.
