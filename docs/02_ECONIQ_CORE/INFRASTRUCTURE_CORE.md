# Core Infrastructure Services
- **Current State:** Async database connection pools, Redis-based locks, and structured Loguru logger settings.
- **Target State:** Robust infra layer capable of scaling on Railway.
- **Gap Analysis:** Lock timeout constraints are hardcoded.
- **Recommended Actions:** Parameterize Redis lock timeouts; add health check endpoints for database and cache connections.
- **Priority:** High
- **Risk:** Medium (connection leaks)
- **Dependencies:** Redis configuration
- **Expected Outcome:** High-availability server loop.
