import os
import pickle
import pandas as pd
import numpy as np
import shap
from loguru import logger

class SHAPService:
    """
    Computes SHAP feature attribution explanations for XGBoost v1 predictions.
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir

    def explain_prediction(self, features: dict, model_type: str = "churn") -> dict:
        """
        Loads the requested XGBoost model and calculates SHAP explainability factors.
        """
        filename = f"{model_type}_v1.pkl"
        model_path = os.path.join(self.models_dir, filename)
        
        # Define standard feature cols order (matching trainer)
        feature_cols = [
            "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
            "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
            "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
            "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
        ]

        # Standard mapping of internal numeric features to user-friendly/categorical names
        FACTOR_MAPPING = {
            "trust_score": "trust_direction",
            "risk_score": "current_state",
            "health_score": "current_state",
            "payment_delay_avg": "payment_delay_avg",
            "outstanding_ratio": "outstanding_ratio",
            "credit_utilization": "credit_utilization",
            "purchase_gap": "purchase_gap",
            "collection_efficiency": "collection_efficiency",
            "payment_delay_trend": "payment_delay_trend"
        }

        # Build feature DataFrame
        row_dict = {col: features.get(col, 0.0) for col in feature_cols}
        X_df = pd.DataFrame([row_dict])

        # If model does not exist, fall back to heuristic probability & explanations
        if not os.path.exists(model_path):
            logger.warning(f"ML | Model {model_path} not found. Using baseline heuristic explanations.")
            if model_type == "churn":
                pred_val = float(1.0 - features.get("health_score", 0.6))
                top_factors = ["purchase_gap", "outstanding_ratio", "trust_direction", "current_state"]
            elif model_type == "delinquency":
                pred_val = float(features.get("collection_score", 0.3))
                top_factors = ["payment_delay_avg", "outstanding_ratio", "payment_delay_trend", "current_state"]
            else: # distress
                pred_val = float(features.get("risk_score", 0.2))
                top_factors = ["outstanding_ratio", "credit_utilization", "current_state", "trust_direction"]
            return {
                "prediction": round(pred_val, 4),
                "top_factors": top_factors
            }

        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
                
            # Get prediction value (probability)
            if hasattr(model, "predict_proba"):
                pred_val = float(model.predict_proba(X_df)[0][1])
            else:
                pred_val = float(model.predict(X_df)[0])

            # Calculate SHAP values
            explainer = shap.TreeExplainer(model)
            shap_values = explainer(X_df)
            
            # Attributions (extract first row, since we passed one sample)
            attributions = shap_values.values[0]
            
            # Map features to attributions
            feature_impacts = {}
            for col, val in zip(feature_cols, attributions):
                mapped_name = FACTOR_MAPPING.get(col, col)
                # Keep the max absolute impact if multiple features map to the same name
                abs_val = abs(float(val))
                if mapped_name in feature_impacts:
                    feature_impacts[mapped_name] = max(feature_impacts[mapped_name], abs_val)
                else:
                    feature_impacts[mapped_name] = abs_val
            
            # Sort factors by absolute attribution impact
            sorted_factors = sorted(feature_impacts.items(), key=lambda item: item[1], reverse=True)
            top_factors = [factor for factor, impact in sorted_factors[:4]]
            
            # Ensure we have at least 4 factors
            fallback_factors = ["payment_delay_avg", "outstanding_ratio", "trust_direction", "current_state"]
            for f in fallback_factors:
                if f not in top_factors and len(top_factors) < 4:
                    top_factors.append(f)

            return {
                "prediction": round(pred_val, 4),
                "top_factors": top_factors
            }

        except Exception as e:
            logger.error(f"ML | SHAP explanation failed: {e}")
            return {
                "prediction": 0.5,
                "top_factors": ["payment_delay_avg", "outstanding_ratio", "trust_direction", "current_state"]
            }
