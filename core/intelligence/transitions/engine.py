from typing import Any

import polars as pl

from core.models.state_models import CustomerIntelligence


class TransitionEngine:
    """
    Computes real behavioral transitions by comparing persisted historical states
    with currently computed states.
    """

    def compute_real_transition(
        self, prev_state: CustomerIntelligence | None, current_state_df: pl.DataFrame
    ) -> dict[str, Any] | None:
        if current_state_df.is_empty():
            return None

        current_row = current_state_df.to_dicts()[0]

        # If no previous state, it's an 'INITIAL' transition
        if not prev_state:
            return {
                "from_state": None,
                "to_state": current_row.get("behavioral_state"),
                "confidence": 1.0,  # Initial observation
                "reason": "INITIAL_OBSERVATION",
                "drivers": {"initial": True},
                "evidence": current_row,
            }

        prev_behavioral_state = prev_state.behavioral_state_current
        prev_trajectory = prev_state.trajectory_direction

        # If state hasn't changed, we might still record a 'STABLE' transition or skip
        if prev_behavioral_state == current_row.get("behavioral_state") and prev_trajectory == current_row.get(
            "trajectory"
        ):
            return None  # No significant transition

        # Detect Causal Drivers (Simple version for now, improved in CausalDiagnosisEngine)
        drivers = {}
        prev_stress = prev_state.evidence_snapshot.get("stress_score", 0.0) if prev_state.evidence_snapshot else 0.0
        if current_row.get("stress_score", 0.0) > prev_stress + 0.2:
            drivers["stress_spike"] = True

        prev_trust = prev_state.trust_score_current or 0.0
        if current_row.get("trust_score", 0.0) < prev_trust - 0.2:
            drivers["trust_decay"] = True

        return {
            "from_state": prev_behavioral_state,
            "to_state": current_row.get("behavioral_state"),
            "confidence": 0.8,  # Transition confidence
            "reason": f"STATE_CHANGE_{prev_behavioral_state}_TO_{current_row.get('behavioral_state')}",
            "drivers": drivers,
            "evidence": {
                "prev": {"state": prev_behavioral_state, "stress": prev_stress, "trust": prev_trust},
                "current": current_row,
            },
        }
