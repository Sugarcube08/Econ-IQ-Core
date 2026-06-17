import gc
from datetime import date, datetime, UTC
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.storage.postgres import AsyncSessionLocal
from core.models.state_models import CustomerIntelligence
from core.ml.features.feature_builder import FeatureBuilder
from core.ml.features.feature_repository import FeatureRepository
from core.ml.features.feature_validator import validate_snapshot
from core.ml.shared.enums import SnapshotSource
from core.ml.shared.types import FeatureSnapshotDTO
from loguru import logger

async def generate_snapshot(
    customer_id: str,
    session: Optional[AsyncSession] = None,
    snapshot_date: Optional[date] = None,
    snapshot_source: SnapshotSource = SnapshotSource.BATCH
) -> FeatureSnapshotDTO:
    """
    Generates, validates, and persists a point-in-time feature snapshot for a customer.
    Workflow:
      customer_id -> FeatureBuilder -> FeatureSnapshot DTO -> Validator -> FeatureRepository -> Persist
    """
    if session is not None:
        return await _generate_and_persist(customer_id, session, snapshot_date, snapshot_source)
    else:
        async with AsyncSessionLocal() as db_session:
            async with db_session.begin():
                return await _generate_and_persist(customer_id, db_session, snapshot_date, snapshot_source)

async def _generate_and_persist(
    customer_id: str,
    session: AsyncSession,
    snapshot_date: Optional[date],
    snapshot_source: SnapshotSource
) -> FeatureSnapshotDTO:
    builder = FeatureBuilder(session)
    dto = await builder.build_snapshot(customer_id, snapshot_date, snapshot_source)
    
    # Validate DTO (raises SnapshotValidationError on invalid data)
    validate_snapshot(dto)
    
    repo = FeatureRepository(session)
    await repo.insert_snapshot(dto)
    
    return dto

async def generate_all_feature_snapshots(
    snapshot_date: Optional[date] = None,
    snapshot_source: SnapshotSource = SnapshotSource.BATCH
) -> dict:
    """
    Sequentially generates, validates, and persists feature snapshots for all customers.
    Guarantees stable memory and no leaks by using a separate session per customer and calling gc.collect().
    """
    if snapshot_date is None:
        snapshot_date = datetime.now(UTC).date()

    # 1. Fetch all customer IDs from the intelligence store
    async with AsyncSessionLocal() as session:
        stmt = select(CustomerIntelligence.customer_id)
        res = await session.execute(stmt)
        customer_ids = [row[0] for row in res.all()]

    total_customers = len(customer_ids)
    logger.info(f"ML | Starting batch snapshot generation for {total_customers} customers sequentially.")

    success_count = 0
    failed_count = 0
    start_time = datetime.now()

    for idx, customer_id in enumerate(customer_ids):
        try:
            # Separate session and transaction per customer to prevent memory leak
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await _generate_and_persist(customer_id, session, snapshot_date, snapshot_source)
            success_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"ML | Failed to generate snapshot for customer {customer_id}: {e}")

        # Explicit garbage collection every 100 customers to ensure memory stability
        if (idx + 1) % 100 == 0:
            gc.collect()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    avg_time = duration / total_customers if total_customers > 0 else 0.0

    logger.info(
        f"ML | Batch snapshot generation completed. "
        f"Processed: {total_customers}, Success: {success_count}, Failed: {failed_count}, "
        f"Duration: {duration:.2f}s, Avg/Customer: {avg_time:.4f}s"
    )

    return {
        "customer_count": total_customers,
        "snapshot_count": success_count,
        "failed_snapshots": failed_count,
        "average_generation_time_sec": avg_time,
        "total_duration_sec": duration,
    }
