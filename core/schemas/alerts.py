from datetime import datetime

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    customer_id: str = Field(..., description="Unique customer ID")
    alert_type: str = Field(..., description="Type of alert (RISK_SPIKE, TRUST_DROP, etc.)")
    alert_severity: str = Field(..., description="Severity (CRITICAL, WARNING, INFO)")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    workspace_id: str | None = Field(None, description="Optional workspace ID")


class AlertResponse(BaseModel):
    id: str
    workspace_id: str | None
    customer_id: str
    alert_type: str
    alert_severity: str
    title: str
    description: str
    status: str
    created_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    class Config:
        from_attributes = True


class AlertCountResponse(BaseModel):
    active: int
    critical: int
    warning: int
