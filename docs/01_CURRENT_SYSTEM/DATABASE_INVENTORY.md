# Database Inventory & Schema Inspection
- **Current State:** PostgreSQL database containing transactional tables (`raw_sales`, `raw_receipts`, `raw_rg`, `raw_customers`) and ledger tables (`event_ledger`, `customer_intelligence`, `customer_recomputation_queue`).
- **Target State:** Econiq data sources (`customers`, `raw_sales`, `raw_payments`, `raw_returns`) properly integrated.
- **Gap Analysis:** Table structures contain econiq-specific names and columns.
- **Recommended Actions:** Align raw table names; apply schema upgrades (processed flags) to target tables.
- **Priority:** Critical
- **Risk:** High (data loss during migrations)
- **Dependencies:** DB migration scripts
- **Expected Outcome:** Standardized transactional database schema.
