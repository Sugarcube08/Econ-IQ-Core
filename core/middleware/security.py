import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from loguru import logger
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# -- METRICS --
# Low cardinality labels only
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)
AUTH_EVENTS = Counter(
    "auth_events_total", "Authentication events", ["event_type", "status", "auth_method"]
)


class HardenedSecurityMiddleware(BaseHTTPMiddleware):
    """
    Production security middleware:
    - Injects X-Correlation-ID
    - Enforces Security Headers (CSP, HSTS, etc.)
    - Handles Request Logging & Timing
    - Global Request Size Protection
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 1. Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Store in state for later retrieval in dependencies/services
        request.state.correlation_id = correlation_id

        # 2. Request Size Check (Fail-Closed)
        # Limit to 10MB by default
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return Response(content="Payload too large", status_code=413)

        # 3. Process Request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception("FAILURE | Unhandled exception in request", extra={"correlation_id": correlation_id, "error": str(e)})
            response = Response(content="Internal Server Error", status_code=500)

        # 4. Inject Security Headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Loosen CSP for API docs to allow Swagger UI / ReDoc to load CDN assets
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "frame-ancestors 'none';"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        
        # 5. Metrics & Logging
        duration = time.time() - start_time
        
        # Use generic path to avoid cardinality explosion
        # In a real app, you might use request.scope.get("route").path if available
        endpoint = "unknown"
        if request.scope.get("route"):
             endpoint = request.scope["route"].path

        REQUEST_COUNT.labels(
            method=request.method, 
            endpoint=endpoint, 
            status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method, 
            endpoint=endpoint
        ).observe(duration)

        logger.info(
            "PROCESSING | HTTP Request Completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": f"{duration:.4f}s",
                "correlation_id": correlation_id
            }
        )

        return response
