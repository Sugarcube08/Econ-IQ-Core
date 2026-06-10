# Configuration Model and Policy Schemas
- **Current State:** Configuration is limited to global environment variables.
- **Target State:** Detailed Pydantic schemas representing rules, weights, and thresholds.
- **Gap Analysis:** No JSON validation schema for dynamic settings.
- **Recommended Actions:** Write Pydantic configurations for state boundaries, payment delays, and stress weights.
- **Priority:** Critical
- **Risk:** Low
- **Dependencies:** Policy Engine
- **Expected Outcome:** Validation rules for dynamic profile updates.
