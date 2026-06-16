from loguru import logger
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.core.responses import error_response
from core.schemas.responses import ErrorDetail


def get_error_code(status_code: int) -> str:
    mapping: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_FAILED",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "HTTP_ERROR")


async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    errors = None
    if hasattr(exc, "detail") and isinstance(exc.detail, str):
        errors = [ErrorDetail(code=get_error_code(exc.status_code), message=exc.detail)]

    return error_response(
        message=str(exc.detail) if isinstance(exc.detail, str) else "An error occurred",
        status_code=exc.status_code,
        errors=errors,
        request=request,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(map(str, error.get("loc", [])))
        code = error.get("type", "VALIDATION_FAILED").upper().replace(".", "_")
        message = error.get("msg", "Validation failed")
        errors.append(ErrorDetail(field=field, code=code, message=message))

    return error_response(
        message="Validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        errors=errors,
        request=request,
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("FAILURE | Unhandled exception", extra={"error": str(exc)})
    errors = [ErrorDetail(code="INTERNAL_SERVER_ERROR", message="An unexpected error occurred.")]
    return error_response(
        message="Internal server error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        errors=errors,
        request=request,
    )
