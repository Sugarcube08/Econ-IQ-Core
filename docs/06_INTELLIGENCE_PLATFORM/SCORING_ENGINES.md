# Scoring Engines & Orchestrator Flow
- **Current State:** `IntelligenceOrchestrator` computes component scores in a specific sequence.
- **Target State:** Generalized pipeline running scoring engines.
- **Gap Analysis:** Orchestrator imports specific calculations.
- **Recommended Actions:** Standardize the execution loop using abstract scoring classes.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Scoring Abstraction
- **Expected Outcome:** Pluggable engine pipeline.
