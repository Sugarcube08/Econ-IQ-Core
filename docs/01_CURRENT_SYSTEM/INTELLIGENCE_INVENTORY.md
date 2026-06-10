# Intelligence Engine Inventory
- **Current State:** Polars-based sub-modules calculating cadence, trade consistency, returned goods ratios, payment delays, outstanding pressure, and stress indicators.
- **Target State:** Modular, policy-guided scoring pipeline.
- **Gap Analysis:** Algorithms directly query settings constants.
- **Recommended Actions:** Abstract engines to take configuration objects.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** BaseScoringEngine interface
- **Expected Outcome:** Configurable calculation pipelines.
