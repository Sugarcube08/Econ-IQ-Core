
from pydantic import BaseModel, Field


class TrainingHyperparameters(BaseModel):
    """
    Standard hyperparameter configuration contract for XGBoost / LightGBM.
    """
    learning_rate: float = Field(0.05, ge=0.001, le=0.5, description="Model training step step size shrinkage.")
    max_depth: int = Field(6, ge=2, le=15, description="Maximum tree depth structure constraint.")
    n_estimators: int = Field(150, ge=10, le=1000, description="Number of boosting iterations.")
    subsample: float = Field(0.8, ge=0.5, le=1.0, description="Subsample ratio of the training instances.")
    colsample_bytree: float = Field(0.8, ge=0.5, le=1.0, description="Subsample ratio of columns when constructing trees.")
    reg_alpha: float = Field(0.1, ge=0.0, description="L1 regularization term on weights.")
    reg_lambda: float = Field(1.0, ge=0.0, description="L2 regularization term on weights.")


class ModelTrainingMetadata(BaseModel):
    """
    Schema for logging training run telemetry and outputs.
    """
    run_id: str = Field(..., description="Unique training run trace uuid.")
    model_name: str = Field(..., description="Target model segment (RISK, CHURN, etc.).")
    model_version: str = Field(..., description="Target registered version (e.g. 2.0.0).")
    training_date: str = Field(..., description="Timestamp ISO string of run execution.")
    dataset_row_count: int = Field(..., description="Total rows in the training split.")
    hyperparameters: TrainingHyperparameters
    metrics_snapshot: dict[str, float] = Field(..., description="Snapshot of training/validation scores.")
    model_binary_path: str = Field(..., description="Target persistent file system location of the compiled model.")
