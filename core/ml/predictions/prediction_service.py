import uuid
from datetime import datetime, UTC
from typing import List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import FeatureSnapshot
from core.ml.predictions.prediction_types import CustomerPredictionDTO, PredictionType, PredictionStatus
from core.ml.predictions.prediction_registry import prediction_registry
from core.ml.predictions.prediction_repository import PredictionRepository
from core.ml.features.feature_repository import FeatureRepository
from core.ml.shared.types import FeatureSnapshotDTO
from core.ml.policies import get_policy_profile

class ChurnModel:
    """Heuristic model for Churn prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO) -> float:
        profile = get_policy_profile("default")
        gap = snapshot.purchase_gap if snapshot.purchase_gap is not None else 30
        prob = gap / float(profile.churn_window_days)
        return max(0.0, min(1.0, prob))

class DelinquencyModel:
    """Heuristic model for Delinquency prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO) -> float:
        profile = get_policy_profile("default")
        delay = snapshot.payment_delay_avg if snapshot.payment_delay_avg is not None else 0.0
        prob = delay / float(profile.delinquency_threshold_days)
        return max(0.0, min(1.0, prob))

class DistressModel:
    """Heuristic model for Distress prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO) -> float:
        profile = get_policy_profile("default")
        risk = snapshot.risk_score if snapshot.risk_score is not None else 0.5
        prob = risk / profile.distress_threshold
        return max(0.0, min(1.0, prob))

class RecoveryModel:
    """Heuristic model for Recovery prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO) -> float:
        trust = snapshot.trust_score if snapshot.trust_score is not None else 0.5
        eff = snapshot.collection_efficiency if snapshot.collection_efficiency is not None else 1.0
        prob = trust * eff
        return max(0.0, min(1.0, prob))

class StateTransitionModel:
    """Heuristic model for State Transition prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO) -> float:
        health = snapshot.health_score if snapshot.health_score is not None else 0.5
        return max(0.0, min(1.0, 1.0 - health))

# Register Models at startup
prediction_registry.register_model("churn_v1", ChurnModel())
prediction_registry.register_model("delinquency_v1", DelinquencyModel())
prediction_registry.register_model("distress_v1", DistressModel())
prediction_registry.register_model("recovery_v1", RecoveryModel())
prediction_registry.register_model("state_transition_v1", StateTransitionModel())


async def generate_predictions_for_snapshot(
    customer_id: str,
    snapshot_id: str,
    session: AsyncSession
) -> List[CustomerPredictionDTO]:
    """
    Runs model inference on a customer's feature snapshot and persists the predictions.
    """
    # 1. Fetch feature snapshot
    stmt = select(FeatureSnapshot).where(FeatureSnapshot.snapshot_id == snapshot_id)
    res = await session.execute(stmt)
    snap_model = res.scalars().first()
    if not snap_model:
        logger.error(f"ML | Snapshot not found: {snapshot_id}")
        return []

    snapshot = FeatureSnapshotDTO.model_validate(snap_model)
    pred_repo = PredictionRepository(session)
    results = []

    mapping = {
        PredictionType.CHURN: "churn_v1",
        PredictionType.DELINQUENCY: "delinquency_v1",
        PredictionType.DISTRESS: "distress_v1",
        PredictionType.RECOVERY: "recovery_v1",
        PredictionType.STATE_TRANSITION: "state_transition_v1"
    }

    for pred_type, model_id in mapping.items():
        # Prevent duplicate predictions per snapshot
        exists = await pred_repo.prediction_exists(customer_id, snapshot_id, pred_type.value)
        if exists:
            continue

        model = prediction_registry.get_model(model_id)
        if not model:
            continue

        value = model.predict(snapshot)
        confidence = 0.85  # heuristic confidence factor

        dto = CustomerPredictionDTO(
            prediction_id=str(uuid.uuid4()),
            customer_id=customer_id,
            snapshot_id=snapshot_id,
            model_id=model_id,
            prediction_type=pred_type,
            prediction_value=value,
            confidence=confidence,
            generated_at=datetime.combine(snapshot.snapshot_date, datetime.min.time()).replace(tzinfo=UTC),
            prediction_horizon_days=90,
            prediction_status=PredictionStatus.PENDING,
            metadata_json={"features": snapshot.model_dump(mode='json')}
        )

        await pred_repo.insert_prediction(dto)
        results.append(dto)

    return results
