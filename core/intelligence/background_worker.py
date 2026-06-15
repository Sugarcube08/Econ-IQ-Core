import asyncio
import gc
from loguru import logger
from sqlalchemy import select, String
from core.config.settings import settings
from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.storage.postgres import AsyncSessionLocal, get_reflected_table
from core.models.state_models import CustomerIntelligence

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
                logger.debug(f"Background worker found {len(unprocessed_ids)} unprocessed customers.")
                return unprocessed_ids
    except Exception as e:
        logger.warning(f"Error querying unprocessed customers: {e}")

    # 2. Stalest first: query existing records ordered by last_updated ASC
    try:
        stmt = select(CustomerIntelligence.customer_id).order_by(
            CustomerIntelligence.last_updated.asc()
        ).limit(settings.RECOMPUTE_BATCH_SIZE)
        
        res = await session.execute(stmt)
        stalest_ids = [str(row[0]) for row in res.all()]
        if stalest_ids:
            logger.debug(f"Background worker found {len(stalest_ids)} stalest customers to refresh.")
            return stalest_ids
    except Exception as e:
        logger.warning(f"Error querying stalest customers: {e}")

    return []

async def start_background_worker():
    """
    Main background loop that slowly and continuously recomputes customer intelligence.
    """
    logger.info("Starting background intelligence worker...")
    orchestrator = IntelligenceOrchestrator()
    
    # Simple delay to let the server start up and handle initial client requests first
    await asyncio.sleep(5)
    
    while True:
        try:
            # 1. Find a small set of pending customers
            async with AsyncSessionLocal() as session:
                customer_ids = await find_pending_customers(session)
            
            # 2. Process
            if customer_ids:
                logger.debug(f"Background worker starting recomputation for batch of {len(customer_ids)} customers.")
                # Orchestrator handles loading context, compute, persist, commit, and session closure
                await orchestrator.run(customer_ids)
                global PROCESSED_CUSTOMERS_COUNT
                PROCESSED_CUSTOMERS_COUNT += len(customer_ids)
                logger.debug(f"Background worker finished recomputation batch. Total processed: {PROCESSED_CUSTOMERS_COUNT}")
            else:
                logger.debug("Background worker: No customers pending processing.")
                
        except asyncio.CancelledError:
            logger.info("Background worker task cancelled.")
            break
        except Exception as e:
            logger.error(f"Unhandled error in background worker loop: {e}")
            
        finally:
            # 5. Explicit cleanup of memory references
            gc.collect()
            
        # 6. Sleep before next cycle
        await asyncio.sleep(settings.WORKER_SLEEP_SECONDS)
