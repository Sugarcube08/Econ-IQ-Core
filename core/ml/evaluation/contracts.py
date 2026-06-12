from pydantic import BaseModel, Field


class EvaluationMetrics(BaseModel):
    """
    Standard performance metrics contract for certified model version verification.
    """
    roc_auc: float = Field(..., ge=0.0, le=1.0, description="Area under the ROC curve.")
    pr_auc: float = Field(..., ge=0.0, le=1.0, description="Area under Precision-Recall curve.")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Overall categorization accuracy.")
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1_score: float = Field(..., ge=0.0, le=1.0)
    log_loss: float = Field(..., ge=0.0, description="Cross-entropy categorical log loss.")


class ModelCertificationContract(BaseModel):
    """
    Contract for certifying an ML model version for production deployment.
    """
    model_name: str
    model_version: str
    evaluated_at: str
    test_dataset_size: int
    metrics: EvaluationMetrics
    is_certified: bool = Field(..., description="True if model matches quality gating thresholds (e.g., ROC-AUC >= 0.80).")
    gating_errors: list[str] = Field(default_factory=list, description="List of threshold violations if certification failed.")
