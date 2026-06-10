# Econiq Implementation & Hackathon Roadmap

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Startup CTO & Hackathon Lead  
**Owner:** Core Engineering Team

---

## 1. Hackathon 2-Week Sprint Plan

To transform the existing analytics dashboard into an AI-first Commercial Decision Infrastructure:

```
[Week 1: Data & Models] ──► [Week 2: Decisions & Front-end Overlay] ──► [Hackathon Demo]
```

### 1.1. Week 1: Data Foundation & Model Training (Days 1–7)
*   **Days 1–2 (Data & Features):** Seeding PostgreSQL with 12 months of synthetic transaction records (Cohort A, B, and C). Configure Go schedulers to populate the Redis Feature Cache.
*   **Days 3–5 (FastAPI ML Containers):** Package FastAPI serving containers. Train XGBoost models for default/churn classifications and CatBoost for collections priority recovery probabilities.
*   **Days 6–7 (Model Explanations):** Configure SHAP estimators inside the FastAPI inference loop to output local feature drivers. Create DB tables to cache predictions and SHAP vectors.

### 1.2. Week 2: Recommendations, Alerts & UI Overlay (Days 8–14)
*   **Days 8–9 (Decision Engine):** Deploy the Recommendation Engine, writing decision rules that translate model probabilities into actions.
*   **Days 10–11 (Copilot Gateway):** Set up the Copilot Gateway interface, injecting resolved JSON customer features into the LLM context (Gemini Flash).
*   **Days 12–13 (Frontend Integration):** Update React components, adding credit override forms, prioritized collection tables, predictive warning flags, and the Copilot sidebar.
*   **Day 14 (Dry Run & Validation):** Run end-to-end sync jobs and simulate customer transactions to confirm prediction outputs and explainability traces.

---

## 2. Post-Hackathon & Future Scale Stages

### 2.1. Phase 2: Production Scaling (Months 1–6)
*   Migrate data pipeline execution checks to Apache Airflow and dbt.
*   Introduce click-to-pay webhooks and auto-reconciliation ledgers.
*   Deploy Feast Feature Store to automate online/offline feature pipelines.

### 2.2. Phase 3: Deep Sequence Learning & GNNs (Months 6–18)
*   **Deep Sequence Models:** Replace tabular models with PyTorch LSTMs and Temporal Fusion Transformers (TFT) to ingest raw sequence timelines.
*   **Graph Neural Networks (GNN):** Build multi-wholesaler graphs on Neo4j/Neptune, using Graph Convolutional Networks (GCN) to propagate credit default contagion warnings across the network.
