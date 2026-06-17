import uuid
from datetime import date, datetime, UTC, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import polars as pl

from core.models.state_models import (
    CustomerIntelligence,
    EventLedger,
    Alert,
    CollectionActivity,
    PaymentCommitment,
    Recommendation,
    DecisionAudit,
)
from core.ml.shared.types import FeatureSnapshotDTO
from core.ml.shared.enums import SnapshotSource, CustomerState, RiskDirection, TrustDirection, CustomerArchetype
from core.ml.features.feature_validator import compute_feature_hash
from core.intelligence.settlement.engine import SettlementMatchingEngine
from core.schemas.intelligence import AnalysisContext
from core.storage.postgres import get_reflected_table


class FeatureBuilder:
    """
    Assembles a customer commercial feature snapshot as a read-only operation.
    Gathers data across boundaries: CustomerIntelligence, EventLedger, Alerts, Collections, Decisioning.
    Never duplicates calculations or writes to the database.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_snapshot(
        self,
        customer_id: str,
        snapshot_date: Optional[date] = None,
        snapshot_source: SnapshotSource = SnapshotSource.BATCH
    ) -> FeatureSnapshotDTO:
        """
        Assembles a read-only FeatureSnapshotDTO for the given customer_id at snapshot_date.
        """
        if snapshot_date is None:
            snapshot_date = datetime.now(UTC).date()

        # 1. Gather Customer Intelligence Scores and States
        stmt_intel = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res_intel = await self.db.execute(stmt_intel)
        intel = res_intel.scalar_one_or_none()

        # 2. Gather EventLedger history up to snapshot_date
        stmt_events = select(EventLedger).where(
            and_(
                EventLedger.customer_id == customer_id,
                EventLedger.event_date <= snapshot_date,
                EventLedger.is_voided == False
            )
        ).order_by(EventLedger.event_date.asc(), EventLedger.global_sequence_number.asc())
        res_events = await self.db.execute(stmt_events)
        events = res_events.scalars().all()

        # Convert events to Polars DataFrame for Settlement Matching
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
        else:
            ledger_df = pl.DataFrame(schema={
                "customer_id": pl.Utf8,
                "event_uid": pl.Utf8,
                "event_type": pl.Utf8,
                "event_date": pl.Datetime,
                "amount": pl.Float64,
                "sequence_number": pl.Int64,
                "is_ok": pl.Int64
            })

        # Calculate Rolling billing sums (SALEs)
        def sum_events(etype: str, days: int) -> float:
            start_date = snapshot_date - timedelta(days=days)
            return sum(e.amount for e in events if e.event_type == etype and start_date < e.event_date <= snapshot_date)

        billing_30d = sum_events("SALE", 30)
        billing_90d = sum_events("SALE", 90)
        billing_180d = sum_events("SALE", 180)

        payments_30d = sum_events("PAYMENT", 30)
        payments_90d = sum_events("PAYMENT", 90)
        payments_180d = sum_events("PAYMENT", 180)

        returns_30d = sum_events("RETURN", 30)
        returns_90d = sum_events("RETURN", 90)

        # Purchase Gap (days since last SALE)
        sale_dates = [e.event_date for e in events if e.event_type == "SALE"]
        if sale_dates:
            latest_sale = max(sale_dates)
            purchase_gap = (snapshot_date - latest_sale).days
        else:
            purchase_gap = None

        # Purchase Frequency (count of SALEs in 365 days)
        sales_365d = [e for e in events if e.event_type == "SALE" and snapshot_date - timedelta(days=365) < e.event_date <= snapshot_date]
        purchase_frequency = float(len(sales_365d))

        # Repayment Delays using FIFO Settlement Engine
        engine = SettlementMatchingEngine()
        context_all = AnalysisContext(end_date=snapshot_date, window_days=365)
        settlement_df = engine.compute_settlements(ledger_df, context_all)
        if not settlement_df.is_empty():
            payment_delay_avg = float(settlement_df["avg_repayment_days"][0])
        else:
            payment_delay_avg = 0.0

        # Repayment Delay Trend
        context_recent = AnalysisContext(end_date=snapshot_date, window_days=90, start_date=snapshot_date - timedelta(days=90))
        settlement_recent = engine.compute_settlements(ledger_df, context_recent)
        avg_recent = float(settlement_recent["avg_repayment_days"][0]) if not settlement_recent.is_empty() else 0.0

        context_prev = AnalysisContext(end_date=snapshot_date - timedelta(days=90), window_days=90, start_date=snapshot_date - timedelta(days=180))
        settlement_prev = engine.compute_settlements(ledger_df, context_prev)
        avg_prev = float(settlement_prev["avg_repayment_days"][0]) if not settlement_prev.is_empty() else 0.0

        payment_delay_trend = avg_recent - avg_prev

        # Collection Efficiency
        collection_efficiency = payments_90d / billing_90d if billing_90d > 0.0 else 1.0
        collection_efficiency = max(0.0, min(1.0, collection_efficiency))

        # Outstanding current
        outstanding_current = intel.outstanding_current if intel and intel.outstanding_current is not None else 0.0

        # Outstanding ratio
        outstanding_ratio = outstanding_current / billing_90d if billing_90d > 0.0 else 0.0

        # Credit utilization (requires credit limit from customers table)
        credit_limit = 0.0
        try:
            customers_tbl = await get_reflected_table("customers", self.db)
            if customers_tbl is not None:
                stmt_limit = select(customers_tbl.c.credit_limit).where(customers_tbl.c.id == uuid.UUID(customer_id))
                res_limit = await self.db.execute(stmt_limit)
                credit_limit = float(res_limit.scalar() or 0.0)
        except Exception:
            pass

        credit_utilization = outstanding_current / credit_limit if credit_limit > 0.0 else 0.0

        # 3. Gather Alerts data (Active alerts count)
        stmt_alerts = select(func.count(Alert.id)).where(
            and_(
                Alert.customer_id == customer_id,
                Alert.status == "ACTIVE"
            )
        )
        res_alerts = await self.db.execute(stmt_alerts)
        active_alerts_count = res_alerts.scalar() or 0

        # 4. Gather Collections activities and commitments
        stmt_coll = select(func.count(CollectionActivity.id)).where(CollectionActivity.customer_id == customer_id)
        res_coll = await self.db.execute(stmt_coll)
        collection_activities_count = res_coll.scalar() or 0

        stmt_commit = select(func.count(PaymentCommitment.id)).where(
            and_(
                PaymentCommitment.customer_id == customer_id,
                PaymentCommitment.status == "PENDING"
            )
        )
        res_commit = await self.db.execute(stmt_commit)
        pending_commitments_count = res_commit.scalar() or 0

        # 5. Gather Decisioning (Recommendations and Audits)
        stmt_recs = select(func.count(Recommendation.id)).where(
            and_(
                Recommendation.customer_id == customer_id,
                Recommendation.status == "ACTIVE"
            )
        )
        res_recs = await self.db.execute(stmt_recs)
        active_recommendations_count = res_recs.scalar() or 0

        stmt_decision = select(func.count(DecisionAudit.id)).where(DecisionAudit.customer_id == customer_id)
        res_decision = await self.db.execute(stmt_decision)
        decision_audits_count = res_decision.scalar() or 0

        # Map States and Directions safely
        def map_enum(enum_cls, val, default):
            if not val:
                return default
            try:
                return enum_cls(val.lower() if isinstance(val, str) else val)
            except ValueError:
                return default

        curr_state_enum = map_enum(CustomerState, intel.current_state if intel else None, CustomerState.DORMANT)
        archetype_enum = map_enum(CustomerArchetype, intel.customer_archetype if intel else None, CustomerArchetype.STABLE_RETAILER)
        risk_dir_enum = map_enum(RiskDirection, intel.risk_direction if intel else None, RiskDirection.STABLE)
        trust_dir_enum = map_enum(TrustDirection, intel.trust_direction if intel else None, TrustDirection.STABLE)

        # Build final Payload
        payload = {
            "health_score": intel.health_score if intel else 0.0,
            "risk_score": intel.risk_score if intel else 0.0,
            "trust_score": intel.trust_score if intel else 0.0,
            "growth_score": intel.growth_score if intel else 0.0,
            "collection_score": intel.collection_score if intel else 0.0,
            "relationship_score": intel.relationship_score if intel else 0.0,
            "credit_score": intel.credit_score if intel else 0.0,
            "opportunity_score": intel.opportunity_score if intel else 0.0,
            "current_state": curr_state_enum.value,
            "customer_archetype": archetype_enum.value,
            "risk_direction": risk_dir_enum.value,
            "trust_direction": trust_dir_enum.value,
            "billing_30d": billing_30d,
            "billing_90d": billing_90d,
            "billing_180d": billing_180d,
            "payments_30d": payments_30d,
            "payments_90d": payments_90d,
            "payments_180d": payments_180d,
            "returns_30d": returns_30d,
            "returns_90d": returns_90d,
            "purchase_gap": purchase_gap,
            "purchase_frequency": purchase_frequency,
            "payment_delay_avg": payment_delay_avg,
            "payment_delay_trend": payment_delay_trend,
            "collection_efficiency": collection_efficiency,
            "outstanding_current": outstanding_current,
            "outstanding_ratio": outstanding_ratio,
            "credit_utilization": credit_utilization,
            "active_alerts_count": active_alerts_count,
            "collection_activities_count": collection_activities_count,
            "pending_commitments_count": pending_commitments_count,
            "active_recommendations_count": active_recommendations_count,
            "decision_audits_count": decision_audits_count,
            "credit_limit": credit_limit,
        }

        feature_hash = compute_feature_hash(customer_id, snapshot_date, payload)

        return FeatureSnapshotDTO(
            snapshot_id=str(uuid.uuid4()),
            customer_id=customer_id,
            snapshot_date=snapshot_date,
            snapshot_source=snapshot_source,
            snapshot_version="1.0.0",
            generator_version="1.0.0",
            feature_hash=feature_hash,
            
            health_score=payload["health_score"],
            risk_score=payload["risk_score"],
            trust_score=payload["trust_score"],
            growth_score=payload["growth_score"],
            collection_score=payload["collection_score"],
            relationship_score=payload["relationship_score"],
            credit_score=payload["credit_score"],
            opportunity_score=payload["opportunity_score"],
            
            current_state=curr_state_enum,
            customer_archetype=archetype_enum,
            risk_direction=risk_dir_enum,
            trust_direction=trust_dir_enum,
            
            billing_30d=billing_30d,
            billing_90d=billing_90d,
            billing_180d=billing_180d,
            payments_30d=payments_30d,
            payments_90d=payments_90d,
            payments_180d=payments_180d,
            returns_30d=returns_30d,
            returns_90d=returns_90d,
            
            purchase_gap=purchase_gap,
            purchase_frequency=purchase_frequency,
            payment_delay_avg=payment_delay_avg,
            payment_delay_trend=payment_delay_trend,
            collection_efficiency=collection_efficiency,
            
            outstanding_current=outstanding_current,
            outstanding_ratio=outstanding_ratio,
            credit_utilization=credit_utilization,
            
            feature_payload_json=payload,
            created_at=datetime.now(UTC)
        )
