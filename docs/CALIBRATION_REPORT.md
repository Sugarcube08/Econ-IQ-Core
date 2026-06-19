# Calibration Audit & Reliability Methodology

Model calibration measures whether predicted probabilities align with actual empirical frequencies. This document details the formulas, processes, and tools used by the EconIQ platform to audit model trustworthiness before production freeze.

## Calibration Metrics

### 1. Expected Calibration Error (ECE)
ECE partitions the predicted probabilities into $M$ equally spaced bins (defaulting to 10 bins: `[0.0-0.1, 0.1-0.2, ..., 0.9-1.0]`). The error is computed as the weighted average difference between the mean predicted confidence and the empirical accuracy in each bin:

$$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

Where:
- $B_m$ is the set of samples in the $m$-th bin.
- $|B_m|$ is the sample count in that bin.
- $N$ is the total number of predictions evaluated.
- $\text{acc}(B_m)$ is the fraction of positive labels.
- $\text{conf}(B_m)$ is the average predicted probability.

### 2. Brier Score
The Brier Score measures the mean squared error of the predicted probability $f_i$ relative to the true binary outcome $y_i \in \{0, 1\}$:

$$\text{BS} = \frac{1}{N} \sum_{i=1}^{N} (f_i - y_i)^2$$

A score of `0.0` represents perfect prediction and calibration; `0.25` represents the performance of random guessing (with a 50% base rate).

### 3. Reliability Curve (Calibration Curve)
Plots the average predicted value (x-axis) against the fraction of positive outcomes (y-axis) for each probability bin. Perfect calibration is represented by the diagonal line $y = x$.

## Audit Process

Calibration runs continuously in the background sync worker. The `CalibrationService` groups predictions that have resolved outcomes, calculates ECE and Brier Score, and generates three vital artifacts:

- **`artifacts/calibration_report.md`**: Summary report comparing active models.
- **`artifacts/reliability_curve.csv`**: Aggregated bin-by-bin confidence vs. accuracy curves.
- **`artifacts/brier_scores.csv`**: Calculated historical scores per model version.

These artifacts are exposed via the `GET /api/v1/ml/calibration` API endpoint.
