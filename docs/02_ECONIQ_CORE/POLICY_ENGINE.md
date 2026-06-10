# Policy Engine Architecture
- **Current State:** Scoring constants are hardcoded inside engine scripts.
- **Target State:** Dynamic configuration models loaded from PostgreSQL or YAML configurations.
- **Gap Analysis:** No database table exists for policy storage.
- **Recommended Actions:** Implement the `business_profiles` database table and reference profiles inside engine computations.
- **Priority:** Critical
- **Risk:** Medium (policy loading latency)
- **Dependencies:** Database Alignment plan
- **Expected Outcome:** Runtime-configurable risk limits.
