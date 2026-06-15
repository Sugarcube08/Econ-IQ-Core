import asyncio
import traceback
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select, update

from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.models.state_models import CustomerRecomputationQueue, RecomputationStatus
from core.storage.postgres import AsyncSessionLocal
from core.config.settings import settings
from core.observability.runtime_state import runtime_state


class IntelligenceQueueWorker:
    def __init__(self, chunk_size: int | None = None, max_retries: int = 3):
        self.orchestrator = IntelligenceOrchestrator()
        self.chunk_size = chunk_size if chunk_size is not None else settings.INTELLIGENCE_CHUNK_SIZE
        self.max_retries = max_retries

    async def run(self, poll_interval: int = 5):
        """
        Continuously polls the recomputation queue and processes pending customers.
        """
        logger.info(f"Starting Intelligence Queue Worker (chunk_size: {self.chunk_size}, interval: {poll_interval}s)")

        while True:
            try:
                processed_count = await self._process_next_chunk()

                # If we processed a full chunk, don't sleep, check for more immediately
                if processed_count >= self.chunk_size:
                    import gc
                    gc.collect()
                    await asyncio.sleep(0.2)
                    continue

            except Exception as e:
                logger.error(f"Error in intelligence queue worker loop: {e}")
                logger.error(traceback.format_exc())

            import gc
            gc.collect()
            await asyncio.sleep(poll_interval)

    def _get_current_rss_mb(self) -> float:
        """Returns the current process RSS memory in MB."""
        try:
            with open('/proc/self/status') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        return int(line.split()[1]) / 1024.0
        except Exception:
            pass
        return 0.0

    async def _process_next_chunk(self) -> int:
        """
        Fetches the next chunk of pending customers and recomputes their intelligence.
        Uses FOR UPDATE SKIP LOCKED for safe concurrent worker execution.
        Dynamically adjusts batch size based on current process RSS to prevent OOM.
        """
        lock_context = runtime_state.lock if settings.PROCESSING_MODE == "sequential" else asyncio.Lock()
        async with lock_context:
            if settings.PROCESSING_MODE == "sequential":
                runtime_state.active_worker = "sequential_worker"
            else:
                runtime_state.active_worker = "intel_worker"
            runtime_state.current_stage = "customer_recomputation"
            try:
                return await self._process_next_chunk_internal()
            finally:
                runtime_state.current_stage = "idle"

    async def _process_next_chunk_internal(self) -> int:
        """
        Internal implementation of processing next chunk.
        """
        if settings.PROCESSING_MODE == "sequential":
            chunk_size = settings.INTELLIGENCE_CHUNK_SIZE
        else:
            # Determine dynamic chunk size based on RSS to prevent memory exhaustion
            rss = self._get_current_rss_mb()
            if rss > 1500.0:  # 1.5 GB
                chunk_size = 10
                logger.warning(f"Intelligence Queue Worker: High memory usage ({rss:.1f} MB RSS). Throttling chunk_size to 10.")
            elif rss > 1000.0:  # 1.0 GB
                chunk_size = 20
                logger.warning(f"Intelligence Queue Worker: Elevated memory usage ({rss:.1f} MB RSS). Throttling chunk_size to 20.")
            elif rss > 750.0:  # 750 MB
                chunk_size = 30
                logger.info(f"Intelligence Queue Worker: Moderate memory usage ({rss:.1f} MB RSS). Adjusting chunk_size to 30.")
            else:
                chunk_size = self.chunk_size

        async with AsyncSessionLocal() as session:
            # 1. Claim a chunk of pending tasks
            stmt = (
                select(CustomerRecomputationQueue)
                .where(CustomerRecomputationQueue.status == RecomputationStatus.PENDING)
                .order_by(CustomerRecomputationQueue.priority.desc(), CustomerRecomputationQueue.created_at.asc())
                .limit(chunk_size)
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            tasks = result.scalars().all()

            if not tasks:
                return 0

            task_ids = [t.id for t in tasks]
            customer_ids = list({t.customer_id for t in tasks})

            logger.debug(f"Claimed {len(tasks)} recomputation tasks for {len(customer_ids)} unique customers")

            # 2. Mark as PROCESSING
            await session.execute(
                update(CustomerRecomputationQueue)
                .where(CustomerRecomputationQueue.id.in_(task_ids))
                .values(status=RecomputationStatus.PROCESSING, locked_at=datetime.now(UTC), locked_by="QUEUE_WORKER")
            )
            await session.commit()

            # 3. Trigger orchestrator recomputation
            try:
                # We pass the list of unique customers to the orchestrator
                # Orchestrator handles individual customer isolation and persistence
                await self.orchestrator.run(customer_ids)

                # 4. Mark tasks as COMPLETED
                await session.execute(
                    update(CustomerRecomputationQueue)
                    .where(CustomerRecomputationQueue.id.in_(task_ids))
                    .values(status=RecomputationStatus.COMPLETED, completed_at=datetime.now(UTC))
                )
                await session.commit()

                logger.debug(f"Successfully processed {len(task_ids)} recomputation tasks")

            except Exception as e:
                logger.error(f"Failed to process recomputation chunk: {e}")
                # Error handling already committed in run() or re-tried
                # We need to roll back the status if failed
                await session.rollback()
                for t_id in task_ids:
                    await session.execute(
                        update(CustomerRecomputationQueue)
                        .where(CustomerRecomputationQueue.id == t_id)
                        .values(
                            status=RecomputationStatus.PENDING,
                            retry_count=CustomerRecomputationQueue.retry_count + 1,
                            error_message=str(e),
                            locked_at=None,
                            locked_by=None,
                        )
                    )
                # Mark those exceeding max retries as FAILED
                await session.execute(
                    update(CustomerRecomputationQueue)
                    .where(CustomerRecomputationQueue.id.in_(task_ids))
                    .where(CustomerRecomputationQueue.retry_count >= self.max_retries)
                    .values(status=RecomputationStatus.FAILED)
                )
                await session.commit()

        return len(tasks)

        return len(tasks)
