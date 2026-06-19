import uuid
from datetime import UTC, date, datetime, timedelta, time
from typing import Any

import polars as pl
from sqlalchemy import select, delete, func, not_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import (
    EventLedger,
    FeatureSnapshot,
    Alert,
    CustomerIntelligence,
    CustomerGraphMV,
    PortfolioGraphMV
)
from core.utils.temporal import normalize_temporal_to_date


class GraphRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def refresh_customer_graphs(
        self, customer_id: str, granularity: str = "monthly", window_days: int = 365
    ) -> list[dict[str, Any]]:
        # 1. Resolve date range
        now = datetime.now(UTC).date()
        end_date = now
        start_date = end_date - timedelta(days=window_days)

        # 2. Get opening outstanding balance before start_date
        opening_stmt = select(
            func.sum(
                func.coalesce(
                    EventLedger.amount * func.case(
                        (EventLedger.event_type.in_(["SALE", "OPENING_BALANCE"]), 1.0),
                        else_=-1.0
                    ),
                    0.0
                )
            )
        ).where(
            func.trim(EventLedger.customer_id) == customer_id,
            EventLedger.event_date < start_date,
            not_(EventLedger.is_voided),
            EventLedger.is_ok == 0
        )
        opening_res = await self.db.execute(opening_stmt)
        opening_outstanding = float(opening_res.scalar() or 0.0)

        # 3. Get daily events in the window
        events_stmt = select(
            EventLedger.event_date,
            EventLedger.event_type,
            EventLedger.amount
        ).where(
            func.trim(EventLedger.customer_id) == customer_id,
            EventLedger.event_date >= start_date,
            EventLedger.event_date <= end_date,
            not_(EventLedger.is_voided),
            EventLedger.is_ok == 0
        ).order_by(EventLedger.event_date.asc())
        events_res = await self.db.execute(events_stmt)
        events_rows = events_res.all()

        # 4. Get historical scores from FeatureSnapshot
        snapshots_stmt = select(
            FeatureSnapshot.snapshot_date,
            FeatureSnapshot.health_score,
            FeatureSnapshot.risk_score,
            FeatureSnapshot.trust_score,
            FeatureSnapshot.growth_score,
            FeatureSnapshot.collection_score
        ).where(
            func.trim(FeatureSnapshot.customer_id) == customer_id,
            FeatureSnapshot.snapshot_date >= start_date,
            FeatureSnapshot.snapshot_date <= end_date
        ).order_by(FeatureSnapshot.snapshot_date.asc())
        snapshots_res = await self.db.execute(snapshots_stmt)
        snapshots_rows = snapshots_res.all()

        # 5. Get current score fallback from CustomerIntelligence
        intel_stmt = select(CustomerIntelligence).where(
            func.trim(CustomerIntelligence.customer_id) == customer_id
        )
        intel_res = await self.db.execute(intel_stmt)
        intel = intel_res.scalar_one_or_none()

        curr_health = intel.health_score if intel else 0.5
        curr_risk = intel.risk_score if intel else 0.5
        curr_trust = intel.trust_score if intel else 0.5
        curr_growth = intel.growth_score if intel else 0.5
        curr_coll = intel.collection_score if intel else 0.5

        # 6. Get alerts history
        alerts_stmt = select(Alert.created_at).where(
            func.trim(Alert.customer_id) == customer_id,
            Alert.created_at >= datetime.combine(start_date, time.min, tzinfo=UTC),
            Alert.created_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
        alerts_res = await self.db.execute(alerts_stmt)
        alerts_rows = [r[0] for r in alerts_res.all()]

        # Construct daily grid using Polars
        days = []
        curr = start_date
        while curr <= end_date:
            days.append(curr)
            curr += timedelta(days=1)

        daily_grid = pl.DataFrame({"date": days})

        # Process ledger events
        daily_events_dict = {}
        for d in days:
            daily_events_dict[d] = {"sales": 0.0, "payments": 0.0, "returns": 0.0}

        for row in events_rows:
            edate = normalize_temporal_to_date(row[0])
            etype = row[1]
            eamt = float(row[2])
            if edate in daily_events_dict:
                if etype in ["SALE", "OPENING_BALANCE"]:
                    daily_events_dict[edate]["sales"] += eamt
                elif etype in ["PAYMENT", "DISCOUNT"]:
                    daily_events_dict[edate]["payments"] += eamt
                elif etype == "RETURN":
                    daily_events_dict[edate]["returns"] += eamt

        # Calculate daily rolling outstanding
        outstanding_vals = []
        running_outstanding = opening_outstanding
        for d in days:
            running_outstanding += (
                daily_events_dict[d]["sales"]
                - daily_events_dict[d]["payments"]
                - daily_events_dict[d]["returns"]
            )
            outstanding_vals.append(running_outstanding)

        daily_metrics = pl.DataFrame({
            "date": days,
            "purchase_volume": [daily_events_dict[d]["sales"] for d in days],
            "payment_volume": [daily_events_dict[d]["payments"] for d in days],
            "returns_amount": [daily_events_dict[d]["returns"] for d in days],
            "outstanding": outstanding_vals
        })

        # Process snapshots/scores
        snap_dict = {}
        for row in snapshots_rows:
            sdate = normalize_temporal_to_date(row[0])
            snap_dict[sdate] = {
                "health": float(row[1] or curr_health),
                "risk": float(row[2] or curr_risk),
                "trust": float(row[3] or curr_trust),
                "growth": float(row[4] or curr_growth),
                "collection": float(row[5] or curr_coll)
            }

        snap_health, snap_risk, snap_trust, snap_growth, snap_coll = [], [], [], [], []
        last_h, last_r, last_t, last_g, last_c = curr_health, curr_risk, curr_trust, curr_growth, curr_coll
        for d in days:
            if d in snap_dict:
                last_h = snap_dict[d]["health"]
                last_r = snap_dict[d]["risk"]
                last_t = snap_dict[d]["trust"]
                last_g = snap_dict[d]["growth"]
                last_c = snap_dict[d]["collection"]
            snap_health.append(last_h)
            snap_risk.append(last_r)
            snap_trust.append(last_t)
            snap_growth.append(last_g)
            snap_coll.append(last_c)

        daily_scores = pl.DataFrame({
            "date": days,
            "health_score": snap_health,
            "risk_score": snap_risk,
            "trust_score": snap_trust,
            "growth_score": snap_growth,
            "collection_score": snap_coll
        })

        # Process alerts
        alert_days_dict = {}
        for d in days:
            alert_days_dict[d] = 0
        for adt in alerts_rows:
            adate = adt.date() if isinstance(adt, datetime) else adt
            if adate in alert_days_dict:
                alert_days_dict[adate] += 1

        daily_alerts = pl.DataFrame({
            "date": days,
            "alerts_count": [alert_days_dict[d] for d in days]
        })

        # Join datasets using polars
        df = daily_grid.join(daily_metrics, on="date", how="left")
        df = df.join(daily_scores, on="date", how="left")
        df = df.join(daily_alerts, on="date", how="left")

        # Dynamically bucket by granularity
        df = df.with_columns(pl.col("date").cast(pl.Datetime))
        every = {"daily": "1d", "weekly": "1w", "monthly": "1mo"}.get(granularity, "1mo")
        
        agg_df = df.sort("date").group_by_dynamic("date", every=every).agg([
            pl.col("purchase_volume").sum(),
            pl.col("payment_volume").sum(),
            pl.col("returns_amount").sum(),
            pl.col("outstanding").last(),
            pl.col("health_score").mean(),
            pl.col("risk_score").mean(),
            pl.col("trust_score").mean(),
            pl.col("growth_score").mean(),
            pl.col("collection_score").mean(),
            pl.col("alerts_count").sum()
        ])

        # Write to materialized view table (Clean & Insert)
        # 1. Clean existing records for this customer and granularity
        await self.db.execute(
            delete(CustomerGraphMV).where(
                CustomerGraphMV.customer_id == customer_id,
                CustomerGraphMV.granularity == granularity
            )
        )

        timeline = []
        for row in agg_df.to_dicts():
            dt = row["date"]
            if granularity == "monthly":
                ts_str = dt.strftime("%Y-%m")
            elif granularity == "weekly":
                ts_str = dt.strftime("%Y-W%V")
            else:
                ts_str = dt.strftime("%Y-%m-%d")

            mv_record = CustomerGraphMV(
                id=str(uuid.uuid4()),
                customer_id=customer_id,
                timestamp=ts_str,
                granularity=granularity,
                purchase_volume=float(row["purchase_volume"] or 0.0),
                payment_volume=float(row["payment_volume"] or 0.0),
                outstanding=float(row["outstanding"] or 0.0),
                health_score=float(row["health_score"] or 0.5),
                risk_score=float(row["risk_score"] or 0.5),
                trust_score=float(row["trust_score"] or 0.5),
                growth_score=float(row["growth_score"] or 0.5),
                collection_score=float(row["collection_score"] or 0.5),
                alerts_count=int(row["alerts_count"] or 0),
                returns_amount=float(row["returns_amount"] or 0.0)
            )
            self.db.add(mv_record)
            timeline.append({
                "timestamp": ts_str,
                "purchase_volume": mv_record.purchase_volume,
                "payment_volume": mv_record.payment_volume,
                "outstanding": mv_record.outstanding,
                "health_score": mv_record.health_score,
                "risk_score": mv_record.risk_score,
                "trust_score": mv_record.trust_score,
                "growth_score": mv_record.growth_score,
                "collection_score": mv_record.collection_score,
                "alerts_count": mv_record.alerts_count,
                "returns_amount": mv_record.returns_amount
            })

        await self.db.commit()
        return timeline

    async def refresh_portfolio_graphs(
        self, granularity: str = "monthly", window_days: int = 365
    ) -> list[dict[str, Any]]:
        # 1. Resolve date range
        now = datetime.now(UTC).date()
        end_date = now
        start_date = end_date - timedelta(days=window_days)

        # 2. Get global opening outstanding balance
        opening_stmt = select(
            func.sum(
                func.coalesce(
                    EventLedger.amount * func.case(
                        (EventLedger.event_type.in_(["SALE", "OPENING_BALANCE"]), 1.0),
                        else_=-1.0
                    ),
                    0.0
                )
            )
        ).where(
            EventLedger.event_date < start_date,
            not_(EventLedger.is_voided),
            EventLedger.is_ok == 0
        )
        opening_res = await self.db.execute(opening_stmt)
        opening_outstanding = float(opening_res.scalar() or 0.0)

        # 3. Get all daily events in window
        events_stmt = select(
            EventLedger.event_date,
            EventLedger.event_type,
            func.sum(EventLedger.amount)
        ).where(
            EventLedger.event_date >= start_date,
            EventLedger.event_date <= end_date,
            not_(EventLedger.is_voided),
            EventLedger.is_ok == 0
        ).group_by(EventLedger.event_date, EventLedger.event_type).order_by(EventLedger.event_date.asc())
        events_res = await self.db.execute(events_stmt)
        events_rows = events_res.all()

        # 4. Get all critical/major alerts history
        alerts_stmt = select(Alert.created_at).where(
            Alert.alert_severity.in_(["CRITICAL", "MAJOR", "HIGH"]),
            Alert.status == "ACTIVE",
            Alert.created_at >= datetime.combine(start_date, time.min, tzinfo=UTC),
            Alert.created_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
        alerts_res = await self.db.execute(alerts_stmt)
        alerts_rows = [r[0] for r in alerts_res.all()]

        # 5. Get historical snapshots for collection backlog calculation
        # Group by snapshot_date and calculate sum of outstanding where collection_score > 0.5
        collection_stmt = select(
            FeatureSnapshot.snapshot_date,
            func.sum(FeatureSnapshot.outstanding_current)
        ).where(
            FeatureSnapshot.collection_score > 0.5,
            FeatureSnapshot.snapshot_date >= start_date,
            FeatureSnapshot.snapshot_date <= end_date
        ).group_by(FeatureSnapshot.snapshot_date).order_by(FeatureSnapshot.snapshot_date.asc())
        collection_res = await self.db.execute(collection_stmt)
        collection_rows = collection_res.all()

        # Fallback collection backlog from CustomerIntelligence if snapshots are empty
        fallback_backlog = 0.0
        intel_stmt = select(func.sum(CustomerIntelligence.outstanding_current)).where(
            CustomerIntelligence.collection_score > 0.5
        )
        intel_res = await self.db.execute(intel_stmt)
        fallback_backlog = float(intel_res.scalar() or 0.0)

        # Reconstruct daily grid
        days = []
        curr = start_date
        while curr <= end_date:
            days.append(curr)
            curr += timedelta(days=1)

        daily_grid = pl.DataFrame({"date": days})

        # Process events
        daily_events_dict = {}
        for d in days:
            daily_events_dict[d] = {"sales": 0.0, "payments": 0.0, "returns": 0.0}

        for row in events_rows:
            edate = normalize_temporal_to_date(row[0])
            etype = row[1]
            eamt = float(row[2])
            if edate in daily_events_dict:
                if etype in ["SALE", "OPENING_BALANCE"]:
                    daily_events_dict[edate]["sales"] += eamt
                elif etype in ["PAYMENT", "DISCOUNT"]:
                    daily_events_dict[edate]["payments"] += eamt
                elif etype == "RETURN":
                    daily_events_dict[edate]["returns"] += eamt

        # Calculate daily rolling outstanding
        outstanding_vals = []
        running_outstanding = opening_outstanding
        for d in days:
            running_outstanding += (
                daily_events_dict[d]["sales"]
                - daily_events_dict[d]["payments"]
                - daily_events_dict[d]["returns"]
            )
            outstanding_vals.append(running_outstanding)

        daily_metrics = pl.DataFrame({
            "date": days,
            "portfolio_purchase": [daily_events_dict[d]["sales"] for d in days],
            "portfolio_payment": [daily_events_dict[d]["payments"] for d in days],
            "portfolio_outstanding": outstanding_vals
        })

        # Process alerts
        alert_days_dict = {}
        for d in days:
            alert_days_dict[d] = 0
        for adt in alerts_rows:
            adate = adt.date() if isinstance(adt, datetime) else adt
            if adate in alert_days_dict:
                alert_days_dict[adate] += 1

        daily_alerts = pl.DataFrame({
            "date": days,
            "critical_alerts": [alert_days_dict[d] for d in days]
        })

        # Process collection backlog
        backlog_dict = {}
        for row in collection_rows:
            bdate = normalize_temporal_to_date(row[0])
            backlog_dict[bdate] = float(row[1] or 0.0)

        backlog_vals = []
        last_b = fallback_backlog
        for d in days:
            if d in backlog_dict:
                last_b = backlog_dict[d]
            backlog_vals.append(last_b)

        daily_backlog = pl.DataFrame({
            "date": days,
            "collection_backlog": backlog_vals
        })

        # Join datasets using polars
        df = daily_grid.join(daily_metrics, on="date", how="left")
        df = df.join(daily_alerts, on="date", how="left")
        df = df.join(daily_backlog, on="date", how="left")

        # Group by dynamic granularity
        df = df.with_columns(pl.col("date").cast(pl.Datetime))
        every = {"daily": "1d", "weekly": "1w", "monthly": "1mo"}.get(granularity, "1mo")
        
        agg_df = df.sort("date").group_by_dynamic("date", every=every).agg([
            pl.col("portfolio_purchase").sum(),
            pl.col("portfolio_payment").sum(),
            pl.col("portfolio_outstanding").last(),
            pl.col("critical_alerts").sum(),
            pl.col("collection_backlog").mean()
        ])

        # Write to materialized view table (Clean & Insert)
        await self.db.execute(
            delete(PortfolioGraphMV).where(
                PortfolioGraphMV.granularity == granularity
            )
        )

        timeline = []
        for row in agg_df.to_dicts():
            dt = row["date"]
            if granularity == "monthly":
                ts_str = dt.strftime("%Y-%m")
            elif granularity == "weekly":
                ts_str = dt.strftime("%Y-W%V")
            else:
                ts_str = dt.strftime("%Y-%m-%d")

            mv_record = PortfolioGraphMV(
                id=str(uuid.uuid4()),
                timestamp=ts_str,
                granularity=granularity,
                portfolio_purchase=float(row["portfolio_purchase"] or 0.0),
                portfolio_payment=float(row["portfolio_payment"] or 0.0),
                portfolio_outstanding=float(row["portfolio_outstanding"] or 0.0),
                critical_alerts=int(row["critical_alerts"] or 0),
                collection_backlog=float(row["collection_backlog"] or 0.0)
            )
            self.db.add(mv_record)
            timeline.append({
                "timestamp": ts_str,
                "portfolio_purchase": mv_record.portfolio_purchase,
                "portfolio_payment": mv_record.portfolio_payment,
                "portfolio_outstanding": mv_record.portfolio_outstanding,
                "critical_alerts": mv_record.critical_alerts,
                "collection_backlog": mv_record.collection_backlog
            })

        await self.db.commit()
        return timeline
