
from fastapi import APIRouter, Depends, Request

from core.config.settings import settings
from core.core.dependencies import get_auth_repo, get_current_user
from core.core.responses import success_response
from core.models.auth_models import User
from core.repositories.auth import AuthRepository
from core.schemas.auth import (
    OTPRequestSchema,
    OTPVerifySchema,
    RefreshRequestSchema,
    TokenResponseSchema,
    UserResponseSchema,
)
from core.schemas.responses import ErrorResponse, StandardResponse
from core.services.auth_service import AuthService
from core.utils.ip import get_client_ip

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/request-otp", 
    response_model=StandardResponse[dict[str, str]],
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"}
    }
)
async def request_otp(
    payload: OTPRequestSchema,
    request: Request,
    repo: AuthRepository = Depends(get_auth_repo)
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = AuthService(repo, correlation_id)
    client_host = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    await service.request_otp(payload.email, client_host, user_agent)
    return success_response(
        message="If an account exists, an OTP has been sent.",
        data={"email": payload.email},
        request=request
    )


@router.post(
    "/verify-otp", 
    response_model=StandardResponse[TokenResponseSchema],
    responses={
        401: {"model": ErrorResponse, "description": "Invalid Credentials"},
        403: {"model": ErrorResponse, "description": "Account Locked"}
    }
)
async def verify_otp(
    payload: OTPVerifySchema,
    request: Request,
    repo: AuthRepository = Depends(get_auth_repo)
):

    correlation_id = getattr(request.state, "correlation_id", None)
    service = AuthService(repo, correlation_id)
    client_host = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    
    tokens = await service.verify_otp(
        email=payload.email,
        otp=payload.otp,
        ip_address=client_host,
        user_agent=user_agent,
        device_id=payload.device_id
    )
    return success_response(
        message="Authentication successful",
        data=TokenResponseSchema.model_validate(tokens).model_dump(),
        request=request
    )


@router.post(
    "/refresh", 
    response_model=StandardResponse[TokenResponseSchema],
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or Expired Refresh Token"}
    }
)
async def refresh_token(
    payload: RefreshRequestSchema,
    request: Request,
    repo: AuthRepository = Depends(get_auth_repo)
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = AuthService(repo, correlation_id)
    client_host = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    tokens = await service.refresh_token(
        refresh_token=payload.refresh_token,
        ip_address=client_host,
        user_agent=user_agent,
        device_id=payload.device_id
    )
    return success_response(
        message="Token refreshed successfully",
        data=TokenResponseSchema.model_validate(tokens).model_dump(),
        request=request
    )


@router.post(
    "/logout", 
    response_model=StandardResponse[dict[str, str]],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def logout(
    payload: RefreshRequestSchema,
    request: Request,
    repo: AuthRepository = Depends(get_auth_repo)
):
    correlation_id = getattr(request.state, "correlation_id", None)
    service = AuthService(repo, correlation_id)
    client_host = get_client_ip(request)

    await service.logout(payload.refresh_token, client_host)
    return success_response(
        message="Successfully logged out.",
        data=None,
        request=request
    )


@router.get(
    "/me", 
    response_model=StandardResponse[UserResponseSchema],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def get_me(request: Request, current_user: User = Depends(get_current_user)):

    return success_response(
        message="User profile retrieved successfully",
        data=UserResponseSchema.model_validate(current_user).model_dump(),
        request=request
    )

