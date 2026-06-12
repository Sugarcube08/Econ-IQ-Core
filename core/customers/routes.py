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

# Hardening Phase: Prediction & Recommendation service/schemas integration
from core.prediction.service import PredictionService
from core.recommendation.service import RecommendationService
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
from core.schemas.recommendation import CustomerRecommendations
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
    current_state: str | None = None,
    health_score_min: float | None = None,
    health_score_max: float | None = None,
    risk_score_min: float | None = None,
    risk_score_max: float | None = None,
    growth_score_min: float | None = None,
    growth_score_max: float | None = None,
    trust_score_min: float | None = None,
    trust_score_max: float | None = None,
    opportunity_score_min: float | None = None,
    opportunity_score_max: float | None = None,
    credit_score_min: float | None = None,
    credit_score_max: float | None = None,
    collection_score_min: float | None = None,
    collection_score_max: float | None = None,
    relationship_score_min: float | None = None,
    relationship_score_max: float | None = None,
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
        "health_score": CustomerIntelligence.health_score,
        "risk_score": CustomerIntelligence.risk_score,
        "growth_score": CustomerIntelligence.growth_score,
        "trust_score": CustomerIntelligence.trust_score,
        "opportunity_score": CustomerIntelligence.opportunity_score,
        "credit_score": CustomerIntelligence.credit_score,
        "collection_score": CustomerIntelligence.collection_score,
        "relationship_score": CustomerIntelligence.relationship_score,
        "state": CustomerIntelligence.state,
        "current_state": CustomerIntelligence.state,
        "outstanding_current": CustomerIntelligence.outstanding_current,
        "contribution_current": CustomerIntelligence.contribution_current,
        "last_purchase_date": CustomerIntelligence.last_purchase_date,
        "updated_at": CustomerIntelligence.last_updated,
    }

    # 2. Base Query
    query = select(
        CustomerIntelligence.customer_id,
        CustomerIntelligence.customer_name,
        CustomerIntelligence.city,
        CustomerIntelligence.health_score,
        CustomerIntelligence.risk_score,
        CustomerIntelligence.growth_score,
        CustomerIntelligence.trust_score,
        CustomerIntelligence.opportunity_score,
        CustomerIntelligence.credit_score,
        CustomerIntelligence.collection_score,
        CustomerIntelligence.relationship_score,
        CustomerIntelligence.state,
        CustomerIntelligence.health_previous,
        CustomerIntelligence.risk_previous,
        CustomerIntelligence.growth_previous,
        CustomerIntelligence.trust_previous,
        CustomerIntelligence.opportunity_previous,
        CustomerIntelligence.credit_previous,
        CustomerIntelligence.collection_previous,
        CustomerIntelligence.relationship_previous,
        CustomerIntelligence.last_updated,
        CustomerIntelligence.outstanding_current,
        CustomerIntelligence.outstanding_previous,
        CustomerIntelligence.contribution_current,
        CustomerIntelligence.contribution_previous,
        CustomerIntelligence.last_purchase_date
    )

    # 3. Dynamic Filtering
    if current_state:
        states = [s.strip().lower() for s in current_state.split(",")]
        if len(states) > 1:
            query = query.where(CustomerIntelligence.state.in_(states))
        else:
            query = query.where(CustomerIntelligence.state.ilike(states[0]))
    
    if health_score_min is not None:
        query = query.where(CustomerIntelligence.health_score >= health_score_min)
    if health_score_max is not None:
        query = query.where(CustomerIntelligence.health_score <= health_score_max)

    if risk_score_min is not None:
        query = query.where(CustomerIntelligence.risk_score >= risk_score_min)
    if risk_score_max is not None:
        query = query.where(CustomerIntelligence.risk_score <= risk_score_max)

    if growth_score_min is not None:
        query = query.where(CustomerIntelligence.growth_score >= growth_score_min)
    if growth_score_max is not None:
        query = query.where(CustomerIntelligence.growth_score <= growth_score_max)

    if trust_score_min is not None:
        query = query.where(CustomerIntelligence.trust_score >= trust_score_min)
    if trust_score_max is not None:
        query = query.where(CustomerIntelligence.trust_score <= trust_score_max)

    if opportunity_score_min is not None:
        query = query.where(CustomerIntelligence.opportunity_score >= opportunity_score_min)
    if opportunity_score_max is not None:
        query = query.where(CustomerIntelligence.opportunity_score <= opportunity_score_max)

    if credit_score_min is not None:
        query = query.where(CustomerIntelligence.credit_score >= credit_score_min)
    if credit_score_max is not None:
        query = query.where(CustomerIntelligence.credit_score <= credit_score_max)

    if collection_score_min is not None:
        query = query.where(CustomerIntelligence.collection_score >= collection_score_min)
    if collection_score_max is not None:
        query = query.where(CustomerIntelligence.collection_score <= collection_score_max)

    if relationship_score_min is not None:
        query = query.where(CustomerIntelligence.relationship_score >= relationship_score_min)
    if relationship_score_max is not None:
        query = query.where(CustomerIntelligence.relationship_score <= relationship_score_max)

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
    current_state: str | None = Query(None, description="Filter by behavioral state"),
    health_score_min: float | None = Query(None, description="Min health score"),
    health_score_max: float | None = Query(None, description="Max health score"),
    risk_score_min: float | None = Query(None, description="Min risk score"),
    risk_score_max: float | None = Query(None, description="Max risk score"),
    growth_score_min: float | None = Query(None, description="Min growth score"),
    growth_score_max: float | None = Query(None, description="Max growth score"),
    trust_score_min: float | None = Query(None, description="Min trust score"),
    trust_score_max: float | None = Query(None, description="Max trust score"),
    opportunity_score_min: float | None = Query(None, description="Min opportunity score"),
    opportunity_score_max: float | None = Query(None, description="Max opportunity score"),
    credit_score_min: float | None = Query(None, description="Min credit score"),
    credit_score_max: float | None = Query(None, description="Max credit score"),
    collection_score_min: float | None = Query(None, description="Min collection score"),
    collection_score_max: float | None = Query(None, description="Max collection score"),
    relationship_score_min: float | None = Query(None, description="Min relationship score"),
    relationship_score_max: float | None = Query(None, description="Max relationship score"),
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
        current_state=current_state,
        health_score_min=health_score_min,
        health_score_max=health_score_max,
        risk_score_min=risk_score_min,
        risk_score_max=risk_score_max,
        growth_score_min=growth_score_min,
        growth_score_max=growth_score_max,
        trust_score_min=trust_score_min,
        trust_score_max=trust_score_max,
        opportunity_score_min=opportunity_score_min,
        opportunity_score_max=opportunity_score_max,
        credit_score_min=credit_score_min,
        credit_score_max=credit_score_max,
        collection_score_min=collection_score_min,
        collection_score_max=collection_score_max,
        relationship_score_min=relationship_score_min,
        relationship_score_max=relationship_score_max,
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
        h_score = c["health_score"] or 0.0
        h_prev = c["health_previous"] or 0.0
        risk_score = c["risk_score"] or 0.0
        risk_prev = c["risk_previous"] or 0.0
        g_score = c["growth_score"] or 0.0
        g_prev = c["growth_previous"] or 0.0
        t_score = c["trust_score"] or 0.0
        t_prev = c["trust_previous"] or 0.0
        opp_score = c["opportunity_score"] or 0.0
        opp_prev = c["opportunity_previous"] or 0.0
        cred_score = c["credit_score"] or 0.0
        cred_prev = c["credit_previous"] or 0.0
        coll_score = c["collection_score"] or 0.0
        coll_prev = c["collection_previous"] or 0.0
        rel_score = c["relationship_score"] or 0.0
        rel_prev = c["relationship_previous"] or 0.0
        
        out_curr = c["outstanding_current"] or 0.0
        out_prev = c["outstanding_previous"] or 0.0
        contrib_curr = c["contribution_current"] or 0.0
        contrib_prev = c["contribution_previous"] or 0.0

        def calculate_pct_delta(curr, prev):
            if not prev:
                return 0.0 if not curr else 100.0
            return round(((curr - prev) / prev) * 100.0, 2)

        rows.append(CustomerDatatableRow(
            customer_id=c["customer_id"],
            customer_name=c["customer_name"],
            city=c["city"],
            
            # 8 Canonical Scores
            health_score=h_score,
            risk_score=risk_score,
            growth_score=g_score,
            trust_score=t_score,
            opportunity_score=opp_score,
            credit_score=cred_score,
            collection_score=coll_score,
            relationship_score=rel_score,
            
            state=c["state"],
            outstanding_current=out_curr,
            outstanding_previous=out_prev,
            contribution_current=contrib_curr,
            contribution_previous=contrib_prev,
            last_purchase_date=c.get("last_purchase_date").strftime("%Y-%m-%d") if c.get("last_purchase_date") else None,
            
            deltas=CustomerDatatableDeltas(
                health_score=round(h_score - h_prev, 4),
                risk_score=round(risk_score - risk_prev, 4),
                growth_score=round(g_score - g_prev, 4),
                trust_score=round(t_score - t_prev, 4),
                opportunity_score=round(opp_score - opp_prev, 4),
                credit_score=round(cred_score - cred_prev, 4),
                collection_score=round(coll_score - coll_prev, 4),
                relationship_score=round(rel_score - rel_prev, 4),
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
            "current_state": current_state,
            "health_score_range": [health_score_min, health_score_max],
            "risk_score_range": [risk_score_min, risk_score_max],
            "growth_score_range": [growth_score_min, growth_score_max],
            "trust_score_range": [trust_score_min, trust_score_max],
            "opportunity_score_range": [opportunity_score_min, opportunity_score_max],
            "credit_score_range": [credit_score_min, credit_score_max],
            "collection_score_range": [collection_score_min, collection_score_max],
            "relationship_score_range": [relationship_score_min, relationship_score_max],
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
    current_state: str | None = Query(None, description="Filter by behavioral state"),
    health_score_min: float | None = Query(None, description="Min health score"),
    health_score_max: float | None = Query(None, description="Max health score"),
    risk_score_min: float | None = Query(None, description="Min risk score"),
    risk_score_max: float | None = Query(None, description="Max risk score"),
    growth_score_min: float | None = Query(None, description="Min growth score"),
    growth_score_max: float | None = Query(None, description="Max growth score"),
    trust_score_min: float | None = Query(None, description="Min trust score"),
    trust_score_max: float | None = Query(None, description="Max trust score"),
    opportunity_score_min: float | None = Query(None, description="Min opportunity score"),
    opportunity_score_max: float | None = Query(None, description="Max opportunity score"),
    credit_score_min: float | None = Query(None, description="Min credit score"),
    credit_score_max: float | None = Query(None, description="Max credit score"),
    collection_score_min: float | None = Query(None, description="Min collection score"),
    collection_score_max: float | None = Query(None, description="Max collection score"),
    relationship_score_min: float | None = Query(None, description="Min relationship score"),
    relationship_score_max: float | None = Query(None, description="Max relationship score"),
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
        current_state=current_state,
        health_score_min=health_score_min,
        health_score_max=health_score_max,
        risk_score_min=risk_score_min,
        risk_score_max=risk_score_max,
        growth_score_min=growth_score_min,
        growth_score_max=growth_score_max,
        trust_score_min=trust_score_min,
        trust_score_max=trust_score_max,
        opportunity_score_min=opportunity_score_min,
        opportunity_score_max=opportunity_score_max,
        credit_score_min=credit_score_min,
        credit_score_max=credit_score_max,
        collection_score_min=collection_score_min,
        collection_score_max=collection_score_max,
        relationship_score_min=relationship_score_min,
        relationship_score_max=relationship_score_max,
        contribution_min=contribution_min,
        contribution_max=contribution_max,
        last_purchase_date_start=last_purchase_date_start,
        last_purchase_date_end=last_purchase_date_end,
    )

    async def generate_csv():
        # CSV Headers
        headers = [
            "Customer ID", "Customer Name", "City", 
            "Health Score", "Risk Score", "Growth Score", "Trust Score", 
            "Opportunity Score", "Credit Score", "Collection Score", "Relationship Score", 
            "State", "Outstanding", "Contribution", "Last Purchase Date"
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
                round(row.health_score, 4) if row.health_score else 0.0,
                round(row.risk_score, 4) if row.risk_score else 0.0,
                round(row.growth_score, 4) if row.growth_score else 0.0,
                round(row.trust_score, 4) if row.trust_score else 0.0,
                round(row.opportunity_score, 4) if row.opportunity_score else 0.0,
                round(row.credit_score, 4) if row.credit_score else 0.0,
                round(row.collection_score, 4) if row.collection_score else 0.0,
                round(row.relationship_score, 4) if row.relationship_score else 0.0,
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
        h_score = cached_intel.health_score or 0.0
        h_prev = cached_intel.health_previous or 0.0
        risk_score = cached_intel.risk_score or 0.0
        risk_prev = cached_intel.risk_previous or 0.0
        g_score = cached_intel.growth_score or 0.0
        g_prev = cached_intel.growth_previous or 0.0
        t_score = cached_intel.trust_score or 0.0
        t_prev = cached_intel.trust_previous or 0.0
        opp_score = cached_intel.opportunity_score or 0.0
        opp_prev = cached_intel.opportunity_previous or 0.0
        cred_score = cached_intel.credit_score or 0.0
        cred_prev = cached_intel.credit_previous or 0.0
        coll_score = cached_intel.collection_score or 0.0
        coll_prev = cached_intel.collection_previous or 0.0
        rel_score = cached_intel.relationship_score or 0.0
        rel_prev = cached_intel.relationship_previous or 0.0
        
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
                    health_score=h_score,
                    risk_score=risk_score,
                    growth_score=g_score,
                    trust_score=t_score,
                    opportunity_score=opp_score,
                    credit_score=cred_score,
                    collection_score=coll_score,
                    relationship_score=rel_score,
                    outstanding_current=out_curr,
                    outstanding_previous=out_prev
                ),
                deltas=CustomerDeltaSchema(
                    health_score=round(h_score - h_prev, 4),
                    risk_score=round(risk_score - risk_prev, 4),
                    growth_score=round(g_score - g_prev, 4),
                    trust_score=round(t_score - t_prev, 4),
                    opportunity_score=round(opp_score - opp_prev, 4),
                    credit_score=round(cred_score - cred_prev, 4),
                    collection_score=round(coll_score - coll_prev, 4),
                    relationship_score=round(rel_score - rel_prev, 4),
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


# --- Predictions & Recommendations Endpoints ---

prediction_service = PredictionService()
recommendation_service = RecommendationService(prediction_service)

@customer_detail_router.get(
    "/{id}/predictions",
    response_model=StandardResponse[dict],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Customer Not Found"},
    }
)
async def get_customer_predictions(
    id: str,
    request: Request,
    version: str | None = Query(None, description="Model version"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Consolidated endpoint to retrieve all predictive dimensions/scores for a customer.
    """
    repo = IntelligenceRepository(db)
    cached_intel = await repo.get_latest_customer_state(id)
    if not cached_intel:
        raise StarletteHTTPException(status_code=404, detail=f"Customer {id} not found.")

    try:
        risk_pred = await prediction_service.get_risk_prediction(db, id, version)
        growth_pred = await prediction_service.get_growth_prediction(db, id, version)
        health_pred = await prediction_service.get_health_prediction(db, id, version)
        churn_pred = await prediction_service.get_churn_prediction(db, id, version)
        collection_pred = await prediction_service.get_collection_prediction(db, id, version)
        opportunity_pred = await prediction_service.get_opportunity_prediction(db, id, version)

        data = {
            "risk": risk_pred.model_dump(),
            "growth": growth_pred.model_dump(),
            "health": health_pred.model_dump(),
            "churn": churn_pred.model_dump(),
            "collection": collection_pred.model_dump(),
            "opportunity": opportunity_pred.model_dump(),
        }
        return success_response("All predictions retrieved successfully", data=data, request=request)
    except KeyError as e:
        raise StarletteHTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise StarletteHTTPException(status_code=500, detail=f"Inference execution failed: {str(e)}") from e


@customer_detail_router.get(
    "/{id}/recommendations",
    response_model=StandardResponse[CustomerRecommendations],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Customer Not Found"},
    }
)
async def get_customer_recommendations_endpoint(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve automated action recommendations for a customer.
    """
    repo = IntelligenceRepository(db)
    cached_intel = await repo.get_latest_customer_state(id)
    if not cached_intel:
        raise StarletteHTTPException(status_code=404, detail=f"Customer {id} not found.")

    try:
        recs = await recommendation_service.generate_recommendations(db, id)
        return success_response("Recommendations generated successfully", data=recs.model_dump(), request=request)
    except Exception as e:
        raise StarletteHTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}") from e


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
