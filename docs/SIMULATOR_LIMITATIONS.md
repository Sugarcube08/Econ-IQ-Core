# Counterfactual Heuristic Simulator v1 Limitations

The simulator in EconIQ V3 is cataloged as `Counterfactual Heuristic Simulator v1`. This document outlines the technical boundaries, behavioral assumptions, and proper interpretation of the what-if simulation results.

## Simulator Mechanics

The simulator applies feature-value shifts based on defined impact rules (e.g., applying a payment commitment increases simulated collection efficiency, decreasing credit limits decreases utilization). The modified features are then pushed through the baseline ML models to predict distress risk differences.

## Key Limitations

### 1. Heuristic Impact Maps
The feature shift amounts (defined in `ActionImpactEstimator`) are heuristically determined parameters rather than learned causal effects. They model expected linear directional changes but do not capture complex non-linear feedbacks or individual customer elasticity.

### 2. Lack of Feedback Loops
Counterfactual simulations are static point-in-time shifts. The simulator assumes all other features remain constant (*ceteris paribus*), ignoring feedback dynamics (e.g., decreasing credit limit might trigger a sales reduction or collection friction in real life).

### 3. Selection Bias & Out-of-Distribution Inputs
Large simulated shifts can push the feature vector outside the support of the trained XGBoost models. Predictions on out-of-distribution (OOD) data points can result in high-variance or non-sensical outcomes.

## Observability Metadata

Every response returned by the simulator contains the attribute `"simulation_source": "HEURISTIC"`. This metadata must be propagated all the way to frontend UIs to visually inform users that the deltas are projections under heuristic assumptions rather than proven causal predictions.
