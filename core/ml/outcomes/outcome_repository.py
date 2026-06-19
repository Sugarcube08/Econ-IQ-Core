from datetime import date
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import PredictionOutcome


class PredictionOutcomeDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outcome_id: str
    prediction_id: str
    customer_id: str
    prediction_type: str
    predicted_value: float
    actual_value: float
    prediction_date: date
    evaluation_date: date
    lead_time_days: int
    is_correct: bool
    absolute_error: float
    metadata_json: dict[str, Any] = Field(default_factory=dict)

class OutcomeRepository:
    """
    SQLAlchemy repository to manage data access for prediction outcomes.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_outcome(self, dto: PredictionOutcomeDTO) -> PredictionOutcomeDTO:
        """Persists a new prediction outcome."""
        model = PredictionOutcome(
            outcome_id=dto.outcome_id,
            prediction_id=dto.prediction_id,
            customer_id=dto.customer_id,
            prediction_type=dto.prediction_type,
            predicted_value=dto.predicted_value,
            actual_value=dto.actual_value,
            prediction_date=dto.prediction_date,
            evaluation_date=dto.evaluation_date,
            lead_time_days=dto.lead_time_days,
            is_correct=dto.is_correct,
            absolute_error=dto.absolute_error,
            metadata_json=dto.metadata_json
        )
        self.db.add(model)
        await self.db.flush()
        logger.debug(f"ML | Outcome Saved: {dto.outcome_id} for Prediction {dto.prediction_id}")
        return dto

    async def get_outcome(self, outcome_id: str) -> PredictionOutcomeDTO | None:
        """Retrieves an outcome by its primary key ID."""
        stmt = select(PredictionOutcome).where(PredictionOutcome.outcome_id == outcome_id)
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return PredictionOutcomeDTO.model_validate(model)

    async def get_prediction_outcome(self, prediction_id: str) -> PredictionOutcomeDTO | None:
        """Retrieves an outcome associated with a prediction ID."""
        stmt = select(PredictionOutcome).where(PredictionOutcome.prediction_id == prediction_id)
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return PredictionOutcomeDTO.model_validate(model)

    async def get_customer_outcomes(self, customer_id: str) -> list[PredictionOutcomeDTO]:
        """Retrieves all outcomes for a customer ordered by evaluation_date descending."""
        stmt = (
            select(PredictionOutcome)
            .where(PredictionOutcome.customer_id == customer_id)
            .order_by(PredictionOutcome.evaluation_date.desc())
        )
        res = await self.db.execute(stmt)
        models = res.scalars().all()
        return [PredictionOutcomeDTO.model_validate(m) for m in models]

    async def outcome_exists(self, prediction_id: str) -> bool:
        """Checks if an outcome already exists for a prediction."""
        stmt = select(PredictionOutcome.outcome_id).where(PredictionOutcome.prediction_id == prediction_id).limit(1)
        res = await self.db.execute(stmt)
        return res.scalar() is not None
