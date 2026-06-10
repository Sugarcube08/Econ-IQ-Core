# Asset Preservation & Backend Reuse Matrix

This document maps all legacy VGIS backend files and assets, evaluating their business value, replacement cost, reuse percentage, and migration actions. The primary goal is to maximize code reuse, minimizing implementation risk during the Econiq transition.

---

## 1. Core Asset Evaluation Matrix

| Module / Asset Location | Purpose | Business Value | Replacement Cost | Reuse % | Target Migration Action |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`ref/app/services/sync_pipeline.py`** | Asynchronously syncs records from raw tables to `event_ledger` using advisory locks and transaction queues. | **Critical** | High | 95% | **GENERALIZE**<br>(Map raw tables to payments/returns; update verification hooks). |
| **`ref/app/features/engineer.py`** | Vectorized rolling window aggregates calculations using Polars expressions. | **Critical** | Medium | 100% | **KEEP**<br>(Pure math aggregation, fully reusable as-is). |
| **`ref/app/intelligence/ledger/reconstruction.py`** | Chronological ledger builder compiling daily outstanding exposure balances. | **Critical** | High | 100% | **KEEP**<br>(Variant accounting core ledger engine). |
| **`ref/app/intelligence/settlement/engine.py`** | Chronologically matches cash receipts against sales invoices to map payment delays. | **High** | High | 100% | **KEEP**<br>(Reuses the invariant FIFO matching algorithm). |
| **`ref/app/intelligence/queue_worker.py`** | Database locking daemon fetching tasks using `FOR UPDATE SKIP LOCKED`. | **High** | Medium | 95% | **KEEP**<br>(Pure infrastructure service). |
| **`ref/app/api/auth.py` & `models/auth_models.py`** | Handles user sessions, EdDSA tokens validation, RBAC middleware, and MFA challenges. | **High** | Medium | 95% | **KEEP**<br>(Standard token infrastructure). |
| **`ref/app/storage/postgres.py` & `redis.py`** | Postgres pooling adapter and Redis connection manager with distributed locking. | **High** | Low | 100% | **KEEP**<br>(Standard persistence drivers). |
| **`ref/app/utils/lock_manager.py`** | Context manager wrapper executing Redis locks. | **Medium** | Low | 100% | **KEEP**<br>(Infrastructure helper). |
| **`ref/app/intelligence/payment/behavior.py`** | Computes payment delay, consistency, fragmentation, clearance, and aging subfactor scores. | **High** | High | 80% | **REFACTOR**<br>(decople progressive delay scale decay bounds and breach days from engine). |
| **`ref/app/intelligence/states/engine.py`** | Inferred merchant risk state machine (`elite`, `active`, `declining`, `irregular`, `inactive`). | **High** | Medium | 50% | **REFACTOR**<br>(decople hardcoded threshold checks; replace constants with policy profiles). |
| **`ref/app/intelligence/stress/engine.py`** | Computes customer stress from returns ratio and deficit. | **High** | Medium | 75% | **REFACTOR**<br>(Correct code comments mismatch; decople returned goods weights). |
| **`ref/app/intelligence/trust/engine.py`** | Combines purchase and payment scores using a 50/50 fusion weight. | **Medium** | Low | 50% | **REFACTOR**<br>(decople weights into policy settings). |
| **`ref/app/intelligence/orchestrator.py`** | Controls sequence execution of components and persists computed metrics to DB. | **Critical** | High | 85% | **GENERALIZE**<br>(Update to load policy configuration context and run dynamic queries). |
| **`ref/app/pipelines/ingestion_pipeline.py`** | Older, duplicated ingestion sync code path. | **Low** | Low | 0% | **DELETE**<br>(Redundant code; `sync_pipeline.py` is the hardened version). |
| **`ref/app/intelligence/resilience.py`** | Unused or experimental error recovery handlers. | **Low** | Low | 0% | **DELETE**<br>(Dead code; error recovery is handled directly in queue loops). |

---

## 2. Generalization Rules Guidelines

To prevent accidental rewrites and control technical risk:

1.  **Do NOT touch Invariant Math:** The FIFO invoice matching algorithm in `settlement/engine.py` and the double-entry balance compiler in `ledger/reconstruction.py` are mathematically correct and must not be altered.
2.  **decople Configuration Only:** Changes to scoring engines must be strictly limited to replacing hardcoded numbers with variable references passed via a `policy` context object.
3.  **Clean Duplicate Pipeline Assets:** Remove older pipelines (`pipelines/ingestion_pipeline.py`) to reduce maintenance complexity.
