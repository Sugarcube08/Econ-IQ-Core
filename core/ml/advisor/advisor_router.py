from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.storage.postgres import get_db
from core.ml.advisor.advisor_engine import AdvisorEngine

router = APIRouter(prefix="/advisor", tags=["Commercial Advisor Engine"])

@router.get("/customer/{customer_id}")
async def get_customer_advice(
    customer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves baseline predictions, customer state, and prioritized action recommendations
    based on counterfactual simulation and model feedback confidence.
    """
    engine = AdvisorEngine()
    advice = await engine.get_advice(customer_id, db)
    
    if not advice:
        raise HTTPException(
            status_code=404,
            detail=f"No scores or features found for customer: {customer_id}. Run recomputation or worker sync first."
        )
        
    return advice
