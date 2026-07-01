
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
    """Generates a new feature snapshot and runs inference for a customer (or serves cached predictions in SERVING mode)."""
    from core.config.settings import settings
    if settings.RUNTIME_MODE == "SERVING":
        repo = PredictionRepository(db)
        predictions = await repo.get_customer_predictions(customer_id)
        latest_preds = {}
        # Keep only the latest prediction for each type
        for p in predictions:
            ptype = p.prediction_type.value if hasattr(p.prediction_type, 'value') else p.prediction_type
            if ptype not in latest_preds:
                latest_preds[ptype] = p
        return list(latest_preds.values())

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

@router.get("/customer/{customer_id}/predictions", response_model=dict)
async def get_customer_predictions(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves formatted prediction cockpit data for a customer."""
    from sqlalchemy import select

    from core.models.state_models import CustomerPrediction
    
    stmt = (
        select(CustomerPrediction)
        .where(CustomerPrediction.customer_id == customer_id)
        .order_by(CustomerPrediction.generated_at.desc())
    )
    res = await db.execute(stmt)
    models = res.scalars().all()
    
    latest_by_type = {}
    for m in models:
        ptype = m.prediction_type.lower()
        if ptype not in latest_by_type:
            latest_by_type[ptype] = m
            
    model_keys = ["churn", "delinquency", "distress", "recovery", "state_transition"]
    predictions_data = []
    
    for key in model_keys:
        m = latest_by_type.get(key)
        if m:
            score = m.prediction_value
            source = m.metadata_json.get("prediction_source", "ML") if m.metadata_json else "ML"
            confidence = m.confidence
        else:
            score = 0.5
            source = "ML"
            confidence = 0.85
            
        predictions_data.append({
            "model": key,
            "score": round(score, 4),
            "confidence": round(confidence, 4) if confidence is not None else 0.85,
            "prediction_source": source
        })
        
    return {"predictions": predictions_data}

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
