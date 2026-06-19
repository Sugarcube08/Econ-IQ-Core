from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelMetadataDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_name: str
    version: str
    status: str
    trained_at: datetime
    dataset_rows: int
    positives: int
    negatives: int
    auc: float
    f1: float
    precision: float
    recall: float
    pr_auc: float
    brier: float
    prediction_count: int
    feedback_count: int
    notes: str | None = None
