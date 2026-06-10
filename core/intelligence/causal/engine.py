from typing import Any

from core.models.state_models import CustomerIntelligence


class CausalDiagnosisEngine:
    """
    Identifies the dominant behavioral drivers behind state changes and scores.
    """

    def diagnose_stress(self, features_row: dict[str, Any]) -> list[str]:
        drivers = []

        # Evidence based on dynamic window signals
        if features_row.get("penalty_window", 0) > 0:
            drivers.append("OPERATIONAL_FRICTION: CUSTOMER_FAULT_RETURNS")

        # Approximation: Using sales_window/payments_window as primary proxies
        if features_row.get("payments_window", 0) < features_row.get("sales_window", 0) * 0.7:
            drivers.append("PAYMENT_DISCIPLINE: FRAGMENTATION_RISK")

        return drivers

    def diagnose_transition(
        self, prev_state: CustomerIntelligence | None, current_state: dict[str, Any]
    ) -> dict[str, Any]:
        if not prev_state:
            return {"primary_driver": "INITIAL_OBSERVATION", "supporting_signals": []}

        signals = []
        primary = "STABLE_BEHAVIOR"

        # Trade Behavior Signals
        if current_state.get("trade_behavior", 0) > 0.8:
            signals.append("STRONG_TRADE_PARTICIPATION")

        # OverAll Class Signals
        if current_state.get("overall_class") == "A":
            signals.append("ELITE_COMMERCIAL_QUALITY")
        elif current_state.get("overall_class") == "D":
            primary = "HIGH_COMMERCIAL_RISK"
            signals.append("CRITICAL_BEHAVIORAL_INSTABILITY")

        # Class Drift
        if prev_state.overall_grade_current and current_state.get("overall_class"):
            if current_state["overall_class"] < prev_state.overall_grade_current:  # A < B in string comparison
                signals.append(f"QUALITY_GAIN: {prev_state.overall_grade_current} -> {current_state['overall_class']}")
            elif current_state["overall_class"] > prev_state.overall_grade_current:
                primary = "QUALITY_DEGRADATION"
                signals.append(f"QUALITY_LOSS: {prev_state.overall_grade_current} -> {current_state['overall_class']}")

        # Exposure Pressure
        if current_state.get("exposure_pressure_score", 0) > 1.5:
            primary = "EXPOSURE_SURGE"
            signals.append("HIGH_DEBIT_PERSISTENCE")

        # Payment Discipline Signals
        if current_state.get("payment_discipline", 0) < 0.4:
            primary = "PAYMENT_DISCIPLINE_DEGRADATION"
            signals.append("SETTLEMENT_RHYTHM_LOSS")

        # Operational Friction Signals
        # Inverted RG: Higher score means more returns.
        if current_state.get("rg_behavior_score", 0) > 0.4:
            primary = "OPERATIONAL_FRICTION"
            signals.append("HIGH_RETURN_VOLUME")

        # Stress acceleration (we'll just use evidence_snapshot if available or skip)
        prev_stress = prev_state.evidence_snapshot.get("stress_score", 0.0) if prev_state.evidence_snapshot else 0.0
        if current_state.get("stress_score", 0.0) > prev_stress + 0.15:
            primary = "STRESS_ACCELERATION"
            signals.append("STRESS_SCORE_SPIKE")

        # Cadence drift
        prev_cadence = (
            prev_state.evidence_snapshot.get("cadence_class", "UNKNOWN") if prev_state.evidence_snapshot else "UNKNOWN"
        )
        if current_state.get("cadence_class", "UNKNOWN") != prev_cadence:
            signals.append(f"CADENCE_DRIFT_FROM_{prev_cadence}")
            if primary == "STABLE_BEHAVIOR":
                primary = "CADENCE_SHIFT"

        # Trust decay
        prev_trust = prev_state.trust_score_current or 0.0
        if current_state.get("trust_score", 0.0) < prev_trust - 0.15:
            signals.append("TRUST_DECAY")
            if primary == "STABLE_BEHAVIOR":
                primary = "RELIABILITY_LOSS"

        return {"primary_driver": primary, "supporting_signals": signals}
