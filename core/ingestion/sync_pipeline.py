import asyncio
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta

import polars as pl
from loguru import logger
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.ingestion.db_provider import DBIngestionProvider
from core.ledger.ledger import LedgerService
from core.models.state_models import (
    BatchStatus,
    CustomerRecomputationQueue,
    RecomputationStatus,
    SyncBatch,
)
from core.storage.postgres import AsyncSessionLocal
from core.config.settings import settings
from core.observability.runtime_state import runtime_state


class SyncPipeline:
    def __init__(self, fetch_limit: int = 10000):
        self.ledger_service = LedgerService()
        self.fetch_limit = fetch_limit
        self.worker_id = f"sync_worker_{socket.gethostname()}_{os.getpid()}"
        self.current_poll_multiplier = 1.0

    async def upgrade_raw_tables_schema(self, session: AsyncSession):
        """DDL migration to ensure external raw tables have state-tracking columns."""
        raw_tables = ["raw_sales", "raw_payments", "raw_returns", "customers"]
        logger.info("Verifying raw tables schemas and upgrading if necessary...")
        
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
                logger.debug(f"Schema verification completed for table: {table}")
            except Exception as e:
                # We log and rollback for the specific table, but continue for others
                logger.warning(f"Potential timeout or lock issue upgrading table {table}: {e}")
                await session.rollback()
                # If it's a critical failure (like table not existing), we'll find out during sync
                continue
        
        logger.info("Raw table schemas verification lifecycle complete.")

    async def run_cycle(self) -> bool:
        """
        Executes a single, isolated, transaction-safe synchronization cycle.
        Returns True if records were processed, False otherwise.
        """
        lock_context = runtime_state.lock if settings.PROCESSING_MODE == "sequential" else asyncio.Lock()
        async with lock_context:
            if settings.PROCESSING_MODE == "sequential":
                runtime_state.active_worker = "sequential_worker"
            else:
                runtime_state.active_worker = "sync_worker"
            runtime_state.current_stage = "sync_ingestion"
            try:
                return await self._run_cycle_internal()
            finally:
                runtime_state.current_stage = "idle"

    async def _run_cycle_internal(self) -> bool:
        """
        Internal implementation of the synchronization cycle.
        """
        async with AsyncSessionLocal() as session:
            # 1. Acquire Session-level Advisory Lock (Key: 42069)
            # Session-level lock is used to control concurrency across multiple transaction boundaries.
            logger.debug(f"Worker {self.worker_id} attempting to acquire PostgreSQL advisory lock...")
            try:
                lock_res = await session.execute(text("SELECT pg_try_advisory_lock(42069)"))
                lock_acquired = bool(lock_res.scalar())
                # CRITICAL: End the implicit transaction started by execute()
                # before entering an explicit session.begin() context.
                if session.in_transaction():
                    await session.commit()
            except Exception as e:
                logger.error(f"Error checking advisory lock: {e}")
                if session.in_transaction():
                    await session.rollback()
                return False

            if not lock_acquired:
                logger.debug("Advisory lock (42069) is held by another sync worker. Yielding execution.")
                return False

            logger.debug(f"Worker {self.worker_id} acquired advisory lock. Starting synchronization cycle.")
            batch_id = str(uuid.uuid4())
            start_time = datetime.now(UTC)

            # 2. Queue Pressure Protection: Stop sync ingestion if intelligence queue is overloaded
            try:
                q_count_res = await session.execute(
                    text("SELECT COUNT(*) FROM customer_recomputation_queue WHERE status = 'PENDING'")
                )
                pending_queue_count = q_count_res.scalar() or 0
                if pending_queue_count > 10000:
                    logger.warning(
                        f"Queue Pressure Protection Active: {pending_queue_count} pending recomputation tasks "
                        f"exceeds the limit of 10,000. Skipping sync ingestion cycle."
                    )
                    return False
            except Exception as q_err:
                logger.error(f"Failed to check recomputation queue count: {q_err}")

            # 3. Query backlog scale to determine limits and sleep multiplier dynamically
            try:
                backlog = await self.get_stale_unprocessed_count()
            except Exception as b_err:
                logger.error(f"Failed to query backlog count: {b_err}")
                backlog = 0

            # Determine limits and loop sleeping multiplier based on backlog size
            if settings.PROCESSING_MODE == "sequential":
                limits = {
                    "raw_sales": settings.SYNC_BATCH_SIZE,
                    "raw_payments": settings.SYNC_BATCH_SIZE,
                    "raw_returns": settings.SYNC_BATCH_SIZE
                }
                self.current_poll_multiplier = 1.0
                logger.info(f"Sync Pipeline (Sequential): Backlog size optimal. Processing up to {settings.SYNC_BATCH_SIZE} rows.")
            elif backlog < 10000:
                limits = {"raw_sales": 5000, "raw_payments": 3000, "raw_returns": 2000}
                self.current_poll_multiplier = 1.0
                logger.info(f"Sync Pipeline: Backlog size optimal ({backlog} rows). Processing up to 10k rows.")
            elif backlog < 100000:
                limits = {"raw_sales": 2000, "raw_payments": 1000, "raw_returns": 500}
                self.current_poll_multiplier = 2.0
                logger.warning(f"Sync Pipeline: Moderate backlog ({backlog} rows) detected. Entering SLOW MODE (throttled limits, double sleep).")
            else:
                limits = {"raw_sales": 1000, "raw_payments": 500, "raw_returns": 200}
                self.current_poll_multiplier = 4.0
                logger.warning(f"Sync Pipeline: Massive backlog ({backlog} rows) detected. Entering RECOVERY MODE (minimal limits, quadruple sleep).")
            
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
                                .limit(settings.SYNC_BATCH_SIZE if settings.PROCESSING_MODE == "sequential" else 1000)
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
                            logger.debug(f"Batch {batch_id}: No unprocessed records detected.")
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

                        logger.debug(f"Processing batch {batch_id}: claimed {total_claimed} rows across raw tables")

                        # 5. Materialize ledger events (if we have sales/payments/returns)
                        unique_customers_set = set()
                        if all_normalized:
                            runtime_state.current_stage = "ledger_materialization"
                            combined_df = pl.concat(all_normalized, how="diagonal_relaxed")
                            await self.ledger_service.process_and_materialize(session, [combined_df], batch_id)

                            # Extract unique customers affected
                            unique_customers_set.update(combined_df["customer_id"].unique().to_list())
                            
                        # Add customers from metadata (raw_customers) to ensure they are also queued
                        unique_customers_set.update(metadata_customers)
                        unique_customers = list(unique_customers_set)
                        
                        if unique_customers:
                            logger.debug(f"Batch {batch_id} affected {len(unique_customers)} unique customers (including metadata)")

                            # 6. Insert deduplicated recomputation tasks into the queue
                            runtime_state.current_stage = "queue_population"
                            queue_records = [
                                {
                                    "customer_id": cid,
                                    "batch_id": batch_id,
                                    "status": RecomputationStatus.PENDING,
                                    "priority": 0,
                                    "reason": f"Ingestion delta synchronization in batch {batch_id}",
                                }
                                for cid in unique_customers
                            ]
                            batch_size = 1000
                            for j in range(0, len(queue_records), batch_size):
                                chunk = queue_records[j : j + batch_size]
                                await session.execute(insert(CustomerRecomputationQueue).values(chunk))

                            logger.debug(f"Queued {len(unique_customers)} customers for intelligence recomputation")

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
                logger.info(
                    f"Sync Batch Completed: batch_id={batch_id[:8]} | "
                    f"rows={total_claimed} | "
                    f"customers={len(unique_customers)} | "
                    f"duration={duration:.2f}s | "
                    f"worker={self.worker_id}"
                )
                return True

            except Exception as batch_error:
                # If transaction fails, it rolls back automatically
                logger.error(f"Error processing sync batch {batch_id}: {batch_error}")

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
                    logger.debug(f"Successfully logged batch {batch_id} failure in DB.")
                except Exception as log_error:
                    logger.critical(f"Failed to log batch failure in database: {log_error}")

                return False

            finally:
                # 7. Always release advisory lock in finally block
                try:
                    await session.execute(text("SELECT pg_advisory_unlock(42069)"))
                    # End the transaction started by the unlock execute
                    if session.in_transaction():
                        await session.commit()
                    logger.debug("PostgreSQL advisory lock released.")
                except Exception as unlock_error:
                    logger.critical(f"Failed to release advisory lock: {unlock_error}")


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

    async def get_stale_unprocessed_count(self) -> int:
        """Returns the number of unprocessed raw rows currently waiting to be synchronized."""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                provider = DBIngestionProvider(session)
                total = 0
                for table_name in ["raw_sales", "raw_payments", "raw_returns", "customers"]:
                    table = await provider._get_table(table_name)
                    if table is not None:
                        change_col = table.c.updated_at if "updated_at" in table.c else table.c.created_at
                        stmt = select(func.count(table.c.id)).where(
                            (
                                (table.c.is_processed.is_(False))
                                | (table.c.processed_at.is_(None))
                                | (change_col > table.c.processed_at)
                            )
                            & (table.c.processing_attempts < 3)
                        )
                        res = await session.execute(stmt)
                        total += res.scalar() or 0
                return total

    async def run_loop(self, poll_interval: int = 15):
        """Continuous polling loop for dedicated Sync Service deployment."""
        logger.info(f"Sync Ingestion Service Loop started (interval: {poll_interval}s, worker_id: {self.worker_id})")
        
        last_idle_log = datetime.now(UTC) - timedelta(minutes=30)
        
        while True:
            try:
                # 1. Ultra-cheap existence check before any orchestration
                if not await self.has_pending_work():
                    # Dormant logging: only log idle status every 30 minutes
                    if datetime.now(UTC) - last_idle_log > timedelta(minutes=30):
                        logger.info(f"Sync service idle — no pending rows detected for 30 minutes (worker: {self.worker_id})")
                        last_idle_log = datetime.now(UTC)
                    
                    await asyncio.sleep(poll_interval)
                    continue

                # Reset idle log timer when work is found
                last_idle_log = datetime.now(UTC) - timedelta(minutes=30)

                # 2. Monitor stale unprocessed rows (DEBUG level)
                stale_count = await self.get_stale_unprocessed_count()
                if stale_count > 0:
                    logger.debug(f"Observability check: {stale_count} stale unprocessed rows waiting in raw tables.")

                processed = await self.run_cycle()

                # If we processed records, check immediately again but yield with a tiny sleep to prevent CPU/memory hoarding
                if processed:
                    import gc
                    gc.collect()
                    await asyncio.sleep(0.2 * self.current_poll_multiplier)
                    continue
            except Exception as e:
                logger.error(f"Unexpected error in background sync loop: {e}")
            
            import gc
            gc.collect()
            await asyncio.sleep(poll_interval * self.current_poll_multiplier)
