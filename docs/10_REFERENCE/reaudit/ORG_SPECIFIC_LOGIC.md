# Organization Assumption Extraction

This document isolates and audits every organization-specific rule, threshold, classification, weight, and formula that is currently hardcoded in the legacy econiq codebase.

---

## 1. Inventory of Hardcoded Logic & Assumptions

### 1.1 Customer State Transitions
*   **Location:** [states/engine.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/states/engine.py#L107-L118)
*   **Purpose:** Assign a customer to one of the following states: `inactive`, `declining`, `elite`, `active`, or `irregular`.
*   **Current Behavior:**
    *   If total events in the window (`events_window`) is `0`, state is `inactive`.
    *   If stress score (`stress_score`) is `> 0.6`, state is `declining`.
    *   If trust score (`trust_score`) is `> 0.75` and stress score is `< 0.15`, state is `elite`.
    *   If trust score is `> 0.45` and stress score is `< 0.35`, state is `active`.
    *   Otherwise, the state defaults to `irregular`.
    *   **Refinement:** If state is not `inactive` and trajectory is `COLLAPSING` or `DECLINING`, or stress score is `> 0.5`, the state is forced to `declining`.
*   **Why It Exists:** Built for a specific company's risk tolerances, where low-trust and high-returns immediately trigger declining classification.
*   **Generic Equivalent:** Dynamic State Classifier using configurable rules.
*   **Migration Strategy:** Move state conditions to a JSON/YAML configuration file or table. Read the rules and evaluate them dynamically using a lightweight rule-engine interpreter.

---

### 1.2 Sales Velocity & Trajectory Classification
*   **Location:** [states/engine.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/states/engine.py#L136-L149)
*   **Purpose:** Determine customer trading trajectory.
*   **Current Behavior:**
    *   If recent events (`events_recent`) in the last 14 days is `0`, trajectory is `inactive`.
    *   If sales velocity ratio (`current_velocity / historical_velocity`) is `> 1.5` and historical velocity is `> 0`, trajectory is `ACCELERATING`.
    *   If velocity ratio is between `1.1` and `1.5`, trajectory is `GROWING`.
    *   If velocity ratio is `< 0.5` and historical velocity is `> 0`, trajectory is `COLLAPSING`.
    *   If velocity ratio is between `0.5` and `0.8`, trajectory is `DECLINING`.
    *   Otherwise, trajectory is `STABLE`.
*   **Why It Exists:** Evaluates if a customer's business scale is growing or shrinking.
*   **Generic Equivalent:** Velocity ratio bands.
*   **Migration Strategy:** Shift boundary values (`1.5`, `1.1`, `0.8`, `0.5`) and rolling windows (14 days, 365 days) into dynamic profile settings.

---

### 1.3 Holistic Credit Classification Bands
*   **Location:** [states/engine.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/states/engine.py#L165-L174)
*   **Purpose:** Assign a customer class grade (`A`, `B`, `C`, or `D`) based on trust score.
*   **Current Behavior:**
    *   `trust_score >= 0.70` $\rightarrow$ Class `A`
    *   `trust_score >= 0.55` $\rightarrow$ Class `B`
    *   `trust_score >= 0.40` $\rightarrow$ Class `C`
    *   Otherwise $\rightarrow$ Class `D`
*   **Why It Exists:** Simple segment assignment to determine credit eligibility.
*   **Generic Equivalent:** Grade boundary thresholds.
*   **Migration Strategy:** Move grade thresholds into the database/policy engine.

---

### 1.4 Trust Score Fusion Weights
*   **Location:** [trust/engine.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/trust/engine.py#L43-L51)
*   **Purpose:** Fuse purchase and payment discipline metrics into a final trust rating.
*   **Current Behavior:**
    *   `trust_score = (purchase_behavior_score * 0.50) + (payment_behavior_score * 0.50)`
*   **Why It Exists:** Equates purchasing volume/regularity and payment speed equally in trust metrics.
*   **Generic Equivalent:** Weighted Fusion Coefficients.
*   **Migration Strategy:** Parameterize weights in a configuration class (`purchase_weight: 0.50, payment_weight: 0.50`).

---

### 1.5 Payment Behavior Subfactors
*   **Location:** [payment/behavior.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/payment/behavior.py#L97-L200)
*   **Purpose:** Calculate the payment behavior score using 7 weighted sub-factors.
*   **Current Behavior:**
    *   **Delay Score (25% weight):**
        *   Repayment $\le 30$ days $\rightarrow$ $1.0$
        *   Repayment $\le 90$ days $\rightarrow$ Linear decay to $0.4$
        *   Repayment $\le 180$ days $\rightarrow$ Linear decay to $0.0$
        *   Repayment $> 180$ days $\rightarrow$ $0.0$
    *   **Consistency Score (15% weight):** $1.0 - \text{repayment\_regularity\_score}$
    *   **Partial Payment Habit (10% weight):** Linear decay as fragmentation rises from $1.0$ to $2.5$.
    *   **Individualized Clearance (15% weight):** Bounded ratio of outstanding to customer's average monthly billing (critical stress at $3.0\times$ monthly billing).
    *   **Exposure-Weighted Aging (15% weight):** Penalty factor of $0.2 \times (60\text{--}90\text{d}) + 0.5 \times (90\text{--}120\text{d}) + 1.0 \times (120\text{d}+)$.
    *   **Outstanding Pressure (10% weight):** $1.0 - \text{pressure\_score} / 2.0$.
    *   **Credit Day Breach (10% weight):** Expected threshold is $60$ days; score decays as delay exceeds $60$ up to $120$ days.
*   **Why It Exists:** Model tuned to represent typical credit windows and collections tolerances.
*   **Generic Equivalent:** Subfactor weights, linear decay bounds, and aging penalties.
*   **Migration Strategy:** Store subfactor weights, decay anchor days ($30$, $90$, $180$), and credit breach thresholds ($60$) as a configurable payment profile.

---

### 1.6 Evidence-Based Scoring Caps
*   **Location:** [payment/behavior.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/payment/behavior.py#L188-L200)
*   **Purpose:** Limit the max score for low-data volume customers to avoid false positives.
*   **Current Behavior:**
    *   `evidence_strength < 0.2` $\rightarrow$ Max score is capped at `0.60`
    *   `evidence_strength < 0.4` $\rightarrow$ Max score is capped at `0.75`
    *   `evidence_strength < 0.6` $\rightarrow$ Max score is capped at `0.90`
*   **Why It Exists:** Restricts high trust scores for new customers with very few transactions.
*   **Generic Equivalent:** Data Density Scoring Caps.
*   **Migration Strategy:** Shift caps and trigger bounds to configuration.

---

### 1.7 Stress Engine Formula
*   **Location:** [stress/engine.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/intelligence/stress/engine.py#L32-L36)
*   **Purpose:** Calculate operational and financial stress.
*   **Current Behavior:**
    *   `rg_ratio = penalty_window / max(sales_window, 100.0)`
    *   `deficiency = (sales_window - payments_window) / max(sales_window, 100.0)`
    *   `stress_score = (rg_ratio * 0.8) + (deficiency * 0.2)`
    *   *Note:* Code comment says returns 70% and deficiency 30%, which is a legacy discrepancy.
*   **Why It Exists:** Penalizes customers heavily for returns (80% weight) and slightly for outstanding debt deficiency (20%).
*   **Generic Equivalent:** Stress formula coefficients.
*   **Migration Strategy:** Make weights and minimum denominator ($100.0$) customizable parameters.

---

### 1.8 Returned Goods (RG) Responsibility Classification
*   **Location:** [db_provider.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/ingestion/db_provider.py#L229-L237) & [ledger.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/ledger/ledger.py#L155-L168)
*   **Purpose:** Determine if returned goods are customer-fault (penalized) or genuine company-fault (exempt).
*   **Current Behavior:**
    *   In `db_provider.py`: If `rgtype` is `"genuine"`, classified as `GENUINE`. If `rgtype` is `"customer rg"`, classified as `CUSTOMER`.
    *   In `ledger.py`: `GENUINE` returns are assigned a weight of `settings.GENUINE_RG_WEIGHT`.
    *   In `settings.py`: `GENUINE_RG_WEIGHT = 1.0` and `CUSTOMER_RG_WEIGHT = 1.0`.
*   **Why It Exists:** Intended to separate returns due to client error versus broken shipments. However, since both weights default to `1.0` in settings, **genuine returns currently penalize the customer just as heavily as customer fault returns**.
*   **Generic Equivalent:** Return classification weights.
*   **Migration Strategy:** Update `GENUINE_RG_WEIGHT` to `0.0` in configuration to correctly exempt company-fault returns, and parameterize this behavior.

---

## 2. Summary of Policy Transformation

The following table details the mapping of hardcoded constants into the proposed Econiq Core dynamic configuration structure:

| Model / Constant | Location | Current Hardcoded Value | Generic Policy Equivalent |
| :--- | :--- | :--- | :--- |
| **Elite Trust Threshold** | `states/engine.py:112` | `> 0.75` | `state_policy.elite.min_trust` |
| **Elite Stress Threshold** | `states/engine.py:112` | `< 0.15` | `state_policy.elite.max_stress` |
| **Declining Stress Limit**| `states/engine.py:110` | `> 0.60` | `state_policy.declining.min_stress` |
| **Active Trust Threshold**| `states/engine.py:114` | `> 0.45` | `state_policy.active.min_trust` |
| **Active Stress Limit**   | `states/engine.py:114` | `< 0.35` | `state_policy.active.max_stress` |
| **Class A Threshold**     | `states/engine.py:166` | `trust >= 0.7` | `grading_policy.A.min_score` |
| **Class B Threshold**     | `states/engine.py:168` | `trust >= 0.55` | `grading_policy.B.min_score` |
| **Class C Threshold**     | `states/engine.py:170` | `trust >= 0.4` | `grading_policy.C.min_score` |
| **Trust Fusion weights**  | `trust/engine.py:46-47` | `0.5 / 0.5` | `fusion_policy.weights` |
| **Breach grace days**     | `payment/behavior.py:162` | `60` | `payment_policy.expected_terms` |
| **Stress Return Weight**  | `stress/engine.py:34` | `0.80` | `stress_policy.weights.returns` |
| **Stress Debt Weight**    | `stress/engine.py:34` | `0.20` | `stress_policy.weights.deficiency` |
| **Genuine Return Penalty**| `settings.py:37` | `1.00` | `rg_policy.genuine_weight` |
| **Customer Return Penalty**| `settings.py:36` | `1.00` | `rg_policy.customer_weight` |
