from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BaseEventSchema(BaseModel):
    """
    The canonical schema that all ingested events MUST map to before entering the ledger.
    """

    event_uid: str = Field(..., description="Unique identifier for the event")
    customer_id: str = Field(..., description="Identifier for the customer")
    event_type: str = Field(..., description="SALE, PAYMENT, RETURN, etc.")
    event_date: datetime = Field(..., description="Timestamp of the event")
    amount: float = Field(..., description="Monetary value of the event")

    # Provenance
    source: str = Field(..., description="Source system or file name")
    source_row_id: str = Field(..., description="Row index or original ID from the source")

    # Business Semantics
    is_ok: int = Field(default=0, description="0 for financially valid, 1 for behavioral only")
    rg_responsibility: str | None = Field(None, description="CUSTOMER, GENUINE, or None. Critical for returns.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Flexible payload for additional context")
