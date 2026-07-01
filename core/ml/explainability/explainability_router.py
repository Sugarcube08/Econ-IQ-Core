from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.explainability.explanation_repository import ExplanationRepository
from core.ml.explainability.shap_service import SHAPService
from core.storage.postgres import get_db

router = APIRouter(prefix="/ml", tags=["ML Explainability"])

@router.get("/explanation/{id}")
async def get_customer_prediction_explanation(
    id: str,
    model_type: str = Query("churn", description="Model type to explain: churn, delinquency, distress"),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes SHAP tree explanations for the given customer prediction.
    """
    if model_type not in ("churn", "delinquency", "distress"):
        raise HTTPException(status_code=400, detail="Invalid model_type. Must be churn, delinquency, or distress.")
        
    from core.config.settings import settings
    if settings.RUNTIME_MODE == "SERVING":
        from core.models.state_models import CustomerPrediction
        from sqlalchemy import select
        stmt = (
            select(CustomerPrediction)
            .where(CustomerPrediction.customer_id == id)
            .where(CustomerPrediction.prediction_type == model_type.upper())
            .order_by(CustomerPrediction.generated_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        pred_obj = res.scalars().first()
        if pred_obj:
            top_factors = pred_obj.metadata_json.get("top_factors")
            if top_factors is not None:
                return {
                    "prediction": round(pred_obj.prediction_value, 4),
                    "top_factors": top_factors
                }
            else:
                # If prediction exists but lacks top_factors, return default heuristic top factors
                if model_type == "churn":
                    tf = ["purchase_gap", "outstanding_ratio", "trust_direction", "current_state"]
                elif model_type == "delinquency":
                    tf = ["payment_delay_avg", "outstanding_ratio", "payment_delay_trend", "current_state"]
                else:
                    tf = ["outstanding_ratio", "credit_utilization", "current_state", "trust_direction"]
                return {
                    "prediction": round(pred_obj.prediction_value, 4),
                    "top_factors": tf
                }
        raise HTTPException(
            status_code=404, 
            detail=f"No precomputed prediction found for customer: {id} and model: {model_type}."
        )

    repo = ExplanationRepository(db)
    features = await repo.get_latest_features(id)
    
    if not features:
        raise HTTPException(
            status_code=404, 
            detail=f"No feature snapshot found for customer: {id}. Run inference or worker sync first."
        )
        
    shap_svc = SHAPService()
    explanation = shap_svc.explain_prediction(features, model_type=model_type)
    return explanation
