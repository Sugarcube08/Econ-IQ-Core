# TODO.md

# ECON-IQ

## 24 HOUR LEARNING INFRASTRUCTURE SPRINT

Status: LOCKED

Rule:

If a task is not listed here, it does not exist.

No frontend work.
No dashboard redesign.
No advisor system.
No LLMs.
No RAG.
No Vector DB.
No Agents.
No MLOps.
No retraining pipelines.
No AutoML.

Only execute the tasks below.

---

# OBJECTIVE

Convert ECON-IQ from:

Rule Engine

into

Learning System

by creating:

✓ Feature Store

✓ Prediction Registry

✓ Outcome Registry

✓ Feedback Engine

✓ Dataset Builder

✓ First Prediction Framework

NOT production models.

The goal is to create a self-learning architecture.

---

# TARGET ARCHITECTURE

Event Ledger
↓
Customer Intelligence
↓
Feature Store
↓
Prediction Registry
↓
Outcome Registry
↓
Feedback Engine
↓
Training Dataset Builder
↓
Future Models

---

# Today's Plan (LOCKED)

Estimated time : 10–12 hours

---

# PHASE 0

## ML Infrastructure Skeleton

Target

```text
core/ml/

    features/

    predictions/

    outcomes/

    feedback/

    datasets/

    inference/

    shared/

    interfaces/
```

Files

```text
__init__.py

interfaces.py

types.py

enums.py
```

Goal

Nothing implemented.

Only architecture.

---

# PHASE 1

# Feature Store

Estimated

4 Hours

First question:

**Can every customer be reconstructed at any point in time?**

If answer is yes

Feature Store PASS

Table

```text
feature_snapshots
```

Add

```text
snapshot_source

snapshot_version

generator_version

feature_hash
```

Because later you'll recalibrate features.

---

### Snapshot philosophy

Never

```text
UPDATE
```

Only

```text
INSERT
```

---

# PHASE 2

# Outcome Registry

Estimated

2 Hours

This is actually the most important thing today.

Table

```text
actual_outcomes
```

Outcome derivation examples

---

Churned

```text
purchase_gap > 90
```

---

Distressed

```text
Healthy

↓

Stressed

↓

Distressed
```

---

Recovered

```text
Distressed

↓

Recovering

↓

Healthy
```

---

Delinquent

```text
repayment_days > 45
```

---

State changed

```text
Healthy

↓

Growing
```

---

PASS

Generate outcomes for all customers.

---

# PHASE 3

# Prediction Registry

Estimated

1 hour

Table

```text
predictions
```

Prediction

Store

```text
prediction_type


predicted_probability


confidence


snapshot_id


status


version


explanation_json
```

Status

```text
PENDING


EVALUATED


CORRECT


WRONG
```

---

PASS

Prediction can be inserted

---

# PHASE 4

# Feedback Engine

Estimated

2 hours

This is the soul of EconIQ.

Compare

```text
Prediction


Outcome
```

Store

```text
accuracy


precision


recall


brier_score


prediction_error
```

---

PASS

Prediction automatically evaluated

---

# PHASE 5

# Dataset Builder

Estimated

2 hours

Generate

```text
training_dataset.parquet
```

from

```text
feature_snapshots


+


actual_outcomes
```

No train split

No test split

No xgboost

No shap

Just

```text
Dataset Exists
```

---

PASS

Dataset generation works

---

# PHASE 6

# Bootstrap Predictor

Estimated

1 hour

No ML.

No sklearn.

Use existing intelligence.

Example

```python

predicted_distress_probability = risk_score


predicted_delinquency_probability = 1 - collection_score


predicted_churn_probability = purchase_gap / 120

```

Insert predictions.

Evaluate predictions.

Generate feedback.

Done.

---

# PHASE 7

# Certification

Generate

```text
docs/


ML_FEATURE_STORE_AUDIT.md


OUTCOME_REGISTRY_AUDIT.md


PREDICTION_REGISTRY_AUDIT.md


FEEDBACK_ENGINE_AUDIT.md


DATASET_BUILDER_AUDIT.md


LEARNING_SYSTEM_CERTIFICATION.md

```

---

# Things forbidden today

Do not build

```text
XGBoost


CatBoost


LightGBM


SHAP


Advisor


LLMs


Retraining


Model Registry


Drift Monitoring


Online Learning


MLOps


Forecasting


Credit Optimization


Collections Prioritization


RAG


Agents
```

---

# End Goal for Tonight

For customer

```text
CUST_00421
```

EconIQ should answer

```text
Feature Snapshot Exists


Prediction Exists


Outcome Exists


Prediction Evaluated


Accuracy Known


Dataset Generated
```

If that works, then tomorrow morning you won't be building ML.

You'll already have built the thing that most companies don't have:

```text
Commercial Intelligence

↓

Prediction Infrastructure

↓

Outcome Tracking

↓

Learning Infrastructure


(Models become plugins)
```

---

Must certify:

Feature Store Operational

Prediction Tracking Operational

Outcome Tracking Operational

Feedback Loop Operational

Dataset Builder Operational

---

# OUT OF SCOPE

DO NOT BUILD

Actual XGBoost Models

LightGBM Models

CatBoost Models

SHAP

Advisor Engine

Forecasting

Collections Prioritization

Credit Limit Optimization

Model Registry

Drift Detection

Retraining

MLOps

---

# DEFINITION OF DONE

A customer can have:

Feature Snapshot
↓
Prediction
↓
Outcome
↓
Feedback

stored and traceable end-to-end.

The platform is officially converted from a rule-only intelligence system into a learning-capable intelligence system.
