# Unified Capability Health Architecture

The Unified Capability Health framework provides a single, queryable API endpoint (`GET /api/v1/system/capabilities`) that conducts real-time verification of the platform's core operational capabilities.

## Monitored Capabilities

The endpoint returns status metadata for 8 core capabilities:

1. **`ledger`**: Assesses whether the transaction event ledger (`event_ledger` table) is readable.
2. **`intelligence`**: Verifies availability of the core credit analytics tables (`customer_intelligence`).
3. **`alerts`**: Verifies that the automated alert engine's persistence layer is queryable.
4. **`collections`**: Assesses collections actions and activity histories.
5. **`decisioning`**: Confirms that audit logs for actions and permissions remain queryable.
6. **`feature_store`**: Checks feature snapshot generation health (`feature_snapshots`).
7. **`ml`**: Returns active model count, verifying that serialization directories (`models/`) and Model Registry meta are aligned.
8. **`advisor`**: Assesses whether prioritized commercial recommendations can be retrieved.

## Response Payload Example

```json
{
  "ledger": { "healthy": true },
  "intelligence": { "healthy": true },
  "alerts": { "healthy": true },
  "collections": { "healthy": true },
  "decisioning": { "healthy": true },
  "feature_store": { "healthy": true },
  "ml": { "healthy": true, "models": 5 },
  "advisor": { "healthy": true }
}
```

## Production Monitoring Usage

In production, infrastructure orchestrators (e.g. Kubernetes readiness probes or external pingers) should target `/api/v1/system/capabilities` in addition to the generic `/health` check. A failure in any of the capability states allows automated healing scripts to flag the backend instance for recycling or route redirection.
