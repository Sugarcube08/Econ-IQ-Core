import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.core.dependencies import require_permissions
from core.core.permissions import Permission
from core.core.responses import success_response
from core.models.auth_models import APIKey, User
from core.repositories.auth import AuthRepository
from core.repositories.dashboard import DashboardRepository
from core.schemas.dashboard import (
    AgingDistributionData,
    CommercialFlowPoint,
    CustomerActivitySummaryData,
    CustomerDeltaInfo,
    ExecutiveOverviewData,
    HighRiskCustomerInfo,
    StateDistributionData,
    TopContributorInfo,
)
from core.schemas.responses import ErrorResponse, StandardResponse
from core.storage.postgres import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


async def resolve_dates(
    db: AsyncSession, window_days: int | None, start_date: date | None, end_date: date | None
) -> tuple[date, date, date, date]:
    """
    Helper to resolve the current and previous period date bounds.
    MANDATORY: Analysis is always anchored to real CURRENT_DATE.
    Future-dated events are never part of the commercial window.
    Enforces standard 365-day canonical window.
    """
    now = datetime.now(UTC).date()
    window = 365
    e_date = now
    s_date = e_date - timedelta(days=window - 1)
    prev_e_date = s_date - timedelta(days=1)
    prev_s_date = prev_e_date - timedelta(days=window - 1)

    return s_date, e_date, prev_s_date, prev_e_date


async def log_dashboard_audit(
    db: AsyncSession, identity: User | APIKey, event_type: str, details: dict[str, Any] | None = None
):
    """Utility to register success audits on dashboard access events."""
    auth_repo = AuthRepository(db)
    user_id = identity.id if isinstance(identity, User) else None
    details = details or {}
    if isinstance(identity, APIKey):
        details["api_key_id"] = str(identity.id)
        details["api_key_name"] = identity.name
    await auth_repo.log_audit_event(
        event_type=event_type,
        status="SUCCESS",
        user_id=user_id,
        severity="INFO",
        details=details,
    )


@router.get(
    "/overview",
    response_model=StandardResponse[ExecutiveOverviewData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_overview(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window (inclusive)"),
    end_date: date | None = Query(None, description="End date of the custom analysis window (inclusive)"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve executive-level KPI cards containing active customer counts, sales metrics, collections metrics,
    outstanding balances, overdue exposures, credit limits, contribution scores, and comparison deltas.
    """
    start_time = time.time()
    s_date, e_date, prev_s_date, prev_e_date = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_executive_overview(s_date, e_date, prev_s_date, prev_e_date)
    
    await log_dashboard_audit(db, identity, "DASHBOARD_OVERVIEW_ACCESS", {
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "window": {
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat(),
            "previous_start_date": prev_s_date.isoformat(),
            "previous_end_date": prev_e_date.isoformat(),
        }
    }
    return success_response("Executive overview retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/commercial-flow",
    response_model=StandardResponse[list[CommercialFlowPoint]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_commercial_flow(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window"),
    end_date: date | None = Query(None, description="End date of the custom analysis window"),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly)$", description="Timeline granularity aggregation scale"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve longitudinal commercial flow timelines containing sales billing, payment receipts,
    and longitudinally reconstructed outstanding exposure balances.
    """
    start_time = time.time()
    s_date, e_date, _, _ = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_commercial_flow(s_date, e_date, granularity)

    await log_dashboard_audit(db, identity, "DASHBOARD_COMMERCIAL_FLOW_ACCESS", {
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
        "granularity": granularity,
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "points": len(data),
        "window": {
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat(),
            "granularity": granularity
        }
    }
    return success_response("Commercial flow retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/aging-distribution",
    response_model=StandardResponse[AgingDistributionData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_aging_distribution(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window"),
    end_date: date | None = Query(None, description="End date of the custom analysis window"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve aging distribution of outstanding receivables grouped by overdue duration buckets:
    current, 0-30 days, 31-60 days, 61-90 days, 91-120 days, and 120+ days.
    """
    start_time = time.time()
    _, e_date, _, _ = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_aging_distribution(e_date)

    await log_dashboard_audit(db, identity, "DASHBOARD_AGING_DISTRIBUTION_ACCESS", {
        "reference_date": e_date.isoformat(),
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "reference_date": e_date.isoformat(),
    }
    return success_response("Aging distribution retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/state-distribution",
    response_model=StandardResponse[StateDistributionData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_state_distribution(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve current customer health segmentation counts and percentages across states:
    HEALTHY, MONITOR, CONTRACT, and LIQUIDITY_STRESS.
    """
    start_time = time.time()
    repo = DashboardRepository(db)
    data = await repo.get_state_distribution()

    await log_dashboard_audit(db, identity, "DASHBOARD_STATE_DISTRIBUTION_ACCESS")

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms
    }
    return success_response("State distribution retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/deteriorating-customers",
    response_model=StandardResponse[list[CustomerDeltaInfo]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_deteriorating_customers(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Max number of deteriorating customers to return"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve immediate attention queue containing customers with the largest composite deterioration scores
    (trust loss, payment delays, repayment health collapse, exposure spikes, and grade downgrades).
    """
    start_time = time.time()
    repo = DashboardRepository(db)
    data = await repo.get_deteriorating_customers(limit)

    await log_dashboard_audit(db, identity, "DASHBOARD_DETERIORATING_CUSTOMERS_ACCESS", {"limit": limit})

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "count": len(data)
    }
    return success_response("Top deteriorating customers retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/improving-customers",
    response_model=StandardResponse[list[CustomerDeltaInfo]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_improving_customers(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Max number of improving customers to return"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve growth opportunity queue containing customers with the largest composite improvement scores
    (trust gains, payment regularity, repayment health improvements, exposure recovery, and grade upgrades).
    """
    start_time = time.time()
    repo = DashboardRepository(db)
    data = await repo.get_improving_customers(limit)

    await log_dashboard_audit(db, identity, "DASHBOARD_IMPROVING_CUSTOMERS_ACCESS", {"limit": limit})

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "count": len(data)
    }
    return success_response("Top improving customers retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/high-risk-customers",
    response_model=StandardResponse[list[HighRiskCustomerInfo]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_high_risk_customers(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window"),
    end_date: date | None = Query(None, description="End date of the custom analysis window"),
    limit: int = Query(20, ge=1, le=100, description="Max number of high risk customers to return"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve credit risk queue containing customers ranked by risk severity (overdue exposure,
    outstanding pressure, repayment health collapse, credit limit utilization, and trust deterioration).
    """
    start_time = time.time()
    _, e_date, _, _ = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_high_risk_customers(e_date, limit)

    await log_dashboard_audit(db, identity, "DASHBOARD_HIGH_RISK_CUSTOMERS_ACCESS", {
        "reference_date": e_date.isoformat(),
        "limit": limit
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "count": len(data),
        "reference_date": e_date.isoformat()
    }
    return success_response("High risk customers retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/activity-summary",
    response_model=StandardResponse[CustomerActivitySummaryData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_activity_summary(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window"),
    end_date: date | None = Query(None, description="End date of the custom analysis window"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve customer activity strip containing summary counts for: newly active/inactive accounts,
    improved/deteriorated trust, new overdue occurrences, and accounts approaching credit limits.
    """
    start_time = time.time()
    s_date, e_date, prev_s_date, prev_e_date = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_activity_summary(s_date, e_date, prev_s_date, prev_e_date)

    await log_dashboard_audit(db, identity, "DASHBOARD_ACTIVITY_SUMMARY_ACCESS", {
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "window": {
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat(),
        }
    }
    return success_response("Activity summary retrieved successfully", data=data, metadata=metadata, request=request)


@router.get(
    "/top-contributors",
    response_model=StandardResponse[list[TopContributorInfo]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def get_top_contributors(
    request: Request,
    window_days: int = Query(30, ge=1, le=720, description="Analysis window in days (ignored if start/end dates are specified)"),
    start_date: date | None = Query(None, description="Start date of the custom analysis window"),
    end_date: date | None = Query(None, description="End date of the custom analysis window"),
    limit: int = Query(10, ge=1, le=100, description="Max number of contributors to return"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve commercial concentration list of customers ranked by contribution percentages to
    total sales volume inside the specified window.
    """
    start_time = time.time()
    s_date, e_date, _, _ = await resolve_dates(db, window_days, start_date, end_date)

    repo = DashboardRepository(db)
    data = await repo.get_top_contributors(s_date, e_date, limit)

    await log_dashboard_audit(db, identity, "DASHBOARD_TOP_CONTRIBUTORS_ACCESS", {
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
        "limit": limit
    })

    processing_time_ms = int((time.time() - start_time) * 1000)
    metadata = {
        "processing_time_ms": processing_time_ms,
        "count": len(data),
        "window": {
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat()
        }
    }
    return success_response("Top contributors retrieved successfully", data=data, metadata=metadata, request=request)

