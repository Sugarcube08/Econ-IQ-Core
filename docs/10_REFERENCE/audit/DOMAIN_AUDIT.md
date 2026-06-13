# Econiq Domain Audit & Reuse Classification

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Startup CTO & Hackathon Judge  
**Owner:** Core Engineering Team

---

## 1. Domain Audit Matrix

We classify the domains of the reference system according to their reuse potential for the **Econiq AI-first Commercial Decision Infrastructure**:

| Domain / Component | Reuse Classification | Core Reasoning |
| :--- | :--- | :--- |
| **Authentication** | `REUSE_AS_IS` | The asymmetric EdDSA key token generation and validation are production-grade and secure. |
| **RBAC & Permissions** | `REUSE_AS_IS` | The hierarchical permissions registry and route guards are robust and fully functional. |
| **User Management** | `REUSE_WITH_MINOR_CHANGES` | Keep user models as-is, but verify default seed passwords. |
| **Organizations** | `REUSE_AS_IS` | Tenant-based isolation functions correctly via Postgres RLS. |
| **Customers** | `REUSE_WITH_MINOR_CHANGES` | Keep metadata columns but associate customer entries with unified global economic identities. |
| **Sales Ledger (Invoices)** | `REUSE_WITH_MINOR_CHANGES` | Map `raw_sales` to `invoices` while maintaining dates. |
| **Payments Ledger** | `REUSE_WITH_MINOR_CHANGES` | Map `raw_receipts` to `payments` with clean sign conventions. |
| **Returns Ledger** | `REUSE_WITH_MINOR_CHANGES` | Keep return metrics but adjust weights to prevent score clipping. |
| **Analytics Engine** | `REFACTOR` | Refactor the orchestrator to correct the semantic inversion where `is_ok = 1` was filtering out valid transactions. |
| **Reporting / Export** | `DELETE` | Excel/CSV report rendering is too slow and unnecessary for the hackathon dashboard demo. |
| **Notifications** | `REPLACE` | Replace standard SMTP dispatch templates with dynamic WebSockets or Redis Streams for real-time alerting. |
| **Dashboard API** | `MODIFY` | Keep backend database repositories, but clean up duplicate queries. |
| **ML Components** | `REPLACE` | Replace dummy classification mock rules with trained XGBoost default/churn models. |
| **Data Ingestion** | `REFACTOR` | Clean up database locks by running ingestion sync loops sequentially rather than in parallel. |

---

## 2. Detailed Technical Explanations

### 2.1. Authentication & RBAC (Reuse As-Is)
The security and permission system (`app/core/dependencies.py` and `app/core/security.py`) is well-designed. It validates EdDSA asymmetric tokens and manages high-entropy API keys. Retaining this avoids security validation rewrites.

### 2.2. Ingestion & Ledger (Refactor / Modify)
The event ingestion daemon uses database transaction locks (`42069`). We keep this but refactor the ingestion mapper (`dbupdater`) to swap `is_ok` values.
*   **Current Broken Logic:** Ingestion maps valid transaction keys (`is_Ok = True / -1`) to `is_ok = 1`. The econiq backend filters out `is_ok = 1` for financial balances.
*   **Target Correct Logic:** Ingestion maps valid transactions to `is_ok = 0`, ensuring they update outstanding balances and risk indicators correctly.

### 2.3. ML & Scoring Components (Replace / Build New)
The original code contains zero predictive model pipelines or feature serving endpoints. We replace the mock state indicators (Elite, Active, Declining) with a FastAPI endpoint running trained XGBoost models.

### 2.4. Reporting Engine (Delete)
The reporting service (`app/services/email_service.py`) relies on synchronous SMTP transport to dispatch large CSV and Excel files, which is slow and adds no value to our dashboard demonstration.
