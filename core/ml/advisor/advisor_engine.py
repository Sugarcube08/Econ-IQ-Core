import os
import pickle

import pandas as pd

from core.ml.advisor.advisor_repository import AdvisorRepository
from core.ml.simulator.simulator import CounterfactualSimulator


class AdvisorEngine:
    """
    Combines commercial state predictions with counterfactual simulations
    to recommend optimal credit risk mitigation or revenue actions.
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.simulator = CounterfactualSimulator(models_dir)

    async def get_advice(self, customer_id: str, session) -> dict:
        """
        Generates advisor recommendations for a customer.
        """
        # 1. Fetch current scores and state
        repo = AdvisorRepository(session)
        intel = await repo.get_customer_state_and_scores(customer_id)
        if not intel:
            return {}

        state = intel["state"].capitalize()

        # 2. Fetch latest features snapshot
        from core.ml.explainability.explanation_repository import ExplanationRepository
        feat_repo = ExplanationRepository(session)
        features = await feat_repo.get_latest_features(customer_id)
        if not features:
            return {}

        current_distress = self._predict_distress(features)
        current_churn = self._predict_churn(features)
        recovery_prob = self._predict_recovery(features)

        # 3. Optimize recommendations using counterfactual simulator
        candidate_actions = [
            "offer_extension",
            "increase_credit_limit",
            "decrease_credit_limit",
            "promise_to_pay",
            "collection_campaign",
            "visit_customer",
            "temporary_block",
            "escalation"
        ]

        from core.ml.model_registry.model_registry_repository import ModelRegistryRepository
        model_repo = ModelRegistryRepository(session)
        model_meta = await model_repo.get_model_by_name("recovery_v1")
        if model_meta:
            model_quality = model_meta.auc
            prediction_source = "ML"
        else:
            model_quality = 0.87
            prediction_source = "ML" if os.path.exists(os.path.join(self.models_dir, "recovery_v1.pkl")) else "HEURISTIC"

        # Phase B Confidence
        label_quality = 0.85
        sample_density = 0.90
        confidence = float(recovery_prob * model_quality * label_quality * sample_density)
        confidence = round(confidence, 4)

        outstanding_current = float(features.get("outstanding_current", 150000.0) or 150000.0)
        expected_recovery = float(recovery_prob * outstanding_current)

        recommendations = []
        for action in candidate_actions:
            sim_res = await self.simulator.simulate(customer_id, [action], session)
            if not sim_res:
                continue
            
            distress_delta = sim_res["delta"]["distress"]
            health_delta = sim_res["delta"]["health"]
            
            # If the action reduces distress risk or improves health score:
            if distress_delta < 0 or health_delta > 0:
                recommendations.append({
                    "recommendation": action,
                    "expected_delta_health": round(float(health_delta), 4),
                    "expected_recovery": round(expected_recovery, 2),
                    "confidence": round(confidence, 4),
                    "simulation_source": "HEURISTIC",
                    "prediction_source": prediction_source,
                    "model": "recovery_v1",
                    "label_type": "semi_synthetic"
                })

        # Sort recommendations by expected_delta_health descending
        recommendations = sorted(recommendations, key=lambda r: r["expected_delta_health"], reverse=True)

        return {
            "customer_id": customer_id,
            "state": state,
            "predictions": {
                "distress": round(current_distress, 4),
                "churn": round(current_churn, 4),
                "recovery": round(recovery_prob, 4)
            },
            "recommendations": recommendations
        }

    def _predict_distress(self, features: dict) -> float:
        model_path = os.path.join(self.models_dir, "distress_v1.pkl")
        return self._run_inference(features, model_path, fallback_col="risk_score", fallback_divisor=0.70)

    def _predict_churn(self, features: dict) -> float:
        model_path = os.path.join(self.models_dir, "churn_v1.pkl")
        return self._run_inference(features, model_path, fallback_col="health_score", fallback_divisor=1.0, invert_fallback=True)

    def _predict_recovery(self, features: dict) -> float:
        model_path = os.path.join(self.models_dir, "recovery_v1.pkl")
        if not os.path.exists(model_path):
            trust = features.get("trust_score", 0.5)
            if trust is None:
                trust = 0.5
            eff = features.get("collection_efficiency", 1.0)
            if eff is None:
                eff = 1.0
            prob = (trust * eff) / 0.65
            return max(0.0, min(1.0, prob))
        return self._run_inference(features, model_path, fallback_col="trust_score", fallback_divisor=0.65)

    def _run_inference(self, features: dict, model_path: str, fallback_col: str, fallback_divisor: float, invert_fallback: bool = False) -> float:
        feature_cols = [
            "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
            "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
            "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
            "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
        ]
        row_dict = {col: features.get(col, 0.0) for col in feature_cols}
        X_df = pd.DataFrame([row_dict])
        
        if not os.path.exists(model_path):
            val = features.get(fallback_col, 0.5)
            prob = (1.0 - val) if invert_fallback else val
            return max(0.0, min(1.0, prob / fallback_divisor))
            
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            if hasattr(model, "predict_proba"):
                return float(model.predict_proba(X_df)[0][1])
            else:
                return float(model.predict(X_df)[0])
        except Exception:
            val = features.get(fallback_col, 0.5)
            prob = (1.0 - val) if invert_fallback else val
            return max(0.0, min(1.0, prob / fallback_divisor))
