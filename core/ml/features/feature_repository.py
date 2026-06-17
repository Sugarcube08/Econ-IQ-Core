from datetime import date
from typing import List, Optional
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.state_models import FeatureSnapshot
from core.ml.shared.types import FeatureSnapshotDTO
from core.ml.shared.enums import CustomerState, RiskDirection, TrustDirection, CustomerArchetype, SnapshotSource

class FeatureRepository:
    """
    SQLAlchemy repository to manage persistence for FeatureSnapshots.
    Ensures snapshots are immutable (only inserts are allowed).
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_snapshot(self, dto: FeatureSnapshotDTO) -> FeatureSnapshotDTO:
        """
        Inserts a new feature snapshot. Snapshots are immutable.
        """
        model = FeatureSnapshot(
            snapshot_id=dto.snapshot_id,
            customer_id=dto.customer_id,
            snapshot_date=dto.snapshot_date,
            snapshot_source=dto.snapshot_source.value if hasattr(dto.snapshot_source, 'value') else dto.snapshot_source,
            snapshot_version=dto.snapshot_version,
            generator_version=dto.generator_version,
            feature_hash=dto.feature_hash,
            
            # Scores
            health_score=dto.health_score,
            risk_score=dto.risk_score,
            trust_score=dto.trust_score,
            growth_score=dto.growth_score,
            collection_score=dto.collection_score,
            relationship_score=dto.relationship_score,
            credit_score=dto.credit_score,
            opportunity_score=dto.opportunity_score,
            
            # Categorical/Directions
            current_state=dto.current_state.value if hasattr(dto.current_state, 'value') and dto.current_state else dto.current_state,
            customer_archetype=dto.customer_archetype.value if hasattr(dto.customer_archetype, 'value') and dto.customer_archetype else dto.customer_archetype,
            risk_direction=dto.risk_direction.value if hasattr(dto.risk_direction, 'value') and dto.risk_direction else dto.risk_direction,
            trust_direction=dto.trust_direction.value if hasattr(dto.trust_direction, 'value') and dto.trust_direction else dto.trust_direction,
            
            # Rolling Windows
            billing_30d=dto.billing_30d,
            billing_90d=dto.billing_90d,
            billing_180d=dto.billing_180d,
            payments_30d=dto.payments_30d,
            payments_90d=dto.payments_90d,
            payments_180d=dto.payments_180d,
            returns_30d=dto.returns_30d,
            returns_90d=dto.returns_90d,
            
            # Operational
            purchase_gap=dto.purchase_gap,
            purchase_frequency=dto.purchase_frequency,
            payment_delay_avg=dto.payment_delay_avg,
            payment_delay_trend=dto.payment_delay_trend,
            collection_efficiency=dto.collection_efficiency,
            
            # Exposure/Utilization
            outstanding_current=dto.outstanding_current,
            outstanding_ratio=dto.outstanding_ratio,
            credit_utilization=dto.credit_utilization,
            
            # Payload & metadata
            feature_payload_json=dto.feature_payload_json,
            created_at=dto.created_at
        )
        self.db.add(model)
        await self.db.flush()
        logger.info("ML | Feature Snapshot Inserted", extra={"customer_id": dto.customer_id, "snapshot_id": dto.snapshot_id})
        return dto

    async def get_latest_snapshot(self, customer_id: str) -> Optional[FeatureSnapshotDTO]:
        """
        Retrieves the latest feature snapshot for a customer.
        """
        stmt = (
            select(FeatureSnapshot)
            .where(FeatureSnapshot.customer_id == customer_id)
            .order_by(FeatureSnapshot.snapshot_date.desc(), FeatureSnapshot.created_at.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return FeatureSnapshotDTO.model_validate(model)

    async def get_customer_snapshots(self, customer_id: str) -> List[FeatureSnapshotDTO]:
        """
        Retrieves all feature snapshots for a customer.
        """
        stmt = (
            select(FeatureSnapshot)
            .where(FeatureSnapshot.customer_id == customer_id)
            .order_by(FeatureSnapshot.snapshot_date.desc(), FeatureSnapshot.created_at.desc())
        )
        res = await self.db.execute(stmt)
        models = res.scalars().all()
        return [FeatureSnapshotDTO.model_validate(m) for m in models]

    async def snapshot_exists(self, customer_id: str, snapshot_date: date) -> bool:
        """
        Checks if a feature snapshot already exists for a customer on a given snapshot date.
        """
        stmt = (
            select(FeatureSnapshot.snapshot_id)
            .where(
                and_(
                    FeatureSnapshot.customer_id == customer_id,
                    FeatureSnapshot.snapshot_date == snapshot_date
                )
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar() is not None
