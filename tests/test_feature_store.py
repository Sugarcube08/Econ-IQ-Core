import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from core.ml.features.feature_builder import FeatureBuilder
from core.ml.features.feature_repository import FeatureRepository
from core.ml.features.feature_snapshot import generate_snapshot
from core.ml.features.feature_validator import SnapshotValidationError, validate_snapshot
from core.models.state_models import (
    Alert,
    CollectionActivity,
    CustomerIntelligence,
    DecisionAudit,
    EventLedger,
    FeatureSnapshot,
    PaymentCommitment,
    Recommendation,
)
from core.storage.postgres import AsyncSessionLocal, get_reflected_table

TEST_CUST_ID = "11111111-1111-1111-1111-111111111111"

async def clear_test_data():
    async with AsyncSessionLocal() as session:
        await session.execute(delete(FeatureSnapshot).where(FeatureSnapshot.customer_id == TEST_CUST_ID))
        await session.execute(delete(Alert).where(Alert.customer_id == TEST_CUST_ID))
        await session.execute(delete(CollectionActivity).where(CollectionActivity.customer_id == TEST_CUST_ID))
        await session.execute(delete(PaymentCommitment).where(PaymentCommitment.customer_id == TEST_CUST_ID))
        await session.execute(delete(Recommendation).where(Recommendation.customer_id == TEST_CUST_ID))
        await session.execute(delete(DecisionAudit).where(DecisionAudit.customer_id == TEST_CUST_ID))
        await session.execute(delete(CustomerIntelligence).where(CustomerIntelligence.customer_id == TEST_CUST_ID))
        await session.execute(delete(EventLedger).where(EventLedger.customer_id == TEST_CUST_ID))
        
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            await session.execute(delete(customers_tbl).where(customers_tbl.c.id == TEST_CUST_ID))
        await session.commit()

async def seed_test_data():
    await clear_test_data()
    async with AsyncSessionLocal() as session:
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            insert_stmt = customers_tbl.insert().values(
                id=TEST_CUST_ID,
                customer_code="FEAT-111",
                business_name="Feature Test Corp",
                city="Pune",
                state="MH",
                country="IND",
                credit_limit=50000.0,
                payment_terms_days=30,
                registration_date=date.today() - timedelta(days=20),
                is_active=True,
                behavioral_profile={"segment": "stable"},
                is_processed=True,
                created_at=datetime.now(UTC) - timedelta(days=20),
                updated_at=datetime.now(UTC) - timedelta(days=20)
            )
            await session.execute(insert_stmt)

        # 1. Customer Intelligence
        intel = CustomerIntelligence(
            customer_id=TEST_CUST_ID,
            customer_name="Feature Test Corp",
            city="Pune",
            health_score=0.85,
            health_previous=0.80,
            risk_score=0.15,
            risk_previous=0.20,
            growth_score=0.75,
            growth_previous=0.70,
            trust_score=0.90,
            trust_previous=0.85,
            opportunity_score=0.40,
            opportunity_previous=0.40,
            credit_score=0.80,
            credit_previous=0.75,
            collection_score=0.95,
            collection_previous=0.90,
            relationship_score=0.85,
            relationship_previous=0.80,
            outstanding_current=5000.0,
            outstanding_previous=4000.0,
            contribution_current=1.2,
            contribution_previous=1.0,
            state="healthy",
            current_state="healthy",
            customer_archetype="stable_retailer",
            risk_direction="decreasing",
            trust_direction="increasing",
            last_purchase_date=date.today() - timedelta(days=2)
        )
        session.add(intel)

        # 2. Event Ledger (Sales, Payments, Returns)
        events = [
            EventLedger(
                event_id="EVT-S-1",
                customer_id=TEST_CUST_ID,
                event_type="SALE",
                event_date=date.today() - timedelta(days=15),
                amount=10000.0,
                customer_sequence_number=1,
                is_ok=0
            ),
            EventLedger(
                event_id="EVT-P-1",
                customer_id=TEST_CUST_ID,
                event_type="PAYMENT",
                event_date=date.today() - timedelta(days=10),
                amount=5000.0,
                customer_sequence_number=2,
                is_ok=0
            ),
            EventLedger(
                event_id="EVT-S-2",
                customer_id=TEST_CUST_ID,
                event_type="SALE",
                event_date=date.today() - timedelta(days=2),
                amount=8000.0,
                customer_sequence_number=3,
                is_ok=0
            ),
        ]
        session.add_all(events)

        # 3. Active Alert
        alert = Alert(
            id=str(uuid.uuid4()),
            customer_id=TEST_CUST_ID,
            alert_type="trust_drop",
            alert_severity="WARNING",
            title="Slight drop in trust score",
            description="Trust score dropped by 5%",
            status="ACTIVE"
        )
        session.add(alert)

        # 4. Collections
        activity = CollectionActivity(
            id=str(uuid.uuid4()),
            customer_id=TEST_CUST_ID,
            user_id="SYSTEM",
            activity_type="EMAIL",
            notes="Reminder email sent",
            outcome="SENT"
        )
        session.add(activity)

        # 5. Recommendation
        rec = Recommendation(
            id=str(uuid.uuid4()),
            customer_id=TEST_CUST_ID,
            recommendation_type="increase_limit",
            severity="LOW",
            reason="Good payment discipline",
            confidence=0.85,
            status="ACTIVE"
        )
        session.add(rec)

        await session.commit()


@pytest.mark.asyncio
async def test_feature_builder_and_validator():
    """Verify that FeatureBuilder accurately assembles snapshots and Validator handles validation rules."""
    await seed_test_data()
    
    async with AsyncSessionLocal() as session:
        builder = FeatureBuilder(session)
        dto = await builder.build_snapshot(TEST_CUST_ID, date.today())
        
        # Verify gathered properties
        assert dto.customer_id == TEST_CUST_ID
        assert dto.health_score == 0.85
        assert dto.risk_score == 0.15
        assert dto.trust_score == 0.90
        assert dto.outstanding_current == 5000.0
        
        # Verify rolling windows
        assert dto.billing_30d == 18000.0  # 10000 + 8000
        assert dto.payments_30d == 5000.0
        assert dto.returns_30d == 0.0
        
        # Verify counts in payload
        payload = dto.feature_payload_json
        assert payload["active_alerts_count"] == 1
        assert payload["collection_activities_count"] == 1
        assert payload["active_recommendations_count"] == 1
        assert payload["credit_limit"] == 50000.0
        assert dto.credit_utilization == 5000.0 / 50000.0

        # Validator should pass a valid DTO
        validate_snapshot(dto)

        # Validator: Health score out of bounds
        bad_dto = dto.model_copy(update={"health_score": 1.5})
        with pytest.raises(SnapshotValidationError, match="health_score must be between 0 and 1"):
            validate_snapshot(bad_dto)

        # Validator: Negative outstanding
        bad_dto = dto.model_copy(update={"outstanding_current": -100.0})
        with pytest.raises(SnapshotValidationError, match="outstanding_current must be >= 0"):
            validate_snapshot(bad_dto)

        # Validator: Invalid current state enum
        bad_dto = dto.model_copy(update={"current_state": "invalid_state"})
        with pytest.raises(SnapshotValidationError):
            validate_snapshot(bad_dto)

        # Validator: Hash mismatch
        bad_dto = dto.model_copy(update={"feature_hash": "incorrect_hash"})
        with pytest.raises(SnapshotValidationError, match="feature_hash mismatch"):
            validate_snapshot(bad_dto)

    await clear_test_data()


@pytest.mark.asyncio
async def test_feature_repository_and_immutability():
    """Verify that FeatureRepository persists correctly and that snapshots are strictly immutable."""
    await seed_test_data()
    
    async with AsyncSessionLocal() as session:
        builder = FeatureBuilder(session)
        dto = await builder.build_snapshot(TEST_CUST_ID, date.today())
        
        repo = FeatureRepository(session)
        
        # Test insert_snapshot
        inserted = await repo.insert_snapshot(dto)
        assert inserted.snapshot_id == dto.snapshot_id
        await session.commit()

        # Test snapshot_exists
        exists = await repo.snapshot_exists(TEST_CUST_ID, date.today())
        assert exists is True

        # Test get_latest_snapshot
        latest = await repo.get_latest_snapshot(TEST_CUST_ID)
        assert latest is not None
        assert latest.snapshot_id == dto.snapshot_id
        assert latest.health_score == 0.85

        # Test get_customer_snapshots
        all_snaps = await repo.get_customer_snapshots(TEST_CUST_ID)
        assert len(all_snaps) == 1
        assert all_snaps[0].snapshot_id == dto.snapshot_id

        # Test database-level immutability enforcement
        # Fetch the SQLAlchemy model instance directly
        stmt = select(FeatureSnapshot).where(FeatureSnapshot.snapshot_id == dto.snapshot_id)
        res = await session.execute(stmt)
        model_instance = res.scalars().first()
        
        assert model_instance is not None
        
        # Attempting to update model
        model_instance.health_score = 0.50
        with pytest.raises(RuntimeError, match="Feature snapshots are immutable and cannot be updated"):
            await session.commit()
        await session.rollback()

    # Attempting to delete model in a fresh session block
    async with AsyncSessionLocal() as session:
        stmt = select(FeatureSnapshot).where(FeatureSnapshot.customer_id == TEST_CUST_ID)
        res = await session.execute(stmt)
        model_instance = res.scalars().first()
        assert model_instance is not None
        
        await session.delete(model_instance)
        with pytest.raises(RuntimeError, match="Feature snapshots are immutable and cannot be deleted"):
            await session.commit()
        await session.rollback()

    await clear_test_data()


@pytest.mark.asyncio
async def test_generate_snapshot_service():
    """Verify the end-to-end generate_snapshot service method."""
    await seed_test_data()
    
    # Generate snapshot using the service
    dto = await generate_snapshot(TEST_CUST_ID, snapshot_date=date.today())
    
    assert dto.customer_id == TEST_CUST_ID
    assert dto.health_score == 0.85
    
    # Confirm it exists in DB
    async with AsyncSessionLocal() as session:
        repo = FeatureRepository(session)
        latest = await repo.get_latest_snapshot(TEST_CUST_ID)
        assert latest is not None
        assert latest.snapshot_id == dto.snapshot_id

    await clear_test_data()
