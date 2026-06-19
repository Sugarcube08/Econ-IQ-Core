from typing import Any

from sqlalchemy import select

from core.ml.interfaces import IFeatureProvider
from core.models.state_models import CustomerIntelligence
from core.storage.postgres import AsyncSessionLocal


class MLFeatureProvider(IFeatureProvider):
    """
    Exposes features for ML inference from customer intelligence database.
    """
    async def get_features(self, customer_id: str) -> dict[str, Any]:
        """
        Retrieves feature snapshot for a customer.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
            res = await session.execute(stmt)
            intel = res.scalars().first()
            
            if not intel:
                return {}
                
            return {
                "customer_id": intel.customer_id,
                "outstanding_current": intel.outstanding_current or 0.0,
                "state": intel.state or "active",
                "archetype": intel.customer_archetype or "stable_retailer",
                "health_score": intel.health_score or 0.0,
                "risk_score": intel.risk_score or 0.0,
                "trust_score": intel.trust_score or 0.0,
                "growth_score": intel.growth_score or 0.0,
                "collection_score": intel.collection_score or 0.0,
                "relationship_score": intel.relationship_score or 0.0,
                "credit_score": intel.credit_score or 0.0,
                "opportunity_score": intel.opportunity_score or 0.0
            }
