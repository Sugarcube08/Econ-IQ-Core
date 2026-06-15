from datetime import date

from pydantic import BaseModel, Field


class CollectionActivityCreate(BaseModel):
    customer_id: str = Field(..., description="Unique customer ID")
    activity_type: str = Field(..., description="Type: CALL, EMAIL, LETTER, OTHER")
    notes: str = Field(..., description="Collector interaction notes")
    outcome: str = Field(..., description="Outcome: CONTACTED, LEFT_VM, NO_ANSWER, EMAIL_SENT")


class PaymentCommitmentCreate(BaseModel):
    customer_id: str = Field(..., description="Unique customer ID")
    amount: float = Field(..., description="Promised payment amount")
    promised_date: date = Field(..., description="Expected date of payment")


class DecisionActionCreate(BaseModel):
    customer_id: str = Field(..., description="Unique customer ID")
    recommendation_id: str | None = Field(None, description="Optional associated recommendation ID")
    action_taken: str = Field(..., description="Action: APPROVED, REJECTED, OVERRIDDEN")
    reason: str = Field(..., description="Explanation/Rationale for action taken")
