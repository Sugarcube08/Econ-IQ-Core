import os
import pickle
import pandas as pd
from typing import Dict, Any
from core.ml.explainability.explanation_repository import ExplanationRepository
from core.ml.simulator.impact_estimator import ActionImpactEstimator

class CounterfactualSimulator:
    """
    Executes what-if impact scenarios by applying dynamic feature shifts
    and running them through XGBoost distress model inference.
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.estimator = ActionImpactEstimator()

    async def simulate(self, customer_id: str, actions: list[str], session) -> dict:
        """
        Runs counterfactual simulation for a set of advisor actions.
        """
        # 1. Fetch latest feature snapshot
        repo = ExplanationRepository(session)
        features = await repo.get_latest_features(customer_id)
        
        if not features:
            return {}
            
        # 2. Score baseline (current state)
        current_health = features.get("health_score", 0.5)
        current_distress = self._predict_distress(features)
        
        # 3. Simulate feature modifications
        simulated_features = self.estimator.apply_actions(features, actions)
        
        # 4. Score counterfactual state
        simulated_health = simulated_features.get("health_score", 0.5)
        simulated_distress = self._predict_distress(simulated_features)
        
        return {
            "current": {
                "distress": round(current_distress, 4),
                "health": round(current_health, 4)
            },
            "simulated": {
                "distress": round(simulated_distress, 4),
                "health": round(simulated_health, 4)
            },
            "delta": {
                "distress": round(simulated_distress - current_distress, 4),
                "health": round(simulated_health - current_health, 4)
            }
        }

    def _predict_distress(self, features: dict) -> float:
        model_path = os.path.join(self.models_dir, "distress_v1.pkl")
        
        # Expected feature columns for the trained distress model
        feature_cols = [
            "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
            "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
            "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
            "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
        ]
        
        # Assemble inference DataFrame
        row_dict = {col: features.get(col, 0.0) for col in feature_cols}
        X_df = pd.DataFrame([row_dict])
        
        if not os.path.exists(model_path):
            # Fallback to heuristic distress risk
            risk = features.get("risk_score", 0.5)
            prob = risk / 0.70
            return max(0.0, min(1.0, prob))
            
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            if hasattr(model, "predict_proba"):
                return float(model.predict_proba(X_df)[0][1])
            else:
                return float(model.predict(X_df)[0])
        except Exception:
            risk = features.get("risk_score", 0.5)
            return max(0.0, min(1.0, risk / 0.70))
