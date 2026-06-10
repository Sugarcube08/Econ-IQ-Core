import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from core.core.dependencies import get_auth_repo, require_permissions
from core.core.permissions import Permission
from core.core.responses import success_response
from core.models.auth_models import User, UserRole
from core.repositories.auth import AuthRepository
from core.schemas.auth import (
    UserCreateSchema,
    UserListResponseData,
    UserResponseSchema,
    UserUpdateSchema,
)
from core.schemas.responses import ErrorResponse, StandardResponse
from core.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "", 
    response_model=StandardResponse[UserListResponseData],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str | None = Query(None, description="Fuzzy search by email or name"),
    role: UserRole | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    current_user: User = Depends(require_permissions([Permission.USER_READ])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = UserService(repo, correlation_id)
    
    users, total_records = await service.list_users(
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        role=role,
        is_active=is_active
    )

    total_pages = (total_records + limit - 1) // limit if limit > 0 else 0
    
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
            "role": role.value if role else None,
            "is_active": is_active
        },
        "search": search
    }

    return success_response(
        message="Users retrieved successfully",
        data=UserListResponseData(users=[UserResponseSchema.model_validate(u) for u in users]).model_dump(),
        metadata=metadata,
        request=request
    )


@router.post(
    "", 
    response_model=StandardResponse[UserResponseSchema], 
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def create_user(
    payload: UserCreateSchema,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.USER_CREATE])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = UserService(repo, correlation_id)
    user = await service.create_user(current_user.id, payload)
    return success_response(
        message="User created successfully",
        data=UserResponseSchema.model_validate(user).model_dump(),
        status_code=status.HTTP_201_CREATED,
        request=request
    )


@router.get(
    "/{user_id}", 
    response_model=StandardResponse[UserResponseSchema],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User Not Found"}
    }
)
async def get_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.USER_READ])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = UserService(repo, correlation_id)
    user = await service.get_user(uuid.UUID(user_id))
    return success_response(
        message="User retrieved successfully",
        data=UserResponseSchema.model_validate(user).model_dump(),
        request=request
    )


@router.patch(
    "/{user_id}", 
    response_model=StandardResponse[UserResponseSchema],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User Not Found"}
    }
)
async def update_user(
    user_id: str,
    payload: UserUpdateSchema,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.USER_UPDATE])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = UserService(repo, correlation_id)
    user = await service.update_user(uuid.UUID(user_id), payload, current_user)
    return success_response(
        message="User updated successfully",
        data=UserResponseSchema.model_validate(user).model_dump(),
        request=request
    )


@router.delete(
    "/{user_id}", 
    response_model=StandardResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User Not Found"}
    }
)
async def delete_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.USER_DELETE])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = UserService(repo, correlation_id)
    await service.delete_user(uuid.UUID(user_id), current_user.id)
    
    return success_response(
        message="User account deactivated (soft-deleted).",
        data={"user_id": user_id},
        request=request
    )
