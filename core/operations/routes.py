from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.core.dependencies import require_permissions
from core.core.permissions import Permission
from core.core.responses import success_response
from core.models.auth_models import APIKey, User
from core.models.state_models import CustomerIntelligence, Recommendation
from core.recommendation.service import RecommendationService
from core.schemas.operations import (
    CollectionActivityCreate,
    DecisionActionCreate,
    PaymentCommitmentCreate,
)
from core.schemas.responses import StandardResponse
from core.services.alert_service import AlertService
from core.services.collections_service import CollectionsService
from core.services.decision_audit_service import DecisionAuditService
from core.storage.postgres import get_db

router = APIRouter(tags=["Operations"])

alert_service = AlertService()
collections_service = CollectionsService()
decision_service = DecisionAuditService()
recommendation_service = RecommendationService()


# --- ALERTS ENDPOINTS ---

@router.get("/alerts", response_model=StandardResponse[Any])
async def get_alerts_endpoint(
    request: Request,
    page: int | None = Query(None, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str | None = Query(None, description="Fuzzy search by title, description, or customer name"),
    status: str | None = Query("ACTIVE", description="Filter by status (ACTIVE, ACKNOWLEDGED, ARCHIVED)"),
    severity: str | None = Query(None, description="Filter by severity (CRITICAL, WARNING, INFO)"),
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve list of system alerts. Supports pagination, search, sorting, and name enrichment.
    """
    is_paginated = (page is not None)
    calc_offset = offset
    if is_paginated:
        calc_offset = (page - 1) * limit

    alerts = await alert_service.get_alerts(
        status=status,
        severity=severity,
        customer_id=customer_id,
        limit=limit,
        offset=calc_offset,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        db_session=db
    )
    # Convert alert model instances to dictionary lists
    alerts_data = []
    for a in alerts:
        alerts_data.append({
            "id": a.id,
            "workspace_id": a.workspace_id,
            "customer_id": a.customer_id,
            "customer_name": getattr(a, "customer_name", "Unknown"),
            "alert_type": a.alert_type,
            "alert_severity": a.alert_severity,
            "title": a.title,
            "description": a.description,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "acknowledged_by": a.acknowledged_by
        })

    if is_paginated:
        total = await alert_service.get_alerts_count_filtered(
            status=status,
            severity=severity,
            customer_id=customer_id,
            search=search,
            db_session=db
        )
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        data = {
            "items": alerts_data,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    else:
        data = alerts_data

    return success_response("Alerts retrieved successfully", data=data, request=request)


@router.get("/alerts/count", response_model=StandardResponse[dict])
async def get_alerts_count_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve counts of active, critical, and warning alerts.
    """
    counts = await alert_service.get_alerts_count(db_session=db)
    return success_response("Alert counts retrieved successfully", data=counts, request=request)


@router.post("/alerts/{id}/acknowledge", response_model=StandardResponse[dict])
async def acknowledge_alert_endpoint(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Acknowledge a specific alert.
    """
    user_id = str(identity.id) if hasattr(identity, "id") else str(getattr(identity, "user_id", "system-api"))
    alert = await alert_service.acknowledge_alert(alert_id=id, user_id=user_id, db_session=db)
    if not alert:
        raise StarletteHTTPException(status_code=404, detail=f"Alert {id} not found.")
    
    data = {
        "id": alert.id,
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
    }
    return success_response("Alert acknowledged successfully", data=data, request=request)


# --- COLLECTIONS ENDPOINTS ---

@router.post("/collections/activity", response_model=StandardResponse[dict])
async def log_collections_activity_endpoint(
    payload: CollectionActivityCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Log a collections outreach action.
    """
    user_id = str(identity.id) if hasattr(identity, "id") else str(getattr(identity, "user_id", "system-api"))
    activity = await collections_service.log_activity(
        customer_id=payload.customer_id,
        user_id=user_id,
        activity_type=payload.activity_type,
        notes=payload.notes,
        outcome=payload.outcome,
        db_session=db
    )
    await db.commit()
    data = {
        "id": activity.id,
        "customer_id": activity.customer_id,
        "activity_type": activity.activity_type,
        "notes": activity.notes,
        "outcome": activity.outcome,
        "created_at": activity.created_at.isoformat()
    }
    return success_response("Activity logged successfully", data=data, request=request)


@router.get("/collections/activity", response_model=StandardResponse[list])
async def get_collections_activities_endpoint(
    request: Request,
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve logged collections activities.
    """
    from core.models.state_models import CollectionActivity, CustomerIntelligence
    stmt = select(CollectionActivity, CustomerIntelligence.customer_name).outerjoin(
        CustomerIntelligence, CollectionActivity.customer_id == CustomerIntelligence.customer_id
    )
    if customer_id:
        stmt = stmt.where(CollectionActivity.customer_id == customer_id)
    stmt = stmt.order_by(desc(CollectionActivity.created_at))
    stmt = stmt.limit(limit).offset(offset)
    
    res = await db.execute(stmt)
    rows = res.all()
    
    activities_data = []
    for a, name in rows:
        activities_data.append({
            "id": a.id,
            "customer_id": a.customer_id,
            "customer_name": name or "Unknown",
            "user_id": a.user_id,
            "activity_type": a.activity_type,
            "notes": a.notes,
            "outcome": a.outcome,
            "created_at": a.created_at.isoformat()
        })
    return success_response("Collections activities retrieved successfully", data=activities_data, request=request)


@router.post("/collections/commitment", response_model=StandardResponse[dict])
async def log_collections_commitment_endpoint(
    payload: PaymentCommitmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Log a customer payment commitment.
    """
    commitment = await collections_service.log_commitment(
        customer_id=payload.customer_id,
        amount=payload.amount,
        promised_date=payload.promised_date,
        db_session=db
    )
    await db.commit()
    data = {
        "id": commitment.id,
        "customer_id": commitment.customer_id,
        "amount": commitment.amount,
        "promised_date": commitment.promised_date.isoformat(),
        "status": commitment.status,
        "created_at": commitment.created_at.isoformat()
    }
    return success_response("Payment commitment registered successfully", data=data, request=request)


@router.get("/collections/commitment", response_model=StandardResponse[list])
async def get_collections_commitments_endpoint(
    request: Request,
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    status: str | None = Query(None, description="Filter by status (PENDING, KEPT, BROKEN)"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve registered payment commitments.
    """
    from core.models.state_models import CustomerIntelligence, PaymentCommitment
    stmt = select(PaymentCommitment, CustomerIntelligence.customer_name).outerjoin(
        CustomerIntelligence, PaymentCommitment.customer_id == CustomerIntelligence.customer_id
    )
    if customer_id:
        stmt = stmt.where(PaymentCommitment.customer_id == customer_id)
    if status:
        stmt = stmt.where(PaymentCommitment.status == status)
        
    res = await db.execute(stmt)
    rows = res.all()
    
    commitments_data = []
    for c, name in rows:
        commitments_data.append({
            "id": c.id,
            "customer_id": c.customer_id,
            "customer_name": name or "Unknown",
            "amount": c.amount,
            "promised_date": c.promised_date.isoformat() if c.promised_date else None,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None
        })
    return success_response("Payment commitments retrieved successfully", data=commitments_data, request=request)


# --- RECOMMENDATIONS & DECISIONS ENDPOINTS ---


@router.post("/decisions/action", response_model=StandardResponse[dict])
async def record_decision_action_endpoint(
    payload: DecisionActionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Log an analyst decision action (approval, rejection, override).
    """
    user_id = str(identity.id) if hasattr(identity, "id") else str(getattr(identity, "user_id", "system-api"))
    audit = await decision_service.record_action(
        customer_id=payload.customer_id,
        recommendation_id=payload.recommendation_id,
        action_taken=payload.action_taken,
        performed_by=user_id,
        reason=payload.reason,
        db_session=db
    )
    await db.commit()
    data = {
        "id": audit.id,
        "customer_id": audit.customer_id,
        "recommendation_id": audit.recommendation_id,
        "action_taken": audit.action_taken,
        "performed_by": audit.performed_by,
        "reason": audit.reason,
        "timestamp": audit.timestamp.isoformat()
    }
    return success_response("Decision action registered and recommendation status updated", data=data, request=request)


@router.get("/decisions/history", response_model=StandardResponse[list])
async def get_decisions_history_endpoint(
    request: Request,
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve decision history logs.
    """
    from core.models.state_models import CustomerIntelligence, DecisionAudit
    stmt = select(DecisionAudit, CustomerIntelligence.customer_name).outerjoin(
        CustomerIntelligence, DecisionAudit.customer_id == CustomerIntelligence.customer_id
    )
    if customer_id:
        stmt = stmt.where(DecisionAudit.customer_id == customer_id)
    stmt = stmt.order_by(desc(DecisionAudit.timestamp))
    res = await db.execute(stmt)
    rows = res.all()
    
    history_data = []
    for h, name in rows:
        history_data.append({
            "id": h.id,
            "customer_id": h.customer_id,
            "customer_name": name or "Unknown",
            "recommendation_id": h.recommendation_id,
            "action_taken": h.action_taken,
            "performed_by": h.performed_by,
            "reason": h.reason,
            "timestamp": h.timestamp.isoformat()
        })
    return success_response("Decision history retrieved successfully", data=history_data, request=request)


@router.get("/recommendations", response_model=StandardResponse[Any])
async def get_recommendations_endpoint(
    request: Request,
    page: int | None = Query(None, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    search: str | None = Query(None, description="Fuzzy search by customer name or reason"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    identity: User | APIKey = Depends(require_permissions([Permission.INTEL_READ])),
):
    """
    Retrieve list of recommendations. Supports pagination, search, sorting, and name enrichment.
    """
    is_paginated = (page is not None)
    calc_offset = offset
    if is_paginated:
        calc_offset = (page - 1) * limit

    # Count Query
    count_stmt = select(func.count(Recommendation.id)).outerjoin(
        CustomerIntelligence, Recommendation.customer_id == CustomerIntelligence.customer_id
    )
    # Main Query
    stmt = select(Recommendation, CustomerIntelligence.customer_name).outerjoin(
        CustomerIntelligence, Recommendation.customer_id == CustomerIntelligence.customer_id
    )

    # Filters
    if status:
        count_stmt = count_stmt.where(Recommendation.status == status)
        stmt = stmt.where(Recommendation.status == status)
    if severity:
        count_stmt = count_stmt.where(Recommendation.severity == severity)
        stmt = stmt.where(Recommendation.severity == severity)
    if customer_id:
        count_stmt = count_stmt.where(Recommendation.customer_id == customer_id)
        stmt = stmt.where(Recommendation.customer_id == customer_id)
    if search:
        search_filter = (
            (Recommendation.reason.ilike(f"%{search}%")) |
            (Recommendation.recommendation_type.ilike(f"%{search}%")) |
            (CustomerIntelligence.customer_name.ilike(f"%{search}%"))
        )
        count_stmt = count_stmt.where(search_filter)
        stmt = stmt.where(search_filter)

    # Sorting
    sort_mapping = {
        "created_at": Recommendation.created_at,
        "severity": Recommendation.severity,
        "recommendation_type": Recommendation.recommendation_type,
        "confidence": Recommendation.confidence,
        "status": Recommendation.status,
        "customer_name": CustomerIntelligence.customer_name,
        "customer_id": Recommendation.customer_id,
    }
    sort_col = sort_mapping.get(sort_by, Recommendation.created_at)
    if sort_order == "desc":
        stmt = stmt.order_by(desc(sort_col))
    else:
        stmt = stmt.order_by(asc(sort_col))

    # Pagination execution
    stmt = stmt.limit(limit).offset(calc_offset)
    
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for rec, name in rows:
        items.append({
            "id": rec.id,
            "customer_id": rec.customer_id,
            "customer_name": name or "Unknown",
            "recommendation_type": rec.recommendation_type,
            "severity": rec.severity,
            "reason": rec.reason,
            "confidence": rec.confidence,
            "status": rec.status,
            "created_at": rec.created_at.isoformat() if rec.created_at else None
        })

    if is_paginated:
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        data = {
            "items": items,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    else:
        data = items

    return success_response("Recommendations retrieved successfully", data=data, request=request)
