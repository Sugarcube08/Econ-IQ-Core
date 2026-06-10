# Ingestion & Sync Pipeline Architecture
- **Current State:** Sync Pipeline runs asynchronous batch cycles using advisory locks.
- **Target State:** Robust transactional sync running on target database.
- **Gap Analysis:** MDB Lock manager coordinates with external databases.
- **Recommended Actions:** Generalize database provider queries; implement deadlock retries.
- **Priority:** High
- **Risk:** Medium (database locks during high traffic)
- **Dependencies:** PostgreSQL setup
- **Expected Outcome:** Concurrency-safe transactional sync.
