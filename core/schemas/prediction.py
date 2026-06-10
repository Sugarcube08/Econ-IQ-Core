from datetime import date
from typing import Any
from pydantic import BaseModel, Field


class BasePrediction(BaseModel):
    customer_id: str
    prediction_date: date
    score: float = Field(..., ge=0.0, le=1.0, description="Model probability or raw score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence/trust interval")
    features_snapshot: dict[str, Any] = Field(default_factory=dict, description="Input features used at the time of prediction")
    key_drivers: list[str] = Field(default_factory=list, description="Top positive or negative feature drivers (e.g., SHAP/feature importance)")


class RiskPrediction(BasePrediction):
    risk_level: str = Field(..., description="Categorized risk rating: LOW, MEDIUM, HIGH, CRITICAL")


class GrowthPrediction(BasePrediction):
    growth_potential: str = Field(..., description="Categorized growth potential: CONTRACTION, STABLE, EXPANSION, ACCELERATING")


class HealthPrediction(BasePrediction):
    health_grade: str = Field(..., description="Holistic health classification: A, B, C, D, F")


class ChurnPrediction(BasePrediction):
    is_churn_risk: bool = Field(..., description="Boolean flag representing whether churn threshold was crossed")


class CollectionPrediction(BasePrediction):
    repayment_probability: float = Field(..., ge=0.0, le=1.0, description="Estimated probability of collection in active billing cycle")
    expected_delay_days: int = Field(..., description="Estimated days past due (DPD) before settlement")
