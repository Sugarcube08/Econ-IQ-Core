# Scoring Engine Abstraction & ML Roadmap

This document analyzes the scoring engines of the legacy backend, decomposing them into universal mathematical functions, configurable policies, and candidates for Machine Learning (ML) and Deep Learning (DL) replacements.

---

## 1. Classification of Scoring Engine Components

To generalise the platform into **Econiq Core**, we partition the scoring engines as follows:

| Engine | Universal Components (Invariant Math) | Organization Components (Business Logic) | Configurable Components (Parameters) | ML / DL Candidates |
| :--- | :--- | :--- | :--- | :--- |
| **Trust Engine** | Weighted fusion algebra of normalized indicators. | Selection of fused indicators. | Weight coefficients (currently $0.5 / 0.5$). | **ML:** Predict probability of default (PD) using XGBoost rather than a static trust score. |
| **Exposure Engine** | Double-entry balance calculation: $\sum \text{sales} - \sum (\text{payments} + \text{returns})$. | Exclusion criteria for certain transactions. | Ledger anchor dates; voided transaction handling. | **DL:** Time-series forecast of future outstanding balance exposure using LSTM/GRUs. |
| **Stress Engine** | Ratios of returned goods to purchases; deficiency ratios. | Deficit calculations; penalty multiplier rules. | Denominator limits ($100.0$ min sales); return stress weight ($0.8$). | **ML:** Anomaly detection on transaction amounts and frequency using Isolation Forests. |
| **States Engine** | Cumulative counts, sorting, and join-as-of temporal bounds. | State label definitions (`elite`, `active`, `declining`, `irregular`). | Score thresholds (e.g. $0.75$, $0.60$, $0.15$); window bounds ($365\text{d}$, $14\text{d}$). | **ML/DL:** Markov Chain models or Recurrent Neural Networks to predict state transitions. |
| **Payment Discipline** | Average repayment days, coefficient of variation (CV) for consistency. | Categorization of repayment speed categories. | Grace credit terms ($60$ days); payment fragmentation limit ($2.5$). | **ML:** Predict probability of next-payment delay using LightGBM. |
| **Returned Goods** | Ratio of returned goods value to total purchase value. | Logic for identifying fault (customer vs. company fault). | Penalty weights ($1.0$ for customer, $0.0$ for genuine returns). | **ML:** Predict return likelihood at checkout based on historical items. |
| **Cadence Engine** | Median and standard deviation of gaps between sale events. | Rhythm classifications (`seasonal`, `stable_cadence`). | Minimum transactions for calculation ($3$); variance scale ($1.5$). | **ML:** Unsupervised clustering (K-Means) to identify merchant buying personas. |

---

## 2. Abstraction Interface Specification

To implement this abstraction, the engines will inherit from a base `BaseScoringEngine` that defines a generic interface. Scoring configurations are injected at runtime via a context block:

```python
from abc import ABC, abstractmethod
import polars as pl

class BaseScoringEngine(ABC):
    @abstractmethod
    def compute(self, features_df: pl.DataFrame, policy_config: dict) -> pl.DataFrame:
        """
        Calculates scores and segments for a batch of customers.
        """
        pass
```

---

## 3. Machine Learning & Deep Learning Transition Roadmap

```mermaid
roadmap
    title Econiq Intelligence Evolution Matrix
    section Phase 1 (Hackathon - Current)
        Deterministic Polars Engines : active, 2026-06-10, 2026-06-15
        Dynamic Config YAML Policies : active, 2026-06-12, 2026-06-16
    section Phase 2 (Next 3 Months)
        XGBoost Risk Classifier : 2026-06-16, 2026-07-31
        LightGBM Churn Predictor : 2026-06-25, 2026-08-15
        CatBoost Priority Router : 2026-07-01, 2026-08-30
    section Phase 3 (Future DL Expansion)
        LSTM Cash Flow Forecaster : 2026-09-01, 2026-12-31
        Temporal State Sequence Model : 2026-10-01, 2026-12-31
```

### 3.1 XGBoost Risk Engine (Phase 2)
*   **Objective:** Replace the deterministic `TrustEngine` and `StateEngine` with a model predicting the probability of default within the next 90 days.
*   **Inputs:** `log_sales_scale`, `participation_density`, `debit_persistence_days`, `repayment_regularity_score`, `rg_rate_score`.
*   **Outputs:** Continuously updated risk percentages ($0.00\text{--}1.00$).

### 3.2 LightGBM Churn Predictor (Phase 2)
*   **Objective:** Replace the deterministic `trajectory` calculations (`COLLAPSING`, `DECLINING`) with a model predicting if a merchant will stop trading within 30 days.
*   **Inputs:** Longitudinal trends in purchase cadence, monthly sales delta, and payment delays.

### 3.3 LSTM Cash Flow & Exposure Forecaster (Phase 3)
*   **Objective:** Predict the daily outstanding balance of a customer for the next 90 days.
*   **Inputs:** Full historical sequence of sales, payments, and return events.
*   **Why DL:** Deep learning (LSTM/GRU or Temporal Fusion Transformers) excels at capturing long-term sequential dependencies and multi-step time series forecasting, which simple statistical rolling aggregations cannot model.
