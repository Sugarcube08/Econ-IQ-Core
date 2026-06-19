from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import CustomerPrediction, FeatureSnapshot, PredictionOutcome


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_raw_dataset_records(self):
        stmt = (
            select(
                FeatureSnapshot.snapshot_id,
                FeatureSnapshot.customer_id,
                FeatureSnapshot.snapshot_date,
                FeatureSnapshot.health_score,
                FeatureSnapshot.risk_score,
                FeatureSnapshot.trust_score,
                FeatureSnapshot.billing_30d,
                FeatureSnapshot.billing_90d,
                FeatureSnapshot.billing_180d,
                FeatureSnapshot.payments_30d,
                FeatureSnapshot.payments_90d,
                FeatureSnapshot.payments_180d,
                FeatureSnapshot.returns_30d,
                FeatureSnapshot.returns_90d,
                FeatureSnapshot.purchase_gap,
                FeatureSnapshot.purchase_frequency,
                FeatureSnapshot.payment_delay_avg,
                FeatureSnapshot.payment_delay_trend,
                FeatureSnapshot.collection_efficiency,
                FeatureSnapshot.outstanding_current,
                FeatureSnapshot.outstanding_ratio,
                FeatureSnapshot.credit_utilization,
                PredictionOutcome.prediction_type,
                PredictionOutcome.actual_value.label("target_label"),
                PredictionOutcome.predicted_value,
                PredictionOutcome.is_correct
            )
            .join(CustomerPrediction, FeatureSnapshot.snapshot_id == CustomerPrediction.snapshot_id)
            .join(PredictionOutcome, CustomerPrediction.prediction_id == PredictionOutcome.prediction_id)
        )
        res = await self.session.execute(stmt)
        return [dict(r._mapping) for r in res.all()]
