from datetime import datetime

from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import PredictionFeedback


class PredictionFeedbackDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: str
    model_id: str
    prediction_type: str
    samples: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float
    ece: float
    created_at: datetime

class FeedbackRepository:
    """
    SQLAlchemy repository to manage data access for prediction feedback metrics.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_feedback(self, dto: PredictionFeedbackDTO) -> PredictionFeedbackDTO:
        """Persists a new feedback record."""
        model = PredictionFeedback(
            feedback_id=dto.feedback_id,
            model_id=dto.model_id,
            prediction_type=dto.prediction_type,
            samples=dto.samples,
            accuracy=dto.accuracy,
            precision=dto.precision,
            recall=dto.recall,
            f1=dto.f1,
            roc_auc=dto.roc_auc,
            brier_score=dto.brier_score,
            ece=dto.ece,
            created_at=dto.created_at
        )
        self.db.add(model)
        await self.db.flush()
        logger.debug(f"ML | Feedback Saved: {dto.feedback_id} for Model {dto.model_id}")
        return dto

    async def get_latest_feedback(self, model_id: str, prediction_type: str) -> PredictionFeedbackDTO | None:
        """Retrieves the latest feedback entry for a model and prediction type."""
        stmt = (
            select(PredictionFeedback)
            .where(
                PredictionFeedback.model_id == model_id,
                PredictionFeedback.prediction_type == prediction_type
            )
            .order_by(PredictionFeedback.created_at.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return PredictionFeedbackDTO.model_validate(model)

    async def get_feedback_history(self, prediction_type: str) -> list[PredictionFeedbackDTO]:
        """Retrieves the history of feedback entries for a prediction type ordered by created_at descending."""
        stmt = (
            select(PredictionFeedback)
            .where(PredictionFeedback.prediction_type == prediction_type)
            .order_by(PredictionFeedback.created_at.desc())
        )
        res = await self.db.execute(stmt)
        models = res.scalars().all()
        return [PredictionFeedbackDTO.model_validate(m) for m in models]
