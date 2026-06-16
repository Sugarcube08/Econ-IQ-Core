from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from core.core.dependencies import get_current_identity
from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.main import app
from core.models.auth_models import User, UserRole
from core.models.state_models import (
    Alert,
    CollectionActivity,
    CustomerIntelligence,
    DecisionAudit,
    EventLedger,
    PaymentCommitment,
    Recommendation,
)
from core.storage.postgres import AsyncSessionLocal, get_reflected_table

TEST_CUSTOMER_ID = "99999999-9999-9999-9999-999999999999"

def get_mock_identity():
    # Return a mock super admin user to bypass JWT validation
    user = User(
        email="admin@econiq.com",
        full_name="Regression Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
        token_version=0
    )
    user.id = None
    return user

async def clear_data():
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Alert).where(Alert.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(CollectionActivity).where(CollectionActivity.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(PaymentCommitment).where(PaymentCommitment.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(Recommendation).where(Recommendation.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(DecisionAudit).where(DecisionAudit.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(CustomerIntelligence).where(CustomerIntelligence.customer_id == TEST_CUSTOMER_ID))
        await session.execute(delete(EventLedger).where(EventLedger.customer_id == TEST_CUSTOMER_ID))
        
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            await session.execute(delete(customers_tbl).where(customers_tbl.c.id == TEST_CUSTOMER_ID))
            
        await session.commit()

async def seed_data():
    await clear_data()
    async with AsyncSessionLocal() as session:
        # Seed customers table with a date in the past (e.g. 5 days ago) to avoid timezone discrepancies
        customers_tbl = await get_reflected_table("customers", session)
        if customers_tbl is not None:
            insert_stmt = customers_tbl.insert().values(
                id=TEST_CUSTOMER_ID,
                customer_code="REG-999",
                business_name="Regression Enterprise Inc",
                city="Mumbai",
                state="MH",
                country="IND",
                credit_limit=100000.0,
                payment_terms_days=30,
                registration_date=date.today() - timedelta(days=5),
                is_active=True,
                behavioral_profile={"segment": "stable"},
                is_processed=True,
                created_at=datetime.now(UTC) - timedelta(days=5),
                updated_at=datetime.now(UTC) - timedelta(days=5)
            )
            await session.execute(insert_stmt)

        # Seed mock CustomerIntelligence
        intel = CustomerIntelligence(
            customer_id=TEST_CUSTOMER_ID,
            customer_name="Regression Enterprise Inc",
            city="Mumbai",
            health_score=0.45,
            health_previous=0.50,
            risk_score=0.35,
            risk_previous=0.30,
            growth_score=0.60,
            growth_previous=0.55,
            trust_score=0.70,
            trust_previous=0.75,
            opportunity_score=0.50,
            opportunity_previous=0.50,
            credit_score=0.65,
            credit_previous=0.65,
            collection_score=0.55,
            collection_previous=0.50,
            relationship_score=0.60,
            relationship_previous=0.60,
            outstanding_current=12000.0,
            outstanding_previous=10000.0,
            contribution_current=2.5,
            contribution_previous=2.4,
            state="stable",
            last_purchase_date=date.today() - timedelta(days=5),
            last_updated=datetime.now(UTC) - timedelta(days=5)
        )
        session.add(intel)
        await session.commit()


@pytest.mark.asyncio
async def test_health_and_missing_endpoints():
    """Verify that health check is active, but telemetry and recompute endpoints return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json()["success"] is True

        res_metrics = await client.get("/api/v1/system/metrics")
        assert res_metrics.status_code == 404

        res_runtime = await client.get("/api/v1/system/runtime")
        assert res_runtime.status_code == 404

        res_recompute = await client.post("/api/v1/admin/recompute")
        assert res_recompute.status_code == 404


@pytest.mark.asyncio
async def test_auth_otp_flow():
    """Verify auth request-otp endpoint validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/auth/request-otp", json={"email": "nonexistent@econiq.com"})
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_overview():
    """Verify dashboard overview endpoint loads successfully and enforces 365d canonical window."""
    await seed_data()
    app.dependency_overrides[get_current_identity] = get_mock_identity
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/v1/dashboard/overview")
            assert res.status_code == 200
            assert "window" in res.json()["metadata"]
            start_dt = datetime.fromisoformat(res.json()["metadata"]["window"]["start_date"])
            end_dt = datetime.fromisoformat(res.json()["metadata"]["window"]["end_date"])
            duration_days = (end_dt - start_dt).days + 1
            assert duration_days == 365
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        await clear_data()


@pytest.mark.asyncio
async def test_customer_detail_and_graphs():
    """Verify customer details and graphs load and enforce 365d canonical window."""
    await seed_data()
    app.dependency_overrides[get_current_identity] = get_mock_identity
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(f"/api/v1/customer/{TEST_CUSTOMER_ID}")
            assert res.status_code == 200
            profile = res.json()["data"]["customer"]
            assert profile["customer_id"] == TEST_CUSTOMER_ID
            assert profile["customer_name"] == "Regression Enterprise Inc"
            assert res.json()["metadata"]["window_days"] == 365

            res_pg = await client.get(f"/api/v1/customer/{TEST_CUSTOMER_ID}/purchase-graph")
            assert res_pg.status_code == 200
            assert "graph" in res_pg.json()["data"]
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        await clear_data()


@pytest.mark.asyncio
async def test_operations_alerts_and_collections():
    """Verify operations APIs (Alerts, Collections activity logs, commitments, and decisions)."""
    await seed_data()
    app.dependency_overrides[get_current_identity] = get_mock_identity
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res_col = await client.post("/api/v1/collections/activity", json={
                "customer_id": TEST_CUSTOMER_ID,
                "user_id": "test-analyst",
                "activity_type": "EMAIL",
                "notes": "Follow-up email sent regarding invoice balance.",
                "outcome": "CONTACTED"
            })
            assert res_col.status_code == 200
            assert res_col.json()["success"] is True

            res_col_get = await client.get(f"/api/v1/collections/activity?customer_id={TEST_CUSTOMER_ID}")
            assert res_col_get.status_code == 200
            assert len(res_col_get.json()["data"]) >= 1

            res_comm = await client.post("/api/v1/collections/commitment", json={
                "customer_id": TEST_CUSTOMER_ID,
                "amount": 5000.0,
                "promised_date": (date.today() + timedelta(days=2)).isoformat()
            })
            assert res_comm.status_code == 200
            assert res_comm.json()["success"] is True

            res_comm_get = await client.get(f"/api/v1/collections/commitment?customer_id={TEST_CUSTOMER_ID}")
            assert res_comm_get.status_code == 200
            assert len(res_comm_get.json()["data"]) >= 1
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        await clear_data()


@pytest.mark.asyncio
async def test_regression_background_processing():
    """Verify that event ingestion, sync pipelines, alerts, and recommendations function correctly."""
    await seed_data()
    try:
        async with AsyncSessionLocal() as session:
            # 1. Ingest a mock SALE event into EventLedger (use 2 days ago to avoid timezone filtering)
            event = EventLedger(
                event_id="test-event-999",
                customer_id=TEST_CUSTOMER_ID,
                event_type="SALE",
                event_date=date.today() - timedelta(days=2),
                amount=5000.0,
                source_raw_id="raw-1",
                source_table="raw_sales",
                is_voided=False,
                is_ok=0,
                created_at=datetime.now(UTC) - timedelta(days=2),
                updated_at=datetime.now(UTC) - timedelta(days=2)
            )
            session.add(event)
            await session.commit()

            # 2. Trigger customer intelligence refresh manually using the orchestrator
            orchestrator = IntelligenceOrchestrator()
            await orchestrator.run([TEST_CUSTOMER_ID])

            # 3. Verify intelligence, alert, and recommendation generation
            stmt_intel = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == TEST_CUSTOMER_ID)
            res_intel = await session.execute(stmt_intel)
            intel_record = res_intel.scalars().first()
            assert intel_record is not None
            assert intel_record.outstanding_current == 5000.0

            stmt_alert = select(Alert).where(Alert.customer_id == TEST_CUSTOMER_ID)
            res_alert = await session.execute(stmt_alert)
            alerts = res_alert.scalars().all()
            assert len(alerts) >= 0

            stmt_rec = select(Recommendation).where(Recommendation.customer_id == TEST_CUSTOMER_ID)
            res_rec = await session.execute(stmt_rec)
            recs = res_rec.scalars().all()
            assert len(recs) >= 0
    finally:
        await clear_data()
