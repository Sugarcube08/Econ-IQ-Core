# API Route Inventory
- **Current State:** FastAPI endpoints under `/api/auth`, `/api/users`, `/api/customers`, `/api/dashboard` returning raw analytics and historical lists.
- **Target State:** APIs returning ML-driven default risks, churn percentages, and Copilot explanations.
- **Gap Analysis:** Customer datatable endpoint lacks pagination for CSV exports; endpoints return hardcoded grade classifications.
- **Recommended Actions:** Modify customer detail DTOs to return predictive metrics; implement pagination on CSV exports.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Target DTO schemas
- **Expected Outcome:** Performance-optimized APIs meeting the sub-200ms latency standard.
