from datetime import date, datetime
from typing import Any

import polars as pl
from sqlalchemy import MetaData, asc, case, desc, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import (
    CustomerIntelligence,
    EventLedger,
)
from core.utils.temporal import normalize_temporal_to_str

_metadata = MetaData()


class DashboardRepository:
    """
    Dedicated repository for the Dashboard API layer.
    Encapsulates all optimized SQL and Polars calculations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_outstanding_and_overdue_amounts(self, reference_date: date, allowed_credit_days: int = 60) -> dict[str, dict[str, float]]:
        """
        Reconstructs outstanding and overdue dollar amounts per customer up to reference_date
        using precise FIFO matching.
        Mandatory: Queries ONLY event_ledger. Raw tables are prohibited for serving.
        """
        # 1. Fetch all relevant events up to the reference date
        stmt = (
            select(
                EventLedger.customer_id,
                EventLedger.event_date,
                EventLedger.amount,
                EventLedger.event_type
            )
            .where(
                not_(EventLedger.is_voided),
                EventLedger.is_ok == 0,
                EventLedger.event_date <= reference_date,
                EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT", "OPENING_BALANCE"])
            )
            .order_by(
                EventLedger.customer_id,
                EventLedger.event_date,
                EventLedger.global_sequence_number
            )
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        from collections import defaultdict
        cust_events = defaultdict(list)
        for cid, edate, amt, etype in rows:
            cust_events[cid].append((edate, amt, etype))

        result = {}
        for cid, evs in cust_events.items():
            bills = []  # list of [bill_date, remaining_amount]
            for edate, amt, etype in evs:
                if isinstance(edate, datetime):
                    edate = edate.date()
                
                if etype in ("SALE", "OPENING_BALANCE"):
                    bills.append([edate, amt])
                elif etype in ("PAYMENT", "RETURN", "DISCOUNT"):
                    credit = amt
                    while credit > 0 and bills:
                        if credit >= bills[0][1]:
                            credit -= bills[0][1]
                            bills.pop(0)
                        else:
                            bills[0][1] -= credit
                            credit = 0

            outstanding_amt = 0.0
            overdue_amt = 0.0
            for b_date, b_rem in bills:
                if b_rem > 0:
                    outstanding_amt += b_rem
                    age = (reference_date - b_date).days
                    if age > allowed_credit_days:
                        overdue_amt += b_rem

            result[cid] = {
                "outstanding": round(outstanding_amt, 2),
                "overdue": round(overdue_amt, 2)
            }
        return result

    async def get_executive_overview(
        self, s_date: date, e_date: date, prev_s_date: date, prev_e_date: date
    ) -> dict[str, Any]:
        """
        Gathers KPIs for the Executive Overview card deck.
        Mandatory: Uses customer_intelligence for default windows.
        Historical Correctness: Uses EventLedger reconstruction for custom/past end_dates.
        """
        # 1. Resolve Anchor Date (Is this the default/latest state?)
        latest_ledger_stmt = select(func.max(EventLedger.event_date)).where(
            not_(EventLedger.is_voided),
            EventLedger.event_date <= func.current_date()
        )
        latest_ledger_res = await self.db.execute(latest_ledger_stmt)
        last_data_date = latest_ledger_res.scalar()

        is_latest = e_date >= (last_data_date or date.today())

        # 2. Sourcing Strategy for Outstanding
        if is_latest:
            # OPTIMIZED PATH: Query materialized serving table for current organization exposure
            intel_agg_stmt = select(
                func.sum(CustomerIntelligence.outstanding_current).label("outstanding_total"),
                func.sum(CustomerIntelligence.outstanding_previous).label("outstanding_previous"),
            )
            intel_res = await self.db.execute(intel_agg_stmt)
            intel_row = intel_res.mappings().one()
            out_total = float(intel_row["outstanding_total"] or 0.0)
            out_prev = float(intel_row["outstanding_previous"] or 0.0)
        else:
            # HISTORICAL PATH: Reconstruct balance at e_date and prev_e_date from ledger
            # (Matches Part 2 Directive: Runtime calculation allowed for custom windows)
            async def get_org_balance(ref_date: date) -> float:
                balance_stmt = select(
                    func.sum(
                        case(
                            (EventLedger.event_type.in_(["SALE", "OPENING_BALANCE"]), EventLedger.amount),
                            else_=-EventLedger.amount
                        )
                    )
                ).where(
                    EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT", "OPENING_BALANCE"]),
                    EventLedger.event_date <= ref_date,
                    not_(EventLedger.is_voided),
                    EventLedger.is_ok == 0
                )
                res = await self.db.execute(balance_stmt)
                return float(res.scalar() or 0.0)
            
            out_total = await get_org_balance(e_date)
            out_prev = await get_org_balance(prev_e_date)

        # 3. Base Aggregates for Health (Always from serving layer for consistent scoring)
        health_agg_stmt = select(
            func.count(CustomerIntelligence.customer_id).label("total_customers"),
            func.avg(CustomerIntelligence.health_score).label("avg_health"),
            func.avg(CustomerIntelligence.health_previous).label("avg_health_prev"),
        )
        health_res = await self.db.execute(health_agg_stmt)
        health_agg = health_res.mappings().one()

        # 4. Window-Specific Totals (Activity always from Ledger)
        window_agg_stmt = select(
            func.sum(case((EventLedger.event_type == "SALE", EventLedger.amount), else_=0.0)).label("sales_total"),
            func.sum(case((EventLedger.event_type == "PAYMENT", EventLedger.amount), else_=0.0)).label("collections_total")
        ).where(
            EventLedger.event_date >= s_date,
            EventLedger.event_date <= e_date,
            not_(EventLedger.is_voided),
        )
        window_res = await self.db.execute(window_agg_stmt)
        window_agg = window_res.mappings().one()

        prev_window_agg_stmt = select(
            func.sum(case((EventLedger.event_type == "SALE", EventLedger.amount), else_=0.0)).label("sales_previous"),
            func.sum(case((EventLedger.event_type == "PAYMENT", EventLedger.amount), else_=0.0)).label("collections_previous")
        ).where(
            EventLedger.event_date >= prev_s_date,
            EventLedger.event_date <= prev_e_date,
            not_(EventLedger.is_voided),
        )
        prev_window_res = await self.db.execute(prev_window_agg_stmt)
        prev_window_agg = prev_window_res.mappings().one()

        # 5. Delta and Health Calculation
        health_curr = round((health_agg["avg_health"] or 0.0) * 100.0, 2)
        health_prev = round((health_agg["avg_health_prev"] or 0.0) * 100.0, 2)

        def calculate_delta(curr, prev):
            if not prev:
                return 0.0 if not curr else 100.0
            return round(((curr - prev) / prev) * 100.0, 2)

        return {
            "active_customers": int(health_agg["total_customers"] or 0),
            "sales_total": round(window_agg["sales_total"] or 0.0, 2),
            "sales_previous": round(prev_window_agg["sales_previous"] or 0.0, 2),
            "sales_delta": calculate_delta(window_agg["sales_total"], prev_window_agg["sales_previous"]),
            "collections_total": round(window_agg["collections_total"] or 0.0, 2),
            "collections_previous": round(prev_window_agg["collections_previous"] or 0.0, 2),
            "collections_delta": calculate_delta(window_agg["collections_total"], prev_window_agg["collections_previous"]),
            "outstanding_total": round(out_total, 2),
            "outstanding_previous": round(out_prev, 2),
            "outstanding_delta": calculate_delta(out_total, out_prev),
            "overdue_total": 0.0,
            "overdue_previous": 0.0,
            "overdue_delta": 0.0,
            "commercial_health_index": health_curr,
            "commercial_health_previous": health_prev,
            "commercial_health_delta": round(health_curr - health_prev, 2),
            "credit_limit_total": 0.0,
            "organization_contribution_total": round(window_agg["sales_total"] or 0.0, 2),
            "last_data_date": last_data_date.isoformat() if last_data_date else None,
        }

    async def get_commercial_flow(
        self, s_date: date, e_date: date, granularity: str
    ) -> list[dict[str, Any]]:
        """
        Reconstructs longitudinal sales, payments, and outstanding balances.
        Mandatory: Queries ONLY event_ledger.
        """
        # 1. Reconstruct Opening Outstanding Balance (before s_date)
        opening_stmt = select(
            func.sum(
                case(
                    (EventLedger.event_type.in_(["SALE", "OPENING_BALANCE"]), EventLedger.amount),
                    else_=-EventLedger.amount
                )
            )
        ).where(
            EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT", "OPENING_BALANCE"]),
            EventLedger.event_date < s_date,
            not_(EventLedger.is_voided),
            EventLedger.is_ok == 0
        )
        opening_res = await self.db.execute(opening_stmt)
        opening_outstanding = float(opening_res.scalar() or 0.0)

        # 2. Fetch Aggregated Ledger Events in window
        stmt = (
            select(
                EventLedger.event_date,
                func.sum(case((EventLedger.event_type == "SALE", EventLedger.amount), else_=0.0)).label("purchase_added"),
                func.sum(case((EventLedger.event_type.in_(["PAYMENT", "DISCOUNT"]), EventLedger.amount), else_=0.0)).label("payment_received"),
                func.sum(case((EventLedger.event_type == "RETURN", EventLedger.amount), else_=0.0)).label("rg_adjustment")
            )
            .where(
                EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT"]),
                EventLedger.event_date >= s_date,
                EventLedger.event_date <= e_date,
                EventLedger.event_date <= func.current_date(),
                not_(EventLedger.is_voided),
                EventLedger.is_ok == 0
            )
            .group_by(EventLedger.event_date)
            .order_by(asc(EventLedger.event_date))
        )
        res = await self.db.execute(stmt)
        rows = res.mappings().all()

        if not rows:
            df = pl.DataFrame(
                schema={
                    "date": pl.Date,
                    "purchase_added": pl.Float64,
                    "payment_received": pl.Float64,
                    "rg_adjustment": pl.Float64,
                }
            )
        else:
            df = pl.DataFrame([dict(r) for r in rows])
            df = df.with_columns(pl.col("event_date").alias("date")).drop("event_date")

        # 3. Create Daily Grid
        date_range = pl.date_range(s_date, e_date, "1d", eager=True).alias("date")
        daily_grid_df = pl.DataFrame(date_range).with_columns(pl.col("date").cast(pl.Datetime))

        # 4. Map Daily Values
        if not df.is_empty():
            df = df.with_columns(pl.col("date").cast(pl.Datetime))
            daily_df = daily_grid_df.join(df, on="date", how="left").fill_null(0.0)
        else:
            daily_df = daily_grid_df.with_columns(
                pl.lit(0.0).alias("purchase_added"),
                pl.lit(0.0).alias("payment_received"),
                pl.lit(0.0).alias("rg_adjustment"),
            )

        # 5. Reconstruct outstanding daily balances
        daily_df = daily_df.with_columns(
            (pl.col("purchase_added") - pl.col("payment_received") - pl.col("rg_adjustment")).alias("daily_balance_delta")
        )
        daily_df = daily_df.with_columns(
            (opening_outstanding + pl.col("daily_balance_delta").cum_sum()).alias("closing_outstanding")
        )

        # 6. Aggregate by Granularity
        every = {"daily": "1d", "weekly": "1w", "monthly": "1mo"}[granularity]
        
        # Sort and ensure date is datetime for group_by_dynamic
        daily_df = daily_df.sort("date")
        
        # CRITICAL: Polars group_by_dynamic works on Datetime columns
        agg_df = (
            daily_df.group_by_dynamic("date", every=every)
            .agg(
                [
                    pl.col("purchase_added").sum(),
                    pl.col("payment_received").sum(),
                    pl.col("rg_adjustment").sum(),
                    pl.col("closing_outstanding").last(),
                ]
            )
        )

        return [
            {
                "period": normalize_temporal_to_str(row["date"]),
                "sales": round(row["purchase_added"], 2),
                "payments": round(row["payment_received"] + row["rg_adjustment"], 2),
                "outstanding": round(row["closing_outstanding"], 2),
            }
            for row in agg_df.to_dicts()
        ]

    async def get_aging_distribution(self, reference_date: date) -> dict[str, dict[str, float]]:
        """
        Reconstructs aging buckets.
        Mandatory: Queries ONLY event_ledger.
        """
        # 1. Fetch all events up to reference_date
        stmt = (
            select(
                EventLedger.customer_id,
                EventLedger.event_date,
                EventLedger.amount,
                EventLedger.event_type
            )
            .where(
                not_(EventLedger.is_voided),
                EventLedger.is_ok == 0,
                EventLedger.event_date <= reference_date,
                EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT", "OPENING_BALANCE"])
            )
            .order_by(
                EventLedger.customer_id,
                EventLedger.event_date,
                EventLedger.global_sequence_number
            )
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        from collections import defaultdict
        cust_events = defaultdict(list)
        for cid, edate, amt, etype in rows:
            cust_events[cid].append((edate, amt, etype))

        buckets = {
            "current": 0.0,
            "0_30": 0.0,
            "31_60": 0.0,
            "61_90": 0.0,
            "91_120": 0.0,
            "120_plus": 0.0
        }

        total_outstanding = 0.0
        for _cid, evs in cust_events.items():
            bills = []
            for edate, amt, etype in evs:
                if isinstance(edate, datetime):
                    edate = edate.date()
                if etype in ("SALE", "OPENING_BALANCE"):
                    bills.append([edate, amt])
                elif etype in ("PAYMENT", "RETURN", "DISCOUNT"):
                    credit = amt
                    while credit > 0 and bills:
                        if credit >= bills[0][1]:
                            credit -= bills[0][1]
                            bills.pop(0)
                        else:
                            bills[0][1] -= credit
                            credit = 0

            for b_date, b_rem in bills:
                if b_rem <= 0:
                    continue
                total_outstanding += b_rem
                age = (reference_date - b_date).days
                if age <= 0:
                    buckets["current"] += b_rem
                elif age <= 30:
                    buckets["0_30"] += b_rem
                elif age <= 60:
                    buckets["31_60"] += b_rem
                elif age <= 90:
                    buckets["61_90"] += b_rem
                elif age <= 120:
                    buckets["91_120"] += b_rem
                else:
                    buckets["120_plus"] += b_rem

        response_data = {}
        for key, amt in buckets.items():
            pct = (amt / total_outstanding * 100.0) if total_outstanding > 0 else 0.0
            response_data[key] = {
                "amount": round(amt, 2),
                "percentage": round(pct, 2)
            }
        return response_data

    async def get_state_distribution(self) -> dict[str, dict[str, Any]]:
        """Computes customer health state distribution and percentages."""
        stmt = select(
            CustomerIntelligence.customer_id,
            CustomerIntelligence.state
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        counts = {
            "HEALTHY": 0,
            "MONITOR": 0,
            "CONTRACT": 0,
            "LIQUIDITY_STRESS": 0
        }

        for _cid, b_state in rows:
            if b_state == "declining":
                segment = "LIQUIDITY_STRESS"
            elif b_state == "inactive":
                segment = "CONTRACT"
            elif b_state == "irregular":
                segment = "MONITOR"
            else:
                segment = "HEALTHY"

            counts[segment] += 1

        total = sum(counts.values())
        response_data = {}
        for key, count in counts.items():
            pct = (count / total * 100.0) if total > 0 else 0.0
            response_data[key] = {
                "count": count,
                "percentage": round(pct, 2)
            }
        return response_data

    async def get_deteriorating_customers(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Fetches top deteriorating customers according to composite deterioration score.
        Queries ONLY customer_intelligence serving layer.
        """
        # Composite Deterioration Score (Higher = Worse)
        # Trust Loss (50%) + Collection Deterioration (30%) + Exposure Spike (20%)
        deterioration_score = (
            -(CustomerIntelligence.trust_score - CustomerIntelligence.trust_previous) * 0.50 +
            -(CustomerIntelligence.collection_score - CustomerIntelligence.collection_previous) * 0.30 +
            (CustomerIntelligence.outstanding_current - CustomerIntelligence.outstanding_previous) / func.nullif(func.abs(CustomerIntelligence.outstanding_previous), 0.0) * 0.20
        ).label("det_score")
 
        query = select(
            CustomerIntelligence,
            deterioration_score
        ).order_by(desc("det_score")).limit(limit)
        
        res = await self.db.execute(query)
        
        return [
            {
                "customer_id": r[0].customer_id,
                "customer_name": r[0].customer_name or r[0].customer_id,
                "city": r[0].city or "Unknown",
                "trust_score": round(r[0].trust_score or 0.0, 4),
                "trust_delta": round((r[0].trust_score or 0.0) - (r[0].trust_previous or 0.0), 4),
                "payment_delta": round((r[0].collection_score or 0.0) - (r[0].collection_previous or 0.0), 4),
                "repayment_health_delta": 0.0,
                "outstanding_delta": round((r[0].outstanding_current or 0.0) - (r[0].outstanding_previous or 0.0), 2),
                "state": r[0].state or "UNKNOWN",
                "grade": "A" if (r[0].trust_score or 0.0) >= 0.70 else "B" if (r[0].trust_score or 0.0) >= 0.55 else "C" if (r[0].trust_score or 0.0) >= 0.40 else "D",
                "last_purchased_at": r[0].last_purchase_date.isoformat() if r[0].last_purchase_date else None,
            } for r in res.all()
        ]
 
    async def get_improving_customers(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Fetches top improving customers sorted by largest improvement score.
        Queries ONLY customer_intelligence serving layer.
        """
        # Composite Improvement Score (Higher = Better)
        # Trust Increase (50%) + Collection Improvement (30%) + Outstanding Reduction (20%)
        improvement_score = (
            (CustomerIntelligence.trust_score - CustomerIntelligence.trust_previous) * 0.50 +
            (CustomerIntelligence.collection_score - CustomerIntelligence.collection_previous) * 0.30 +
            -(CustomerIntelligence.outstanding_current - CustomerIntelligence.outstanding_previous) / func.nullif(func.abs(CustomerIntelligence.outstanding_previous), 0.0) * 0.20
        ).label("imp_score")
 
        query = select(
            CustomerIntelligence,
            improvement_score
        ).order_by(desc("imp_score")).limit(limit)
        
        res = await self.db.execute(query)
 
        return [
            {
                "customer_id": r[0].customer_id,
                "customer_name": r[0].customer_name or r[0].customer_id,
                "city": r[0].city or "Unknown",
                "trust_score": round(r[0].trust_score or 0.0, 4),
                "trust_delta": round((r[0].trust_score or 0.0) - (r[0].trust_previous or 0.0), 4),
                "payment_delta": round((r[0].collection_score or 0.0) - (r[0].collection_previous or 0.0), 4),
                "repayment_health_delta": 0.0,
                "outstanding_delta": round((r[0].outstanding_current or 0.0) - (r[0].outstanding_previous or 0.0), 2),
                "state": r[0].state or "UNKNOWN",
                "grade": "A" if (r[0].trust_score or 0.0) >= 0.70 else "B" if (r[0].trust_score or 0.0) >= 0.55 else "C" if (r[0].trust_score or 0.0) >= 0.40 else "D",
                "last_purchased_at": r[0].last_purchase_date.isoformat() if r[0].last_purchase_date else None,
            } for r in res.all()
        ]

    async def get_high_risk_customers(self, reference_date: date, limit: int = 20) -> list[dict[str, Any]]:
        """
        Fetches top high credit-risk customers sorted by risk severity.
        Queries ONLY customer_intelligence serving layer.
        """
        # SQL-side Risk Severity Score (1 - trust_score)
        risk_score = (1.0 - func.coalesce(CustomerIntelligence.trust_score, 0.0)).label("risk_score")

        query = select(
            CustomerIntelligence,
            risk_score
        ).order_by(desc("risk_score")).limit(limit)
        
        res = await self.db.execute(query)

        return [
            {
                "customer_id": r[0].customer_id,
                "customer_name": r[0].customer_name or r[0].customer_id,
                "state": r[0].state or "UNKNOWN",
                "grade": "A" if (r[0].trust_score or 0.0) >= 0.70 else "B" if (r[0].trust_score or 0.0) >= 0.55 else "C" if (r[0].trust_score or 0.0) >= 0.40 else "D",
                "trust_score": round(r[0].trust_score or 0.0, 4),
                "outstanding_current": round(r[0].outstanding_current or 0.0, 2),
                "overdue_amount": 0.0,
                "credit_limit": 0.0,
                "credit_utilization": 0.0,
                "repayment_health_score": 0.0,
                "last_purchased_at": r[0].last_purchase_date.isoformat() if r[0].last_purchase_date else None,
            } for r in res.all()
        ]

    async def get_top_contributors(self, s_date: date, e_date: date, limit: int = 10) -> list[dict[str, Any]]:
        """
        Fetches top N customers ranked by commercial contribution.
        Mandatory: Uses contribution_current from customer_intelligence.
        """
        stmt = (
            select(CustomerIntelligence)
            .order_by(desc(CustomerIntelligence.contribution_current))
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        rows = res.scalars().all()

        return [
            {
                "customer_id": intel.customer_id,
                "customer_name": intel.customer_name or intel.customer_id,
                "contribution_percent": round(intel.contribution_current or 0.0, 2),
                "sales_total": 0.0,  # Absolute sales total not available in intelligence table
                "outstanding_current": round(intel.outstanding_current or 0.0, 2),
                "trust_score": round(intel.trust_score or 0.0, 4)
            }
            for intel in rows
        ]

    async def get_activity_summary(
        self, s_date: date, e_date: date, prev_s_date: date, prev_e_date: date
    ) -> dict[str, int]:
        """
        Calculates customer activity summary metrics.
        Uses ledger only for active/inactive transitions in the specified window.
        """
        # 1. Newly Active/Inactive (Requires ledger for window comparison)
        current_sales_stmt = select(EventLedger.customer_id).where(
            EventLedger.event_type == "SALE",
            EventLedger.event_date >= s_date,
            EventLedger.event_date <= e_date,
            not_(EventLedger.is_voided),
        ).distinct()
        curr_res = await self.db.execute(current_sales_stmt)
        curr_active = {r[0] for r in curr_res.all()}

        prev_sales_stmt = select(EventLedger.customer_id).where(
            EventLedger.event_type == "SALE",
            EventLedger.event_date >= prev_s_date,
            EventLedger.event_date <= prev_e_date,
            not_(EventLedger.is_voided),
        ).distinct()
        prev_res = await self.db.execute(prev_sales_stmt)
        prev_active = {r[0] for r in prev_res.all()}

        newly_active = len(curr_active - prev_active)
        newly_inactive = len(prev_active - curr_active)

        # 2. Improved/Deteriorated (Materialized in CustomerIntelligence)
        intel_stmt = select(
            func.count(case(((CustomerIntelligence.trust_score - CustomerIntelligence.trust_previous) > 0.05, 1), else_=None)).label("improved"),
            func.count(case(((CustomerIntelligence.trust_score - CustomerIntelligence.trust_previous) < -0.05, 1), else_=None)).label("deteriorated"),
        )
        intel_res = await self.db.execute(intel_stmt)
        intel_row = intel_res.mappings().one()

        return {
            "newly_active_customers": newly_active,
            "newly_inactive_customers": newly_inactive,
            "customers_improved": int(intel_row["improved"] or 0),
            "customers_deteriorated": int(intel_row["deteriorated"] or 0),
            "customers_with_new_overdue": 0,  # Removed dynamic overdue scan for performance
            "customers_near_credit_limit": 0
        }


