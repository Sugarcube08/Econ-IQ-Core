# Railway Deployment & Latency Optimization

This document outlines the performance configurations, database indexes, caching setups, and memory footprint optimizations required to deploy the Econiq Core backend on **Railway** while achieving sub-200ms API response latency.

---

## 1. Architectural Blueprint for Railway

Econiq is deployed as a consolidated monolithic container hosting the FastAPI server and the asynchronous background workers (sync ingestion and intelligence queue loops). This structure fits perfectly on Railway's hosting tier:

```text
               Railway HTTP Router
                        │
                        ▼
                [FastAPI Gateway] <──(Redis Session & Cache)
                  │          │
                  │ Reads    │ Writes task
                  ▼          ▼
            [PostgreSQL] <── [Queue Worker (XGBoost/LightGBM inference)]
```

---

## 2. Sub-200ms API Latency Strategy

To guarantee rapid loading speeds, we shift processing from API request threads to background tasks:

### 2.1 Write-Heavy vs. Read-Heavy Separation
*   **Background Worker:** Computes Polars rolling features, runs XGBoost/LightGBM inference, and saves the final outputs to the `customer_intelligence` table.
*   **FastAPI Gateway:** Performs simple SELECT queries from the `customer_intelligence` table. This keeps response times under **15ms** by avoiding real-time calculation overhead on HTTP requests.

### 2.2 Redis Cache Setup
Configure Redis to cache static dashboard aggregates (such as state distribution and aging profiles) with a 5-minute TTL:

```python
from app.storage.redis import redis_manager

async def get_cached_dashboard_overview(org_id: str):
    cache_key = f"dashboard:overview:{org_id}"
    
    # 1. Try reading from Redis cache
    cached_data = await redis_manager.client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
        
    # 2. On cache miss, fetch from PostgreSQL
    data = await fetch_dashboard_overview_from_db(org_id)
    
    # 3. Store in Redis cache with 300s TTL
    await redis_manager.client.setex(cache_key, 300, json.dumps(data))
    return data
```

> [!TIP]
> **Cache Invalidation:** Invalidate all `dashboard:*` keys inside the [SyncPipeline.run_cycle()](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/services/sync_pipeline.py#L56) final transaction commit to ensure dashboard data updates immediately when a new transactional sync batch completes.

---

## 3. Database Connection Pooling & Index Tuning

### 3.1 SQLAlchemy Pool Settings
Configure pool sizes inside the Railway environment variables to prevent exhausting database connection limits:

```properties
POSTGRES_POOL_SIZE=15
POSTGRES_MAX_OVERFLOW=25
POSTGRES_TIMEOUT=15
```

### 3.2 SQL Index Checklist
Ensure critical lookup paths are indexed to prevent full-table scans during updates:

```sql
-- Fast historical lookups by customer and date
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ledger_customer_date 
ON event_ledger (customer_id, event_date);

-- Fast queue claiming
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recomp_queue_status_priority 
ON customer_recomputation_queue (status, priority) 
WHERE status = 'PENDING';
```

---

## 4. Resource Allocation & Memory Optimization

To run the entire suite (PostgreSQL, Redis, FastAPI, Polars, and ML models) efficiently on a standard Railway plan:

1.  **Polars Garbage Collection:** Avoid maintaining multiple dataframe copies in memory. Use Polars' in-place mutations and call `pl.DataFrame.clear()` on temporary datasets.
2.  **Lightweight ML Libraries:** Use pre-compiled wheels for XGBoost and LightGBM. Avoid installing heavy ML packages like TensorFlow or PyTorch.
3.  **Asynchronous Network I/O:** Run all external HTTP calls (such as the Google Gemini API) using `httpx.AsyncClient` or the Gemini SDK's async methods (`generate_content_async`) to prevent blocking the event loop.
4.  **Logging Optimization:** Set `LOG_LEVEL=INFO` in production to prevent disk I/O bottlenecks from trace log emissions.
