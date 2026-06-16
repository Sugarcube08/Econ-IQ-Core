import polars as pl
from loguru import logger
from core.observability.failure_registry import FailureRegistry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import settings
from core.models.state_models import EventLedger


class LedgerService:
    def __init__(self):
        pass

    async def process_and_materialize(
        self, session: AsyncSession, dataframes: list[pl.DataFrame], batch_id: str
    ) -> pl.DataFrame:
        """
        Takes a list of normalized DataFrames, unifies them,
        assigns global and customer sequences based on EXISTING ledger state,
        and materializes to Postgres.
        """
        if not dataframes:
            FailureRegistry.record("LEDGER_NO_DATAFRAMES", f"No dataframes provided for batch {batch_id}", "WARNING")
            return pl.DataFrame()

        new_events_df = pl.concat(dataframes, how="diagonal_relaxed")

        # 1. Start global sequence
        result = await session.execute(select(func.max(EventLedger.global_sequence_number)))
        max_global = result.scalar()
        start_global_seq = max_global + 1 if max_global is not None else 0

        # 2. Add placeholder columns
        new_events_df = new_events_df.with_columns(
            [
                pl.lit(None).alias("global_sequence_number").cast(pl.Int64),
                pl.lit(None).alias("customer_sequence_number").cast(pl.Int64),
                pl.lit(None).alias("behavioral_penalty_weight").cast(pl.Float64),
                pl.lit(batch_id).alias("batch_id"),
            ]
        )

        # 3. Sequencing (Global)
        new_events_df = new_events_df.with_columns(
            (pl.lit(start_global_seq) + pl.int_range(0, new_events_df.height)).alias("global_sequence_number")
        )

        # 4. Sequencing (Customer)
        affected_ids = new_events_df["customer_id"].unique().to_list()

        # Load existing customer sequence counts
        stmt = (
            select(EventLedger.customer_id, func.max(EventLedger.customer_sequence_number).label("max_seq"))
            .where(EventLedger.customer_id.in_(affected_ids))
            .group_by(EventLedger.customer_id)
        )
        result = await session.execute(stmt)
        history_seqs = {row.customer_id: row.max_seq for row in result.all()}

        # Apply sequencing within the dataframe
        new_events_df = new_events_df.sort(["customer_id", "event_date"])

        # Vectorized calculation of customer sequence offsets
        offsets = {cid: (max_seq if max_seq is not None else -1) + 1 for cid, max_seq in history_seqs.items()}

        new_events_df = new_events_df.with_columns(
            (
                pl.col("customer_id").replace(offsets, default=0).cast(pl.Int64)
                + pl.int_range(0, pl.len()).over("customer_id").cast(pl.Int64)
            ).alias("customer_sequence_number")
        )

        # 5. Apply RG Semantics
        batch_events = self._apply_rg_semantics(new_events_df)

        # 6. Materialize Batch to Postgres
        # Store source-specific columns in metadata before insertion
        metadata_cols = [
            "discount_amount",
            "bank_name",
            "payment_mode",
            "rg_responsibility",
            "batch_id",
            "behavioral_penalty_weight",
            "product_category",
            "product_name",
            "quantity",
            "tax_amount",
            "unit_price",
            "business_type",
            "registration_date",
            "credit_limit",
            "payment_terms_days",
            "return_reason",
        ]
        batch_events = batch_events.with_columns(
            pl.struct([c for c in metadata_cols if c in batch_events.columns]).alias("metadata")
        )

        await self._bulk_insert_events(session, batch_events)

        return batch_events

    async def _bulk_insert_events(self, session: AsyncSession, df: pl.DataFrame):
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # Filter columns to only those present in the EventLedger model
        event_columns = [c.name for c in EventLedger.__table__.columns if c.name not in ["created_at", "updated_at"]]

        # Select only valid columns that exist in the dataframe
        valid_cols = [c for c in event_columns if c in df.columns]
        df_to_insert = df.select(valid_cols)

        records = df_to_insert.to_dicts()

        # Ensure metadata is JSON-serializable (converts Decimal, UUID, date/datetime)
        if records:
            import decimal
            import uuid
            from datetime import date, datetime
            from typing import Any

            def serialize_val(v: Any) -> Any:
                if isinstance(v, dict):
                    return {key: serialize_val(val) for key, val in v.items()}
                elif isinstance(v, list):
                    return [serialize_val(val) for val in v]
                elif isinstance(v, decimal.Decimal):
                    return float(v)
                elif isinstance(v, uuid.UUID):
                    return str(v)
                elif isinstance(v, (datetime, date)):
                    return v.isoformat()
                return v

            for r in records:
                if "metadata" in r and isinstance(r["metadata"], dict):
                    r["metadata"] = serialize_val(r["metadata"])

        # Check for null event_ids which would cause insertion failures
        if records:
            null_event_ids = [r for r in records if r.get("event_id") is None]
            if null_event_ids:
                FailureRegistry.record(
                    "LEDGER_NULL_EVENT_ID",
                    f"Found {len(null_event_ids)} records with NULL event_id. These will fail insertion.",
                    "ERROR",
                )
                # Filter out null event_ids to allow rest to proceed
                records = [r for r in records if r.get("event_id") is not None]

        if records:
            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                # Use PostgreSQL ON CONFLICT DO UPDATE
                # Use the table object directly to avoid collisions with the 'metadata' class property
                stmt = pg_insert(EventLedger.__table__).values(batch)

                # Fields to update on conflict
                # Use bracket notation to avoid collisions with reserved attributes like 'metadata'
                update_fields = {
                    "amount": stmt.excluded["amount"],
                    "event_date": stmt.excluded["event_date"],
                    "is_ok": stmt.excluded["is_ok"],
                    "metadata": stmt.excluded["metadata"],
                    "updated_at": func.now(),
                }

                stmt = stmt.on_conflict_do_update(index_elements=["event_id", "event_date"], set_=update_fields)

                await session.execute(stmt)

            FailureRegistry.recover("LEDGER_NO_RECORDS")
            FailureRegistry.recover("LEDGER_NULL_EVENT_ID")
            FailureRegistry.recover("LEDGER_NO_DATAFRAMES")
        else:
            FailureRegistry.record(
                "LEDGER_NO_RECORDS", "No records found to insert into event_ledger after column filtering", "WARNING"
            )

    def _apply_rg_semantics(self, df: pl.DataFrame) -> pl.DataFrame:
        if not settings.ENABLE_RG_SEMANTIC_CLASSIFICATION:
            return df.with_columns(pl.lit(1.0).alias("behavioral_penalty_weight"))

        # handle missing rg_responsibility column which might not be in dataframe if source didn't provide it
        if "rg_responsibility" not in df.columns:
            df = df.with_columns(pl.lit(None).alias("rg_responsibility").cast(pl.Utf8))

        from core.policy.manager import policy_manager

        policy = policy_manager.policy.stress

        return df.with_columns(
            pl.when(pl.col("event_type") == "RETURN")
            .then(
                pl.when(pl.col("rg_responsibility").str.to_uppercase().is_in(["CUSTOMER", "CUSTOMER RG"]))
                .then(pl.lit(policy.customer_fault_weight))
                .when(pl.col("rg_responsibility").str.to_uppercase().is_in(["GENUINE"]))
                .then(pl.lit(policy.genuine_fault_weight))
                .when(pl.col("rg_responsibility").is_null() | (pl.col("rg_responsibility") == ""))
                .then(pl.lit(policy.unknown_fault_weight))
                .otherwise(pl.lit(0.0))
            )
            .otherwise(pl.lit(0.0))
            .alias("behavioral_penalty_weight")
        )
