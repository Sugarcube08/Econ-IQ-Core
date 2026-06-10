# Econiq Current State Baseline

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Startup CTO & Hackathon Lead  
**Owner:** Core Engineering Team

---

## 1. System Inventory

Econiq is built on top of an already functioning B2B analytics platform. We are **not** starting from a greenfield state. Approximately **70% of the backend** and **90% of the frontend** are already implemented and operational.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CURRENT PLATFORM STACK                         │
├──────────────────┬──────────────────┬──────────────────┬────────────────┤
│    Frontend      │     Backend      │    Database      │   Analytics    │
│  React Dashboard │  Go REST API     │  PostgreSQL 15   │ Standard SQL   │
│  (Charts, Views) │  (Voucher sync)  │  (Ledger Tables) │ (Averages, DPD)│
└──────────────────┴──────────────────┴──────────────────┴────────────────┘
```

### 1.1. Frontend Assets (React SPA - ~90% Complete)
*   **Customer Directory:** List of retailers with outstanding balances, credit terms, and status.
*   **Wholesaler Dashboard:** Displays total sales volumes, outstanding collections, and payment delays.
*   **Credit Approval View:** Page displaying agreed terms and limit override forms.
*   **User Management:** standard RBAC role forms.

### 1.2. Backend Services (Go REST API - ~70% Complete)
*   **Auth Service:** standard JWT session issuance and validation.
*   **Sync API:** REST endpoint receiving raw JSON/CSV imports from desktop connectors (Tally, BUSY).
*   **Normalization Workers:** Cleans text formatting and date strings, writing records to PostgreSQL.
*   **Ledger Service:** Manages transactional state tracking of invoices and payments.

### 1.3. Relational Database (PostgreSQL 15 - Operational)
Maintains normalized transactional schemas:
*   `customers`: Retailer business details and limits.
*   `invoices`: Debit records with statuses (`UNPAID`, `PAID`, `OVERDUE`).
*   `payments`: Credit records mapping cash/bank transactions.
*   `returns`: Credit notes issued for damaged stock.

---

## 2. Reusable Core Assets (The Foundation)

We leverage and reuse the following subsystems directly to accelerate the hackathon sprint:
1.  **Authentication and Tenant Scoping:** Row-Level Security (RLS) and JWT auth middleware are stable and isolate tenant data perfectly.
2.  **Data Ingestion Connectors:** Go normalizer workers reliably translate messy desktop accounting records into canonical transactions.
3.  **UI Layout Components:** Theme layouts, chart visualizations, tables, and side navigation menus are fully styled and functional.

---

## 3. Current Platform Bottlenecks

While the transactional tracking is stable, the system operates purely as a historical reporter (Analytics) rather than a decision support engine (Intelligence):

| Feature Area | Current Implementation | Target AI-First Upgrade |
| :--- | :--- | :--- |
| **Credit Decisions** | Manual overrides based on simple DPD stats. | Recommendation Engine suggests limits based on Risk & Opportunity. |
| **Collections Routing** | Standard lists sorted by oldest invoice date. | ML prioritizes accounts using collection recovery probabilities. |
| **Default Tracking** | Point-in-time DPD warnings. | XGBoost forecasts default and churn risks 90 days out. |
| **Customer Profiling** | Scattered ledger pages. | LLM-driven Copilot explains risk scores and payment behaviors. |
| **Ledger Auditing** | Manual calculations of balances. | Isolation Forest flags transaction anomalies automatically. |

---

## 4. Pruning and Deprioritization

To hit our 2-week hackathon target, we are stripping out enterprise-scale systems that add deployment complexity without demo value:
*   **No Kafka/Redpanda Cluster:** Replaced with local Go channels and Redis Streams to process queues.
*   **No Multi-Region Database:** Pin deployment to a single PostgreSQL/ClickHouse instance.
*   **No Kubernetes/Knative Clusters:** Host services using simple Docker Compose on a single VM.
*   **No Advanced Event-Sourcing (CQRS):** Write features and metrics directly to PostgreSQL tables after sync runs.
*   **No Graph Databases (Neo4j):** Fuzzy matches and identity groups are stored using standard SQL link tables.
