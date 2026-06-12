from datetime import date

import polars as pl
from loguru import logger
from sqlalchemy import func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import EventLedger


class LedgerContextService:
    """
    Provides scoped access to the historical event ledger.
    Ensures that intelligence engines have access to full customer context.
    """

    def __init__(self):
        pass

    async def load_customer_history(self, session: AsyncSession, customer_ids: list[str]) -> pl.DataFrame:
        """
        Loads the FULL historical event timeline for a list of customer IDs from PostgreSQL.
        MANDATORY: Live-injects opening_balance from raw_customers to ensure financial anchor is never missing.
        """
        if not customer_ids:
            return pl.DataFrame()

        logger.debug(f"Loading historical context for {len(customer_ids)} customers from PostgreSQL")

        # 1. Fetch Live Opening Balances from customers
        try:
            from core.storage.postgres import get_reflected_table
            customers_tbl = await get_reflected_table("customers", session)
            
            if customers_tbl is not None and "opening_balance" in customers_tbl.c:
                opening_stmt = select(customers_tbl.c.id, customers_tbl.c.opening_balance).where(
                    customers_tbl.c.id.in_(customer_ids)
                )
                opening_res = await session.execute(opening_stmt)
                opening_balances = {str(row.id): float(row.opening_balance or 0.0) for row in opening_res.all()}
            else:
                opening_balances = {}
        except Exception as e:
            logger.debug(f"Could not fetch live opening balances for {len(customer_ids)} customers: {e}")
            opening_balances = {}

        # 2. Fetch history from EventLedger, excluding any stale OPENING_BALANCE events
        stmt = select(EventLedger).where(
            EventLedger.customer_id.in_(customer_ids), 
            not_(EventLedger.is_voided),
            EventLedger.event_type != "OPENING_BALANCE",
            EventLedger.event_date <= func.current_date()
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        # Convert to dicts, taking care of metadata_
        dicts = []
        for r in rows:
            d = {
                "event_id": r.event_id,
                "customer_id": r.customer_id,
                "event_type": r.event_type,
                "event_date": r.event_date,
                "amount": r.amount,
                "is_ok": r.is_ok,
                "source_raw_id": r.source_raw_id,
                "source_table": r.source_table,
                "sequence_number": r.customer_sequence_number,
                "event_hash": r.event_hash,
                "metadata": r.metadata_ if r.metadata_ is not None else {},
                "discount_amount": 0.0,
                "rg_responsibility": "",
                "bank_name": None,
                "payment_mode": None,
                "batch_id": None,
                "behavioral_penalty_weight": None,
                "product_category": None,
                "product_name": None,
                "quantity": None,
                "tax_amount": None,
                "unit_price": None,
                "business_type": None,
                "registration_date": None,
                "credit_limit": None,
                "payment_terms_days": None,
                "return_reason": None,
            }
            if r.metadata_:
                for k, v in r.metadata_.items():
                    if k in [
                        "discount_amount", "quantity", "tax_amount", 
                        "unit_price", "credit_limit", "payment_terms_days"
                    ]:
                        d[k] = float(v) if v is not None else 0.0
                    elif k == "registration_date":
                        d[k] = date.fromisoformat(v) if v is not None else None
                    else:
                        d[k] = v
            dicts.append(d)

        # 3. Inject Live Opening Balance events as the chronological anchor
        for cid, balance in opening_balances.items():
            if balance != 0:
                dicts.append({
                    "event_id": f"OPENING_BALANCE_LIVE_{cid}",
                    "customer_id": cid,
                    "event_type": "OPENING_BALANCE",
                    "event_date": date(2000, 1, 1),
                    "amount": balance,
                    "is_ok": 0,
                    "source_raw_id": f"LIVE_{cid}",
                    "source_table": "raw_customers",
                    "sequence_number": -1, # Chronological anchor
                    "event_hash": None,
                    "metadata": {},
                    "discount_amount": 0.0,
                    "rg_responsibility": "",
                    "bank_name": None,
                    "payment_mode": None,
                    "batch_id": "LIVE_SYNC",
                    "behavioral_penalty_weight": 0.0,
                })

        # For backwards compatibility with engines that expect 'event_uid'
        df = pl.DataFrame(dicts, infer_schema_length=None)
        if not df.is_empty():
            df = df.with_columns(pl.col("event_id").alias("event_uid"))

        return df
