from core.ml.policies.policy_thresholds import PolicyThresholds

DEFAULT_PROFILE = PolicyThresholds(
    delinquency_threshold_days=45,
    churn_window_days=90,
    distress_threshold=0.70,
    recovery_window_days=60
)

CONSERVATIVE_PROFILE = PolicyThresholds(
    delinquency_threshold_days=30,
    churn_window_days=60,
    distress_threshold=0.60,
    recovery_window_days=45
)

AGGRESSIVE_PROFILE = PolicyThresholds(
    delinquency_threshold_days=60,
    churn_window_days=120,
    distress_threshold=0.80,
    recovery_window_days=90
)

PROFILES = {
    "default": DEFAULT_PROFILE,
    "conservative": CONSERVATIVE_PROFILE,
    "aggressive": AGGRESSIVE_PROFILE
}

def get_policy_profile(name: str = "default") -> PolicyThresholds:
    """Retrieves a PolicyThresholds instance based on profile name."""
    return PROFILES.get(name.lower(), DEFAULT_PROFILE)
