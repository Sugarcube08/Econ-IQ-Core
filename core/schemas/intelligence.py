from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisContext(BaseModel):
    window_days: int = Field(default=365, description="Analysis window in days")
    start_date: date | None = None
    end_date: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def window_str(self) -> str:
        return f"{self.window_days}d"


class ContextValidator:
    MIN_WINDOW_DAYS = 30
    MAX_WINDOW_DAYS = 720
    RECOMMENDED_MIN_FOR_TRAJECTORY = 60
    MIN_RECENT_WINDOW = 14

    @classmethod
    def validate_context(cls, context: AnalysisContext) -> AnalysisContext:
        if context.window_days < cls.MIN_WINDOW_DAYS:
            context.window_days = cls.MIN_WINDOW_DAYS
        elif context.window_days > cls.MAX_WINDOW_DAYS:
            context.window_days = cls.MAX_WINDOW_DAYS
        return context


class BehavioralMemorySchema(BaseModel):
    historically_stable: bool
    prior_recoveries: int
    seasonal_pattern: bool


class IntelligenceObjectSchema(BaseModel):
    customer_id: str
    current_state: str
    previous_state: str | None
    transition: str | None
    trajectory: str
    trust_score: float
    stress_score: float
    confidence: float
    purchase_behavior_score: float
    payment_behavior_score: float
    rg_rate_score: float
    behavioral_confidence: float
    analysis_window: int
    commercial_grade: str | None
    primary_drivers: list[str]
    negative_drivers: list[str]
    sustainable_potential: float | None
    exposure_pressure: float | None
    overall_class: str | None
    avg_repayment_days: float | None
    primary_driver: str
    supporting_signals: list[str]
    behavioral_memory: dict[str, Any]
    generated_at: datetime


class StateHistoryEntrySchema(BaseModel):
    state: str
    timestamp: datetime
    confidence: float
    stress: float
    trust: float
    purchase_behavior_score: float | None = None
    payment_behavior_score: float | None = None
    rg_rate_score: float | None = None
    potential: float | None
    exposure: float | None
    overall_class: str | None


class TransitionEntrySchema(BaseModel):
    from_state: str | None
    to_state: str
    timestamp: datetime
    reason: str
    drivers: dict[str, Any]
