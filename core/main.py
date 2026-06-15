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
from core.schemas.responses import StandardResponse
from core.storage.postgres import AsyncSessionLocal, Base, engine
from core.storage.redis import redis_manager





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

    yield

    # Shutdown Logic
    logger.info("Shutting down econiq Backend...")
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


@api_v1_router.get("/health", response_model=StandardResponse[dict])
async def health_check(request: Request):
    """
    Lightweight health check for infrastructure orchestration.
    """
    data = {"status": "healthy", "environment": settings.APP_ENV, "version": "2.0.0"}
    return success_response("System healthy", data=data, request=request)


@api_v1_router.get("/system/metrics", response_model=StandardResponse[dict])
async def system_metrics(request: Request):
    """
    Exposes system metrics including memory, thread counts, and sync backlog count.
    """
    # 1. System Memory and Threads
    rss_mb = 0.0
    vms_mb = 0.0
    threads = 0
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_mb = float(line.split()[1]) / 1024.0
                elif line.startswith("VmSize:"):
                    vms_mb = float(line.split()[1]) / 1024.0
                elif line.startswith("Threads:"):
                    threads = int(line.split()[1])
    except Exception as e:
        logger.warning(f"Failed to read system status from /proc: {e}")

    # 2. Database statistics (Backlog)
    sync_backlog = 0
    try:
        sync_pipeline = getattr(request.app.state, "sync_pipeline", None)
        if sync_pipeline is None:
            sync_pipeline = SyncPipeline()
        sync_backlog = await sync_pipeline.get_stale_unprocessed_count()
    except Exception as e:
        logger.error(f"Failed to get sync backlog count: {e}")

    data = {
        "rss_mb": round(rss_mb, 2),
        "vms_mb": round(vms_mb, 2),
        "threads": threads,
        "pending_queue": 0,
        "sync_backlog": sync_backlog,
        "active_workers": 0,
        "startup_mode": settings.STARTUP_MODE,
    }
    return success_response("System metrics retrieved successfully", data=data, request=request)


@api_v1_router.get("/system/runtime", response_model=StandardResponse[dict])
async def system_runtime(request: Request):
    """
    Exposes runtime metrics including memory, thread counts, and sync backlog count.
    """
    # 1. System Memory and Threads
    rss_mb = 0.0
    vms_mb = 0.0
    threads = 0
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_mb = float(line.split()[1]) / 1024.0
                elif line.startswith("VmSize:"):
                    vms_mb = float(line.split()[1]) / 1024.0
                elif line.startswith("Threads:"):
                    threads = int(line.split()[1])
    except Exception as e:
        logger.warning(f"Failed to read system status from /proc: {e}")

    # 2. Database statistics (Backlog)
    sync_backlog = 0
    try:
        sync_pipeline = getattr(request.app.state, "sync_pipeline", None)
        if sync_pipeline is None:
            sync_pipeline = SyncPipeline()
        sync_backlog = await sync_pipeline.get_stale_unprocessed_count()
    except Exception as e:
        logger.error(f"Failed to get sync backlog count: {e}")

    data = {
        "rss_mb": round(rss_mb, 2),
        "vms_mb": round(vms_mb, 2),
        "threads": threads,
        "queue_depth": 0,
        "sync_backlog": sync_backlog,
        "active_workers": 0,
        "processing_mode": "simple",
        "active_worker": "none",
        "current_stage": "idle",
    }
    return success_response("System runtime metrics retrieved successfully", data=data, request=request)


@api_v1_router.post("/admin/recompute", response_model=StandardResponse[dict])
async def admin_recompute(request: Request):
    """
    Explicitly triggers full data synchronization followed by intelligence recomputation.
    """
    try:
        from core.ingestion.sync_pipeline import SyncPipeline
        from core.recompute_all import recompute_all
        
        logger.info("Admin Recompute: Triggering sync pipeline cycle...")
        sync_pipeline = SyncPipeline()
        await sync_pipeline.run_cycle()
        
        logger.info("Admin Recompute: Triggering customer recomputation...")
        await recompute_all()
        
        logger.info("Admin Recompute: Data sync and recomputation completed successfully.")
        return success_response("Data synchronization and intelligence recomputation completed successfully", data={"status": "completed"}, request=request)
    except Exception as e:
        logger.error(f"Failed to execute recomputation: {e}")
        raise FastAPIHTTPException(status_code=500, detail=f"Recomputation failed: {str(e)}")


app.include_router(api_v1_router)

# -- OBSERVABILITY --

# Metrics Endpoint (Internal Use)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
