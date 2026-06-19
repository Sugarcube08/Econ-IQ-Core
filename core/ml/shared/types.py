from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.ml.shared.enums import CustomerArchetype, CustomerState, RiskDirection, SnapshotSource, TrustDirection


class FeatureSnapshotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    customer_id: str
    snapshot_date: date
    snapshot_source: SnapshotSource
    snapshot_version: str
    generator_version: str
    feature_hash: str

    health_score: float | None = None
    risk_score: float | None = None
    trust_score: float | None = None
    growth_score: float | None = None
    collection_score: float | None = None
    relationship_score: float | None = None
    credit_score: float | None = None
    opportunity_score: float | None = None

    current_state: CustomerState | None = None
    customer_archetype: CustomerArchetype | None = None
    risk_direction: RiskDirection | None = None
    trust_direction: TrustDirection | None = None

    billing_30d: float | None = None
    billing_90d: float | None = None
    billing_180d: float | None = None
    payments_30d: float | None = None
    payments_90d: float | None = None
    payments_180d: float | None = None
    returns_30d: float | None = None
    returns_90d: float | None = None

    purchase_gap: int | None = None
    purchase_frequency: float | None = None
    payment_delay_avg: float | None = None
    payment_delay_trend: float | None = None
    collection_efficiency: float | None = None

    outstanding_current: float | None = None
    outstanding_ratio: float | None = None
    credit_utilization: float | None = None

    feature_payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
