# Feature Engineering Pipeline
- **Current State:** polars windowing features calculation.
- **Target State:** Vectorized rolling aggregation store.
- **Gap Analysis:** Window days parameters are hardcoded.
- **Recommended Actions:** Read window sizes from the injected policy config.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Feature store design
- **Expected Outcome:** Real-time feature calculation engine.
