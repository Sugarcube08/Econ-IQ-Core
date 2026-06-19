import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import SyncLock
from core.observability.failure_registry import FailureRegistry


class MDBLockManager:
    def __init__(self, session: AsyncSession, locked_by: str = "intelligence_system"):
        self.session = session
        self.locked_by = locked_by
        self.lock_name = "MDB_FILE_LOCK"

    async def __aenter__(self):
        """Acquires the lock when entering the context."""
        await self.acquire_lock()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Releases the lock when exiting the context."""
        await self.release_lock()

    async def acquire_lock(self, timeout_minutes: int = 30, retry_interval_seconds: int = 30):
        """
        Acquires the MDB file lock, waiting if necessary.
        Aligned with the Shared Locking Protocol.
        """
        
        while True:
            # 1. Clean expired locks (Safety First)
            await self.session.execute(
                delete(SyncLock).where(SyncLock.expires_at < datetime.now(UTC))
            )
            await self.session.commit()

            # 2. Try to insert/acquire lock
            try:
                expires_at = datetime.now(UTC) + timedelta(minutes=timeout_minutes)
                
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(SyncLock).values(
                    lock_name=self.lock_name,
                    locked_by=self.locked_by,
                    acquired_at=datetime.now(UTC),
                    expires_at=expires_at
                ).on_conflict_do_update(
                    index_elements=["lock_name"],
                    set_={"expires_at": expires_at},
                    where=(SyncLock.locked_by == self.locked_by)
                )

                await self.session.execute(stmt)
                await self.session.commit()
                
                # 3. Verify ownership
                # In PostgreSQL, we can check if the row exists and belongs to us
                res = await self.session.execute(
                    select(SyncLock).where(SyncLock.lock_name == self.lock_name)
                )
                lock = res.scalar_one_or_none()
                
                if lock and lock.locked_by == self.locked_by:
                    FailureRegistry.recover("LOCK_ACQUIRE_FAILED")
                    # CRITICAL: End the transaction started by select() before returning
                    if self.session.in_transaction():
                        await self.session.commit()
                    return True
                
                # If not ours, commit the read transaction and wait
                if self.session.in_transaction():
                    await self.session.commit()
                
                await asyncio.sleep(retry_interval_seconds)

            except Exception as e:
                await self.session.rollback()
                FailureRegistry.record("LOCK_ACQUIRE_FAILED", f"Error while acquiring lock: {e}", "ERROR")
                await asyncio.sleep(retry_interval_seconds)

    async def release_lock(self):
        """Releases the lock."""
        try:
            await self.session.execute(
                delete(SyncLock).where(
                    SyncLock.lock_name == self.lock_name,
                    SyncLock.locked_by == self.locked_by
                )
            )
            await self.session.commit()
            FailureRegistry.recover("LOCK_RELEASE_FAILED")
        except Exception as e:
            await self.session.rollback()
            FailureRegistry.record("LOCK_RELEASE_FAILED", f"Error while releasing lock: {e}", "ERROR")
