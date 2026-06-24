import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.postgres import Base


class BatchStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    status: Mapped[BatchStatus] = mapped_column(SQLEnum(BatchStatus), default=BatchStatus.PENDING)
    event_count: Mapped[int] = mapped_column(default=0)
    checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class EventLedger(Base):
    __tablename__ = "event_ledger"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)  # SALE, PAYMENT, RETURN
    event_date: Mapped[date] = mapped_column(Date, index=True, primary_key=True)
    amount: Mapped[float] = mapped_column(Float)

    source_raw_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_table: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    global_sequence_number: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    customer_sequence_number: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    event_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ok: Mapped[int] = mapped_column(Integer, default=0, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        # Composite index for lightning-fast customer history retrieval
        Index("idx_ledger_customer_date", "customer_id", "event_date"),
    )


class CustomerIntelligence(Base):
    __tablename__ = "customer_intelligence"

    # Identity
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)

    # Current Window Fields (8 Canonical Scores)
    health_score: Mapped[float | None] = mapped_column(Float)
    risk_score: Mapped[float | None] = mapped_column(Float, index=True)
    growth_score: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float | None] = mapped_column(Float)
    opportunity_score: Mapped[float | None] = mapped_column(Float)
    credit_score: Mapped[float | None] = mapped_column(Float)
    collection_score: Mapped[float | None] = mapped_column(Float)
    relationship_score: Mapped[float | None] = mapped_column(Float)
    
    contribution_current: Mapped[float | None] = mapped_column(Float)
    outstanding_current: Mapped[float | None] = mapped_column(Float)
    state: Mapped[str | None] = mapped_column(String, index=True)
    current_state: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_archetype: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_direction: Mapped[str | None] = mapped_column(String, nullable=True)
    trust_direction: Mapped[str | None] = mapped_column(String, nullable=True)

    # 2. Recovery / Received Metrics
    recovered_current_30d: Mapped[float | None] = mapped_column(Float, default=0.0) # Actual payments cleared in last 30d
    recovered_total_ytd: Mapped[float | None] = mapped_column(Float, default=0.0)    # YTD collections recovery volume
    
    # 3. Priority Scoring Model
    collection_priority_score: Mapped[float | None] = mapped_column(Float, default=0.0) # Calculated CPI score (0-100)
    priority_level: Mapped[str | None] = mapped_column(String, default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    primary_dunning_reason: Mapped[str | None] = mapped_column(String, nullable=True) # e.g., "Broken Promise", "90+ DPD"

    # Previous Window Fields (8 Canonical Scores)
    health_previous: Mapped[float | None] = mapped_column(Float)
    risk_previous: Mapped[float | None] = mapped_column(Float)
    growth_previous: Mapped[float | None] = mapped_column(Float)
    trust_previous: Mapped[float | None] = mapped_column(Float)
    opportunity_previous: Mapped[float | None] = mapped_column(Float)
    credit_previous: Mapped[float | None] = mapped_column(Float)
    collection_previous: Mapped[float | None] = mapped_column(Float)
    relationship_previous: Mapped[float | None] = mapped_column(Float)
    
    contribution_previous: Mapped[float | None] = mapped_column(Float)
    outstanding_previous: Mapped[float | None] = mapped_column(Float)

    # Operational Tracking
    last_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True
    )

    async def get_score_breakdown(self, score_type: str, session=None) -> dict:
        import asyncio
        from sqlalchemy.orm import object_session
        from sqlalchemy import text
        import json
        
        session = session or object_session(self)
        profile = None
        
        if session is not None:
            stmt = text("SELECT behavioral_profile FROM customers WHERE id = :cid")
            try:
                from sqlalchemy.ext.asyncio import AsyncSession
                if isinstance(session, AsyncSession):
                    res = await session.execute(stmt, {"cid": self.customer_id})
                    row = res.fetchone()
                else:
                    res = session.execute(stmt, {"cid": self.customer_id})
                    row = res.fetchone()
                if row and row[0]:
                    profile = row[0]
                    if isinstance(profile, str):
                        profile = json.loads(profile)
            except Exception:
                pass
                
        v2_scores = profile.get("v2_scores", {}) if profile else {}
        dims = v2_scores.get("dimensions", {}) if v2_scores else {}
        
        activity = dims.get("activity", 0.5)
        discipline = dims.get("discipline", 0.5)
        credit = dims.get("credit", 0.5)
        relationship = dims.get("relationship", 0.5)
        product = dims.get("product", 0.5)
        friction = dims.get("friction", 1.0)
        growth = dims.get("growth", 0.5)
        stability = dims.get("stability", 0.5)
        
        score_val = 0.0
        contributors = []
        
        s_type = score_type.lower().replace("_score", "")
        
        if s_type == "health":
            score_val = self.health_score or 0.0
            contributors = [
                {"factor": "Commercial Activity", "impact": round(activity * 0.40, 2)},
                {"factor": "Operational Friction", "impact": round(friction * 0.35, 2)},
                {"factor": "Stability & Maturity", "impact": round(stability * 0.25, 2)}
            ]
        elif s_type == "risk":
            score_val = self.risk_score or 0.0
            contributors = [
                {"factor": "Credit Default Risk", "impact": round((1.0 - credit) * 0.40, 2)},
                {"factor": "Payment Discipline Risk", "impact": round((1.0 - discipline) * 0.40, 2)},
                {"factor": "Stability Risk", "impact": round((1.0 - stability) * 0.20, 2)}
            ]
        elif s_type == "growth":
            score_val = self.growth_score or 0.0
            contributors = [
                {"factor": "Growth Dynamics", "impact": round(growth * 0.50, 2)},
                {"factor": "Product Diversity", "impact": round(product * 0.30, 2)},
                {"factor": "Commercial Activity", "impact": round(activity * 0.20, 2)}
            ]
        elif s_type == "trust":
            score_val = self.trust_score or 0.0
            contributors = [
                {"factor": "Payment Discipline", "impact": round(discipline * 0.50, 2)},
                {"factor": "Relationship Quality", "impact": round(relationship * 0.30, 2)},
                {"factor": "Stability & Maturity", "impact": round(stability * 0.20, 2)}
            ]
        elif s_type == "opportunity":
            score_val = self.opportunity_score or 0.0
            contributors = [
                {"factor": "Catalog Expansion Potential", "impact": round((1.0 - product) * 0.50, 2)},
                {"factor": "Growth Dynamics", "impact": round(growth * 0.30, 2)},
                {"factor": "Relationship Quality", "impact": round(relationship * 0.20, 2)}
            ]
        elif s_type == "credit":
            score_val = self.credit_score or 0.0
            t_score = self.trust_score or (discipline * 0.50 + relationship * 0.30 + stability * 0.20)
            r_score = self.risk_score or ((1.0 - credit) * 0.40 + (1.0 - discipline) * 0.40 + (1.0 - stability) * 0.20)
            contributors = [
                {"factor": "Terms Compliance Reliability", "impact": round(t_score * 0.40, 2)},
                {"factor": "Operational Default Safety", "impact": round((1.0 - r_score) * 0.40, 2)},
                {"factor": "Commercial Activity", "impact": round(activity * 0.20, 2)}
            ]
        elif s_type == "collection":
            score_val = self.collection_score or 0.0
            r_score = self.risk_score or ((1.0 - credit) * 0.40 + (1.0 - discipline) * 0.40 + (1.0 - stability) * 0.20)
            contributors = [
                {"factor": "Payment Indiscipline", "impact": round((1.0 - discipline) * 0.50, 2)},
                {"factor": "Operational Default Risk", "impact": round(r_score * 0.30, 2)},
                {"factor": "Commercial Activity", "impact": round(activity * 0.20, 2)}
            ]
        elif s_type == "relationship":
            score_val = self.relationship_score or 0.0
            contributors = [
                {"factor": "Relationship Quality", "impact": round(relationship * 0.40, 2)},
                {"factor": "Stability & Maturity", "impact": round(stability * 0.40, 2)},
                {"factor": "Commercial Activity", "impact": round(activity * 0.20, 2)}
            ]
            
        return {
            "score": round(score_val, 2),
            "contributors": contributors
        }


class ProcessingAuditLog(Base):
    __tablename__ = "processing_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)  # INGESTION, RECOMPUTATION
    status: Mapped[str] = mapped_column(String)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    error_details: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class SyncState(Base):
    __tablename__ = "sync_state"

    table_name: Mapped[str] = mapped_column(String, primary_key=True)
    last_pk: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_reconcile_pk: Mapped[str | None] = mapped_column(String, nullable=True)


class SyncLock(Base):
    __tablename__ = "sync_locks"

    lock_name: Mapped[str] = mapped_column(String, primary_key=True)
    locked_by: Mapped[str] = mapped_column(String)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SyncBatch(Base):
    __tablename__ = "sync_batches"

    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    customers_affected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[BatchStatus] = mapped_column(SQLEnum(BatchStatus), default=BatchStatus.PENDING)
    worker_id: Mapped[str] = mapped_column(String)
    error_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    alert_type: Mapped[str] = mapped_column(String, index=True)
    alert_severity: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String, nullable=True)


class CollectionActivity(Base):
    __tablename__ = "collections_activity"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    activity_type: Mapped[str] = mapped_column(String, index=True)
    notes: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class PaymentCommitment(Base):
    __tablename__ = "payment_commitments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    promised_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String, default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    recommendation_type: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class DecisionAudit(Base):
    __tablename__ = "decision_audit"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    action_taken: Mapped[str] = mapped_column(String, index=True)
    performed_by: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    __table_args__ = (
        UniqueConstraint("customer_id", "snapshot_date", name="uq_customer_snapshot_date"),
    )

    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    snapshot_source: Mapped[str] = mapped_column(String, index=True)
    snapshot_version: Mapped[str] = mapped_column(String)
    generator_version: Mapped[str] = mapped_column(String)
    feature_hash: Mapped[str] = mapped_column(String, index=True)

    # 8 Canonical Scores
    health_score: Mapped[float | None] = mapped_column(Float)
    risk_score: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float | None] = mapped_column(Float)
    growth_score: Mapped[float | None] = mapped_column(Float)
    collection_score: Mapped[float | None] = mapped_column(Float)
    relationship_score: Mapped[float | None] = mapped_column(Float)
    credit_score: Mapped[float | None] = mapped_column(Float)
    opportunity_score: Mapped[float | None] = mapped_column(Float)

    # Categorical/Directions
    current_state: Mapped[str | None] = mapped_column(String)
    customer_archetype: Mapped[str | None] = mapped_column(String)
    risk_direction: Mapped[str | None] = mapped_column(String)
    trust_direction: Mapped[str | None] = mapped_column(String)

    # Billing & Payments History (Rolling Windows)
    billing_30d: Mapped[float | None] = mapped_column(Float)
    billing_90d: Mapped[float | None] = mapped_column(Float)
    billing_180d: Mapped[float | None] = mapped_column(Float)
    payments_30d: Mapped[float | None] = mapped_column(Float)
    payments_90d: Mapped[float | None] = mapped_column(Float)
    payments_180d: Mapped[float | None] = mapped_column(Float)
    returns_30d: Mapped[float | None] = mapped_column(Float)
    returns_90d: Mapped[float | None] = mapped_column(Float)

    # Operational Metrics
    purchase_gap: Mapped[int | None] = mapped_column(Integer)
    purchase_frequency: Mapped[float | None] = mapped_column(Float)
    payment_delay_avg: Mapped[float | None] = mapped_column(Float)
    payment_delay_trend: Mapped[float | None] = mapped_column(Float)
    collection_efficiency: Mapped[float | None] = mapped_column(Float)

    # Exposure & Utilization
    outstanding_current: Mapped[float | None] = mapped_column(Float)
    outstanding_ratio: Mapped[float | None] = mapped_column(Float)
    credit_utilization: Mapped[float | None] = mapped_column(Float)

    # Payload & Timestamps
    feature_payload_json: Mapped[dict[str, Any]] = mapped_column("feature_payload_json", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


from sqlalchemy import event

@event.listens_for(FeatureSnapshot, "before_update")
def prevent_update(mapper, connection, target):
    raise RuntimeError("Feature snapshots are immutable and cannot be updated.")

@event.listens_for(FeatureSnapshot, "before_delete")
def prevent_delete(mapper, connection, target):
    raise RuntimeError("Feature snapshots are immutable and cannot be deleted.")


class CustomerPrediction(Base):
    __tablename__ = "customer_predictions"

    prediction_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    snapshot_id: Mapped[str] = mapped_column(String, index=True)
    model_id: Mapped[str] = mapped_column(String, index=True)
    prediction_type: Mapped[str] = mapped_column(String, index=True)
    prediction_value: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    prediction_horizon_days: Mapped[int] = mapped_column(Integer)
    prediction_status: Mapped[str] = mapped_column(String, index=True)  # PENDING, RESOLVED, FAILED
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_label: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata_json", JSON, default=dict)


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    outcome_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(String, index=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    prediction_type: Mapped[str] = mapped_column(String, index=True)
    predicted_value: Mapped[float] = mapped_column(Float)
    actual_value: Mapped[float] = mapped_column(Float)
    prediction_date: Mapped[date] = mapped_column(Date, index=True)
    evaluation_date: Mapped[date] = mapped_column(Date, index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    absolute_error: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata_json", JSON, default=dict)


class PredictionFeedback(Base):
    __tablename__ = "prediction_feedback"

    feedback_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String, index=True)
    prediction_type: Mapped[str] = mapped_column(String, index=True)
    samples: Mapped[int] = mapped_column(Integer)
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    roc_auc: Mapped[float] = mapped_column(Float)
    brier_score: Mapped[float] = mapped_column(Float)
    ece: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CustomerStateHistory(Base):
    __tablename__ = "customer_state_history"

    history_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    state: Mapped[str] = mapped_column(String)
    risk_score: Mapped[float | None] = mapped_column(Float)
    health_score: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float | None] = mapped_column(Float)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String, default="1.0.0")
    status: Mapped[str] = mapped_column(String, index=True)  # ACTIVE, BASELINE, EXPERIMENTAL, DEPRECATED
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    dataset_rows: Mapped[int] = mapped_column(Integer, default=0)
    positives: Mapped[int] = mapped_column(Integer, default=0)
    negatives: Mapped[int] = mapped_column(Integer, default=0)
    auc: Mapped[float] = mapped_column(Float, default=0.0)
    f1: Mapped[float] = mapped_column(Float, default=0.0)
    precision: Mapped[float] = mapped_column(Float, default=0.0)
    recall: Mapped[float] = mapped_column(Float, default=0.0)
    pr_auc: Mapped[float] = mapped_column(Float, default=0.0)
    brier: Mapped[float] = mapped_column(Float, default=0.0)
    prediction_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


class CustomerGraphMV(Base):
    __tablename__ = "customer_graph_mv"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[str] = mapped_column(String, index=True)
    granularity: Mapped[str] = mapped_column(String, index=True)
    
    purchase_volume: Mapped[float] = mapped_column(Float, default=0.0)
    payment_volume: Mapped[float] = mapped_column(Float, default=0.0)
    outstanding: Mapped[float] = mapped_column(Float, default=0.0)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    growth_score: Mapped[float] = mapped_column(Float, default=0.0)
    collection_score: Mapped[float] = mapped_column(Float, default=0.0)
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    returns_amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class PortfolioGraphMV(Base):
    __tablename__ = "portfolio_graph_mv"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[str] = mapped_column(String, index=True)
    granularity: Mapped[str] = mapped_column(String, index=True)

    portfolio_purchase: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_payment: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_outstanding: Mapped[float] = mapped_column(Float, default=0.0)
    critical_alerts: Mapped[int] = mapped_column(Integer, default=0)
    collection_backlog: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


# Import policy models to register with Base metadata for Alembic migrations
from core.ml.policies.policy_models import MLPolicyProfile, PolicyVersion, PolicyThreshold  # noqa: F401




