
from fastapi import APIRouter, Depends, Request, status
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.core.dependencies import get_auth_repo, require_permissions
from core.core.permissions import Permission
from core.core.responses import success_response
from core.models.auth_models import User
from core.repositories.auth import AuthRepository
from core.schemas.auth import APIKeyCreateResponseSchema, APIKeyCreateSchema, APIKeyResponseSchema
from core.schemas.responses import ErrorResponse, StandardResponse
from core.services.auth_service import AuthService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post(
    "", 
    response_model=StandardResponse[APIKeyCreateResponseSchema], 
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def create_api_key(
    payload: APIKeyCreateSchema,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.API_KEY_CREATE])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = AuthService(repo, correlation_id)
    api_key, raw_key = await service.create_api_key(current_user.id, payload.name, payload.scopes)

    data = {
        "id": api_key.id,
        "key_prefix": api_key.key_prefix,
        "name": api_key.name,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
        "raw_key": raw_key,
    }
    
    return success_response(
        message="API Key created successfully",
        data=APIKeyCreateResponseSchema.model_validate(data).model_dump(),
        status_code=status.HTTP_201_CREATED,
        request=request
    )


@router.get(
    "", 
    response_model=StandardResponse[list[APIKeyResponseSchema]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
async def list_api_keys(
    request: Request,
    current_user: User = Depends(require_permissions([Permission.API_KEY_READ])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    keys = await repo.get_user_api_keys(current_user.id)
    data = [APIKeyResponseSchema.model_validate(k).model_dump() for k in keys]
    return success_response(
        message="API Keys retrieved successfully",
        data=data,
        request=request
    )


@router.delete(
    "/{key_id}", 
    response_model=StandardResponse[dict[str, str]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "API Key Not Found"}
    }
)
async def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(require_permissions([Permission.API_KEY_REVOKE])),
    repo: AuthRepository = Depends(get_auth_repo),
):
    keys = await repo.get_user_api_keys(current_user.id)
    key_obj = next((k for k in keys if str(k.id) == key_id), None)
    
    if not key_obj:
        raise StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
        
    from datetime import UTC, datetime
    key_obj.is_active = False
    key_obj.revoked_at = datetime.now(UTC)
    await repo.update_api_key(key_obj)
    await repo.log_audit_event("API_KEY_REVOKED", "SUCCESS", current_user.id, details={"key_id": key_id})
    await repo.commit()
    return success_response(
        message="API Key revoked successfully",
        data=None,
        request=request
    )
