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

# PHASE 1

## FEATURE STORE

Target Time:
4 Hours

Create:

core/ml/features/

Files:

feature_builder.py

feature_snapshot.py

feature_repository.py

feature_validator.py

---

Create table:

feature_snapshots

Columns:

snapshot_id

customer_id

snapshot_date

health_score

risk_score

trust_score

growth_score

collection_score

relationship_score

credit_score

opportunity_score

current_state

customer_archetype

risk_direction

trust_direction

billing_30d

billing_90d

payments_30d

payments_90d

returns_30d

purchase_gap

payment_delay_avg

outstanding_current

credit_utilization

feature_payload_json

created_at

---

Requirements:

Every customer must be snapshot-able.

Snapshots must be immutable.

Never update snapshots.

Always append.

PASS CONDITION:

Feature snapshots generated successfully for all customers.

---

# PHASE 2

## PREDICTION REGISTRY

Target Time:
2 Hours

Create:

core/ml/predictions/

Files:

prediction_registry.py

prediction_service.py

---

Create table:

predictions

Columns:

prediction_id

customer_id

prediction_type

prediction_value

confidence

explanation_json

feature_snapshot_id

model_version

created_at

status

---

Prediction Types:

CHURN

DELINQUENCY

DISTRESS

STATE_TRANSITION

---

Requirements:

Store predictions.

Never overwrite.

Always append.

PASS CONDITION:

Predictions persist successfully.

---

# PHASE 3

## OUTCOME REGISTRY

Target Time:
3 Hours

Create:

core/ml/outcomes/

Files:

outcome_tracker.py

outcome_service.py

---

Create table:

actual_outcomes

Columns:

outcome_id

customer_id

outcome_type

outcome_value

event_date

source_event_id

resolved_at

created_at

---

Outcome Types:

CHURNED

DELINQUENT

DISTRESSED

RECOVERED

STATE_CHANGED

---

Requirements:

Outcomes derived automatically from ledger behavior.

No manual labeling.

PASS CONDITION:

Outcomes generated automatically.

---

# PHASE 4

## FEEDBACK ENGINE

Target Time:
3 Hours

Create:

core/ml/feedback/

Files:

feedback_engine.py

feedback_repository.py

---

Create table:

prediction_feedback

Columns:

feedback_id

prediction_id

outcome_id

was_correct

error_distance

evaluation_date

created_at

---

Responsibilities:

Compare:

Prediction

vs

Actual Outcome

Calculate:

Accuracy

Precision

Recall

Outcome Match

Prediction Error

---

PASS CONDITION:

Predictions automatically evaluated.

---

# PHASE 5

## DATASET BUILDER

Target Time:
3 Hours

Create:

core/ml/datasets/

Files:

dataset_builder.py

dataset_validator.py

---

Generate:

training_dataset.parquet

from:

feature_snapshots
+
actual_outcomes

---

Rules:

No future leakage.

No target leakage.

Point-in-time safe.

---

PASS CONDITION:

Dataset generated automatically.

No manual exports required.

---

# PHASE 6

## FIRST PREDICTION FRAMEWORK

Target Time:
4 Hours

Create:

core/ml/inference/

Files:

risk_predictor.py

delinquency_predictor.py

prediction_orchestrator.py

---

IMPORTANT

Do NOT train models yet.

Use current intelligence outputs as bootstrap predictors.

Example:

Risk Prediction

Input:

risk_score

Output:

predicted_distress_probability

Store prediction inside registry.

---

Goal:

Exercise the complete prediction lifecycle.

Prediction
↓
Registry
↓
Outcome
↓
Feedback

---

PASS CONDITION:

End-to-end prediction lifecycle works.

---

# PHASE 7

## ML READINESS AUDIT

Target Time:
2 Hours

Create:

docs/

ML_FEATURE_STORE_AUDIT.md

PREDICTION_REGISTRY_AUDIT.md

OUTCOME_REGISTRY_AUDIT.md

FEEDBACK_ENGINE_AUDIT.md

DATASET_BUILDER_AUDIT.md

ML_READINESS_CERTIFICATION.md

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
