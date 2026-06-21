import uuid
from datetime import UTC, date, datetime, timedelta

import polars as pl
from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.settlement.engine import SettlementMatchingEngine
from core.ml.outcomes.outcome_repository import OutcomeRepository, PredictionOutcomeDTO
from core.ml.predictions.prediction_repository import PredictionRepository
from core.ml.predictions.prediction_types import PredictionType
from core.models.state_models import (
    CustomerIntelligence,
    EventLedger,
    PaymentCommitment,
)
from core.schemas.intelligence import AnalysisContext


async def get_customer_state_at(customer_id: str, target_date: date, session: AsyncSession) -> str:
    """Retrieves the state of a customer from CustomerStateHistory as of target_date, falling back to CustomerIntelligence."""
    from core.models.state_models import CustomerStateHistory
    
    stmt = (
        select(CustomerStateHistory.state)
        .where(
            and_(
                CustomerStateHistory.customer_id == customer_id,
                CustomerStateHistory.snapshot_date <= target_date
            )
        )
        .order_by(CustomerStateHistory.snapshot_date.desc(), CustomerStateHistory.created_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    state = res.scalar()
    if state is not None:
        return state
        
    # Fallback if no history is recorded yet for target_date
    stmt_ci = select(CustomerIntelligence.current_state).where(CustomerIntelligence.customer_id == customer_id)
    res_ci = await session.execute(stmt_ci)
    ci_state = res_ci.scalar()
    return ci_state or "healthy"

async def resolve_churn(customer_id: str, prediction_date: date, evaluation_date: date, session: AsyncSession) -> float:
    """Churn: 1.0 if no SALE events occurred in the tracking window after prediction date, else 0.0."""
    stmt = select(func.count(EventLedger.event_id)).where(
        and_(
            EventLedger.customer_id == customer_id,
            EventLedger.event_type == 'SALE',
            EventLedger.event_date > prediction_date,
            EventLedger.event_date <= evaluation_date,
            EventLedger.is_voided.is_(False)
        )
    )
    res = await session.execute(stmt)
    sale_count = res.scalar() or 0
    return 1.0 if sale_count == 0 else 0.0

async def resolve_delinquency(customer_id: str, prediction_date: date, evaluation_date: date, session: AsyncSession, thresholds: dict) -> float:
    """Delinquency: 1.0 if average delay > delinquency_threshold_days or any broken commitment occurred, else 0.0."""
    delinquency_days = thresholds.get("DELINQUENCY_WINDOW_DAYS", 45)
    
    # 1. Check broken commitments
    stmt_commit = select(func.count(PaymentCommitment.id)).where(
        and_(
            PaymentCommitment.customer_id == customer_id,
            PaymentCommitment.status == 'BROKEN',
            PaymentCommitment.promised_date > prediction_date,
            PaymentCommitment.promised_date <= evaluation_date
        )
    )
    res_commit = await session.execute(stmt_commit)
    broken_count = res_commit.scalar() or 0
    if broken_count > 0:
        return 1.0

    # 2. Check average delay in the window using SettlementMatchingEngine
    stmt_events = select(EventLedger).where(
        and_(
            EventLedger.customer_id == customer_id,
            EventLedger.event_date <= evaluation_date,
            EventLedger.is_voided.is_(False)
        )
    ).order_by(EventLedger.event_date.asc(), EventLedger.global_sequence_number.asc())
    res_events = await session.execute(stmt_events)
    events = res_events.scalars().all()

    event_list = []
    for e in events:
        event_list.append({
            "customer_id": e.customer_id,
            "event_uid": e.event_id,
            "event_type": e.event_type,
            "event_date": datetime.combine(e.event_date, datetime.min.time()),
            "amount": e.amount,
            "sequence_number": e.customer_sequence_number or 0,
            "is_ok": e.is_ok or 0
        })

    if event_list:
        ledger_df = pl.DataFrame(event_list)
        engine = SettlementMatchingEngine()
        context = AnalysisContext(end_date=evaluation_date, start_date=prediction_date, window_days=(evaluation_date - prediction_date).days)
        settlement_df = engine.compute_settlements(ledger_df, context)
        if not settlement_df.is_empty():
            avg_delay = float(settlement_df["avg_repayment_days"][0])
            if avg_delay > delinquency_days:
                return 1.0

    return 0.0

async def resolve_distress(customer_id: str, prediction_date: date, evaluation_date: date, session: AsyncSession) -> float:
    """Distress: 1.0 if state is distressed at evaluation date, else 0.0."""
    state = await get_customer_state_at(customer_id, evaluation_date, session)
    return 1.0 if state == "distressed" else 0.0

async def resolve_recovery(customer_id: str, prediction_date: date, evaluation_date: date, session: AsyncSession) -> float:
    """Recovery: 1.0 if customer state at evaluation date transitioned to recovering, else 0.0."""
    state = await get_customer_state_at(customer_id, evaluation_date, session)
    return 1.0 if state == "recovering" else 0.0

async def resolve_transition(customer_id: str, prediction_date: date, evaluation_date: date, session: AsyncSession, baseline_state: str) -> float:
    """Transition: 1.0 if state at evaluation date differs from baseline state, else 0.0."""
    state = await get_customer_state_at(customer_id, evaluation_date, session)
    return 1.0 if state != baseline_state else 0.0


async def evaluate_pending_predictions(session: AsyncSession) -> list[PredictionOutcomeDTO]:
    """
    Scans for PENDING predictions whose horizon has passed, resolves the actual outcomes,
    persists them to the database, and marks the predictions as RESOLVED.
    """
    pred_repo = PredictionRepository(session)
    out_repo = OutcomeRepository(session)
    pending = await pred_repo.get_pending_predictions()

    resolved_outcomes = []
    now_dt = datetime.now(UTC)
    current_date = now_dt.date()

    # Load policy thresholds
    from core.ml.policies.policy_service import PolicyService
    policy_svc = PolicyService(session)
    thresholds = await policy_svc.get_active_thresholds()

    for pred in pending:
        # Check if the evaluation date has arrived
        evaluation_date = pred.generated_at.date() + timedelta(days=pred.prediction_horizon_days)
        if evaluation_date > current_date:
            continue

        try:
            # Determine baseline state for transition checking
            baseline_state = pred.metadata_json.get("features", {}).get("current_state", "healthy")

            # Resolve actual value
            actual_value = 0.0
            p_type = pred.prediction_type
            
            if p_type == PredictionType.CHURN.value:
                actual_value = await resolve_churn(pred.customer_id, pred.generated_at.date(), evaluation_date, session)
            elif p_type == PredictionType.DELINQUENCY.value:
                actual_value = await resolve_delinquency(pred.customer_id, pred.generated_at.date(), evaluation_date, session, thresholds)
            elif p_type == PredictionType.DISTRESS.value:
                actual_value = await resolve_distress(pred.customer_id, pred.generated_at.date(), evaluation_date, session)
            elif p_type == PredictionType.RECOVERY.value:
                actual_value = await resolve_recovery(pred.customer_id, pred.generated_at.date(), evaluation_date, session)
            elif p_type == PredictionType.STATE_TRANSITION.value:
                actual_value = await resolve_transition(pred.customer_id, pred.generated_at.date(), evaluation_date, session, baseline_state)

            # Evaluate binary classification correctness
            predicted_class = 1.0 if pred.prediction_value > 0.5 else 0.0
            actual_class = 1.0 if actual_value > 0.5 else 0.0
            is_correct = (predicted_class == actual_class)
            absolute_error = abs(pred.prediction_value - actual_value)
            actual_label = "TRUE" if actual_class == 1.0 else "FALSE"

            if p_type == PredictionType.STATE_TRANSITION.value:
                # Actual state name at evaluation date
                actual_label = await get_customer_state_at(pred.customer_id, evaluation_date, session)
                is_correct = (actual_label != baseline_state) if predicted_class == 1.0 else (actual_label == baseline_state)

            # Create outcome DTO
            outcome_dto = PredictionOutcomeDTO(
                outcome_id=str(uuid.uuid4()),
                prediction_id=pred.prediction_id,
                customer_id=pred.customer_id,
                prediction_type=p_type,
                predicted_value=pred.prediction_value,
                actual_value=actual_value,
                prediction_date=pred.generated_at.date(),
                evaluation_date=evaluation_date,
                lead_time_days=pred.prediction_horizon_days,
                is_correct=is_correct,
                absolute_error=absolute_error,
                metadata_json={"resolved_at": now_dt.isoformat()}
            )

            # Persist outcome
            await out_repo.insert_outcome(outcome_dto)

            # Mark prediction resolved
            await pred_repo.mark_prediction_resolved(pred.prediction_id, actual_label, now_dt)
            resolved_outcomes.append(outcome_dto)

        except Exception as e:
            logger.error(f"ML | Failed to resolve prediction {pred.prediction_id}: {e}")

    return resolved_outcomes
