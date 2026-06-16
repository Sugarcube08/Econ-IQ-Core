import asyncio
import sys
from loguru import logger
from core.config.settings import settings
from core.observability.logger import setup_logging
from core.storage.redis import redis_manager
from core.ingestion.sync_pipeline import SyncPipeline
from core.intelligence.background_worker import start_background_worker
from core.observability.failure_registry import FailureRegistry

async def start_sync_worker():
    logger.info("WORKER | Starting background event sync worker loop")
    sync_pipeline = SyncPipeline()
    while True:
        try:
            await sync_pipeline.run_cycle()
            FailureRegistry.recover("BACKGROUND_SYNC_WORKER_UNHANDLED")
        except asyncio.CancelledError:
            logger.info("WORKER | Background sync worker cancelled")
            break
        except Exception as e:
            FailureRegistry.record("BACKGROUND_SYNC_WORKER_UNHANDLED", f"Unhandled error in background sync worker: {e}", "ERROR", extra={"error": str(e)})
        await asyncio.sleep(10)

async def main():
    setup_logging()
    logger.info("WORKER | Initializing econiq worker process")

    # Connect to Redis
    await redis_manager.connect()

    # Start background tasks
    sync_task = asyncio.create_task(start_sync_worker())
    worker_task = asyncio.create_task(start_background_worker())

    logger.info("WORKER | econiq Worker Process Operational")
    try:
        await asyncio.gather(sync_task, worker_task)
    except asyncio.CancelledError:
        logger.info("WORKER | Worker cancelled. Cleaning up...")
    except KeyboardInterrupt:
        logger.info("WORKER | Worker interrupted by user. Cleaning up...")
    finally:
        sync_task.cancel()
        worker_task.cancel()
        # Wait for cancellation
        await asyncio.gather(sync_task, worker_task, return_exceptions=True)
        await redis_manager.disconnect()
        logger.info("WORKER | Worker shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
        sys.exit(0)
