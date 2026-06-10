from datetime import date
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class RecommendationType(StrEnum):
    CREDIT_LIMIT = "CREDIT_LIMIT"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    RETENTION_STRATEGY = "RETENTION_STRATEGY"
    COLLECTION_STRATEGY = "COLLECTION_STRATEGY"


class ActionRecommendation(BaseModel):
    recommendation_type: RecommendationType
    action: str = Field(..., description="Proposed action description")
    value: Any = Field(None, description="Quantitative value associated with recommendation (e.g., credit limit amount)")
    rationale: str = Field(..., description="Explanatory rationale for the recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")


class CustomerRecommendations(BaseModel):
    customer_id: str
    generated_date: date
    recommendations: list[ActionRecommendation] = Field(default_factory=list)
