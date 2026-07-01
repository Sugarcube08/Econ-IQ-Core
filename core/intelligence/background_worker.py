import asyncio
import gc

from loguru import logger
from sqlalchemy import String, select

from core.config.settings import settings
from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.models.state_models import CustomerIntelligence
from core.observability.failure_registry import FailureRegistry
from core.storage.postgres import AsyncSessionLocal, get_reflected_table

PROCESSED_CUSTOMERS_COUNT = 0


async def find_pending_customers(session) -> list[str]:
    """
    Finds a small set of pending customers to recompute.
    1. First tries to find customers that do not exist in customer_intelligence yet.
    2. If all are initialized, falls back to refreshing the stalest records (ordered by last_updated ASC).
    """
    # 1. Bootstrapping: customers not yet in customer_intelligence
    try:
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            stmt = select(customers_tbl.c.id).select_from(
                customers_tbl.join(
                    CustomerIntelligence,
                    customers_tbl.c.id.cast(String) == CustomerIntelligence.customer_id,
                    isouter=True
                )
            ).where(
                CustomerIntelligence.customer_id.is_(None)
            ).limit(settings.RECOMPUTE_BATCH_SIZE)
            
            res = await session.execute(stmt)
            unprocessed_ids = [str(row[0]) for row in res.all()]
            if unprocessed_ids:
                return unprocessed_ids
    except Exception as e:
        FailureRegistry.record("BACKGROUND_WORKER_QUERY_FAILED", f"Error querying unprocessed customers: {e}", "WARNING", extra={"error": str(e)})

    # 2. Stalest first: query existing records ordered by last_updated ASC
    try:
        stmt = select(CustomerIntelligence.customer_id).order_by(
            CustomerIntelligence.last_updated.asc()
        ).limit(settings.RECOMPUTE_BATCH_SIZE)
        
        res = await session.execute(stmt)
        stalest_ids = [str(row[0]) for row in res.all()]
        if stalest_ids:
            return stalest_ids
    except Exception as e:
        FailureRegistry.record("BACKGROUND_WORKER_QUERY_FAILED", f"Error querying stalest customers: {e}", "WARNING", extra={"error": str(e)})

    return []

async def start_background_worker():
    """
    Background worker that recomputes customer intelligence once.
    """
    from core.config.settings import settings
    logger.info(f"SYSTEM | Starting background intelligence worker (mode={settings.RUNTIME_MODE})")
    if settings.RUNTIME_MODE == "SERVING":
        logger.warning("SYSTEM | Background worker is disabled in SERVING mode.")
        return

    orchestrator = IntelligenceOrchestrator()
    
    try:
        # Find a small set of pending customers
        async with AsyncSessionLocal() as session:
            customer_ids = await find_pending_customers(session)
        
        # Process
        if customer_ids:
            # Orchestrator handles loading context, compute, persist, commit, and session closure
            await orchestrator.run(customer_ids)
            global PROCESSED_CUSTOMERS_COUNT
            PROCESSED_CUSTOMERS_COUNT += len(customer_ids)
            FailureRegistry.recover("BACKGROUND_WORKER_QUERY_FAILED")
            FailureRegistry.recover("BACKGROUND_WORKER_UNHANDLED")
            
    except Exception as e:
        FailureRegistry.record("BACKGROUND_WORKER_UNHANDLED", f"Unhandled error in background worker: {e}", "ERROR", extra={"error": str(e)})
        
    finally:
        # Explicit cleanup of memory references
        gc.collect()
