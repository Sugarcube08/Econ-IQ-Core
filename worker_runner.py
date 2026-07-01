import asyncio
import sys

from loguru import logger

from core.ingestion.sync_pipeline import SyncPipeline
from core.intelligence.background_worker import start_background_worker
from core.ml.worker import start_ml_worker_loop
from core.observability.failure_registry import FailureRegistry
from core.observability.logger import setup_logging
from core.storage.redis import redis_manager


async def start_sync_worker():
    from core.config.settings import settings
    logger.info(f"WORKER | Starting event sync worker (mode={settings.RUNTIME_MODE})")
    if settings.RUNTIME_MODE == "SERVING":
        logger.warning("WORKER | Sync worker is disabled in SERVING mode.")
        return

    sync_pipeline = SyncPipeline()
    try:
        await sync_pipeline.run_cycle()
        FailureRegistry.recover("BACKGROUND_SYNC_WORKER_UNHANDLED")
    except Exception as e:
        FailureRegistry.record("BACKGROUND_SYNC_WORKER_UNHANDLED", f"Unhandled error in background sync worker: {e}", "ERROR", extra={"error": str(e)})

async def main():
    setup_logging()
    logger.info("WORKER | Initializing econiq worker process")

    from core.config.settings import settings
    if settings.RUNTIME_MODE == "SERVING":
        logger.warning("WORKER | Runtime mode is set to SERVING. Background workers are disabled. Exiting worker process.")
        sys.exit(0)

    # Connect to Redis
    await redis_manager.connect()

    # Wait for DB schema to be ready
    from core.storage.postgres import wait_for_db_tables
    if not await wait_for_db_tables(timeout=30):
        logger.error("WORKER | Database schema is not ready. Exiting.")
        sys.exit(1)

    # Start background tasks
    sync_task = asyncio.create_task(start_sync_worker())
    worker_task = asyncio.create_task(start_background_worker())
    ml_task = asyncio.create_task(start_ml_worker_loop())

    logger.info("WORKER | econiq Worker Process Operational")
    try:
        await asyncio.gather(sync_task, worker_task, ml_task)
    except asyncio.CancelledError:
        logger.info("WORKER | Worker cancelled. Cleaning up...")
    except KeyboardInterrupt:
        logger.info("WORKER | Worker interrupted by user. Cleaning up...")
    finally:
        sync_task.cancel()
        worker_task.cancel()
        ml_task.cancel()
        # Wait for cancellation
        await asyncio.gather(sync_task, worker_task, ml_task, return_exceptions=True)
        await redis_manager.disconnect()
        logger.info("WORKER | Worker shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
        sys.exit(0)
