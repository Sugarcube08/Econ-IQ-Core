from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import CustomerIntelligence


class AdvisorRepository:
    """
    Retrieves baseline customer state and scores to seed advisor reviews.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_customer_state_and_scores(self, customer_id: str) -> dict:
        """
        Loads the current CustomerIntelligence state and score record.
        """
        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res = await self.session.execute(stmt)
        intel = res.scalar_one_or_none()
        if not intel:
            return {}
            
        return {
            "customer_id": intel.customer_id,
            "state": intel.state or "healthy",
            "health_score": intel.health_score or 0.0,
            "risk_score": intel.risk_score or 0.0,
            "trust_score": intel.trust_score or 0.0,
            "collection_score": intel.collection_score or 0.0,
        }
