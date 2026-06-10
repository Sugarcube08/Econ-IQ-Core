import os

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


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
