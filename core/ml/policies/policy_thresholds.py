class PolicyThresholds:
    """Represents configuration thresholds for predictions and outcome resolution."""
    def __init__(
        self,
        delinquency_threshold_days: int = 45,
        churn_window_days: int = 90,
        distress_threshold: float = 0.70,
        recovery_window_days: int = 60
    ):
        self.delinquency_threshold_days = delinquency_threshold_days
        self.churn_window_days = churn_window_days
        self.distress_threshold = distress_threshold
        self.recovery_window_days = recovery_window_days

    def to_dict(self) -> dict:
        return {
            "delinquency_threshold_days": self.delinquency_threshold_days,
            "churn_window_days": self.churn_window_days,
            "distress_threshold": self.distress_threshold,
            "recovery_window_days": self.recovery_window_days,
        }
