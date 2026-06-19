# EconIQ Backend Code Freeze Policy

This document defines the strict read-only policy for the EconIQ core backend service. This freeze ensures absolute runtime stability for integration and the final hackathon submission.

---

## 1. Objective and Duration
- **Scope:** All sub-directories and files in [Econ-Core](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core).
- **Status:** **ACTIVE**
- **Authorized Date:** June 19, 2026

---

## 2. Allowed Activities
Only non-intrusive operations and critical fixes are permitted:
- **Logging & Diagnostics:** Adding or adjusting `loguru` statements to aid execution monitoring.
- **Reporting & Telemetry:** Modifying query paths inside telemetry exporters if they cause memory leaks or deadlocks.
- **Small Bugfixes:** Resolving exceptions, typing issues, or syntax anomalies that actively break the UI or ingestion pipeline.
- **Calibration Auditing:** Adjusting binary threshold calculations for active model inferences within existing pathways.
- **Documentation:** Updating metadata schemas and Markdown documentation.

---

## 3. Forbidden Activities (Strictly Enforced)
No structural, behavioral, or dependency changes are permitted:
- **New Capabilities:** No new business logic, API routing prefixes, or backend processing engines.
- **New Models:** No additions to the `models/` directory or database schemas representing new machine learning paradigms.
- **New Services:** No supplementary service objects, worker threads, or external connector managers.
- **Distributed Infrastructure:** No modifications to multi-node Redis clusters, Postgres replicas, or Celery task brokers.
- **Scheduler Changes:** No adjustments to the interval execution loops of sync workers or background workers.
- **Schema Mutations:** Absolute zero policy on migrations (`alembic upgrade/downgrade`). SQL schemas are read-only.

---

## 4. Verification Checklists
Before any change is committed under this freeze, it must satisfy the following pipeline validations:
```bash
# 1. Run local test suite to ensure zero regressions
pytest tests/

# 2. Verify pipeline schemas (Zero Mutations, validation check only)
python verify_feature_store.py

# 3. Check ML model register state
python verify_ml_pipeline.py
```

---

## 5. Compliance Sign-Off
All changes must be audited against [core/main.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/main.py) integration logic to guarantee that no new service lifespans or routers are declared.
