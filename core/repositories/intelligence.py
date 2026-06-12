from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import desc, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import CustomerIntelligence, EventLedger


class CustomerResolutionError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)


class IntelligenceRepository:
    """
    Central repository for serving fresh intelligence.
    Ensures synchronization between the runtime state and the API responses.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_customer_state(self, customer_id: str) -> CustomerIntelligence | None:
        """
        Fetches the latest materialized intelligence from PostgreSQL.
        """
        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res = await self.db.execute(stmt)
        intelligence = res.scalar_one_or_none()
        return intelligence

    async def persist_intelligence(self, intelligence_data: dict):
        """
        Persists or updates the materialized intelligence for a customer.
        Includes lightweight forensic summaries and diagnostics.
        """
        from sqlalchemy import JSON
        customer_id = intelligence_data["customer_id"]
        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res = await self.db.execute(stmt)
        intelligence = res.scalar_one_or_none()

        if not intelligence:
            intelligence = CustomerIntelligence(customer_id=customer_id)
            self.db.add(intelligence)

        # Update fields selectively: Sanitize only for JSON columns
        for key, value in intelligence_data.items():
            if hasattr(intelligence, key):
                column = CustomerIntelligence.__table__.columns.get(key)
                # Check if column type is JSON or JSONB
                if column is not None and isinstance(column.type, JSON):
                    setattr(intelligence, key, self._sanitize_for_json(value))
                else:
                    setattr(intelligence, key, value)

        intelligence.last_updated = datetime.now(UTC)

        # Also update customers.behavioral_profile if the customers table exists
        try:
            import uuid
            from sqlalchemy import update
            from core.storage.postgres import get_reflected_table

            customers_tbl = await get_reflected_table("customers", self.db)
            if customers_tbl is not None:
                # Storing scores in behavioral_profile
                profile_payload = {
                    "health_score": intelligence_data.get("health_score"),
                    "risk_score": intelligence_data.get("risk_score"),
                    "growth_score": intelligence_data.get("growth_score"),
                    "trust_score": intelligence_data.get("trust_score"),
                    "opportunity_score": intelligence_data.get("opportunity_score"),
                    "credit_score": intelligence_data.get("credit_score"),
                    "collection_score": intelligence_data.get("collection_score"),
                    "relationship_score": intelligence_data.get("relationship_score"),
                    "state": intelligence_data.get("state"),
                    "outstanding_current": intelligence_data.get("outstanding_current"),
                    "contribution_current": intelligence_data.get("contribution_current"),
                    "v2_scores": intelligence_data.get("v2_scores", {}),
                    "last_updated": datetime.now(UTC).isoformat()
                }
                stmt_cust = (
                    update(customers_tbl)
                    .where(customers_tbl.c.id == uuid.UUID(customer_id))
                    .values(behavioral_profile=self._sanitize_for_json(profile_payload))
                )
                await self.db.execute(stmt_cust)
        except Exception as e:
            logger.warning(f"Could not update customers.behavioral_profile for {customer_id}: {e}")


    async def get_timeline(self, customer_id: str) -> list[dict]:
        """
        Fetches the fresh event ledger from PostgreSQL.
        """
        logger.debug(f"Serving timeline for {customer_id} from PostgreSQL")
        stmt = (
            select(EventLedger)
            .where(
                EventLedger.customer_id == customer_id, 
                not_(EventLedger.is_voided),
                EventLedger.event_date <= func.current_date()
            )
            .order_by(desc(EventLedger.event_date), desc(EventLedger.customer_sequence_number))
        )
        res = await self.db.execute(stmt)
        rows = res.scalars().all()
        return [
            {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "event_date": row.event_date.isoformat() if row.event_date else None,
                "amount": row.amount,
                "is_ok": row.is_ok,
                "customer_sequence": row.customer_sequence_number,
                "metadata": row.metadata_,
            }
            for row in rows
        ]

    async def get_latest_ledger_date(self) -> date | None:
        """
        Retrieves the latest event date from the EventLedger.
        Used as a data-driven anchor for analysis windows.
        MANDATORY: Filters out future-dated events.
        """
        stmt = select(func.max(EventLedger.event_date)).where(
            not_(EventLedger.is_voided),
            EventLedger.event_date <= func.current_date()
        )
        res = await self.db.execute(stmt)
        return res.scalar()

    async def get_total_sales_in_window(
        self, start_date: datetime, end_date: datetime, customer_id: str | None = None
    ) -> float:
        """
        Efficiently aggregates SALE amounts from event_ledger for a specific window.
        Supports optional customer_id filtering for specific vs organizational contribution.
        MANDATORY: Uses ALL purchase events (ignores is_ok) for commercial volume calculation.
        """
        stmt = select(func.sum(EventLedger.amount)).where(
            EventLedger.event_type == "SALE",
            EventLedger.event_date >= start_date,
            EventLedger.event_date <= end_date,
            EventLedger.event_date <= func.current_date(),
            not_(EventLedger.is_voided),
            # EventLedger.is_ok == 0,  <-- REMOVED: Commercial reality uses all sales
        )

        if customer_id:
            stmt = stmt.where(EventLedger.customer_id == customer_id)

        res = await self.db.execute(stmt)
        return float(res.scalar() or 0.0)

    async def get_bulk_total_sales_in_window(
        self, start_date: datetime, end_date: datetime, customer_ids: list[str]
    ) -> dict[str, float]:
        """
        Aggregates SALE amounts for a list of customers in a single query.
        Returns a mapping of customer_id -> total_sales.
        """
        if not customer_ids:
            return {}

        stmt = (
            select(
                EventLedger.customer_id, 
                func.sum(EventLedger.amount).label("total_sales")
            )
            .where(
                EventLedger.event_type == "SALE",
                EventLedger.event_date >= start_date,
                EventLedger.event_date <= end_date,
                EventLedger.event_date <= func.current_date(),
                not_(EventLedger.is_voided),
                EventLedger.customer_id.in_(customer_ids),
            )
            .group_by(EventLedger.customer_id)
        )

        res = await self.db.execute(stmt)
        return {row[0]: float(row[1] or 0.0) for row in res.fetchall()}

    async def get_org_distribution_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, float]:
        """
        Calculates organization-wide distribution metrics (P95) for normalization.
        Returns P95 billing volume and P95 participation density.
        """
        # 1. Fetch sales volume per customer
        sales_stmt = (
            select(
                EventLedger.customer_id, 
                func.sum(EventLedger.amount).label("total_sales")
            )
            .where(
                EventLedger.event_type == "SALE",
                EventLedger.event_date >= start_date,
                EventLedger.event_date <= end_date,
                not_(EventLedger.is_voided),
            )
            .group_by(EventLedger.customer_id)
        )
        sales_res = await self.db.execute(sales_stmt)
        sales_data = [row[1] for row in sales_res.fetchall()]

        # 2. Fetch participation density per customer
        # We need distinct dates of SALES per customer in the window
        density_stmt = (
            select(
                EventLedger.customer_id,
                func.count(func.distinct(EventLedger.event_date)).label("active_days"),
            )
            .where(
                EventLedger.event_type == "SALE",
                EventLedger.event_date >= start_date,
                EventLedger.event_date <= end_date,
                not_(EventLedger.is_voided),
            )
            .group_by(EventLedger.customer_id)
        )
        density_res = await self.db.execute(density_stmt)
        
        window_days = (end_date - start_date).days or 1
        densities = [row[1] / window_days for row in density_res.fetchall()]

        if not sales_data or not densities:
            return {"p95_billing": 100000.0, "p95_density": 0.4, "avg_org_billing": 10000.0}

        import polars as pl
        
        sales_q = pl.Series("sales", sales_data)
        density_q = pl.Series("density", densities)

        return {
            "p95_billing": float(sales_q.quantile(0.95) or 100000.0),
            "p95_density": float(density_q.quantile(0.95) or 0.4),
            "avg_org_billing": float(sales_q.mean() or 10000.0),
        }

    async def get_bulk_avg_monthly_billing(
        self, start_date: datetime, end_date: datetime, customer_ids: list[str]
    ) -> dict[str, float]:
        """
        Calculates average monthly billing for a list of customers.
        Used for individualized clearance discipline.
        """
        if not customer_ids:
            return {}

        stmt = (
            select(
                EventLedger.customer_id, 
                func.sum(EventLedger.amount).label("total_sales")
            )
            .where(
                EventLedger.event_type == "SALE",
                EventLedger.event_date >= start_date,
                EventLedger.event_date <= end_date,
                not_(EventLedger.is_voided),
                EventLedger.customer_id.in_(customer_ids),
            )
            .group_by(EventLedger.customer_id)
        )

        res = await self.db.execute(stmt)
        window_months = ((end_date - start_date).days / 30.0) or 1.0
        
        return {row[0]: float(row[1] or 0.0) / window_months for row in res.fetchall()}

    async def get_bulk_latest_customer_states(self, customer_ids: list[str]) -> dict[str, CustomerIntelligence]:
        """
        Fetches the latest intelligence records for a list of customers in a single query.
        """
        if not customer_ids:
            return {}

        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id.in_(customer_ids))
        res = await self.db.execute(stmt)
        return {c.customer_id: c for c in res.scalars().all()}

    def _sanitize_for_json(self, obj: Any) -> Any:
        """Recursively sanitizes objects for JSONB persistence (handles datetimes)."""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_for_json(v) for v in obj]
        if hasattr(obj, "to_dict"):
            return self._sanitize_for_json(obj.to_dict())
        return obj
