import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.auth.api_keys import router as api_keys_router
from core.auth.routes import router as auth_router
from core.auth.users import router as users_router
from core.config.settings import settings
from core.core.exceptions import custom_http_exception_handler, global_exception_handler, validation_exception_handler
from core.core.responses import success_response
from core.customers.routes import customer_detail_router
from core.customers.routes import router as customers_listing_router
from core.dashboard.routes import router as dashboard_router
from core.ingestion.sync_pipeline import SyncPipeline
from core.middleware.security import HardenedSecurityMiddleware
from core.models import auth_models, state_models  # noqa: F401
from core.observability.logger import setup_logging
from core.operations.routes import router as operations_router
from core.schemas.responses import StandardResponse
from core.storage.postgres import AsyncSessionLocal, Base, engine
from core.storage.redis import redis_manager


async def start_sync_worker():
    """
    Main background loop that periodically checks and runs the event sync pipeline.
    """
    logger.info("Starting background event sync worker...")
    sync_pipeline = SyncPipeline()
    while True:
        try:
            logger.debug("Running background event sync cycle...")
            await sync_pipeline.run_cycle()
        except asyncio.CancelledError:
            logger.info("Background sync worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Unhandled error in background sync worker: {e}")
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup Logic
    setup_logging()
    logger.info("Initializing econiq Hardened Backend...")

    # Strict Production Validation
    settings.validate_production()

    # Initialize Ingestion Schema (Sync Service Logic)
    sync_pipeline = SyncPipeline()
    app.state.sync_pipeline = sync_pipeline

    # Initialize Persistence
    if not settings.SKIP_SCHEMA_VERIFICATION:
        async with engine.begin() as conn:
            logger.info("Verifying database schema...")
            try:
                await conn.run_sync(Base.metadata.create_all)
            except Exception as e:
                if "already exists" in str(e):
                    logger.warning(f"Database schema verification race condition handled: {e}")
                else:
                    raise
            logger.info("Database schema verified.")

        async with AsyncSessionLocal() as session:
            await sync_pipeline.upgrade_raw_tables_schema(session)
    else:
        logger.info("Skipping database schema verification (SKIP_SCHEMA_VERIFICATION=True).")

    # Connect to Redis (Fail-Closed)
    await redis_manager.connect()

    logger.info("econiq Backend Operational.")

    # Start lightweight background processing tasks
    app.state.sync_task = asyncio.create_task(start_sync_worker())
    from core.intelligence.background_worker import start_background_worker
    app.state.worker_task = asyncio.create_task(start_background_worker())

    yield

    # Shutdown Logic
    logger.info("Shutting down econiq Backend...")
    if hasattr(app.state, "sync_task"):
        app.state.sync_task.cancel()
        try:
            await app.state.sync_task
        except asyncio.CancelledError:
            pass
    if hasattr(app.state, "worker_task"):
        app.state.worker_task.cancel()
        try:
            await app.state.worker_task
        except asyncio.CancelledError:
            pass
    await redis_manager.disconnect()
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Stateful Behavioral Intelligence Runtime - Hardened Production Edition",
    version="2.0.0",
    lifespan=lifespan,
)

# -- EXCEPTION HANDLERS --
app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler)
app.add_exception_handler(FastAPIHTTPException, custom_http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# -- MIDDLEWARE --

# 1. CORS Hardening
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to trusted domains
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID"],
    max_age=3600,
)

# 2. Production Security & Observability Middleware
app.add_middleware(HardenedSecurityMiddleware)

# -- ROUTERS --

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(api_keys_router)
api_v1_router.include_router(customers_listing_router)
api_v1_router.include_router(customer_detail_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(operations_router)


@api_v1_router.get("/health", response_model=StandardResponse[dict])
async def health_check(request: Request):
    """
    Lightweight health check for infrastructure orchestration.
    """
    data = {"status": "healthy", "environment": settings.APP_ENV, "version": "2.0.0"}
    return success_response("System healthy", data=data, request=request)



app.include_router(api_v1_router)

# -- OBSERVABILITY --

# Metrics Endpoint (Internal Use)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
