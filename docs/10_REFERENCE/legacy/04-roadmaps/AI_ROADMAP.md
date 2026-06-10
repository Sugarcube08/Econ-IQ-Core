# Econiq AI & Intelligence Roadmap

**Version:** 2.1.0  
**Status:** Approved  
**Author:** ML Architect & Data Science Lead  
**Owner:** Analytics & ML Team

---

## 1. Evolution Matrix

The platform's intelligence evolves through three distinct capability phases:

```
[Current State: Analytics & SQL]
               │
               ▼
[Target State (2-Week Demo): Applied ML & XGBoost]
               │
               ▼
[Future State: Deep Sequence & Graph Contagion]
```

| Phase | Capability Level | Core Algorithms | Primary Output | Explainability Method |
| :--- | :--- | :--- | :--- | :--- |
| **Current State** | Analytics | SQL aggregations | Days Past Due (DPD) logs | 100% (SQL formulas) |
| **Target State (Sprint)**| Applied ML | XGBoost, CatBoost, Isolation Forest | Default, Churn, & Recovery probabilities | SHAP Value Allocations |
| **Future State** | Deep Learning | LSTMs, Temporal Fusion Transformers | Sequence-based settlement dates | Self-attention weights |
| **Network State** | Graph Intelligence| Graph Convolutional Networks (GCN) | Systemic contagion risks | Network node graphs |

---

## 2. Current State: Analytics & SQL (Baseline)
*   **Approach:** Heuristic and rules-based calculations.
*   **Infrastructure:** PostgreSQL database running raw SQL query sweeps.
*   **Explainability:** High. Simple calculations, but historical state changes are lost.

---

## 3. Target State: Applied ML (The Hackathon Scope)
*   **Approach:** Tabular classification models run on cached feature tables.
*   **Infrastructure:** Python FastAPI container fetching online feature matrices from Redis.
*   **Algorithms:**
    *   **XGBoost Classifiers:** Default and churn risk forecasting.
    *   **CatBoost Regressors:** Settlement date and recovery probability prediction.
    *   **Isolation Forest:** Transaction outlier detection.
*   **Explainability:** SHAP values represent individual feature contributions.

---

## 4. Future State: Deep Learning & Graphs (Post-Demo)

### 4.1. Sequence Learning (Months 6–12)
*   **Approach:** PyTorch sequence models.
*   **Technology:** LSTMs and Temporal Fusion Transformers (TFT).
*   **Value:** Ingests raw chronology sequences of invoices, payments, and returns, removing the need for manual feature engineering.

### 4.2. Graph Contagion (Months 12–18)
*   **Approach:** Graph Neural Networks (GNN).
*   **Technology:** Graph Convolutional Networks (GCN) running on Neo4j.
*   **Value:** Maps credit links across multiple wholesalers to flag risk propagation: if a retailer defaults on Wholesaler A, the network propagates warning indicators to Wholesaler B.
