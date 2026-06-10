# Performance Optimization Guide
- **Current State:** Real-time scoring calculation.
- **Target State:** Pre-calculated scoring caches with sub-20ms reads.
- **Gap Analysis:** Calculations run on request threads.
- **Recommended Actions:** Cache outputs in Redis; write invalidation hooks.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Redis Cache
- **Expected Outcome:** Meets the sub-200ms REST latency SLA.
