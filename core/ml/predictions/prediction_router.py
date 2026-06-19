
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.features.feature_snapshot import generate_snapshot
from core.ml.feedback.feedback_repository import PredictionFeedbackDTO
from core.ml.predictions.prediction_registry import prediction_registry
from core.ml.predictions.prediction_repository import PredictionRepository
from core.ml.predictions.prediction_service import generate_predictions_for_snapshot
from core.ml.predictions.prediction_types import CustomerPredictionDTO
from core.models.state_models import PredictionFeedback
from core.storage.postgres import get_db

router = APIRouter(prefix="/ai", tags=["AI / ML Engine"])

@router.get("/models", response_model=list[str])
async def list_models():
    """Lists registered prediction model IDs."""
    return prediction_registry.list_models()

@router.post("/predict", response_model=list[CustomerPredictionDTO])
async def predict_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Generates a new feature snapshot and runs inference for a customer."""
    try:
        # 1. Generate snapshot
        snapshot = await generate_snapshot(customer_id, db)
        
        # 2. Run inference & persist predictions
        predictions = await generate_predictions_for_snapshot(customer_id, snapshot.snapshot_id, db)
        
        # Commit the transaction
        await db.commit()
        return predictions
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}") from e

@router.get("/customer/{customer_id}/predictions", response_model=list[CustomerPredictionDTO])
async def get_customer_predictions(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves prediction history for a customer."""
    repo = PredictionRepository(db)
    return await repo.get_customer_predictions(customer_id)

@router.get("/pending", response_model=list[CustomerPredictionDTO])
async def get_pending_predictions(db: AsyncSession = Depends(get_db)):
    """Retrieves all pending predictions."""
    repo = PredictionRepository(db)
    return await repo.get_pending_predictions()

@router.get("/metrics", response_model=list[PredictionFeedbackDTO])
async def get_latest_metrics(db: AsyncSession = Depends(get_db)):
    """Retrieves latest feedback accuracy metrics."""
    stmt = select(PredictionFeedback).order_by(PredictionFeedback.created_at.desc())
    res = await db.execute(stmt)
    models = res.scalars().all()
    return [PredictionFeedbackDTO.model_validate(m) for m in models]
