# Ground Truth & Reference Reality
- **Current State:** The reference backend is a specialized, high-performance Commercial Intelligence Engine, not a simple CRUD application or generic ERP. It runs vectorized gap calculations, cash flow settlements, and stress computations in Polars.
- **Target State:** Generalization into the Econiq Core Platform with a modularized, config-driven ingestion pipeline and ML inference steps.
- **Gap Analysis:** Direct mappings assume a single merchant structure and hardcoded business rules (like return fault weight ratios).
- **Recommended Actions:** Preserve the Polars rolling feature engineering pipelines; extract organization assumptions into dynamic configuration policies.
- **Priority:** High
- **Risk:** Low (codebase structures are well understood)
- **Dependencies:** None
- **Expected Outcome:** Unified understanding of the system's baseline assets.
