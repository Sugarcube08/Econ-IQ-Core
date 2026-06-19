from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete

from core.ml.feedback.feedback_repository import FeedbackRepository
from core.ml.feedback.feedback_service import calculate_and_persist_feedback_metrics
from core.ml.outcomes.outcome_repository import OutcomeRepository
from core.ml.outcomes.outcome_service import evaluate_pending_predictions
from core.ml.predictions.prediction_repository import PredictionRepository
from core.ml.predictions.prediction_service import generate_predictions_for_snapshot
from core.ml.predictions.prediction_types import PredictionStatus, PredictionType
from core.ml.shared.enums import SnapshotSource
from core.models.state_models import (
    CustomerIntelligence,
    CustomerPrediction,
    EventLedger,
    FeatureSnapshot,
    PredictionFeedback,
    PredictionOutcome,
)
from core.storage.postgres import AsyncSessionLocal, get_reflected_table

TEST_CUST_ID = "22222222-2222-2222-2222-222222222222"

async def clear_ml_data():
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PredictionFeedback).where(PredictionFeedback.model_id.like("test_%")))
        await session.execute(delete(PredictionOutcome).where(PredictionOutcome.customer_id == TEST_CUST_ID))
        await session.execute(delete(CustomerPrediction).where(CustomerPrediction.customer_id == TEST_CUST_ID))
        await session.execute(delete(FeatureSnapshot).where(FeatureSnapshot.customer_id == TEST_CUST_ID))
        await session.execute(delete(CustomerIntelligence).where(CustomerIntelligence.customer_id == TEST_CUST_ID))
        await session.execute(delete(EventLedger).where(EventLedger.customer_id == TEST_CUST_ID))
        
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            await session.execute(delete(customers_tbl).where(customers_tbl.c.id == TEST_CUST_ID))
        await session.commit()

async def seed_ml_data(snapshot_date: date):
    await clear_ml_data()
    async with AsyncSessionLocal() as session:
        # Seed customer
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            insert_stmt = customers_tbl.insert().values(
                id=TEST_CUST_ID,
                customer_code="ML-222",
                business_name="ML Test Enterprise",
                city="Mumbai",
                state="MH",
                country="IND",
                credit_limit=100000.0,
                payment_terms_days=30,
                registration_date=date.today() - timedelta(days=120),
                is_active=True,
                behavioral_profile={"segment": "stable"},
                is_processed=True,
                created_at=datetime.now(UTC) - timedelta(days=120),
                updated_at=datetime.now(UTC) - timedelta(days=120)
            )
            await session.execute(insert_stmt)

        # 1. Customer Intelligence
        intel = CustomerIntelligence(
            customer_id=TEST_CUST_ID,
            customer_name="ML Test Enterprise",
            city="Mumbai",
            health_score=0.90,
            health_previous=0.85,
            risk_score=0.10,
            risk_previous=0.15,
            growth_score=0.80,
            growth_previous=0.75,
            trust_score=0.95,
            trust_previous=0.90,
            opportunity_score=0.50,
            opportunity_previous=0.50,
            credit_score=0.85,
            credit_previous=0.80,
            collection_score=0.95,
            collection_previous=0.90,
            relationship_score=0.90,
            relationship_previous=0.85,
            outstanding_current=0.0,
            outstanding_previous=1000.0,
            contribution_current=2.0,
            contribution_previous=1.8,
            state="healthy",
            current_state="healthy",
            customer_archetype="stable_retailer",
            risk_direction="decreasing",
            trust_direction="increasing",
            last_purchase_date=date.today() - timedelta(days=1)
        )
        session.add(intel)

        # 2. Event Ledger (Sales)
        events = [
            EventLedger(
                event_id="EVT-ML-S1",
                customer_id=TEST_CUST_ID,
                event_type="SALE",
                event_date=snapshot_date - timedelta(days=10),
                amount=20000.0,
                customer_sequence_number=1,
                is_ok=0
            )
        ]
        session.add_all(events)

        # 3. Snapshot
        snap = FeatureSnapshot(
            snapshot_id="test-snap-id-222",
            customer_id=TEST_CUST_ID,
            snapshot_date=snapshot_date,
            snapshot_source=SnapshotSource.BATCH.value,
            snapshot_version="1.0.0",
            generator_version="1.0.0",
            feature_hash="dummy_hash",
            health_score=0.90,
            risk_score=0.10,
            trust_score=0.95,
            outstanding_current=0.0,
            current_state="healthy",
            customer_archetype="stable_retailer",
            risk_direction="decreasing",
            trust_direction="increasing"
        )
        session.add(snap)
        
        await session.commit()


@pytest.mark.asyncio
async def test_prediction_registry_and_service():
    """Verify that predictions can be registered, ran, and saved correctly."""
    snapshot_date = date.today() - timedelta(days=95)
    await seed_ml_data(snapshot_date)

    async with AsyncSessionLocal() as session:
        # Generate predictions for the seeded snapshot
        preds = await generate_predictions_for_snapshot(TEST_CUST_ID, "test-snap-id-222", session)
        await session.commit()

        # Should generate 5 predictions (CHURN, DELINQUENCY, DISTRESS, RECOVERY, STATE_TRANSITION)
        assert len(preds) == 5

        # Verify repository functions
        repo = PredictionRepository(session)
        
        # get_customer_predictions
        cust_preds = await repo.get_customer_predictions(TEST_CUST_ID)
        assert len(cust_preds) == 5
        
        # get_pending_predictions
        pending = await repo.get_pending_predictions()
        assert len(pending) >= 5

        # check specific prediction types
        churn_pred = next(p for p in cust_preds if p.prediction_type == PredictionType.CHURN)
        assert churn_pred.prediction_status == PredictionStatus.PENDING
        assert churn_pred.prediction_horizon_days == 90
        assert churn_pred.model_id == "churn_v1"

    await clear_ml_data()


@pytest.mark.asyncio
async def test_outcome_resolution_and_feedback():
    """Verify that pending predictions are evaluated correctly and feedback is compiled."""
    snapshot_date = date.today() - timedelta(days=95)
    await seed_ml_data(snapshot_date)

    async with AsyncSessionLocal() as session:
        # 1. Generate predictions
        await generate_predictions_for_snapshot(TEST_CUST_ID, "test-snap-id-222", session)
        await session.commit()

    # Seed events representing outcome observations after the snapshot (within T+90 window)
    async with AsyncSessionLocal() as session:
        # Let's seed a SALE event at T+5 days (meaning the customer did NOT churn)
        sale_event = EventLedger(
            event_id="EVT-ML-S2",
            customer_id=TEST_CUST_ID,
            event_type="SALE",
            event_date=snapshot_date + timedelta(days=5),
            amount=5000.0,
            customer_sequence_number=2,
            is_ok=0
        )
        session.add(sale_event)
        await session.commit()

    # 2. Run outcome resolution (should evaluate since T+90 has passed)
    async with AsyncSessionLocal() as session:
        resolved_outcomes = await evaluate_pending_predictions(session)
        await session.commit()

        assert len(resolved_outcomes) == 5

        # OutRepo validation
        out_repo = OutcomeRepository(session)
        outcomes = await out_repo.get_customer_outcomes(TEST_CUST_ID)
        assert len(outcomes) == 5

        # Validate Churn outcome: should be 0.0 (not churned) because a SALE was made at T+5 days
        churn_outcome = next(o for o in outcomes if o.prediction_type == PredictionType.CHURN.value)
        assert churn_outcome.actual_value == 0.0
        assert churn_outcome.is_correct is True  # predicted value was low, actual was 0.0

    # 3. Calculate and persist feedback metrics
    async with AsyncSessionLocal() as session:
        feedback = await calculate_and_persist_feedback_metrics(session)
        await session.commit()

        assert len(feedback) == 5
        
        feed_repo = FeedbackRepository(session)
        latest_feedback = await feed_repo.get_latest_feedback("churn_v1", PredictionType.CHURN.value)
        assert latest_feedback is not None
        assert latest_feedback.samples >= 1

    await clear_ml_data()
