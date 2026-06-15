import os

from sqlalchemy import MetaData, Table
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config.settings import settings

postgres_url = os.getenv("POSTGRES_URL", settings.POSTGRES_URL)

# Normalize the URL for asyncpg driver if needed
if postgres_url.startswith("postgresql://"):
    postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif postgres_url.startswith("postgres://"):
    postgres_url = postgres_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    postgres_url,
    echo=False,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_TIMEOUT,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "command_timeout": 60,
    },
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass




# Global metadata cache for reflected tables to prevent memory leaks
reflected_metadata = MetaData()
_missing_tables = set()
_lock = None


def _get_lock():
    global _lock
    if _lock is None:
        import asyncio
        _lock = asyncio.Lock()
    return _lock


async def get_reflected_table(table_name: str, session: AsyncSession) -> Table | None:
    """
    Safely reflects a table from the database, caching the result globally to prevent memory leaks
    from repeated MetaData instantiations and table reflection. Caches missing tables to prevent
    redundant database queries.
    """
    # 1. Quick check without lock
    if table_name in reflected_metadata.tables:
        return reflected_metadata.tables[table_name]
    if table_name in _missing_tables:
        return None

    # 2. Acquire lock to reflect table
    async with _get_lock():
        # Re-check inside lock
        if table_name in reflected_metadata.tables:
            return reflected_metadata.tables[table_name]
        if table_name in _missing_tables:
            return None

        try:
            table = await session.run_sync(
                lambda sync_conn: Table(table_name, reflected_metadata, autoload_with=sync_conn.bind)
            )
            return table
        except NoSuchTableError:
            _missing_tables.add(table_name)
            return None
        except Exception as e:
            # Do not cache general connection/transient errors as missing
            raise e


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
