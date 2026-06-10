import polars as pl
from loguru import logger
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
            logger.warning(f"No dataframes provided for batch {batch_id}")
            return pl.DataFrame()

        logger.debug(f"Processing batch {batch_id} with {len(dataframes)} dataframes")
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

        # Helper to apply customer sequence offset
        def assign_customer_seq(df_group: pl.DataFrame) -> pl.DataFrame:
            cid = df_group["customer_id"][0]
            offset = (history_seqs.get(cid) or -1) + 1
            return df_group.with_columns(
                (pl.lit(offset) + pl.int_range(0, df_group.height)).alias("customer_sequence_number")
            )

        new_events_df = new_events_df.group_by("customer_id", maintain_order=True).map_groups(assign_customer_seq)

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
        logger.debug(f"EventLedger table columns: {event_columns}")
        logger.debug(f"DataFrame columns: {df.columns}")

        # Select only valid columns that exist in the dataframe
        valid_cols = [c for c in event_columns if c in df.columns]
        logger.debug(f"Valid columns for insertion: {valid_cols}")
        df_to_insert = df.select(valid_cols)

        records = df_to_insert.to_dicts()
        logger.debug(f"Attempting to bulk upsert {len(records)} records into event_ledger")
        
        # Check for null event_ids which would cause insertion failures
        if records:
            null_event_ids = [r for r in records if r.get("event_id") is None]
            if null_event_ids:
                logger.error(f"Found {len(null_event_ids)} records with NULL event_id. These will fail insertion.")
                # Filter out null event_ids to allow rest to proceed
                records = [r for r in records if r.get("event_id") is not None]
                logger.debug(f"Proceeding with {len(records)} records after filtering null event_ids")

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

            logger.debug(f"Bulk upserted {len(records)} events into event_ledger")
        else:
            logger.warning("No records found to insert into event_ledger after column filtering")

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
