import asyncio

from loguru import logger
from sqlalchemy import select

from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.storage.postgres import AsyncSessionLocal


async def recompute_all():
    """
    Triggers a full intelligence recomputation for all customers in the system.
    Used to populate new cached columns in the customer_intelligence table.
    """
    logger.info("Starting full intelligence recomputation for all customers...")
    
    orchestrator = IntelligenceOrchestrator()
    
    async with AsyncSessionLocal() as session:
        customer_ids = []
        
        # 1. Attempt to get IDs from customers table (Complete set)
        try:
            logger.info("Reflecting customers table...")
            from core.storage.postgres import get_reflected_table
            customers = await get_reflected_table("customers", session)
            
            if customers is not None:
                res = await session.execute(select(customers.c.id))
                customer_ids = [str(row[0]) for row in res.all()]
                logger.info(f"Found {len(customer_ids)} customers in customers table.")
            else:
                logger.warning("customers table does not exist.")
        except Exception as e:
            logger.warning(f"Could not reflect customers: {e}.")
            customer_ids = []
            
        # 2. Fallback: Get IDs from CustomerIntelligence (Existing records to update)
        if not customer_ids:
            logger.info("Falling back to customer_intelligence table.")
            try:
                from core.models.state_models import CustomerIntelligence
                res = await session.execute(select(CustomerIntelligence.customer_id))
                customer_ids = [str(row[0]) for row in res.all()]
                logger.info(f"Found {len(customer_ids)} customers in customer_intelligence.")
            except Exception as e2:
                logger.error(f"Failed to retrieve customers from customer_intelligence: {e2}")
        
        # 3. Fallback: Get IDs from EventLedger (if customer_intelligence is empty)
        if not customer_ids:
            logger.info("Falling back to event_ledger table to fetch unique customer IDs.")
            try:
                from core.models.state_models import EventLedger
                res = await session.execute(select(EventLedger.customer_id).distinct())
                customer_ids = [str(row[0]) for row in res.all()]
                logger.info(f"Found {len(customer_ids)} customers in event_ledger.")
            except Exception as e3:
                logger.error(f"Failed to retrieve customers from event_ledger: {e3}")
        
        if not customer_ids:
            logger.warning("No customers found in customers, customer_intelligence, or event_ledger. Nothing to recompute.")
            return

        # 4. Resume Support: Exclude customers already in customer_intelligence
        try:
            from core.models.state_models import CustomerIntelligence
            res_done = await session.execute(select(CustomerIntelligence.customer_id))
            done_ids = {str(row[0]) for row in res_done.all()}
            logger.info(f"Found {len(done_ids)} already processed customers in customer_intelligence.")
            customer_ids = [cid for cid in customer_ids if cid not in done_ids]
            logger.info(f"{len(customer_ids)} customers remaining to be processed.")
        except Exception as e_done:
            logger.warning(f"Could not filter already processed customers: {e_done}")

        if not customer_ids:
            logger.info("All customers have already been processed. Nothing to recompute.")
            return

        # Process in chunks to ensure system stability and avoid long-running transaction issues
        chunk_size = 10
        total_chunks = (len(customer_ids) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(customer_ids), chunk_size):
            chunk = customer_ids[i : i + chunk_size]
            current_chunk_num = i // chunk_size + 1
            logger.info(f"Processing chunk {current_chunk_num}/{total_chunks} ({len(chunk)} customers)...")
            
            try:
                await orchestrator.run(chunk)
                logger.info(f"Successfully processed chunk {current_chunk_num}.")
            except Exception as e:
                logger.error(f"Failed to process chunk {current_chunk_num}: {e}")
                # Continue with next chunk even if one fails
            
    logger.info("Full recomputation lifecycle complete.")

if __name__ == "__main__":
    try:
        asyncio.run(recompute_all())
    except KeyboardInterrupt:
        logger.info("Recomputation script stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in recomputation script: {e}")
