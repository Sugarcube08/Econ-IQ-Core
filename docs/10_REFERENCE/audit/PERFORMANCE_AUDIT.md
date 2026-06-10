# Econiq Performance Audit & Optimization Plan

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Distributed Systems Architect & Lead DevOps Engineer  
**Owner:** Core Engineering Team

---

## 1. Performance Diagnostics

This section analyzes potential bottlenecks in our target **Railway deployment** running on PostgreSQL and FastAPI:

```
                  ┌───────────────────────────────┐
                  │        PERFORMANCE FLOW       │
                  └───────────────┬───────────────┘
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│  Conn Pool   │           │ Query Tuning │           │ Redis Cache  │
│ (10->50 pool)│           │ (Comp Index) │           │ (Sub-5ms serving)
└──────────────┘           └──────────────┘           └──────────────┘
```

### 1.1. Connection Pooling (SQLAlchemy Async)
*   **Current Settings:** `pool_size = 10`, `max_overflow = 20`.
*   **Audit finding:** In high-volume sync loops or concurrent API calls, 10 connections can saturate quickly, causing queries to block.
*   **Improvement:** Adjust settings in `settings.py` for the production environment: `pool_size = 50`, `max_overflow = 10` to handle spike loads.

### 1.2. Database Query Indexing
*   **Current Settings:** The index `idx_ledger_customer_date` is configured on `event_ledger` columns `(customer_id, event_date)`.
*   **Audit finding:** This is highly optimized for sequential timeline queries. However, queries filtering by `is_ok` lack an index.
*   **Improvement:** Create an index to support financial filtering:
```sql
CREATE INDEX idx_ledger_financial_lookup ON event_ledger (customer_id, event_date) WHERE is_ok = 0;
```

### 1.3. API Latency & Caching
*   **Current Settings:** API listing endpoints retrieve raw customer metrics directly from the DB.
*   **Audit finding:** Real-time query sweeps over large tables will exceed our **200ms response time SLA**.
*   **Improvement:** Cache processed features and scores in the Redis cache. Real-time API requests read directly from Redis (sub-5ms serving), updating cache values asynchronously.

---

## 2. Railway Deployment Suitability

*   **Database Scaling:** Railway provides managed PostgreSQL databases with automatic disk resizing. RLS policies and partitioned tables are supported.
*   **Memory Footprint:** FastAPI and Go services consume minimal memory ($< 250$MB per container). Python ML inference containers will consume about 1GB of memory, which fits within Railway's standard container limits.
*   **Cold Starts:** Container builds run continuously. Zero-downtime health checks prevent cold start latency spikes for users.

---

## 3. Performance Improvement Specifications

| Improvement Area | Action | Impact | Target Latency |
| :--- | :--- | :--- | :--- |
| **Connection pool** | Increase pool size to 50 in `settings.py`. | Prevents query blocking under sync loads. | $< 10$ms connection time |
| **API response** | Cache customer profile responses in Redis. | Eliminates database queries on page loads. | Sub-5ms API response |
| **Metrics query** | Deploy composite index on `is_ok`. | Optimizes SQL timeline sweeps. | $< 50$ms execution time |
| **Inference API** | Pre-compute and store model outputs. | Decouples ML models from front-end page loads. | $< 20$ms API response |
