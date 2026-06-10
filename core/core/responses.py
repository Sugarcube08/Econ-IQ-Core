import math
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.schemas.responses import ErrorDetail


def get_request_id(request: Request | None = None) -> str:
    if request:
        if hasattr(request.state, "correlation_id") and request.state.correlation_id:
            return request.state.correlation_id
        return request.headers.get("X-Correlation-ID", "unknown")
    return "unknown"


def build_response_dict(
    success: bool,
    status_code: int,
    message: str,
    data: Any | None = None,
    metadata: dict[str, Any] | None = None,
    errors: list[ErrorDetail] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "status_code": status_code,
        "message": message,
        "data": data,
        "metadata": metadata or {},
        "errors": [err.model_dump() for err in errors] if errors else None,
        "request_id": get_request_id(request),
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def success_response(
    message: str,
    data: Any | None = None,
    metadata: dict[str, Any] | None = None,
    status_code: int = 200,
    request: Request | None = None,
) -> JSONResponse:
    content = build_response_dict(
        success=True,
        status_code=status_code,
        message=message,
        data=data,
        metadata=metadata,
        errors=None,
        request=request,
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(content))


def error_response(
    message: str,
    status_code: int,
    errors: list[ErrorDetail] | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> JSONResponse:
    content = build_response_dict(
        success=False,
        status_code=status_code,
        message=message,
        data=None,
        metadata=metadata,
        errors=errors,
        request=request,
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(content))


def paginated_response(
    message: str,
    data: Any,
    page: int,
    page_size: int,
    total_records: int,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> JSONResponse:
    total_pages = math.ceil(total_records / page_size) if page_size > 0 else 0
    pagination_meta = {
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_records": total_records,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }

    final_metadata = metadata or {}
    final_metadata["pagination"] = pagination_meta

    return success_response(
        message=message,
        data=data,
        metadata=final_metadata,
        status_code=200,
        request=request,
    )
