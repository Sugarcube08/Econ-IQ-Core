from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.simulator.simulator import CounterfactualSimulator
from core.storage.postgres import get_db

router = APIRouter(prefix="/ml", tags=["ML Simulation Engine"])

class SimulationRequest(BaseModel):
    customer_id: str = Field(..., description="Unique ID of the customer to simulate")
    actions: list[str] = Field(..., description="List of counterfactual actions to apply")

class ScoreState(BaseModel):
    distress: float
    health: float

class SimulationResponse(BaseModel):
    current: ScoreState
    simulated: ScoreState
    delta: ScoreState
    simulation_source: str = "HEURISTIC"

@router.post("/simulate", response_model=SimulationResponse)
async def simulate_customer_actions(
    req: SimulationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes what-if scenario simulations for a customer under specified actions.
    """
    simulator = CounterfactualSimulator()
    result = await simulator.simulate(req.customer_id, req.actions, db)
    
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"No feature snapshot found for customer: {req.customer_id}. Run inference or worker sync first."
        )
        
    return result
