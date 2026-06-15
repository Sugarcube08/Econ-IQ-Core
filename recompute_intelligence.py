import asyncio
import sys
from loguru import logger
from core.ingestion.sync_pipeline import SyncPipeline
from core.recompute_all import recompute_all

async def main():
    logger.info("Starting explicit intelligence recomputation...")
    
    # 1. Run raw ingestion / sync pipeline to update event ledger
    logger.info("Step 1: Running data ingestion sync cycle...")
    try:
        sync = SyncPipeline()
        processed = await sync.run_cycle()
        logger.info(f"Data ingestion sync cycle complete. Processed state: {processed}")
    except Exception as e:
        logger.error(f"Ingestion sync cycle failed: {e}")
        # Continue to recompute what we already have in the ledger even if sync fails
        
    # 2. Run customer intelligence recomputations
    logger.info("Step 2: Triggering customer intelligence recomputations...")
    try:
        await recompute_all()
        logger.info("Customer intelligence recomputations completed successfully.")
    except Exception as e:
        logger.critical(f"Intelligence recomputations failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Recomputation interrupted by user.")
        sys.exit(0)
