import asyncio
from typing import Optional

import redis.asyncio as redis
from loguru import logger

from core.config.settings import settings


class RedisManager:
    _instance: Optional["RedisManager"] = None
    _client: redis.Redis | None = None
    _is_healthy: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("RedisManager not initialized. Call connect() first.")
        return self._client

    async def connect(self):
        """Initialize the Redis connection pool and start health checker."""
        if self._client is not None:
            return

        logger.info(f"Connecting to Redis at {settings.REDIS_URL}")
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=settings.REDIS_TIMEOUT,
                retry_on_timeout=True,
            )
            # Initial health check
            await self._client.ping()
            self._is_healthy = True
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._is_healthy = False
            # In strict mode, we might want to exit here, but we'll let the circuit breaker handle it
            raise

    def is_operational(self) -> bool:
        """Returns True if Redis is healthy and available."""
        return self._is_healthy

    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._client = None
            self._is_healthy = False
            logger.info("Redis connection closed.")

    async def ensure_operational(self):
        """Fail-closed check. Raises an exception if Redis is down."""
        if not self.is_operational():
            logger.error("Security critical operation denied: Redis is unavailable (Fail-Closed).")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security infrastructure unavailable. Please try again later.",
            )


redis_manager = RedisManager()
