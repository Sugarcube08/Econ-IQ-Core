from core.ml.policies.policy_thresholds import PolicyThresholds

POLICY_VERSIONS = {
    "1.0.0": PolicyThresholds(
        delinquency_threshold_days=45,
        churn_window_days=90,
        distress_threshold=0.70,
        recovery_window_days=60
    ),
    "2.0.0": PolicyThresholds(
        delinquency_threshold_days=30,
        churn_window_days=90,
        distress_threshold=0.65,
        recovery_window_days=60
    )
}

CURRENT_POLICY_VERSION = "1.0.0"

def get_policy_by_version(version: str = CURRENT_POLICY_VERSION) -> PolicyThresholds:
    """Retrieves a PolicyThresholds instance based on version string."""
    return POLICY_VERSIONS.get(version, POLICY_VERSIONS[CURRENT_POLICY_VERSION])
