import os
import socket
import uuid
from datetime import UTC, datetime

import polars as pl
from loguru import logger
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import settings
from core.ingestion.db_provider import DBIngestionProvider
from core.ledger.ledger import LedgerService
from core.models.state_models import (
    BatchStatus,
    SyncBatch,
)
from core.storage.postgres import AsyncSessionLocal


class SyncPipeline:
    def __init__(self, fetch_limit: int = 10000):
        self.ledger_service = LedgerService()
        self.fetch_limit = fetch_limit
        self.worker_id = f"sync_worker_{socket.gethostname()}_{os.getpid()}"
        self.current_poll_multiplier = 1.0

    async def upgrade_raw_tables_schema(self, session: AsyncSession):
        """DDL migration to ensure external raw tables have state-tracking columns."""
        raw_tables = ["raw_sales", "raw_payments", "raw_returns", "customers"]
        logger.info("SYSTEM | Verifying raw tables schemas")
        
        for table in raw_tables:
            try:
                # Add columns if they do not exist
                # We use individual execution and commits to avoid massive long-running DDL transactions
                # which can cause timeouts on large tables.
                await session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;"))
                await session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;"))
                await session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(255);"))
                await session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS processing_attempts INTEGER DEFAULT 0;"))
                await session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS last_processing_error TEXT;"))
                
                # Commit after each table to release locks and reset transaction timer
                await session.commit()
                logger.debug("SYSTEM | Schema verification completed for table", extra={"table_name": table})
            except Exception as e:
                # We log and rollback for the specific table, but continue for others
                logger.warning("FAILURE | Potential timeout or lock issue upgrading table", extra={"table_name": table, "error": str(e)})
                await session.rollback()
                # If it's a critical failure (like table not existing), we'll find out during sync
                continue
        
        logger.info("SYSTEM | Raw table schemas verification complete")

    async def run_cycle(self) -> bool:
        """
        Executes a single, isolated, transaction-safe synchronization cycle.
        Returns True if records were processed, False otherwise.
        """
        async with AsyncSessionLocal() as session:
            # 1. Acquire Session-level Advisory Lock (Key: 42069)
            # Session-level lock is used to control concurrency across multiple transaction boundaries.
            logger.debug("PROCESSING | Worker attempting to acquire PostgreSQL advisory lock", extra={"worker_id": self.worker_id})
            try:
                lock_res = await session.execute(text("SELECT pg_try_advisory_lock(42069)"))
                lock_acquired = bool(lock_res.scalar())
                # CRITICAL: End the implicit transaction started by execute()
                # before entering an explicit session.begin() context.
                if session.in_transaction():
                    await session.commit()
            except Exception as e:
                logger.error("FAILURE | Error checking advisory lock", extra={"error": str(e)})
                if session.in_transaction():
                    await session.rollback()
                return False

            if not lock_acquired:
                logger.debug("PROCESSING | Advisory lock (42069) is held by another sync worker. Yielding execution.")
                return False

            logger.debug("PROCESSING | Worker acquired advisory lock. Starting synchronization cycle.", extra={"worker_id": self.worker_id})
            batch_id = str(uuid.uuid4())
            start_time = datetime.now(UTC)

            # Queue Pressure Protection removed under simple architecture

            # 3. Backlog scale check (Deprecated under simple architecture)
            _backlog = 0

            # Determine limits based on config settings
            limits = {
                "raw_sales": settings.SYNC_BATCH_SIZE,
                "raw_payments": settings.SYNC_BATCH_SIZE,
                "raw_returns": settings.SYNC_BATCH_SIZE
            }
            self.current_poll_multiplier = 1.0
            logger.info("PROCESSING | Sync Pipeline started", extra={"sync_batch_size": settings.SYNC_BATCH_SIZE})
            
            # State tracking for error handling
            claimed_ids = {}
            unique_customers = []

            # CRITICAL: End the implicit transaction started by queue count query
            # before entering an explicit session.begin() context.
            if session.in_transaction():
                await session.commit()

            # 4. Insert initial batch log
            async with session.begin():
                batch_log = SyncBatch(
                    batch_id=batch_id,
                    started_at=start_time,
                    status=BatchStatus.PROCESSING,
                    worker_id=self.worker_id,
                    retry_count=0,
                )
                session.add(batch_log)

            try:
                # 5. Acquire MDB Lock (Coordination with external DB Updater)
                # This ensures we only read when the source MDB is not being actively synced to raw tables
                from core.utils.lock_manager import MDBLockManager
                async with MDBLockManager(session) as _mdb_lock:
                    # 6. Process records in a clean transaction
                    # Ensure no dangling transaction from lock acquisition
                    if session.in_transaction():
                        await session.commit()
                        
                    async with session.begin():
                        provider = DBIngestionProvider(session, fetch_limit=self.fetch_limit)
                        all_normalized = []
                        total_claimed = 0
                        
                        source_configs = [
                            ("raw_sales", provider._normalize_sales, limits["raw_sales"]),
                            ("raw_payments", provider._normalize_payments, limits["raw_payments"]),
                            ("raw_returns", provider._normalize_rg, limits["raw_returns"]),
                        ]

                        for table_name, normalizer, table_limit in source_configs:
                            table = await provider._get_table(table_name)
                            if table is None:
                                continue

                            # Select id for rows that are unprocessed/updated and not dead-letter (attempts < 3)
                            # Use FOR UPDATE SKIP LOCKED for high-concurrency safety
                            # Column-awareness: use created_at if updated_at is not present
                            change_col = table.c.updated_at if "updated_at" in table.c else table.c.created_at
                            
                            stmt = (
                                select(table.c.id)
                                .where(
                                    (
                                        (table.c.is_processed.is_(False))
                                        | (table.c.processed_at.is_(None))
                                        | (change_col > table.c.processed_at)
                                    )
                                    & (table.c.processing_attempts < 3)
                                )
                                .limit(table_limit)
                                .with_for_update(skip_locked=True)
                            )
                            res = await session.execute(stmt)
                            ids = [r[0] for r in res.fetchall()]

                            if not ids:
                                continue

                            # Update claimed rows with current batch_id and increment attempts
                            update_stmt = (
                                update(table)
                                .where(table.c.id.in_(ids))
                                .values(
                                    processing_batch_id=batch_id,
                                    processing_attempts=table.c.processing_attempts + 1,
                                )
                                .returning(table)
                            )
                            update_res = await session.execute(update_stmt)
                            rows = update_res.fetchall()

                            dicts = [dict(row._mapping) for row in rows]
                            raw_df = pl.DataFrame(dicts, infer_schema_length=None)

                            # Clean object columns
                            object_cols = [c for c in raw_df.columns if raw_df[c].dtype == pl.Object]
                            if object_cols:
                                raw_df = raw_df.with_columns(
                                    [
                                        pl.col(c).map_elements(
                                            lambda x: str(x) if x is not None else None, return_dtype=pl.Utf8
                                        )
                                        for c in object_cols
                                    ]
                                )

                            norm_df = normalizer(raw_df)
                            if not norm_df.is_empty():
                                all_normalized.append(norm_df)
                                total_claimed += raw_df.height
                                claimed_ids[table_name] = ids

                        # Claim metadata tables (customers) as well
                        metadata_customers = set()
                        for extra_table in ["customers"]:
                            table = await provider._get_table(extra_table)
                            if table is None:
                                continue

                            # For customers, we want to capture the id to ensure they are queued
                            columns_to_select = [table.c.id]

                            change_col = table.c.updated_at if "updated_at" in table.c else table.c.created_at

                            stmt = (
                                select(*columns_to_select)
                                .where(
                                    (
                                        (table.c.is_processed.is_(False))
                                        | (table.c.processed_at.is_(None))
                                        | (change_col > table.c.processed_at)
                                    )
                                    & (table.c.processing_attempts < 3)
                                )
                                .limit(settings.SYNC_BATCH_SIZE)
                                .with_for_update(skip_locked=True)
                            )
                            res = await session.execute(stmt)
                            rows = res.fetchall()
                            ids = [r[0] for r in rows]

                            if extra_table == "customers":
                                metadata_customers.update({str(r[0]) for r in rows if r[0]})

                            if ids:
                                update_stmt = (
                                    update(table)
                                    .where(table.c.id.in_(ids))
                                    .values(
                                        processing_batch_id=batch_id,
                                        processing_attempts=table.c.processing_attempts + 1,
                                    )
                                )
                                await session.execute(update_stmt)
                                claimed_ids[extra_table] = ids
                                total_claimed += len(ids)

                        # 4. If nothing claimed, finish immediately
                        if total_claimed == 0:
                            logger.debug("PROCESSING | No unprocessed records detected for batch", extra={"batch_id": batch_id})
                            # Clean up sync batch as completed with 0 rows
                            complete_stmt = (
                                update(SyncBatch)
                                .where(SyncBatch.batch_id == batch_id)
                                .values(
                                    status=BatchStatus.COMPLETED,
                                    completed_at=datetime.now(UTC),
                                    rows_processed=0,
                                    customers_affected=0,
                                )
                            )
                            await session.execute(complete_stmt)
                            return False

                        logger.debug("PROCESSING | Processing batch, claimed rows across raw tables", extra={"batch_id": batch_id, "total_claimed": total_claimed})

                        # 5. Materialize ledger events (if we have sales/payments/returns)
                        unique_customers_set = set()
                        if all_normalized:
                            combined_df = pl.concat(all_normalized, how="diagonal_relaxed")
                            await self.ledger_service.process_and_materialize(session, [combined_df], batch_id)

                            # Extract unique customers affected
                            unique_customers_set.update(combined_df["customer_id"].unique().to_list())
                            
                        # Add customers from metadata (raw_customers) to ensure they are tracked
                        unique_customers_set.update(metadata_customers)
                        unique_customers = list(unique_customers_set)

                        # 7. Mark claimed rows as processed successfully
                        for table_name, ids in claimed_ids.items():
                            table = await provider._get_table(table_name)
                            if table is not None:
                                update_stmt = (
                                    update(table)
                                    .where(table.c.id.in_(ids))
                                    .values(
                                        is_processed=True,
                                        processed_at=datetime.now(UTC),
                                        last_processing_error=None,
                                    )
                                )
                                await session.execute(update_stmt)

                        # Update SyncBatch stats to COMPLETED
                        end_time = datetime.now(UTC)
                        complete_stmt = (
                            update(SyncBatch)
                            .where(SyncBatch.batch_id == batch_id)
                            .values(
                                status=BatchStatus.COMPLETED,
                                completed_at=end_time,
                                rows_processed=total_claimed,
                                customers_affected=len(unique_customers),
                            )
                        )
                        await session.execute(complete_stmt)

                # Commit transaction
                duration = (datetime.now(UTC) - start_time).total_seconds()
                sales_cnt = len(claimed_ids.get("raw_sales", []))
                payments_cnt = len(claimed_ids.get("raw_payments", []))
                returns_cnt = len(claimed_ids.get("raw_returns", []))
                logger.info(
                    "PROCESSING | Sync Completed",
                    extra={
                        "Sales": sales_cnt,
                        "Payments": payments_cnt,
                        "Returns": returns_cnt,
                        "Duration": f"{duration:.2f}s",
                        "batch_id": batch_id[:8],
                        "customers": len(unique_customers),
                        "worker": self.worker_id
                    }
                )
                return True

            except Exception as batch_error:
                # If transaction fails, it rolls back automatically
                logger.error("FAILURE | Error processing sync batch", extra={"batch_id": batch_id, "error": str(batch_error)})

                # Save failure status in a new transaction
                try:
                    async with session.begin():
                        # Update SyncBatch log
                        fail_stmt = (
                            update(SyncBatch)
                            .where(SyncBatch.batch_id == batch_id)
                            .values(
                                status=BatchStatus.FAILED,
                                completed_at=datetime.now(UTC),
                                error_summary=str(batch_error)[:500],
                            )
                        )
                        await session.execute(fail_stmt)

                        # Mark claimed rows with error summary so they can be audited/retried
                        for table_name, ids in claimed_ids.items():
                            table = await provider._get_table(table_name)
                            if table is not None:
                                update_stmt = (
                                    update(table)
                                    .where(table.c.id.in_(ids))
                                    .values(
                                        is_processed=False,
                                        last_processing_error=str(batch_error)[:500],
                                    )
                                )
                                await session.execute(update_stmt)
                    logger.debug("PROCESSING | Successfully logged batch failure in DB.", extra={"batch_id": batch_id})
                except Exception as log_error:
                    logger.critical("FAILURE | Failed to log batch failure in database", extra={"error": str(log_error)})

                return False

            finally:
                # 7. Always release advisory lock in finally block
                try:
                    await session.execute(text("SELECT pg_advisory_unlock(42069)"))
                    # End the transaction started by the unlock execute
                    if session.in_transaction():
                        await session.commit()
                    logger.debug("PROCESSING | PostgreSQL advisory lock released.")
                except Exception as unlock_error:
                    logger.critical("FAILURE | Failed to release advisory lock", extra={"error": str(unlock_error)})


    async def has_pending_work(self) -> bool:
        """
        Performs an ultra-cheap existence check across all raw tables.
        Returns True if at least one unprocessed/updated row exists.
        """
        async with AsyncSessionLocal() as session:
            async with session.begin():
                provider = DBIngestionProvider(session)
                for table_name in ["raw_sales", "raw_payments", "raw_returns", "customers"]:
                    table = await provider._get_table(table_name)
                    if table is not None:
                        # ultra-cheap EXISTS check
                        change_col = table.c.updated_at if "updated_at" in table.c else table.c.created_at
                        stmt = select(text("1")).select_from(table).where(
                            (
                                (table.c.is_processed.is_(False))
                                | (table.c.processed_at.is_(None))
                                | (change_col > table.c.processed_at)
                            )
                            & (table.c.processing_attempts < 3)
                        ).limit(1)
                        res = await session.execute(stmt)
                        if res.scalar() is not None:
                            return True
                return False


