import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictionType(enum.StrEnum):
    CHURN = "CHURN"
    DELINQUENCY = "DELINQUENCY"
    DISTRESS = "DISTRESS"
    RECOVERY = "RECOVERY"
    STATE_TRANSITION = "STATE_TRANSITION"

class PredictionStatus(enum.StrEnum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"

class CustomerPredictionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prediction_id: str
    customer_id: str
    snapshot_id: str
    model_id: str
    prediction_type: PredictionType
    prediction_value: float
    confidence: float
    generated_at: datetime
    prediction_horizon_days: int
    prediction_status: PredictionStatus
    resolved_at: datetime | None = None
    actual_label: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    prediction_source: str | None = "HEURISTIC"

    @model_validator(mode="before")
    @classmethod
    def populate_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "prediction_source" not in data:
                meta = data.get("metadata_json") or {}
                data["prediction_source"] = meta.get("prediction_source", "HEURISTIC")
        else:
            meta = getattr(data, "metadata_json", None) or {}
            source_val = meta.get("prediction_source", "HEURISTIC")
            data.prediction_source = source_val
        return data
