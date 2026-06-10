# Database Alignment Plan
- **Current State:** Target PostgreSQL database contains raw tables.
- **Target State:** Econiq schema upgraded with sync tracking columns.
- **Gap Analysis:** Target tables lack processing audit fields.
- **Recommended Actions:** Apply DDL statements to upgrade tables with `is_processed` and `processed_at` columns.
- **Priority:** Critical
- **Risk:** High
- **Dependencies:** PostgreSQL access
- **Expected Outcome:** database-level integration.
