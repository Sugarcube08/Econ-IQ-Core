import enum
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

class PredictionType(str, enum.Enum):
    CHURN = "CHURN"
    DELINQUENCY = "DELINQUENCY"
    DISTRESS = "DISTRESS"
    RECOVERY = "RECOVERY"
    STATE_TRANSITION = "STATE_TRANSITION"

class PredictionStatus(str, enum.Enum):
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
    resolved_at: Optional[datetime] = None
    actual_label: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
