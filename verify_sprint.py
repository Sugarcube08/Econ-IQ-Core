import asyncio
import time
from datetime import date

from sqlalchemy import delete, select

from core.models.state_models import (
    Alert,
    CollectionActivity,
    CustomerIntelligence,
    DecisionAudit,
    PaymentCommitment,
    Recommendation,
)
from core.recommendation.rules_engine import RecommendationRulesEngine
from core.services.alert_service import AlertService
from core.services.collections_service import CollectionsService
from core.services.decision_audit_service import DecisionAuditService
from core.storage.postgres import AsyncSessionLocal, engine


async def run_verification():
    print("--- STARTING SPRINT VERIFICATION RUN ---")
    start_time = time.time()
    
    # Run strict schema validation (Zero mutations, verification only)
    async with engine.connect() as conn:
        def validate_schema(sync_conn):
            from sqlalchemy import inspect
            inspector = inspect(sync_conn)
            cols = [c["name"] for c in inspector.get_columns("customer_intelligence")]
            required = ["current_state", "customer_archetype", "risk_direction", "trust_direction"]
            missing = [r for r in required if r not in cols]
            if missing:
                raise RuntimeError(
                    f"Database schema misalignment: missing columns in 'customer_intelligence': {missing}. "
                    "Please run Alembic migrations ('alembic upgrade head') before starting verification."
                )
        await conn.run_sync(validate_schema)
    
    async with AsyncSessionLocal() as session:
        # Clean up existing test data
        customer_id = "test-verification-customer-123"
        print(f"Cleaning up previous test data for customer: {customer_id}")
        await session.execute(delete(Alert).where(Alert.customer_id == customer_id))
        await session.execute(delete(CollectionActivity).where(CollectionActivity.customer_id == customer_id))
        await session.execute(delete(PaymentCommitment).where(PaymentCommitment.customer_id == customer_id))
        await session.execute(delete(Recommendation).where(Recommendation.customer_id == customer_id))
        await session.execute(delete(DecisionAudit).where(DecisionAudit.customer_id == customer_id))
        await session.execute(delete(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id))
        await session.commit()
        
        # 1. Initialize Customer Intelligence
        print("Inserting CustomerIntelligence mock state...")
        intel = CustomerIntelligence(
            customer_id=customer_id,
            customer_name="Test Enterprise Corp",
            city="Mumbai",
            health_score=0.35, # low health -> REVIEW_ACCOUNT
            health_previous=0.80, # drop -> SEGMENT_DOWNGRADE
            risk_score=0.75, # high risk -> RISK_SPIKE, REDUCE_EXPOSURE
            risk_previous=0.55,
            trust_score=0.45,
            trust_previous=0.70, # drop -> TRUST_DROP
            collection_score=0.35,
            collection_previous=0.60, # drop -> DSO_SPIKE / payment deterioration
            outstanding_current=50000.0,
            outstanding_previous=40000.0, # outstanding spike
            state="declining", # maps to liquidity_stress
            last_purchase_date=date.today()
        )
        session.add(intel)
        await session.commit()
        
        # 2. Verify Alerting Platform (Phase 2)
        print("\nVerifying Alerting Platform...")
        alert_service = AlertService()
        alerts = await alert_service.scan_and_generate_alerts(customer_id, session)
        await session.commit()
        print(f"Generated {len(alerts)} alerts:")
        for a in alerts:
            print(f"  - [{a.alert_severity}] Type: {a.alert_type} | Title: {a.title}")
        
        assert len(alerts) > 0, "No alerts were generated."
        
        # Test Retrieval & Acknowledgment
        active_alerts = await alert_service.get_alerts(status="ACTIVE", severity=None, customer_id=customer_id, limit=10, offset=0, db_session=session)
        print(f"Retrieved {len(active_alerts)} active alerts from database.")
        
        counts = await alert_service.get_alerts_count(session)
        print(f"Current alert counts in database: {counts}")
        
        target_alert = active_alerts[0]
        ack_res = await alert_service.acknowledge_alert(target_alert.id, "analyst-user-id", session)
        print(f"Acknowledged alert: {ack_res.id} | New Status: {ack_res.status}")
        assert ack_res.status == "ACKNOWLEDGED", "Acknowledge status failed."

        # 3. Verify Collections Activity Engine (Phase 3)
        print("\nVerifying Collections Activity Engine...")
        collections_service = CollectionsService()
        activity = await collections_service.log_activity(
            customer_id=customer_id,
            user_id="analyst-user-id",
            activity_type="CALL",
            notes="Dunning call. Client promised to settle outstanding balance of 15,000 next week.",
            outcome="CONTACTED",
            db_session=session
        )
        await session.commit()
        print(f"Logged CollectionActivity: {activity.id} | Type: {activity.activity_type} | Notes: {activity.notes}")
        
        commitment = await collections_service.log_commitment(
            customer_id=customer_id,
            amount=15000.0,
            promised_date=date.today(),
            db_session=session
        )
        await session.commit()
        print(f"Logged PaymentCommitment: {commitment.id} | Amount: {commitment.amount} | Date: {commitment.promised_date}")
        
        # Test query
        activities_list = await collections_service.get_activities(customer_id=customer_id, limit=10, offset=0, db_session=session)
        commitments_list = await collections_service.get_commitments(customer_id=customer_id, status="PENDING", db_session=session)
        assert len(activities_list) == 1
        assert len(commitments_list) == 1
        print("Collections activity and commitments successfully persisted and queryable.")

        # 4. Verify Commercial Decision Engine & Audit Trail (Phase 4)
        print("\nVerifying Commercial Decision Engine...")
        rules_engine = RecommendationRulesEngine()
        recs_schema = await rules_engine.evaluate_policies(session, customer_id)
        await session.commit()
        print(f"Generated {len(recs_schema.recommendations)} Pydantic recommendations.")
        
        # Get from DB
        stmt = select(Recommendation).where(Recommendation.customer_id == customer_id, Recommendation.status == "ACTIVE")
        res_recs = await session.execute(stmt)
        db_recs = res_recs.scalars().all()
        print(f"Retrieved {len(db_recs)} active recommendations from database:")
        for r in db_recs:
            print(f"  - [{r.severity}] Type: {r.recommendation_type} | Reason: {r.reason}")
        
        assert len(db_recs) > 0, "No recommendations saved to DB."
        
        # Log Decision Action / Override
        decision_service = DecisionAuditService()
        target_rec = db_recs[0]
        audit = await decision_service.record_action(
            customer_id=customer_id,
            recommendation_id=target_rec.id,
            action_taken="OVERRIDDEN",
            performed_by="analyst-user-id",
            reason="Override recommended limit reduction based on corporate tax return audit.",
            db_session=session
        )
        await session.commit()
        print(f"Logged DecisionAudit: {audit.id} | Action: {audit.action_taken} | Reason: {audit.reason}")
        
        # Verify Recommendation status updated to OVERRIDDEN
        stmt_check = select(Recommendation).where(Recommendation.id == target_rec.id)
        res_check = await session.execute(stmt_check)
        updated_rec = res_check.scalars().first()
        print(f"Updated Recommendation status: {updated_rec.status}")
        assert updated_rec.status == "OVERRIDDEN"
        
        # Retrieve Audit history
        history = await decision_service.get_history(customer_id=customer_id, db_session=session)
        assert len(history) == 1
        print("Decision audit trail and overrides successfully persisted and validated.")
        
    print(f"\n--- SPRINT VERIFICATION RUN COMPLETED IN {time.time() - start_time:.4f} SECONDS ---")

if __name__ == "__main__":
    asyncio.run(run_verification())
