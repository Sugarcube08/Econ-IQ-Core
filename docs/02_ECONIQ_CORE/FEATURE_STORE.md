# Feature Store Design
- **Current State:** Features are calculated on the fly and discarded after database updates.
- **Target State:** Unified feature storage caching layers using Redis.
- **Gap Analysis:** Real-time ML models require immediate feature vector loading.
- **Recommended Actions:** Store Polars-engineered vectors in Redis as JSON key-values during recomputations.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Redis setup
- **Expected Outcome:** sub-10ms feature vector retrievals.
