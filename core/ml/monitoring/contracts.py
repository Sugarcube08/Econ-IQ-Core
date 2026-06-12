from pydantic import BaseModel, Field


class FeatureDriftMetric(BaseModel):
    """
    Contract for logging drift tracking metrics (PSI, KS Test) for features.
    """
    feature_name: str
    psi_value: float = Field(..., description="Population Stability Index comparing inference distribution vs training baseline.")
    ks_p_value: float = Field(..., description="Kolmogorov-Smirnov test p-value for similarity.")
    drift_detected: bool = Field(..., description="True if PSI >= 0.25 or KS p-value <= 0.05.")


class PredictionDriftLog(BaseModel):
    """
    Telemetry payload for logging model inference performance and tracking decay.
    """
    model_name: str
    model_version: str
    logged_at: str
    total_inferences: int
    mean_prediction_score: float = Field(..., description="Average prediction score to detect target distribution shifts.")
    drift_metrics: list[FeatureDriftMetric] = Field(default_factory=list, description="Drift statistics for key engineered features.")
    accuracy_degradation_detected: bool = Field(False, description="True if validation performance has degraded compared to baseline.")
