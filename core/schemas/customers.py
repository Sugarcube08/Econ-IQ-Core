from typing import Any

from pydantic import BaseModel


class CustomerDatatableDeltas(BaseModel):
    trust_score: float | None = 0.0
    purchase_behavior_score: float | None = 0.0
    payment_behavior_score: float | None = 0.0
    rg_behavior_score: float | None = 0.0
    contribution_score: float | None = 0.0
    outstanding_delta: float | None = 0.0


class CustomerDatatableRow(BaseModel):
    customer_id: str
    customer_name: str | None = None
    city: str | None = None
    
    # Standard Fields
    trust_score: float | None = 0.0
    purchase_score: float | None = 0.0
    payment_score: float | None = 0.0
    rg_score: float | None = 0.0
    state: str | None = None
    overall_grade: str | None = None
    outstanding_current: float | None = 0.0
    outstanding_previous: float | None = 0.0
    contribution_current: float | None = 0.0
    contribution_previous: float | None = 0.0
    last_purchase_date: str | None = None
    
    # Legacy Fields (Backward Compatibility)
    purchase_behavior_score: float | None = 0.0
    payment_behavior_score: float | None = 0.0
    rg_behavior_score: float | None = 0.0
    current_state: str | None = None
    contribution_score_current: float | None = 0.0
    last_purchased_at: str | None = None
    
    deltas: CustomerDatatableDeltas


class PaginationMetadata(BaseModel):
    page: int
    limit: int
    total_records: int
    total_pages: int
    has_next: bool
    has_previous: bool


class SortingMetadata(BaseModel):
    sort_by: str
    sort_order: str


class DatatableMetadata(BaseModel):
    pagination: PaginationMetadata
    sorting: SortingMetadata
    filters: dict[str, Any]
    search: str | None = None
    processing_time_ms: int


class CustomerDatatableResponseData(BaseModel):
    customers: list[CustomerDatatableRow]


class CustomerScoreSchema(BaseModel):
    trust_score: float | None = 0.0
    purchase_behavior_score: float | None = 0.0
    payment_behavior_score: float | None = 0.0
    rg_behavior_score: float | None = 0.0
    outstanding_current: float | None = 0.0
    outstanding_previous: float | None = 0.0


class CustomerDeltaSchema(BaseModel):
    trust_score: float | None = 0.0
    purchase_behavior_score: float | None = 0.0
    payment_behavior_score: float | None = 0.0
    rg_behavior_score: float | None = 0.0
    outstanding_delta: float | None = 0.0


class OrgContributionSchema(BaseModel):
    current_percentage: float | None = 0.0
    delta: float | None = 0.0


class CustomerDetailSchema(BaseModel):
    customer_id: str
    customer_name: str | None = None
    city: str | None = None
    scores: CustomerScoreSchema
    deltas: CustomerDeltaSchema
    behavior_state: str | None = "UNKNOWN"
    organization_contribution: OrgContributionSchema
    last_purchased_at: str | None = None
    updated_at: str | None = None


class WindowMetadataSchema(BaseModel):
    mode: str = "dynamic"
    window_days: int
    start_date: str | None = None
    end_date: str | None = None
    previous_window_days: int


class CustomerProfileResponseData(BaseModel):
    customer: CustomerDetailSchema


# --- Graph Schemas ---

class PurchaseGraphPoint(BaseModel):
    period_start: str
    period_end: str
    purchase_amount: float
    invoice_count: int


class PaymentGraphPoint(BaseModel):
    period_start: str
    period_end: str
    payment_amount: float
    payment_count: int


class RGGraphPoint(BaseModel):
    period_start: str
    period_end: str
    rg_amount: float
    raw_rg_amount: float = 0.0
    rg_count: int


class OutstandingGraphPoint(BaseModel):
    period_start: str
    period_end: str
    opening_outstanding: float
    purchase_added: float
    payment_received: float
    rg_adjustment: float
    closing_outstanding: float
    outstanding: float = 0.0


class GraphResponseData[T](BaseModel):
    graph: list[T]
