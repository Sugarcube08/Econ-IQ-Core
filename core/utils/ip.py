from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP address from request headers.
    Prioritizes Cloudflare and standard proxy headers.
    """
    # 1. Cloudflare
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip

    # 2. Standard Proxy Header
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2>
        # The first IP is the original client
        return forwarded_for.split(",")[0].strip()

    # 3. Direct Connection
    return request.client.host if request.client else "unknown"


def parse_rate_limit(limit_str: str) -> tuple[int, int]:
    """
    Parses a rate limit string (e.g., "5/minute", "20/day") into (max_requests, window_seconds).
    Defaults to 1/minute if parsing fails.
    """
    try:
        parts = limit_str.split("/")
        if len(parts) != 2:
            return 1, 60

        count = int(parts[0])
        unit = parts[1].lower().strip()

        if unit == "second":
            return count, 1
        elif unit == "minute":
            return count, 60
        elif unit == "hour":
            return count, 3600
        elif unit == "day":
            return count, 86400
        else:
            return count, 60
    except (ValueError, AttributeError):
        return 1, 60
