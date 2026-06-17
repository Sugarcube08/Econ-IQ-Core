from datetime import date, datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from core.ml.shared.enums import CustomerState, RiskDirection, TrustDirection, CustomerArchetype, SnapshotSource

class FeatureSnapshotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    customer_id: str
    snapshot_date: date
    snapshot_source: SnapshotSource
    snapshot_version: str
    generator_version: str
    feature_hash: str

    health_score: Optional[float] = None
    risk_score: Optional[float] = None
    trust_score: Optional[float] = None
    growth_score: Optional[float] = None
    collection_score: Optional[float] = None
    relationship_score: Optional[float] = None
    credit_score: Optional[float] = None
    opportunity_score: Optional[float] = None

    current_state: Optional[CustomerState] = None
    customer_archetype: Optional[CustomerArchetype] = None
    risk_direction: Optional[RiskDirection] = None
    trust_direction: Optional[TrustDirection] = None

    billing_30d: Optional[float] = None
    billing_90d: Optional[float] = None
    billing_180d: Optional[float] = None
    payments_30d: Optional[float] = None
    payments_90d: Optional[float] = None
    payments_180d: Optional[float] = None
    returns_30d: Optional[float] = None
    returns_90d: Optional[float] = None

    purchase_gap: Optional[int] = None
    purchase_frequency: Optional[float] = None
    payment_delay_avg: Optional[float] = None
    payment_delay_trend: Optional[float] = None
    collection_efficiency: Optional[float] = None

    outstanding_current: Optional[float] = None
    outstanding_ratio: Optional[float] = None
    credit_utilization: Optional[float] = None

    feature_payload_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
