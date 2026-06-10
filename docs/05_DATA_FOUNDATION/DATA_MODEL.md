# Data Model & Entity Relations
- **Current State:** Database models track client-specific variables.
- **Target State:** Generic relational model mapping customers, sales, payments, and returns.
- **Gap Analysis:** Database tables.
- **Recommended Actions:** Map `raw_receipts` to payments; map `raw_rg` to returns.
- **Priority:** Critical
- **Risk:** High
- **Dependencies:** Database Alignment
- **Expected Outcome:** Invariant entity-relationship model.
