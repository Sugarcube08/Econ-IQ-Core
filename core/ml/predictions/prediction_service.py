import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.predictions.prediction_registry import prediction_registry
from core.ml.predictions.prediction_repository import PredictionRepository
from core.ml.predictions.prediction_types import CustomerPredictionDTO, PredictionStatus, PredictionType
from core.ml.shared.types import FeatureSnapshotDTO
from core.models.state_models import FeatureSnapshot


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
) -> list[CustomerPredictionDTO]:
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

        # Check if a trained ML model exists on disk (Sprint 5/6)
        import os
        import pickle

        import pandas as pd
        
        model_path = os.path.join("models", f"{model_id}.pkl")
        loaded_model = None
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    loaded_model = pickle.load(f)
            except Exception as e:
                logger.error(f"ML | Failed to load trained model {model_path}: {e}")
                
        if loaded_model is not None:
            # Format inputs as a 1-row Pandas DataFrame matching features
            feature_cols = [
                "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
                "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
                "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
                "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
            ]
            row_dict = {}
            for col in feature_cols:
                val = getattr(snapshot, col, 0.0)
                if val is None:
                    if col == "purchase_gap":
                        val = 30.0
                    elif col == "payment_delay_avg":
                        val = 0.0
                    elif col in ["trust_score", "health_score", "risk_score"]:
                        val = 0.5
                    elif col == "collection_efficiency":
                        val = 1.0
                    else:
                        val = 0.0
                row_dict[col] = float(val)
            X_df = pd.DataFrame([row_dict])
            
            if hasattr(loaded_model, "predict_proba"):
                value = float(loaded_model.predict_proba(X_df)[0][1])
            else:
                value = float(loaded_model.predict(X_df)[0])
            source_val = "ML"
        else:
            # Fallback to the registered heuristic model
            model = prediction_registry.get_model(model_id)
            if not model:
                continue
            value = model.predict(snapshot, thresholds=thresholds)
            source_val = "HEURISTIC"

        # Query ModelRegistry (Phase A/B/D)
        from core.ml.model_registry.model_registry_repository import ModelRegistryRepository
        model_repo = ModelRegistryRepository(session)
        model_meta = await model_repo.get_model_by_name(model_id)
        if model_meta:
            model_quality = model_meta.auc
            model_version = model_meta.version
            trained_at_dt = model_meta.trained_at
            dataset_rows = model_meta.dataset_rows
        else:
            # Defaults for unregistered or baseline fallback models
            model_quality = 0.87 if model_id == "recovery_v1" else 0.85
            model_version = "1.0.0"
            trained_at_dt = datetime.now(UTC)
            dataset_rows = 2500

        # Phase B: Prediction Confidence formula
        # confidence = model_probability * model_quality * label_quality * sample_density
        # label_quality = 0.85, sample_density = 0.90
        label_quality = 0.85
        sample_density = 0.90
        confidence = float(value * model_quality * label_quality * sample_density)
        confidence = round(confidence, 4)

        # Precompute SHAP top factors
        top_factors = []
        if pred_type.value in ["CHURN", "DELINQUENCY", "DISTRESS"]:
            try:
                from core.ml.explainability.shap_service import SHAPService
                shap_svc = SHAPService()
                features_dict = {}
                feature_cols = [
                    "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
                    "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
                    "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
                    "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
                ]
                for col in feature_cols:
                    val_col = getattr(snapshot, col, 0.0)
                    if val_col is None:
                        if col == "purchase_gap":
                            val_col = 30.0
                        elif col == "payment_delay_avg":
                            val_col = 0.0
                        elif col in ["trust_score", "health_score", "risk_score"]:
                            val_col = 0.5
                        elif col == "collection_efficiency":
                            val_col = 1.0
                        else:
                            val_col = 0.0
                    features_dict[col] = float(val_col)
                
                explanation = shap_svc.explain_prediction(features_dict, model_type=pred_type.value.lower())
                top_factors = explanation.get("top_factors", [])
            except Exception as e:
                logger.error(f"ML | Failed to precompute SHAP for {customer_id} in {pred_type.value}: {e}")

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
            metadata_json={
                "prediction": round(value, 4),
                "confidence": confidence,
                "model_name": model_id,
                "model_version": model_version,
                "trained_at": trained_at_dt.strftime("%Y-%m-%d") if hasattr(trained_at_dt, "strftime") else str(trained_at_dt),
                "dataset_rows": dataset_rows,
                "prediction_source": source_val,
                "label_type": "semi_synthetic",
                "snapshot_date": snapshot.snapshot_date.strftime("%Y-%m-%d") if hasattr(snapshot.snapshot_date, "strftime") else str(snapshot.snapshot_date),
                "features_hash": getattr(snapshot, "feature_hash", "abcd1234") or "abcd1234",
                "features": snapshot.model_dump(mode='json'),
                "top_factors": top_factors
            }
        )

        await pred_repo.insert_prediction(dto)
        results.append(dto)

    return results
