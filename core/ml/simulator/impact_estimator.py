from typing import Dict, Any

class ActionImpactEstimator:
    """
    Estimates the counterfactual impact of credit advisor actions on customer features.
    Maps business actions to deterministic modifications in the feature snapshot.
    """
    
    # Define effects of actions as a dictionary of transformations
    ACTION_EFFECTS = {
        "offer_extension": {
            "payment_delay_avg_multiplier": 0.5,
            "payment_delay_trend_delta": -5.0,
            "collection_efficiency_delta": 0.15,
            "health_score_delta": 0.10,
            "risk_score_delta": -0.15
        },
        "increase_credit_limit": {
            "credit_utilization_multiplier": 0.8,
            "outstanding_ratio_multiplier": 0.9,
            "health_score_delta": 0.05,
            "risk_score_delta": -0.05
        },
        "decrease_credit_limit": {
            "credit_utilization_multiplier": 1.2,
            "health_score_delta": -0.05,
            "risk_score_delta": 0.10
        },
        "promise_to_pay": {
            "outstanding_current_multiplier": 0.85,
            "outstanding_ratio_multiplier": 0.85,
            "credit_utilization_multiplier": 0.85,
            "collection_efficiency_delta": 0.10,
            "health_score_delta": 0.05
        },
        "collection_campaign": {
            "collection_efficiency_delta": 0.20,
            "payment_delay_avg_multiplier": 0.7,
            "risk_score_delta": 0.05
        },
        "visit_customer": {
            "collection_efficiency_delta": 0.25,
            "payment_delay_avg_multiplier": 0.6,
            "risk_score_delta": 0.08
        },
        "temporary_block": {
            "purchase_gap_delta": 10.0,
            "outstanding_current_multiplier": 0.9,
            "health_score_delta": -0.10
        },
        "escalation": {
            "collection_efficiency_delta": 0.30,
            "payment_delay_avg_multiplier": 0.5,
            "risk_score_delta": 0.15
        }
    }

    def apply_actions(self, original_features: Dict[str, Any], actions: list[str]) -> Dict[str, Any]:
        """
        Applies a list of actions sequentially to original features, producing simulated features.
        """
        simulated = original_features.copy()
        
        for action in actions:
            effects = self.ACTION_EFFECTS.get(action)
            if not effects:
                continue
            
            # Apply multipliers
            if "payment_delay_avg_multiplier" in effects and "payment_delay_avg" in simulated:
                simulated["payment_delay_avg"] *= effects["payment_delay_avg_multiplier"]
                
            if "credit_utilization_multiplier" in effects and "credit_utilization" in simulated:
                simulated["credit_utilization"] *= effects["credit_utilization_multiplier"]
                simulated["credit_utilization"] = min(1.0, max(0.0, simulated["credit_utilization"]))
                
            if "outstanding_ratio_multiplier" in effects and "outstanding_ratio" in simulated:
                simulated["outstanding_ratio"] *= effects["outstanding_ratio_multiplier"]
                
            if "outstanding_current_multiplier" in effects and "outstanding_current" in simulated:
                simulated["outstanding_current"] *= effects["outstanding_current_multiplier"]
                
            # Apply additions
            if "payment_delay_trend_delta" in effects and "payment_delay_trend" in simulated:
                simulated["payment_delay_trend"] += effects["payment_delay_trend_delta"]
                
            if "collection_efficiency_delta" in effects and "collection_efficiency" in simulated:
                simulated["collection_efficiency"] += effects["collection_efficiency_delta"]
                simulated["collection_efficiency"] = min(1.0, max(0.0, simulated["collection_efficiency"]))
                
            if "health_score_delta" in effects and "health_score" in simulated:
                simulated["health_score"] += effects["health_score_delta"]
                simulated["health_score"] = min(1.0, max(0.0, simulated["health_score"]))
                
            if "risk_score_delta" in effects and "risk_score" in simulated:
                simulated["risk_score"] += effects["risk_score_delta"]
                simulated["risk_score"] = min(1.0, max(0.0, simulated["risk_score"]))
                
            if "purchase_gap_delta" in effects and "purchase_gap" in simulated:
                if simulated["purchase_gap"] is not None:
                    simulated["purchase_gap"] += int(effects["purchase_gap_delta"])
                else:
                    simulated["purchase_gap"] = int(effects["purchase_gap_delta"])

        return simulated
