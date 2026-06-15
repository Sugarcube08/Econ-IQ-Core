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
from core.intelligence.queue_worker import IntelligenceQueueWorker
from core.middleware.security import HardenedSecurityMiddleware
from core.models import auth_models, state_models  # noqa: F401
from core.observability.logger import setup_logging
from core.schemas.responses import StandardResponse
from core.storage.postgres import AsyncSessionLocal, Base, engine
from core.storage.redis import redis_manager


async def sequential_worker_loop(sync_pipeline: SyncPipeline, queue_worker: IntelligenceQueueWorker):
    """
    Unified sequential processing loop designed for sequential processing mode.
    Guarantees no overlap between ingestion sync, ledger materialization, and recomputation.
    """
    from core.observability.runtime_state import runtime_state
    
    poll_interval = min(settings.SYNC_POLL_INTERVAL, settings.INTELLIGENCE_POLL_INTERVAL)
    logger.info(f"Starting Integrated Sequential Processing Loop (interval: {poll_interval}s)")
    
    # Ensure active_worker is correctly initialized
    runtime_state.active_worker = "sequential_worker"
    
    while True:
        try:
            # 1. Sync Cycle (Sync Ingestion, Ledger Materialization, Queue Population)
            processed_sync = await sync_pipeline.run_cycle()
            
            # 2. Customer Recomputation
            processed_recompute_count = await queue_worker._process_next_chunk()
            
            # Clean up memory
            import gc
            gc.collect()
            
            # Update stage to sleeping if no work was done, otherwise tiny yield
            if not processed_sync and processed_recompute_count == 0:
                runtime_state.current_stage = "sleeping"
                await asyncio.sleep(poll_interval)
            else:
                runtime_state.current_stage = "idle"
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            logger.info("Sequential worker loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in sequential worker loop: {e}")
            runtime_state.current_stage = "idle"
            await asyncio.sleep(poll_interval)


async def delayed_worker_start(sync_pipeline: SyncPipeline, queue_worker: IntelligenceQueueWorker, background_tasks: list):
    """
    Decoupled background worker startup with a 15-second delay to prioritize API availability
    and accommodate Render/Railway health check tolerances.
    Supports STARTUP_MODE: full, recovery, api-only.
    """
    logger.info(f"Background worker startup scheduler: waiting 15 seconds (Mode: {settings.STARTUP_MODE}, Processing Mode: {settings.PROCESSING_MODE})...")
    try:
        await asyncio.sleep(15)
    except asyncio.CancelledError:
        logger.info("Background worker startup delayed sleep was cancelled.")
        return

    if settings.STARTUP_MODE == "api-only":
        logger.info("Startup Mode is 'api-only'. Background tasks are completely disabled.")
        return

    if settings.PROCESSING_MODE == "sequential":
        logger.info("Starting sequential background worker...")
        task_seq = asyncio.create_task(
            sequential_worker_loop(sync_pipeline, queue_worker),
            name="sequential_worker"
        )
        background_tasks.append(task_seq)
        logger.info("Sequential background worker is operational.")
        return

    if settings.STARTUP_MODE == "recovery":
        logger.warning("Startup Mode is 'recovery'. Starting Ingestion Sync loop only; Intelligence Worker remains suspended.")
        task = asyncio.create_task(
            sync_pipeline.run_loop(poll_interval=settings.SYNC_POLL_INTERVAL),
            name="sync_worker"
        )
        background_tasks.append(task)
    else:  # full
        logger.info("Starting integrated background workers (Sync Ingestion + Intelligence Queue)...")
        task_sync = asyncio.create_task(
            sync_pipeline.run_loop(poll_interval=settings.SYNC_POLL_INTERVAL),
            name="sync_worker"
        )
        task_intel = asyncio.create_task(
            queue_worker.run(poll_interval=settings.INTELLIGENCE_POLL_INTERVAL),
            name="intel_worker"
        )
        background_tasks.append(task_sync)
        background_tasks.append(task_intel)
        logger.info("Integrated background workers are operational.")


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

    # 2. Background Workers (Optional)
    background_tasks = []
    app.state.background_tasks = background_tasks
    if settings.ENABLE_BACKGROUND_WORKERS:
        logger.info("Scheduling background workers initialization...")
        queue_worker = IntelligenceQueueWorker()
        startup_task = asyncio.create_task(
            delayed_worker_start(sync_pipeline, queue_worker, background_tasks),
            name="startup_task"
        )
        background_tasks.append(startup_task)

    logger.info("econiq Backend Operational.")

    yield

    # 3. Shutdown Logic
    logger.info("Shutting down econiq Backend...")

    if background_tasks:
        logger.info("Stopping background workers...")
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("Background workers stopped.")

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
    Exposes system metrics including memory, thread counts, pending queue tasks,
    sync backlog count, active background worker tasks, and startup mode.
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

    # 2. Database statistics (Pending Queue and Backlog)
    pending_queue = 0
    sync_backlog = 0
    
    try:
        from sqlalchemy import func, select

        from core.models.state_models import CustomerRecomputationQueue, RecomputationStatus
        
        async with AsyncSessionLocal() as session:
            stmt_queue = select(func.count(CustomerRecomputationQueue.id)).where(
                CustomerRecomputationQueue.status == RecomputationStatus.PENDING
            )
            res_queue = await session.execute(stmt_queue)
            pending_queue = res_queue.scalar() or 0
    except Exception as e:
        logger.error(f"Failed to count pending queue: {e}")

    try:
        sync_pipeline = getattr(request.app.state, "sync_pipeline", None)
        if sync_pipeline is None:
            sync_pipeline = SyncPipeline()
        sync_backlog = await sync_pipeline.get_stale_unprocessed_count()
    except Exception as e:
        logger.error(f"Failed to get sync backlog count: {e}")

    # 3. Active Workers Count
    active_workers = 0
    background_tasks = getattr(request.app.state, "background_tasks", [])
    for task in background_tasks:
        if not task.done() and task.get_name() in ("sync_worker", "intel_worker", "sequential_worker"):
            active_workers += 1

    data = {
        "rss_mb": round(rss_mb, 2),
        "vms_mb": round(vms_mb, 2),
        "threads": threads,
        "pending_queue": pending_queue,
        "sync_backlog": sync_backlog,
        "active_workers": active_workers,
        "startup_mode": settings.STARTUP_MODE,
    }
    return success_response("System metrics retrieved successfully", data=data, request=request)


@api_v1_router.get("/system/runtime", response_model=StandardResponse[dict])
async def system_runtime(request: Request):
    """
    Exposes runtime metrics including memory, thread counts, pending queue tasks,
    sync backlog count, active background worker tasks, processing mode,
    active worker, and current processing stage.
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

    # 2. Database statistics (Pending Queue and Backlog)
    pending_queue = 0
    sync_backlog = 0
    
    try:
        from sqlalchemy import func, select

        from core.models.state_models import CustomerRecomputationQueue, RecomputationStatus
        
        async with AsyncSessionLocal() as session:
            stmt_queue = select(func.count(CustomerRecomputationQueue.id)).where(
                CustomerRecomputationQueue.status == RecomputationStatus.PENDING
            )
            res_queue = await session.execute(stmt_queue)
            pending_queue = res_queue.scalar() or 0
    except Exception as e:
        logger.error(f"Failed to count pending queue: {e}")

    try:
        sync_pipeline = getattr(request.app.state, "sync_pipeline", None)
        if sync_pipeline is None:
            sync_pipeline = SyncPipeline()
        sync_backlog = await sync_pipeline.get_stale_unprocessed_count()
    except Exception as e:
        logger.error(f"Failed to get sync backlog count: {e}")

    # 3. Active Workers Count
    active_workers = 0
    background_tasks = getattr(request.app.state, "background_tasks", [])
    for task in background_tasks:
        if not task.done() and task.get_name() in ("sync_worker", "intel_worker", "sequential_worker"):
            active_workers += 1

    # 4. Active Worker and Stage from runtime_state
    from core.observability.runtime_state import runtime_state
    
    data = {
        "rss_mb": round(rss_mb, 2),
        "vms_mb": round(vms_mb, 2),
        "threads": threads,
        "queue_depth": pending_queue,
        "sync_backlog": sync_backlog,
        "active_workers": active_workers,
        "processing_mode": settings.PROCESSING_MODE,
        "active_worker": runtime_state.active_worker,
        "current_stage": runtime_state.current_stage,
    }
    return success_response("System runtime metrics retrieved successfully", data=data, request=request)


app.include_router(api_v1_router)

# -- OBSERVABILITY --

# Metrics Endpoint (Internal Use)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
