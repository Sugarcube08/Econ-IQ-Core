from datetime import datetime

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.predictions.prediction_types import CustomerPredictionDTO, PredictionStatus
from core.models.state_models import CustomerPrediction


class PredictionRepository:
    """
    SQLAlchemy repository to manage data access for customer predictions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_prediction(self, dto: CustomerPredictionDTO) -> CustomerPredictionDTO:
        """Persists a new prediction."""
        model = CustomerPrediction(
            prediction_id=dto.prediction_id,
            customer_id=dto.customer_id,
            snapshot_id=dto.snapshot_id,
            model_id=dto.model_id,
            prediction_type=dto.prediction_type.value if hasattr(dto.prediction_type, 'value') else dto.prediction_type,
            prediction_value=dto.prediction_value,
            confidence=dto.confidence,
            generated_at=dto.generated_at,
            prediction_horizon_days=dto.prediction_horizon_days,
            prediction_status=dto.prediction_status.value if hasattr(dto.prediction_status, 'value') else dto.prediction_status,
            resolved_at=dto.resolved_at,
            actual_label=dto.actual_label,
            metadata_json=dto.metadata_json
        )
        self.db.add(model)
        await self.db.flush()
        logger.debug(f"ML | Prediction Saved: {dto.prediction_id} for Customer {dto.customer_id}")
        return dto

    async def get_prediction(self, prediction_id: str) -> CustomerPredictionDTO | None:
        """Retrieves a prediction by its primary key ID."""
        stmt = select(CustomerPrediction).where(CustomerPrediction.prediction_id == prediction_id)
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return CustomerPredictionDTO.model_validate(model)

    async def get_customer_predictions(self, customer_id: str) -> list[CustomerPredictionDTO]:
        """Retrieves all predictions for a customer ordered by generated_at descending."""
        stmt = (
            select(CustomerPrediction)
            .where(CustomerPrediction.customer_id == customer_id)
            .order_by(CustomerPrediction.generated_at.desc())
        )
        res = await self.db.execute(stmt)
        models = res.scalars().all()
        return [CustomerPredictionDTO.model_validate(m) for m in models]

    async def get_pending_predictions(self) -> list[CustomerPredictionDTO]:
        """Retrieves all pending predictions."""
        stmt = select(CustomerPrediction).where(CustomerPrediction.prediction_status == PredictionStatus.PENDING.value)
        res = await self.db.execute(stmt)
        models = res.scalars().all()
        return [CustomerPredictionDTO.model_validate(m) for m in models]

    async def mark_prediction_resolved(self, prediction_id: str, actual_label: str, resolved_at: datetime) -> CustomerPredictionDTO | None:
        """Resolves a pending prediction with actual outcome label."""
        stmt = select(CustomerPrediction).where(CustomerPrediction.prediction_id == prediction_id)
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if model:
            model.prediction_status = PredictionStatus.RESOLVED.value
            model.actual_label = actual_label
            model.resolved_at = resolved_at
            await self.db.flush()
            return CustomerPredictionDTO.model_validate(model)
        return None

    async def bulk_insert_predictions(self, dtos: list[CustomerPredictionDTO]) -> list[CustomerPredictionDTO]:
        """Inserts multiple predictions in bulk."""
        for dto in dtos:
            await self.insert_prediction(dto)
        return dtos

    async def prediction_exists(self, customer_id: str, snapshot_id: str, prediction_type: str) -> bool:
        """Checks if a prediction of the given type already exists for a customer snapshot."""
        stmt = (
            select(CustomerPrediction.prediction_id)
            .where(
                and_(
                    CustomerPrediction.customer_id == customer_id,
                    CustomerPrediction.snapshot_id == snapshot_id,
                    CustomerPrediction.prediction_type == prediction_type
                )
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar() is not None
