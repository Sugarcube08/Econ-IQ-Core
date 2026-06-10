from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

class ErrorDetail(BaseModel):
    field: str | None = None
    code: str
    message: str

class PaginationMetadata(BaseModel):
    page: int
    page_size: int
    total_pages: int
    total_records: int
    has_next: bool
    has_previous: bool

class StandardResponse[T](BaseModel):
    success: bool
    status_code: int
    message: str
    data: T | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorDetail] | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

# Unified Error Response Schema for documentation
ErrorResponse = StandardResponse[Any]
