# Econiq Core Platform Blueprint
- **Current State:** Invariant platform mechanics (auth, database, queue scheduling) are tightly coupled with the econiq client logic.
- **Target State:** Clean separation between the platform core, client policy config, and AI models.
- **Gap Analysis:** Lacks clear package boundaries.
- **Recommended Actions:** Refactor directories; import policy context objects into core workflows.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Base schemas alignment
- **Expected Outcome:** Clean, scalable platform core.
