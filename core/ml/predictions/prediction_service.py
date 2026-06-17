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

class ChurnModel:
    """Heuristic model for Churn prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO, thresholds: dict = None) -> float:
        churn_window = thresholds.get("CHURN_WINDOW_DAYS", 90) if thresholds else 90
        gap = snapshot.purchase_gap if snapshot.purchase_gap is not None else 30
        prob = gap / float(churn_window)
        return max(0.0, min(1.0, prob))

class DelinquencyModel:
    """Heuristic model for Delinquency prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO, thresholds: dict = None) -> float:
        delinquency_days = thresholds.get("DELINQUENCY_WINDOW_DAYS", 45) if thresholds else 45
        delay = snapshot.payment_delay_avg if snapshot.payment_delay_avg is not None else 0.0
        prob = delay / float(delinquency_days)
        return max(0.0, min(1.0, prob))

class DistressModel:
    """Heuristic model for Distress prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO, thresholds: dict = None) -> float:
        distress_thresh = thresholds.get("DISTRESS_THRESHOLD", 0.70) if thresholds else 0.70
        risk = snapshot.risk_score if snapshot.risk_score is not None else 0.5
        prob = risk / distress_thresh
        return max(0.0, min(1.0, prob))

class RecoveryModel:
    """Heuristic model for Recovery prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO, thresholds: dict = None) -> float:
        recovery_thresh = thresholds.get("RECOVERY_THRESHOLD", 0.65) if thresholds else 0.65
        trust = snapshot.trust_score if snapshot.trust_score is not None else 0.5
        eff = snapshot.collection_efficiency if snapshot.collection_efficiency is not None else 1.0
        prob = (trust * eff) / recovery_thresh
        return max(0.0, min(1.0, prob))

class StateTransitionModel:
    """Heuristic model for State Transition prediction."""
    def predict(self, snapshot: FeatureSnapshotDTO, thresholds: dict = None) -> float:
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

    # Load active policy thresholds from PolicyRegistry
    from core.ml.policies.policy_service import PolicyService
    policy_svc = PolicyService(session)
    thresholds = await policy_svc.get_active_thresholds()

    mapping = {
        PredictionType.CHURN: ("churn_v1", thresholds.get("CHURN_WINDOW_DAYS", 90)),
        PredictionType.DELINQUENCY: ("delinquency_v1", thresholds.get("DELINQUENCY_WINDOW_DAYS", 45)),
        PredictionType.DISTRESS: ("distress_v1", 90),
        PredictionType.RECOVERY: ("recovery_v1", thresholds.get("RECOVERY_WINDOW_DAYS", 60)),
        PredictionType.STATE_TRANSITION: ("state_transition_v1", 90)
    }

    for pred_type, (model_id, horizon_days) in mapping.items():
        # Prevent duplicate predictions per snapshot
        exists = await pred_repo.prediction_exists(customer_id, snapshot_id, pred_type.value)
        if exists:
            continue

        model = prediction_registry.get_model(model_id)
        if not model:
            continue

        # Pass the loaded thresholds to the predict method (or check if it is a real model with predict_proba)
        if hasattr(model, "predict_proba"):
            import numpy as np
            value = float(model.predict_proba(snapshot)[0])
        else:
            value = model.predict(snapshot, thresholds=thresholds)

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
            prediction_horizon_days=horizon_days,
            prediction_status=PredictionStatus.PENDING,
            metadata_json={"features": snapshot.model_dump(mode='json')}
        )

        await pred_repo.insert_prediction(dto)
        results.append(dto)

    return results
