# Policy Engine Architecture Design

This document details the architectural design for decoupling organization-specific business rules, thresholds, scoring weights, and classifications from the execution codebase and externalizing them into a dynamic **Policy Engine**.

---

## 1. Architectural Strategy

Currently, risk, trust, and stress calculations are locked into hardcoded python expressions. The proposed design converts these rules into dynamic, tenant-specific policies loaded at runtime from a database or configuration file.

```text
Hardcoded Engine Code
       ↓
Dynamic Policy Manager ──> [Loads YAML Profile or Database Config]
       ↓
Generic Processing Engines (Polars Vectorized Rules)
```

---

## 2. Policy Schema Specification (`policy_profile.yaml`)

Each organization will run under a specific Policy Profile. Below is the complete YAML specification representing the econiq default settings, which can be modified for any tenant without code changes:

```yaml
version: "1.0"
tenant_id: "default_econiq_tenant"
description: "Default commercial intelligence rules profile"

# 1. State Inference Engine Settings
state_inference:
  window_days: 365
  recent_window_days: 14
  states:
    elite:
      min_trust: 0.75
      max_stress: 0.15
    active:
      min_trust: 0.45
      max_stress: 0.35
    declining:
      min_stress: 0.60
      force_on_negative_trajectory: true
      force_stress_threshold: 0.50
    inactive:
      max_events: 0

# 2. Trajectory Classification Settings
trajectory_classification:
  recent_window_days: 14
  ratios:
    accelerating:
      min_ratio: 1.5
    growing:
      min_ratio: 1.1
      max_ratio: 1.5
    declining:
      min_ratio: 0.5
      max_ratio: 0.8
    collapsing:
      max_ratio: 0.5

# 3. Overall Credit Letter Grading
credit_grading:
  bands:
    A: 0.70
    B: 0.55
    C: 0.40
    D: 0.00

# 4. Behavioral Score Fusion Weights
trust_fusion:
  weights:
    purchase_behavior: 0.50
    payment_behavior: 0.50

# 5. Payment Behavior Subfactors
payment_behavior:
  delay_subfactor:
    weight: 0.25
    grace_days: 30
    moderate_decay_days: 90
    moderate_decay_min: 0.4
    critical_decay_days: 180
  consistency_subfactor:
    weight: 0.15
  partial_payment_subfactor:
    weight: 0.10
    max_fragmentation: 2.5
  clearance_subfactor:
    weight: 0.15
    critical_multiplier: 3.0
  exposure_aging_subfactor:
    weight: 0.15
    penalties:
      overdue_60_90: 0.20
      overdue_90_120: 0.50
      overdue_120p: 1.00
  outstanding_pressure_subfactor:
    weight: 0.10
    divisor: 2.0
  credit_breach_subfactor:
    weight: 0.10
    expected_credit_terms: 60
    max_breach_days: 60

# 6. Stress Scoring Engine
stress_calculation:
  min_denominator: 100.0
  weights:
    returns_ratio: 0.80
    outstanding_deficiency: 0.20

# 7. Returned Goods (RG) Semantics
returned_goods:
  weights:
    customer_fault: 1.00
    genuine_company_fault: 0.00   # Decoupled to avoid penalizing customers for broken shipments
    unknown_fault: 0.80
```

---

## 3. Database Schema Implementation

To persist these profiles, a new metadata table `business_profiles` will be introduced in PostgreSQL:

```sql
CREATE TABLE business_profiles (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL, -- Holds the complete policy JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Associate tenant organization with a specific profile
ALTER TABLE organizations ADD COLUMN profile_id VARCHAR(255) REFERENCES business_profiles(id) DEFAULT 'default';
```

---

## 4. Engine Integration Implementation Pattern

The scoring engines will load this configuration at runtime. Below is the refactoring pattern for `StateEngine`:

```python
import polars as pl
from pydantic import BaseModel

class StateInferenceConfig(BaseModel):
    min_trust: float
    max_stress: float

class StatePolicy(BaseModel):
    elite: StateInferenceConfig
    active: StateInferenceConfig

# Engine reads parameters from dynamic configuration
class ConfigurableStateEngine:
    def compute(
        self,
        features_df: pl.DataFrame,
        stress_df: pl.DataFrame,
        trust_df: pl.DataFrame,
        policy: StatePolicy
    ) -> pl.DataFrame:
        
        df = features_df.join(stress_df, on="customer_id").join(trust_df, on="customer_id")
        
        # Resolve rules dynamically from policy config parameters
        return df.with_columns(
            pl.when(pl.col("events_window") == 0)
            .then(pl.lit("inactive"))
            .when(
                (pl.col("trust_score") > policy.elite.min_trust) & 
                (pl.col("stress_score") < policy.elite.max_stress)
            )
            .then(pl.lit("elite"))
            .when(
                (pl.col("trust_score") > policy.active.min_trust) & 
                (pl.col("stress_score") < policy.active.max_stress)
            )
            .then(pl.lit("active"))
            .otherwise(pl.lit("irregular"))
            .alias("behavioral_state")
        )
```

---

## 5. Architectural Benefits

1.  **Zero-Downtime Adaptability:** Modifying risk rules or grading bands requires a simple PostgreSQL UPDATE or Git commit to a YAML profile. No deployment or code compilation is necessary.
2.  **Multitenancy-Ready:** Econiq can serve multiple distributor tenants on the same Railway container cluster, each utilizing distinct score weights based on their specific industry sector.
3.  **Audit Trail of Rules:** Storing rules as config files allows tracking changes via Git commits or DB change audit tables.
