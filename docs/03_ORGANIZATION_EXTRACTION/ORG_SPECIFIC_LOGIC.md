# Organization Specific Logic Mapping
- **Current State:** Hardcoded scoring weights (50% purchase, 50% payment), grading bands (0.7, 0.55, 0.4), and states definitions.
- **Target State:** Zero business logic rules inside the core application code.
- **Gap Analysis:** Logic segments depend on configuration constants.
- **Recommended Actions:** Isolate and parameterize all weights, limits, and classifications into settings policies.
- **Priority:** Critical
- **Risk:** Low
- **Dependencies:** Settings cleanup
- **Expected Outcome:** Zero hardcoded assumptions.
