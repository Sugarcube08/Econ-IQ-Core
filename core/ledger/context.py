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
        MANDATORY: Live-injects opening_balance and static metadata from customers.
        """
        if not customer_ids:
            return pl.DataFrame()

        customer_ids = [str(cid) for cid in customer_ids]

        # 1. Fetch Live metadata from customers table
        customer_meta = {}
        opening_balances = {}
        try:
            from core.storage.postgres import get_reflected_table
            customers_tbl = await get_reflected_table("customers", session)
            
            if customers_tbl is not None:
                cols = [
                    customers_tbl.c.id,
                    customers_tbl.c.registration_date,
                    customers_tbl.c.business_type,
                    customers_tbl.c.credit_limit,
                    customers_tbl.c.payment_terms_days
                ]
                has_ob = "opening_balance" in customers_tbl.c
                if has_ob:
                    cols.append(customers_tbl.c.opening_balance)
                
                opening_stmt = select(*cols).where(
                    customers_tbl.c.id.in_(customer_ids)
                )
                opening_res = await session.execute(opening_stmt)
                for row in opening_res.all():
                    cid_str = str(row.id)
                    opening_balances[cid_str] = float(row.opening_balance or 0.0) if has_ob else 0.0
                    customer_meta[cid_str] = {
                        "registration_date": row.registration_date,
                        "business_type": row.business_type,
                        "credit_limit": float(row.credit_limit) if row.credit_limit is not None else None,
                        "payment_terms_days": int(row.payment_terms_days) if row.payment_terms_days is not None else None
                    }
        except Exception as e:
            logger.warning(f"Failed to fetch customer metadata in load_customer_history: {e}")

        # 2. Fetch history from EventLedger, excluding any stale OPENING_BALANCE events
        # OPTIMIZATION: Query specific columns directly to avoid SQLAlchemy ORM memory bloat and session identity map caching.
        stmt = select(
            EventLedger.event_id,
            EventLedger.customer_id,
            EventLedger.event_type,
            EventLedger.event_date,
            EventLedger.amount,
            EventLedger.is_ok,
            EventLedger.source_raw_id,
            EventLedger.source_table,
            EventLedger.customer_sequence_number,
            EventLedger.event_hash,
            EventLedger.metadata_,
        ).where(
            EventLedger.customer_id.in_(customer_ids), 
            not_(EventLedger.is_voided),
            EventLedger.event_type != "OPENING_BALANCE",
            EventLedger.event_date <= func.current_date()
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Convert to dicts, taking care of metadata_
        dicts = []
        for r in rows:
            meta = customer_meta.get(r.customer_id, {})
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
                "business_type": meta.get("business_type"),
                "registration_date": meta.get("registration_date"),
                "credit_limit": meta.get("credit_limit"),
                "payment_terms_days": meta.get("payment_terms_days"),
                "return_reason": None,
            }
            if r.metadata_:
                for k, v in r.metadata_.items():
                    if k in [
                        "discount_amount", "quantity", "tax_amount", 
                        "unit_price"
                    ]:
                        d[k] = float(v) if v is not None else 0.0
                    elif k == "registration_date" and d[k] is None:
                        d[k] = date.fromisoformat(v) if v is not None else None
                    elif k == "business_type" and d[k] is None:
                        d[k] = v
                    elif k == "credit_limit" and d[k] is None:
                        d[k] = float(v) if v is not None else None
                    elif k == "payment_terms_days" and d[k] is None:
                        d[k] = int(v) if v is not None else None
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
