# Security Protocols & RBAC Policies
- **Current State:** JWT authentication and RBAC models.
- **Target State:** Multi-tenant endpoint security rules.
- **Gap Analysis:** Tenant boundaries are not enforced on databases.
- **Recommended Actions:** Implement query filters restricting queries by tenant.
- **Priority:** High
- **Risk:** High (data leakage)
- **Dependencies:** Auth models
- **Expected Outcome:** Secure multitenancy.
