import asyncio
import traceback
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select, update

from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.models.state_models import CustomerRecomputationQueue, RecomputationStatus
from core.storage.postgres import AsyncSessionLocal


class IntelligenceQueueWorker:
    def __init__(self, chunk_size: int = 50, max_retries: int = 3):
        self.orchestrator = IntelligenceOrchestrator()
        self.chunk_size = chunk_size
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
                    continue

            except Exception as e:
                logger.error(f"Error in intelligence queue worker loop: {e}")
                logger.error(traceback.format_exc())

            await asyncio.sleep(poll_interval)

    async def _process_next_chunk(self) -> int:
        """
        Fetches the next chunk of pending customers and recomputes their intelligence.
        Uses FOR UPDATE SKIP LOCKED for safe concurrent worker execution.
        """
        async with AsyncSessionLocal() as session:
            # 1. Claim a chunk of pending tasks
            stmt = (
                select(CustomerRecomputationQueue)
                .where(CustomerRecomputationQueue.status == RecomputationStatus.PENDING)
                .order_by(CustomerRecomputationQueue.priority.desc(), CustomerRecomputationQueue.created_at.asc())
                .limit(self.chunk_size)
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
