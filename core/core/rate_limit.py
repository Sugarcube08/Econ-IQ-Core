import time

from loguru import logger

from core.config.settings import settings
from core.storage.redis import redis_manager
from core.utils.ip import parse_rate_limit


class RateLimiter:
    """
    Production-grade sliding window rate limiter using Redis Lua scripts for atomicity.
    Handles per-IP, per-email, and per-endpoint limits.
    """

    # Lua script for sliding window rate limiting
    # KEYS[1]: rate limit key
    # ARGV[1]: window size in seconds
    # ARGV[2]: max requests in window
    # ARGV[3]: current timestamp
    LUA_SLIDING_WINDOW = """
    local key = KEYS[1]
    local window = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local min = now - window

    redis.call('ZREMRANGEBYSCORE', key, 0, min)
    local count = redis.call('ZCARD', key)

    if count < limit then
        redis.call('ZADD', key, now, now)
        redis.call('EXPIRE', key, window)
        return {1, count + 1}
    else
        return {0, count}
    end
    """

    @classmethod
    async def check_rate_limit(
        cls,
        resource_id: str,
        limit_name: str,
        window_seconds: int,
        max_requests: int
    ) -> tuple[bool, int]:
        """
        Generic rate limit check.
        Returns (is_allowed, current_count)
        """
        await redis_manager.ensure_operational()
        
        # Development override: significantly relax limits
        if settings.APP_ENV == "development":
            # Still record the hit for testing, but allow much higher volume
            max_requests = max(max_requests, 1000)
            window_seconds = 1
        
        key = f"rl:{limit_name}:{resource_id}"
        now = time.time()
        
        try:
            # We don't register the script every time, but for simplicity here we use eval
            # In higher volume, pre-load the script with SCRIPT LOAD
            result = await redis_manager.client.eval(
                cls.LUA_SLIDING_WINDOW, 
                1, 
                key, 
                window_seconds, 
                max_requests, 
                now
            )
            is_allowed = bool(result[0])
            current_count = result[1]
            
            if not is_allowed:
                logger.warning(
                    "SECURITY | Rate limit triggered",
                    extra={
                        "limit_name": limit_name,
                        "resource_id": resource_id,
                        "current_count": current_count,
                        "max_requests": max_requests,
                        "window_seconds": window_seconds
                    }
                )
            
            return is_allowed, current_count
        except Exception as e:
            logger.error("FAILURE | Error executing rate limit script", extra={"key": key, "error": str(e)})
            # Fail closed for security
            return False, -1

    @classmethod
    async def is_otp_request_allowed(cls, email: str, ip_address: str) -> bool:
        """
        Specific hardened logic for OTP requests.
        Enforces both per-email and per-IP limits using settings.
        """
        # Parse limits from settings
        ip_burst_max, ip_burst_window = parse_rate_limit(settings.AUTH_RATE_LIMIT_LOGIN_BURST)
        email_burst_max, email_burst_window = parse_rate_limit(settings.AUTH_RATE_LIMIT_OTP_RESEND)
        email_day_max, email_day_window = parse_rate_limit(settings.AUTH_RATE_LIMIT_LOGIN_SUSTAINED)

        # 1. Per-IP Burst (e.g., 5/min)
        ip_allowed, _ = await cls.check_rate_limit(
            ip_address, "otp_ip_burst", ip_burst_window, ip_burst_max
        )
        if not ip_allowed:
            return False
            
        # 2. Per-Email Burst (e.g., 1/min)
        email_burst_allowed, _ = await cls.check_rate_limit(
            email, "otp_email_burst", email_burst_window, email_burst_max
        )
        if not email_burst_allowed:
            return False
            
        # 3. Per-Email Sustained (e.g., 20/day)
        email_sustained_allowed, _ = await cls.check_rate_limit(
            email, "otp_email_day", email_day_window, email_day_max
        )
        if not email_sustained_allowed:
            return False
            
        return True

    @classmethod
    async def set_cooldown(cls, key_id: str, cooldown_name: str, seconds: int):
        """Sets a temporary lock/cooldown for a specific resource."""
        await redis_manager.ensure_operational()
        key = f"cooldown:{cooldown_name}:{key_id}"
        await redis_manager.client.set(key, "1", ex=seconds)

    @classmethod
    async def is_on_cooldown(cls, key_id: str, cooldown_name: str) -> bool:
        """Checks if a resource is currently on cooldown."""
        await redis_manager.ensure_operational()
        key = f"cooldown:{cooldown_name}:{key_id}"
        return await redis_manager.client.exists(key) > 0
