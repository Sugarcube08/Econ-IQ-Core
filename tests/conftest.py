import asyncio
import pytest
from core.storage.postgres import engine
from core.storage.redis import redis_manager

@pytest.fixture(scope="session")
def event_loop():
    """Create a single session-wide event loop for all async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def run_app_lifespan():
    from core.main import app, lifespan
    async with lifespan(app):
        yield

@pytest.fixture(autouse=True)
async def cleanup_connections():
    yield
    # Dispose of engine to clear connection pool
    await engine.dispose()
    # Ensure redis is disconnected
    await redis_manager.disconnect()




