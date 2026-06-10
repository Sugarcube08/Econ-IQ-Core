import time
from datetime import UTC, date, datetime, timedelta

import polars as pl
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import MetaData, asc, case, desc, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.core.dependencies import require_permissions
from core.core.permissions import Permission
from core.core.responses import success_response
from core.intelligence.orchestrator import IntelligenceOrchestrator
from core.intelligence.resilience import ResilientIntelligenceOrchestrator
from core.models.auth_models import APIKey, User
from core.models.state_models import CustomerIntelligence, EventLedger
from core.repositories.intelligence import IntelligenceRepository
from core.schemas.customers import (
    CustomerDatatableDeltas,
    CustomerDatatableResponseData,
    CustomerDatatableRow,
    CustomerDeltaSchema,
    CustomerDetailSchema,
    CustomerProfileResponseData,
    CustomerScoreSchema,
    GraphResponseData,
    OrgContributionSchema,
    OutstandingGraphPoint,
    PaymentGraphPoint,
    PurchaseGraphPoint,
    RGGraphPoint,
)
from core.schemas.intelligence import AnalysisContext
from core.schemas.responses import ErrorResponse, StandardResponse
from core.storage.postgres import get_db
from core.utils.temporal import normalize_temporal_to_date, normalize_temporal_to_str

router = APIRouter(prefix="/customers", tags=["Customers"])

# Global metadata to cache reflected tables
_metadata = MetaData()


async def resolve_customer_dates(
    db: AsyncSession, window_days: int, start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    """
    Helper to resolve anchor date for customer endpoints.
    MANDATORY: Analysis is always anchored to real CURRENT_DATE.
    Future-dated events are never part of the commercial window.
    """
    now = datetime.now(UTC).date()

    # Clip future end_date
    if end_date and end_date > now:
        end_date = now

    if start_date and end_date:
        s_date = start_date
        e_date = end_date
    elif start_date:
        s_date = start_date
        e_date = now
    elif end_date:
        s_date = (datetime.combine(end_date, datetime.min.time()) - timedelta(days=window_days)).date()
        e_date = end_date
    else:
        s_date = now - timedelta(days=window_days)
        e_date = now

    return s_date, e_date


def build_customers_query(
    sort_by: str = "trust_score",
    sort_order: str = "desc",
    search: str | None = None,
    overall_grade: str | None = None,
    current_state: str | None = None,
    trust_score_min: float | None = None,
    trust_score_max: float | None = None,
    payment_score_min: float | None = None,
    payment_score_max: float | None = None,
    purchase_score_min: float | None = None,
    purchase_score_max: float | None = None,
    payment_behavior_min: float | None = None,
    payment_behavior_max: float | None = None,
    purchase_behavior_min: float | None = None,
    purchase_behavior_max: float | None = None,
    rg_score_min: float | None = None,
    rg_score_max: float | None = None,
    contribution_min: float | None = None,
    contribution_max: float | None = None,
    last_purchase_date_start: date | None = None,
    last_purchase_date_end: date | None = None,
):
    """
    Constructs the base SQLAlchemy query with all filters and sorting applied.
    Shared between JSON datatable and CSV export.
    """
    # 1. Column Mapping
    sort_mapping = {
        "customer_id": CustomerIntelligence.customer_id,
        "customer_name": CustomerIntelligence.customer_name,
        "city": CustomerIntelligence.city,
        "trust_score": CustomerIntelligence.trust_score,
        "purchase_score": CustomerIntelligence.purchase_score,
        "purchase_behavior_score": CustomerIntelligence.purchase_score,
        "payment_score": CustomerIntelligence.payment_score,
        "payment_behavior_score": CustomerIntelligence.payment_score,
        "rg_score": CustomerIntelligence.rg_score,
        "rg_behavior_score": CustomerIntelligence.rg_score,
        "state": CustomerIntelligence.state,
        "current_state": CustomerIntelligence.state,
        "overall_grade": CustomerIntelligence.trust_score,
        "outstanding_current": CustomerIntelligence.outstanding_current,
        "contribution_current": CustomerIntelligence.contribution_current,
        "contribution_score_current": CustomerIntelligence.contribution_current,
        "last_purchase_date": CustomerIntelligence.last_purchase_date,
        "updated_at": CustomerIntelligence.last_updated,
    }

    # 2. Base Query
    query = select(
        CustomerIntelligence.customer_id,
        CustomerIntelligence.customer_name,
        CustomerIntelligence.city,
        CustomerIntelligence.trust_score,
        CustomerIntelligence.purchase_score,
        CustomerIntelligence.payment_score,
        CustomerIntelligence.rg_score,
        CustomerIntelligence.state,
        CustomerIntelligence.trust_previous,
        CustomerIntelligence.purchase_previous,
        CustomerIntelligence.payment_previous,
        CustomerIntelligence.rg_previous,
        CustomerIntelligence.last_updated,
        CustomerIntelligence.outstanding_current,
        CustomerIntelligence.outstanding_previous,
        CustomerIntelligence.contribution_current,
        CustomerIntelligence.contribution_previous,
        CustomerIntelligence.last_purchase_date
    )

    # 3. Dynamic Filtering
    if overall_grade:
        grades = [g.strip().upper() for g in overall_grade.split(",")]
        grade_conditions = []
        for g in grades:
            if g == "A":
                grade_conditions.append(CustomerIntelligence.trust_score >= 0.70)
            elif g == "B":
                grade_conditions.append((CustomerIntelligence.trust_score >= 0.55) & (CustomerIntelligence.trust_score < 0.70))
            elif g == "C":
                grade_conditions.append((CustomerIntelligence.trust_score >= 0.40) & (CustomerIntelligence.trust_score < 0.55))
            elif g == "D":
                grade_conditions.append((CustomerIntelligence.trust_score < 0.40) | (CustomerIntelligence.trust_score.is_(None)))
        if grade_conditions:
            query = query.where(or_(*grade_conditions))

    if current_state:
        states = [s.strip().lower() for s in current_state.split(",")]
        if len(states) > 1:
            query = query.where(CustomerIntelligence.state.in_(states))
        else:
            query = query.where(CustomerIntelligence.state.ilike(states[0]))
    
    if trust_score_min is not None:
        query = query.where(CustomerIntelligence.trust_score >= trust_score_min)
    if trust_score_max is not None:
        query = query.where(CustomerIntelligence.trust_score <= trust_score_max)
        
    pay_min = payment_score_min if payment_score_min is not None else payment_behavior_min
    pay_max = payment_score_max if payment_score_max is not None else payment_behavior_max
    pur_min = purchase_score_min if purchase_score_min is not None else purchase_behavior_min
    pur_max = purchase_score_max if purchase_score_max is not None else purchase_behavior_max

    if pay_min is not None:
        query = query.where(CustomerIntelligence.payment_score >= pay_min)
    if pay_max is not None:
        query = query.where(CustomerIntelligence.payment_score <= pay_max)
        
    if pur_min is not None:
        query = query.where(CustomerIntelligence.purchase_score >= pur_min)
    if pur_max is not None:
        query = query.where(CustomerIntelligence.purchase_score <= pur_max)

    if rg_score_min is not None:
        query = query.where(CustomerIntelligence.rg_score >= rg_score_min)
    if rg_score_max is not None:
        query = query.where(CustomerIntelligence.rg_score <= rg_score_max)

    if contribution_min is not None:
        query = query.where(CustomerIntelligence.contribution_current >= contribution_min)
    if contribution_max is not None:
        query = query.where(CustomerIntelligence.contribution_current <= contribution_max)

    if last_purchase_date_start is not None:
        query = query.where(CustomerIntelligence.last_purchase_date >= last_purchase_date_start)
    if last_purchase_date_end is not None:
        query = query.where(CustomerIntelligence.last_purchase_date <= last_purchase_date_end)

    if search:
        search_filters = [
            CustomerIntelligence.customer_id.ilike(f"%{search}%"),
            CustomerIntelligence.customer_name.ilike(f"%{search}%"),
            CustomerIntelligence.city.ilike(f"%{search}%")
        ]
        query = query.where(or_(*search_filters))

    # 4. Sorting
    sort_col = sort_mapping.get(sort_by, CustomerIntelligence.trust_score)
    query = query.where(sort_col.is_not(None))

    if sort_order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))

    return query


@router.get(
    "", 
    response_model=StandardResponse[CustomerDatatableResponseData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def list_customers_datatable(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    sort_by: str = Query("trust_score", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str | None = Query(None, description="Fuzzy search by customer ID or name"),
    overall_grade: str | None = Query(None, description="Filter by overall grade (A, B, C, etc.)"),
    current_state: str | None = Query(None, description="Filter by behavioral state"),
    trust_score_min: float | None = Query(None, description="Min trust score"),
    trust_score_max: float | None = Query(None, description="Max trust score"),
    payment_score_min: float | None = Query(None, description="Min payment score"),
    payment_score_max: float | None = Query(None, description="Max payment score"),
    purchase_score_min: float | None = Query(None, description="Min purchase score"),
    purchase_score_max: float | None = Query(None, description="Max purchase score"),
    payment_behavior_min: float | None = Query(None, description="Min payment behavior score"),
    payment_behavior_max: float | None = Query(None, description="Max payment behavior score"),
    purchase_behavior_min: float | None = Query(None, description="Min purchase behavior score"),
    purchase_behavior_max: float | None = Query(None, description="Max purchase behavior score"),
    rg_score_min: float | None = Query(None, description="Min RG score"),
    rg_score_max: float | None = Query(None, description="Max RG score"),
    contribution_min: float | None = Query(None, description="Min contribution score"),
    contribution_max: float | None = Query(None, description="Max contribution score"),
    last_purchase_date_start: date | None = Query(None, description="Start date of last purchase"),
    last_purchase_date_end: date | None = Query(None, description="End date of last purchase"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Production-grade customer listing endpoint for datatable population.
    Queries ONLY customer_intelligence for extreme performance.
    """
    start_time = time.time()

    # 1. Build Query using Helper
    base_query = build_customers_query(
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        overall_grade=overall_grade,
        current_state=current_state,
        trust_score_min=trust_score_min,
        trust_score_max=trust_score_max,
        payment_score_min=payment_score_min,
        payment_score_max=payment_score_max,
        purchase_score_min=purchase_score_min,
        purchase_score_max=purchase_score_max,
        payment_behavior_min=payment_behavior_min,
        payment_behavior_max=payment_behavior_max,
        purchase_behavior_min=purchase_behavior_min,
        purchase_behavior_max=purchase_behavior_max,
        rg_score_min=rg_score_min,
        rg_score_max=rg_score_max,
        contribution_min=contribution_min,
        contribution_max=contribution_max,
        last_purchase_date_start=last_purchase_date_start,
        last_purchase_date_end=last_purchase_date_end,
    )

    # 2. Pagination & Execution
    count_stmt = select(func.count()).select_from(base_query.subquery())
    count_res = await db.execute(count_stmt)
    total_records = count_res.scalar() or 0

    # Apply offset and limit to the base_query
    query = base_query.offset((page - 1) * limit).limit(limit)
    res = await db.execute(query)
    customers = res.mappings().all()

    # 3. Response Mapping
    rows = []
    for c in customers:
        t_score = c["trust_score"] or 0.0
        t_prev = c["trust_previous"] or 0.0
        pur_score = c["purchase_score"] or 0.0
        pur_prev = c["purchase_previous"] or 0.0
        pay_score = c["payment_score"] or 0.0
        pay_prev = c["payment_previous"] or 0.0
        rg_score = c["rg_score"] or 0.0
        rg_prev = c["rg_previous"] or 0.0
        out_curr = c["outstanding_current"] or 0.0
        out_prev = c["outstanding_previous"] or 0.0
        contrib_curr = c["contribution_current"] or 0.0
        contrib_prev = c["contribution_previous"] or 0.0

        derived_grade = "A" if t_score >= 0.70 else "B" if t_score >= 0.55 else "C" if t_score >= 0.40 else "D"

        def calculate_pct_delta(curr, prev):
            if not prev:
                return 0.0 if not curr else 100.0
            return round(((curr - prev) / prev) * 100.0, 2)

        rows.append(CustomerDatatableRow(
            customer_id=c["customer_id"],
            customer_name=c["customer_name"],
            city=c["city"],
            
            # Standard Fields
            trust_score=t_score,
            purchase_score=pur_score,
            payment_score=pay_score,
            rg_score=rg_score,
            state=c["state"],
            overall_grade=derived_grade,
            outstanding_current=out_curr,
            outstanding_previous=out_prev,
            contribution_current=contrib_curr,
            contribution_previous=contrib_prev,
            last_purchase_date=c.get("last_purchase_date").strftime("%Y-%m-%d") if c.get("last_purchase_date") else None,
            
            # Legacy Fields (Backward Compatibility)
            purchase_behavior_score=pur_score,
            payment_behavior_score=pay_score,
            rg_behavior_score=rg_score,
            current_state=c["state"],
            contribution_score_current=contrib_curr,
            last_purchased_at=c.get("last_purchase_date").strftime("%Y-%m-%d") if c.get("last_purchase_date") else None,
            
            deltas=CustomerDatatableDeltas(
                trust_score=round(t_score - t_prev, 4),
                purchase_behavior_score=round(pur_score - pur_prev, 4),
                payment_behavior_score=round(pay_score - pay_prev, 4),
                rg_behavior_score=round(rg_score - rg_prev, 4),
                contribution_score=round(contrib_curr - contrib_prev, 4),
                outstanding_delta=calculate_pct_delta(out_curr, out_prev)
            )
        ))

    processing_time_ms = int((time.time() - start_time) * 1000)
    total_pages = (total_records + limit - 1) // limit if limit > 0 else 0

    # 4. Standardized Metadata
    metadata = {
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        },
        "sorting": {
            "sort_by": sort_by,
            "sort_order": sort_order
        },
        "filters": {
            "overall_grade": overall_grade,
            "current_state": current_state,
            "trust_score_range": [trust_score_min, trust_score_max],
            "payment_score_range": [payment_score_min, payment_score_max],
            "purchase_score_range": [purchase_score_min, purchase_score_max],
            "payment_behavior_range": [payment_behavior_min, payment_behavior_max],
            "purchase_behavior_range": [purchase_behavior_min, purchase_behavior_max],
            "rg_score_range": [rg_score_min, rg_score_max],
            "contribution_range": [contribution_min, contribution_max],
            "last_purchase_date_range": [
                last_purchase_date_start.strftime("%Y-%m-%d") if last_purchase_date_start else None,
                last_purchase_date_end.strftime("%Y-%m-%d") if last_purchase_date_end else None
            ]
        },
        "search": search,
        "processing_time_ms": processing_time_ms
    }

    return success_response(
        message="Customers retrieved successfully",
        data={"customers": [r.model_dump() for r in rows]},
        metadata=metadata,
        request=request
    )


@router.get(
    "/export/csv",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def export_customers_csv(
    request: Request,
    sort_by: str = Query("trust_score", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str | None = Query(None, description="Fuzzy search by customer ID or name"),
    overall_grade: str | None = Query(None, description="Filter by overall grade (A, B, C, etc.)"),
    current_state: str | None = Query(None, description="Filter by behavioral state"),
    trust_score_min: float | None = Query(None, description="Min trust score"),
    trust_score_max: float | None = Query(None, description="Max trust score"),
    payment_score_min: float | None = Query(None, description="Min payment score"),
    payment_score_max: float | None = Query(None, description="Max payment score"),
    purchase_score_min: float | None = Query(None, description="Min purchase score"),
    purchase_score_max: float | None = Query(None, description="Max purchase score"),
    payment_behavior_min: float | None = Query(None, description="Min payment behavior score"),
    payment_behavior_max: float | None = Query(None, description="Max payment behavior score"),
    purchase_behavior_min: float | None = Query(None, description="Min purchase behavior score"),
    purchase_behavior_max: float | None = Query(None, description="Max purchase behavior score"),
    rg_score_min: float | None = Query(None, description="Min RG score"),
    rg_score_max: float | None = Query(None, description="Max RG score"),
    contribution_min: float | None = Query(None, description="Min contribution score"),
    contribution_max: float | None = Query(None, description="Max contribution score"),
    last_purchase_date_start: date | None = Query(None, description="Start date of last purchase"),
    last_purchase_date_end: date | None = Query(None, description="End date of last purchase"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Exports the filtered and sorted customer list as a CSV file.
    Streams the response for large datasets.
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    # 1. Build Query using same helper
    query = build_customers_query(
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        overall_grade=overall_grade,
        current_state=current_state,
        trust_score_min=trust_score_min,
        trust_score_max=trust_score_max,
        payment_score_min=payment_score_min,
        payment_score_max=payment_score_max,
        purchase_score_min=purchase_score_min,
        purchase_score_max=purchase_score_max,
        payment_behavior_min=payment_behavior_min,
        payment_behavior_max=payment_behavior_max,
        purchase_behavior_min=purchase_behavior_min,
        purchase_behavior_max=purchase_behavior_max,
        rg_score_min=rg_score_min,
        rg_score_max=rg_score_max,
        contribution_min=contribution_min,
        contribution_max=contribution_max,
        last_purchase_date_start=last_purchase_date_start,
        last_purchase_date_end=last_purchase_date_end,
    )

    async def generate_csv():
        # CSV Headers
        headers = [
            "Customer ID", "Customer Name", "City", "Trust Score", 
            "Purchase Score", "Payment Score", "RG Score", "State",
            "Outstanding", "Contribution", "Last Purchase Date"
        ]
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        # Execute and stream
        result = await db.stream(query)
        async for row in result:
            # Map row to CSV format
            writer.writerow([
                row.customer_id,
                row.customer_name,
                row.city,
                round(row.trust_score, 4) if row.trust_score else 0.0,
                round(row.purchase_score, 4) if row.purchase_score else 0.0,
                round(row.payment_score, 4) if row.payment_score else 0.0,
                round(row.rg_score, 4) if row.rg_score else 0.0,
                row.state,
                round(row.outstanding_current, 2) if row.outstanding_current else 0.0,
                round(row.contribution_current, 2) if row.contribution_current else 0.0,
                row.last_purchase_date.strftime("%Y-%m-%d") if row.last_purchase_date else ""
            ])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    filename = f"customers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# --- Customer Detail Intelligence Endpoint ---

customer_detail_router = APIRouter(prefix="/customer", tags=["Customers"])


@customer_detail_router.get(
    "/{id}",
    response_model=StandardResponse[CustomerProfileResponseData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Customer Not Found"},
    },
)
async def get_customer_profile(
    id: str,
    request: Request,
    window_days: int = Query(365, ge=1, le=720, description="Window size in days"),
    start_date: date | None = Query(None, description="Custom start date"),
    end_date: date | None = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Returns a complete longitudinal customer intelligence profile.
    Mandatory: Queries customer_intelligence exclusively for default serving.
    """
    start_time = time.time()
    repo = IntelligenceRepository(db)
    orchestrator = IntelligenceOrchestrator()

    # 1. Fetch Materialized Intelligence (Single Source of Serving)
    cached_intel = await repo.get_latest_customer_state(id)
    
    if not cached_intel:
        raise StarletteHTTPException(status_code=404, detail=f"Customer {id} not found in intelligence serving layer.")

    # 2. Hybrid Decision Logic
    is_default_window = not start_date and not end_date and window_days == 365
    
    if is_default_window:
        # PURE CACHE RETURN: No runtime calculations, no joins, no ledger scans.
        t_score = cached_intel.trust_score or 0.0
        t_prev = cached_intel.trust_previous or 0.0
        pur_val = cached_intel.purchase_score or 0.0
        pur_prev = cached_intel.purchase_previous or 0.0
        pay_val = cached_intel.payment_score or 0.0
        pay_prev = cached_intel.payment_previous or 0.0
        rg_val = cached_intel.rg_score or 0.0
        rg_prev = cached_intel.rg_previous or 0.0
        out_curr = cached_intel.outstanding_current or 0.0
        out_prev = cached_intel.outstanding_previous or 0.0
        contrib_curr = cached_intel.contribution_current or 0.0
        contrib_prev = cached_intel.contribution_previous or 0.0

        def calculate_pct_delta(curr, prev):
            if not prev:
                return 0.0 if not curr else 100.0
            return round(((curr - prev) / prev) * 100.0, 2)

        data = CustomerProfileResponseData(
            customer=CustomerDetailSchema(
                customer_id=id,
                customer_name=cached_intel.customer_name,
                city=cached_intel.city,
                scores=CustomerScoreSchema(
                    trust_score=t_score,
                    purchase_behavior_score=pur_val,
                    payment_behavior_score=pay_val,
                    rg_behavior_score=rg_val,
                    outstanding_current=out_curr,
                    outstanding_previous=out_prev
                ),
                deltas=CustomerDeltaSchema(
                    trust_score=round(t_score - t_prev, 4),
                    purchase_behavior_score=round(pur_val - pur_prev, 4),
                    payment_behavior_score=round(pay_val - pay_prev, 4),
                    rg_behavior_score=round(rg_val - rg_prev, 4),
                    outstanding_delta=calculate_pct_delta(out_curr, out_prev)
                ),
                behavior_state=cached_intel.state or "UNKNOWN",
                organization_contribution=OrgContributionSchema(
                    current_percentage=round(contrib_curr, 2),
                    delta=round(contrib_curr - contrib_prev, 4)
                ),
                last_purchased_at=cached_intel.last_purchase_date.strftime("%Y-%m-%d") if cached_intel.last_purchase_date else None,
                updated_at=cached_intel.last_updated.isoformat() if cached_intel.last_updated else None
            )
        )
        return success_response(
            message="Customer profile retrieved successfully (materialized cache)",
            data=data.model_dump(),
            metadata={
                "mode": "materialized",
                "window_days": 365,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            },
            request=request
        )

    # 3. Dynamic Calculation (ONLY for Custom Window)
    customer_basic = {
        "customer_id": id,
        "customer_name": cached_intel.customer_name,
        "city_name": cached_intel.city
    }

    latest_data_date = await repo.get_latest_ledger_date()
    now = datetime.now(UTC)
    # Anchor on latest data if no custom end_date provided
    anchor_dt = datetime.combine(latest_data_date or now.date(), now.time(), tzinfo=UTC)
    mode = "dynamic"
    
    if start_date and end_date:
        mode = "custom"
        curr_end = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        curr_start = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        duration = (curr_end - curr_start).days + 1
        prev_end = curr_start - timedelta(microseconds=1)
        prev_start = curr_start - timedelta(days=duration)
    else:
        curr_end = anchor_dt
        curr_start = anchor_dt - timedelta(days=window_days)
        prev_end = curr_start - timedelta(microseconds=1)
        prev_start = curr_start - timedelta(days=window_days)

    curr_ctx = AnalysisContext(window_days=window_days, end_date=curr_end.date(), start_date=curr_start.date())
    prev_window_days = window_days if mode == "dynamic" else (curr_end.date() - curr_start.date()).days + 1
    prev_ctx = AnalysisContext(
        window_days=prev_window_days, 
        end_date=prev_end.date(),
        start_date=prev_start.date()
    )

    correlation_id = request.state.correlation_id if hasattr(request.state, "correlation_id") else None
    resilient_orchestrator = ResilientIntelligenceOrchestrator(db, correlation_id=correlation_id)
    
    res = await resilient_orchestrator.execute_resilient(
        customer_id=id,
        customer_basic=customer_basic,
        curr_ctx=curr_ctx,
        prev_ctx=prev_ctx,
        orchestrator=orchestrator,
        start_time=start_time
    )

    metadata = {
        "mode": res.mode.value,
        "health_status": res.health_status.value,
        "window_days": window_days,
        "start_date": curr_start.isoformat(),
        "end_date": curr_end.isoformat(),
        "previous_window": {
            "start_date": prev_start.isoformat(),
            "end_date": prev_end.isoformat(),
        },
        "forensics": res.forensics,
        **res.metadata
    }
    
    return success_response(
        f"Customer profile retrieved successfully ({res.mode.value} mode)", 
        data=res.data.model_dump(), 
        metadata=metadata, 
        request=request
    )


# --- Graph Endpoints ---

@customer_detail_router.get(
    "/{id}/purchase-graph",
    response_model=StandardResponse[GraphResponseData[PurchaseGraphPoint]],
)
async def get_purchase_graph(
    id: str,
    request: Request,
    window_days: int = Query(365, ge=1, le=720),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly|yearly)$"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """Longitudinal purchase activity timeline reconstructed from ledger events."""
    start_time = time.time()
    
    # 1. Resolve Date Range
    s_date, e_date = await resolve_customer_dates(db, window_days, start_date, end_date)

    # 2. Fetch Ledger Events
    stmt = select(EventLedger.event_date, EventLedger.amount).where(
        func.trim(EventLedger.customer_id) == id,
        EventLedger.event_type == "SALE",
        EventLedger.event_date >= s_date,
        EventLedger.event_date <= e_date,
        EventLedger.event_date <= func.current_date(),
        not_(EventLedger.is_voided)
    )
    res = await db.execute(stmt)
    rows = res.all()
    
    if not rows:
        df = pl.DataFrame(schema={"date": pl.Date, "purchase_amount": pl.Float64, "invoice_count": pl.Int64})
    else:
        df = pl.DataFrame([{"date": normalize_temporal_to_date(r[0]), "purchase_amount": float(r[1]), "invoice_count": 1} for r in rows])
    
    # 3. Create Daily Grid
    date_range = pl.date_range(s_date, e_date, "1d", eager=True).alias("date")
    daily_grid_df = pl.DataFrame(date_range) # Keep as Date type

    # 4. Map Daily Values
    if not df.is_empty():
        daily_events = df.group_by("date").agg([
            pl.col("purchase_amount").sum(),
            pl.col("invoice_count").sum()
        ]) # Already Date type
        daily_df = daily_grid_df.join(daily_events, on="date", how="left").fill_null(0.0)
    else:
        daily_df = daily_grid_df.with_columns(
            pl.lit(0.0).alias("purchase_amount"),
            pl.lit(0).alias("invoice_count")
        )

    # 5. Aggregate by Granularity
    daily_df = daily_df.with_columns(pl.col("date").cast(pl.Datetime))
    every = {"daily": "1d", "weekly": "1w", "monthly": "1mo", "yearly": "1y"}[granularity]
    agg_df = daily_df.sort("date").group_by_dynamic("date", every=every).agg([
        pl.col("purchase_amount").sum(),
        pl.col("invoice_count").sum()
    ])

    # 6. Calculate period bounds
    final_df = agg_df.with_columns(
        pl.col("date").alias("period_start"),
        pl.col("date").dt.offset_by(every).dt.offset_by("-1d").alias("period_end")
    )
    
    # Clip bounds to [s_date, e_date]
    s_dt_clipping = datetime.combine(s_date, datetime.min.time())
    e_dt_clipping = datetime.combine(e_date, datetime.max.time())
    
    final_df = final_df.with_columns(
        pl.when(pl.col("period_start") < s_dt_clipping).then(pl.lit(s_dt_clipping)).otherwise(pl.col("period_start")).alias("period_start"),
        pl.when(pl.col("period_end") > e_dt_clipping).then(pl.lit(e_dt_clipping)).otherwise(pl.col("period_end")).alias("period_end")
    )

    graph_data = [
        PurchaseGraphPoint(
            period_start=normalize_temporal_to_str(row["period_start"]),
            period_end=normalize_temporal_to_str(row["period_end"]),
            purchase_amount=round(row["purchase_amount"], 2),
            invoice_count=int(row["invoice_count"])
        )
        for row in final_df.to_dicts()
    ]

    metadata = {
        "window": {
            "mode": "custom" if start_date or end_date else "dynamic", 
            "window_days": (e_date - s_date).days,
            "start_date": s_date.isoformat(), 
            "end_date": e_date.isoformat(), 
            "granularity": granularity
        },
        "points_returned": len(graph_data),
        "processing_time_ms": int((time.time() - start_time) * 1000)
    }
    return success_response("Purchase graph retrieved successfully", data={"graph": graph_data}, metadata=metadata, request=request)


@customer_detail_router.get(
    "/{id}/payment-graph",
    response_model=StandardResponse[GraphResponseData[PaymentGraphPoint]],
)
async def get_payment_graph(
    id: str,
    request: Request,
    window_days: int = Query(365, ge=1, le=720),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly|yearly)$"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """Visualize payment activity over time from ledger events."""
    start_time = time.time()
    
    # 1. Resolve Date Range
    s_date, e_date = await resolve_customer_dates(db, window_days, start_date, end_date)

    # 2. Fetch Ledger Events
    stmt = select(EventLedger.event_date, EventLedger.amount).where(
        func.trim(EventLedger.customer_id) == id,
        EventLedger.event_type == "PAYMENT",
        EventLedger.event_date >= s_date,
        EventLedger.event_date <= e_date,
        EventLedger.event_date <= func.current_date(),
        not_(EventLedger.is_voided)
    )
    res = await db.execute(stmt)
    rows = res.all()
    
    if not rows:
        df = pl.DataFrame(schema={"date": pl.Date, "payment_amount": pl.Float64, "payment_count": pl.Int64})
    else:
        df = pl.DataFrame([{"date": normalize_temporal_to_date(r[0]), "payment_amount": float(r[1]), "payment_count": 1} for r in rows])
    
    # 3. Create Daily Grid
    date_range = pl.date_range(s_date, e_date, "1d", eager=True).alias("date")
    daily_grid_df = pl.DataFrame(date_range) # Keep as Date type

    # 4. Map Daily Values
    if not df.is_empty():
        daily_events = df.group_by("date").agg([
            pl.col("payment_amount").sum(),
            pl.col("payment_count").sum()
        ]) # Already Date type
        daily_df = daily_grid_df.join(daily_events, on="date", how="left").fill_null(0.0)
    else:
        daily_df = daily_grid_df.with_columns(
            pl.lit(0.0).alias("payment_amount"),
            pl.lit(0).alias("payment_count")
        )

    # 5. Aggregate by Granularity
    daily_df = daily_df.with_columns(pl.col("date").cast(pl.Datetime))
    every = {"daily": "1d", "weekly": "1w", "monthly": "1mo", "yearly": "1y"}[granularity]
    agg_df = daily_df.sort("date").group_by_dynamic("date", every=every).agg([
        pl.col("payment_amount").sum(),
        pl.col("payment_count").sum()
    ])

    # 6. Calculate period bounds
    final_df = agg_df.with_columns(
        pl.col("date").alias("period_start"),
        pl.col("date").dt.offset_by(every).dt.offset_by("-1d").alias("period_end")
    )
    
    # Clip bounds to [s_date, e_date]
    s_dt_clipping = datetime.combine(s_date, datetime.min.time())
    e_dt_clipping = datetime.combine(e_date, datetime.max.time())
    
    final_df = final_df.with_columns(
        pl.when(pl.col("period_start") < s_dt_clipping).then(pl.lit(s_dt_clipping)).otherwise(pl.col("period_start")).alias("period_start"),
        pl.when(pl.col("period_end") > e_dt_clipping).then(pl.lit(e_dt_clipping)).otherwise(pl.col("period_end")).alias("period_end")
    )

    graph_data = [
        PaymentGraphPoint(
            period_start=normalize_temporal_to_str(row["period_start"]),
            period_end=normalize_temporal_to_str(row["period_end"]),
            payment_amount=round(row["payment_amount"], 2),
            payment_count=int(row["payment_count"])
        )
        for row in final_df.to_dicts()
    ]

    metadata = {
        "window": {
            "mode": "custom" if start_date or end_date else "dynamic", 
            "window_days": (e_date - s_date).days,
            "start_date": s_date.isoformat(), 
            "end_date": e_date.isoformat(), 
            "granularity": granularity
        },
        "points_returned": len(graph_data),
        "processing_time_ms": int((time.time() - start_time) * 1000)
    }
    return success_response("Payment graph retrieved successfully", data={"graph": graph_data}, metadata=metadata, request=request)


@customer_detail_router.get(
    "/{id}/rg-graph",
    response_model=StandardResponse[GraphResponseData[RGGraphPoint]],
)
async def get_rg_graph(
    id: str,
    request: Request,
    window_days: int = Query(365, ge=1, le=720),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly|yearly)$"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """Visualize returns/credit behavior longitudinally from ledger events."""
    start_time = time.time()
    
    # 1. Resolve Date Range
    s_date, e_date = await resolve_customer_dates(db, window_days, start_date, end_date)

    # 2. Fetch Ledger Events
    stmt = select(EventLedger.event_date, EventLedger.amount).where(
        func.trim(EventLedger.customer_id) == id,
        EventLedger.event_type == "RETURN",
        EventLedger.event_date >= s_date,
        EventLedger.event_date <= e_date,
        EventLedger.event_date <= func.current_date(),
        not_(EventLedger.is_voided)
    )
    res = await db.execute(stmt)
    rows = res.all()
    
    if not rows:
        df = pl.DataFrame(schema={"date": pl.Date, "rg_amount": pl.Float64, "raw_rg_amount": pl.Float64, "rg_count": pl.Int64})
    else:
        df = pl.DataFrame([
            {
                "date": normalize_temporal_to_date(r[0]), 
                "rg_amount": abs(float(r[1])), 
                "raw_rg_amount": abs(float(r[1])),
                "rg_count": 1
            } for r in rows
        ])
    
    # 3. Create Daily Grid
    date_range = pl.date_range(s_date, e_date, "1d", eager=True).alias("date")
    daily_grid_df = pl.DataFrame(date_range) # Keep as Date type

    # 4. Map Daily Values
    if not df.is_empty():
        daily_events = df.group_by("date").agg([
            pl.col("rg_amount").sum(),
            pl.col("raw_rg_amount").sum(),
            pl.col("rg_count").sum()
        ]) # Already Date type from df
        daily_df = daily_grid_df.join(daily_events, on="date", how="left").fill_null(0.0)
    else:
        daily_df = daily_grid_df.with_columns(
            pl.lit(0.0).alias("rg_amount"),
            pl.lit(0.0).alias("raw_rg_amount"),
            pl.lit(0).alias("rg_count")
        )

    # 5. Aggregate by Granularity (requires Datetime for group_by_dynamic in some polars versions)
    daily_df = daily_df.with_columns(pl.col("date").cast(pl.Datetime))
    every = {"daily": "1d", "weekly": "1w", "monthly": "1mo", "yearly": "1y"}[granularity]
    agg_df = daily_df.sort("date").group_by_dynamic("date", every=every).agg([
        pl.col("rg_amount").sum(),
        pl.col("raw_rg_amount").sum(),
        pl.col("rg_count").sum()
    ])

    # 6. Calculate period bounds
    final_df = agg_df.with_columns(
        pl.col("date").alias("period_start"),
        pl.col("date").dt.offset_by(every).dt.offset_by("-1d").alias("period_end")
    )
    
    # Clip bounds
    s_dt_clipping = datetime.combine(s_date, datetime.min.time())
    e_dt_clipping = datetime.combine(e_date, datetime.max.time())
    
    final_df = final_df.with_columns(
        pl.when(pl.col("period_start") < s_dt_clipping).then(pl.lit(s_dt_clipping)).otherwise(pl.col("period_start")).alias("period_start"),
        pl.when(pl.col("period_end") > e_dt_clipping).then(pl.lit(e_dt_clipping)).otherwise(pl.col("period_end")).alias("period_end")
    )

    graph_data = [
        RGGraphPoint(
            period_start=normalize_temporal_to_str(row["period_start"]),
            period_end=normalize_temporal_to_str(row["period_end"]),
            rg_amount=round(row["rg_amount"], 2),
            raw_rg_amount=round(row["raw_rg_amount"], 2),
            rg_count=int(row["rg_count"])
        )
        for row in final_df.to_dicts()
    ]

    metadata = {
        "window": {
            "mode": "custom" if start_date or end_date else "dynamic", 
            "window_days": (e_date - s_date).days,
            "start_date": s_date.isoformat(), 
            "end_date": e_date.isoformat(), 
            "granularity": granularity
        },
        "points_returned": len(graph_data),
        "processing_time_ms": int((time.time() - start_time) * 1000)
    }
    return success_response("RG graph retrieved successfully", data={"graph": graph_data}, metadata=metadata, request=request)


@customer_detail_router.get(
    "/{id}/outstanding-graph",
    response_model=StandardResponse[GraphResponseData[OutstandingGraphPoint]],
)
async def get_outstanding_graph(
    id: str,
    request: Request,
    window_days: int = Query(365, ge=1, le=720),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly|yearly)$"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """Visualize longitudinal outstanding exposure evolution and movement reconstructed from ledger events."""
    start_time = time.time()
    
    # 1. Resolve Date Range
    s_date, e_date = await resolve_customer_dates(db, window_days, start_date, end_date)

    # 2. Reconstruct Opening Outstanding Balance (before s_date)
    opening_stmt = select(
        func.sum(
            case(
                (EventLedger.event_type.in_(["SALE", "OPENING_BALANCE"]), EventLedger.amount),
                else_=-EventLedger.amount
            )
        )
    ).where(
        func.trim(EventLedger.customer_id) == id,
        EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT", "OPENING_BALANCE"]),
        EventLedger.event_date < s_date,
        EventLedger.event_date <= func.current_date(),
        not_(EventLedger.is_voided),
        EventLedger.is_ok == 0
    )
    opening_res = await db.execute(opening_stmt)
    opening_outstanding_initial = float(opening_res.scalar() or 0.0)

    # 3. Fetch Ledger Events in window
    stmt = select(EventLedger.event_date, EventLedger.amount, EventLedger.event_type).where(
        func.trim(EventLedger.customer_id) == id,
        EventLedger.event_type.in_(["SALE", "PAYMENT", "RETURN", "DISCOUNT"]),
        EventLedger.event_type != "OPENING_BALANCE",
        EventLedger.event_date >= s_date,
        EventLedger.event_date <= e_date,
        EventLedger.event_date <= func.current_date(),
        not_(EventLedger.is_voided),
        EventLedger.is_ok == 0
    ).order_by(asc(EventLedger.event_date), asc(EventLedger.customer_sequence_number))

    res = await db.execute(stmt)
    rows = res.all()
    
    if not rows:
        df = pl.DataFrame(schema={"date": pl.Date, "purchase_added": pl.Float64, "payment_received": pl.Float64, "rg_adjustment": pl.Float64})
    else:
        df = pl.DataFrame([
            {
                "date": normalize_temporal_to_date(r[0]),
                "purchase_added": float(r[1]) if r[2] in ["SALE", "OPENING_BALANCE"] else 0.0,
                "payment_received": float(r[1]) if r[2] in ["PAYMENT", "DISCOUNT"] else 0.0,
                "rg_adjustment": float(r[1]) if r[2] == "RETURN" else 0.0
            } for r in rows
        ])
    
    # 4. Create Daily Grid
    date_range = pl.date_range(s_date, e_date, "1d", eager=True).alias("date")
    daily_grid_df = pl.DataFrame(date_range) # Keep as Date type

    # 5. Map Daily Values
    if not df.is_empty():
        daily_events = df.group_by("date").agg([
            pl.col("purchase_added").sum(),
            pl.col("payment_received").sum(),
            pl.col("rg_adjustment").sum()
        ]) # Already Date type
        daily_df = daily_grid_df.join(daily_events, on="date", how="left").fill_null(0.0)
    else:
        daily_df = daily_grid_df.with_columns(
            pl.lit(0.0).alias("purchase_added"),
            pl.lit(0.0).alias("payment_received"),
            pl.lit(0.0).alias("rg_adjustment")
        )

    # 6. Reconstruct running outstanding daily balances
    # Accountant Formula: Outstanding(t) = Opening + Purchases - Payments - RG
    daily_df = daily_df.with_columns(
        (pl.col("purchase_added") - pl.col("payment_received") - pl.col("rg_adjustment")).alias("daily_balance_delta")
    )
    daily_df = daily_df.with_columns(
        (opening_outstanding_initial + pl.col("daily_balance_delta").cum_sum()).alias("closing_outstanding")
    )
    daily_df = daily_df.with_columns(
        pl.col("closing_outstanding").shift(1).fill_null(opening_outstanding_initial).alias("opening_outstanding")
    )

    # 7. Aggregate by Granularity
    daily_df = daily_df.with_columns(pl.col("date").cast(pl.Datetime))
    every = {"daily": "1d", "weekly": "1w", "monthly": "1mo", "yearly": "1y"}[granularity]
    agg_df = daily_df.sort("date").group_by_dynamic("date", every=every).agg([
        pl.col("purchase_added").sum(),
        pl.col("payment_received").sum(),
        pl.col("rg_adjustment").sum(),
        pl.col("opening_outstanding").first(),
        pl.col("closing_outstanding").last(),
    ])

    # 8. Calculate period bounds
    final_df = agg_df.with_columns(
        pl.col("date").alias("period_start"),
        pl.col("date").dt.offset_by(every).dt.offset_by("-1d").alias("period_end")
    )
    
    # Clip bounds
    s_dt_clipping = datetime.combine(s_date, datetime.min.time())
    e_dt_clipping = datetime.combine(e_date, datetime.max.time())
    
    final_df = final_df.with_columns(
        pl.when(pl.col("period_start") < s_dt_clipping).then(pl.lit(s_dt_clipping)).otherwise(pl.col("period_start")).alias("period_start"),
        pl.when(pl.col("period_end") > e_dt_clipping).then(pl.lit(e_dt_clipping)).otherwise(pl.col("period_end")).alias("period_end")
    )

    graph_data = [
        OutstandingGraphPoint(
            period_start=normalize_temporal_to_str(row["period_start"]),
            period_end=normalize_temporal_to_str(row["period_end"]),
            opening_outstanding=round(row["opening_outstanding"], 2),
            purchase_added=round(row["purchase_added"], 2),
            payment_received=round(row["payment_received"], 2),
            rg_adjustment=round(row["rg_adjustment"], 2),
            closing_outstanding=round(row["closing_outstanding"], 2),
            outstanding=round(row["closing_outstanding"], 2)
        )
        for row in final_df.to_dicts()
    ]

    metadata = {
        "window": {
            "mode": "custom" if start_date or end_date else "dynamic", 
            "window_days": (e_date - s_date).days,
            "start_date": s_date.isoformat(), 
            "end_date": e_date.isoformat(), 
            "granularity": granularity
        },
        "points_returned": len(graph_data),
        "processing_time_ms": int((time.time() - start_time) * 1000)
    }
    return success_response("Outstanding graph retrieved successfully", data={"graph": graph_data}, metadata=metadata, request=request)
