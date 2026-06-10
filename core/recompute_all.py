import asyncio

from loguru import logger
from sqlalchemy import MetaData, Table, select

from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.storage.postgres import AsyncSessionLocal


async def recompute_all():
    """
    Triggers a full intelligence recomputation for all customers in the system.
    Used to populate new cached columns in the customer_intelligence table.
    """
    logger.info("Starting full intelligence recomputation for all customers...")
    
    metadata = MetaData()
    orchestrator = IntelligenceOrchestrator()
    
    async with AsyncSessionLocal() as session:
        customer_ids = []
        
        # 1. Attempt to get IDs from customers table (Complete set)
        try:
            logger.info("Reflecting customers table...")
            customers = await session.run_sync(
                lambda sync_conn: Table("customers", metadata, autoload_with=sync_conn.bind)
            )
            res = await session.execute(select(customers.c.id))
            customer_ids = [str(row[0]) for row in res.all()]
            logger.info(f"Found {len(customer_ids)} customers in customers table.")
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
        
        if not customer_ids:
            logger.warning("No customers found in either customers or customer_intelligence. Nothing to recompute.")
            return

        # Process in chunks to ensure system stability and avoid long-running transaction issues
        chunk_size = 50
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
