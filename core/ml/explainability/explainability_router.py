from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.storage.postgres import get_db
from core.ml.explainability.explanation_repository import ExplanationRepository
from core.ml.explainability.shap_service import SHAPService

router = APIRouter(prefix="/ml", tags=["ML Explainability"])

@router.get("/explanation/{customer_id}")
async def get_customer_prediction_explanation(
    customer_id: str,
    model_type: str = Query("churn", description="Model type to explain: churn, delinquency, distress"),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes SHAP tree explanations for the given customer prediction.
    """
    if model_type not in ("churn", "delinquency", "distress"):
        raise HTTPException(status_code=400, detail="Invalid model_type. Must be churn, delinquency, or distress.")
        
    repo = ExplanationRepository(db)
    features = await repo.get_latest_features(customer_id)
    
    if not features:
        raise HTTPException(
            status_code=404, 
            detail=f"No feature snapshot found for customer: {customer_id}. Run inference or worker sync first."
        )
        
    shap_svc = SHAPService()
    explanation = shap_svc.explain_prediction(features, model_type=model_type)
    return explanation
