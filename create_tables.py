import asyncio

from core.models import auth_models, state_models  # noqa: F401
from core.storage.postgres import Base, engine


async def create_all_tables():
    async with engine.begin() as conn:
        print("Creating all tables in PostgreSQL database...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(create_all_tables())
