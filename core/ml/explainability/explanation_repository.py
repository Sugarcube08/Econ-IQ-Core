from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.state_models import FeatureSnapshot

class ExplanationRepository:
    """
    Handles retrieval of dynamic point-in-time feature snapshots for explanation generation.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_features(self, customer_id: str) -> dict:
        """
        Fetches the latest numeric feature values for a customer from FeatureSnapshots.
        """
        stmt = (
            select(FeatureSnapshot)
            .where(FeatureSnapshot.customer_id == customer_id)
            .order_by(FeatureSnapshot.snapshot_date.desc(), FeatureSnapshot.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        snapshot = res.scalar_one_or_none()
        if not snapshot:
            return {}
            
        return {
            "health_score": snapshot.health_score or 0.0,
            "risk_score": snapshot.risk_score or 0.0,
            "trust_score": snapshot.trust_score or 0.0,
            "billing_30d": snapshot.billing_30d or 0.0,
            "billing_90d": snapshot.billing_90d or 0.0,
            "billing_180d": snapshot.billing_180d or 0.0,
            "payments_30d": snapshot.payments_30d or 0.0,
            "payments_90d": snapshot.payments_90d or 0.0,
            "payments_180d": snapshot.payments_180d or 0.0,
            "returns_30d": snapshot.returns_30d or 0.0,
            "returns_90d": snapshot.returns_90d or 0.0,
            "purchase_gap": snapshot.purchase_gap or 30,
            "purchase_frequency": snapshot.purchase_frequency or 0.0,
            "payment_delay_avg": snapshot.payment_delay_avg or 0.0,
            "payment_delay_trend": snapshot.payment_delay_trend or 0.0,
            "collection_efficiency": snapshot.collection_efficiency or 1.0,
            "outstanding_current": snapshot.outstanding_current or 0.0,
            "outstanding_ratio": snapshot.outstanding_ratio or 0.0,
            "credit_utilization": snapshot.credit_utilization or 0.0,
        }
