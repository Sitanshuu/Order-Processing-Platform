import time
import uuid
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from shared.config import settings
from shared.logging import correlation_id_ctx, request_id_ctx, setup_logger

logger = setup_logger("api-gateway-middleware")


class GatewayTracingAndRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests_per_minute: int = 120):
        super().__init__(app)
        self.max_requests = max_requests_per_minute
        self._redis: Optional[aioredis.Redis] = None

    async def get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception:
                self._redis = None
        return self._redis

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # 1. Tracing Context Injection
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id_ctx.set(correlation_id)
        request_id_ctx.set(request_id)

        # 2. Rate Limiting check (skip for health checks)
        if request.url.path not in ["/health", "/ready", "/docs", "/openapi.json"]:
            client_ip = request.client.host if request.client else "127.0.0.1"
            client = await self.get_redis()
            if client:
                try:
                    minute_window = int(time.time() // 60)
                    rate_key = f"ratelimit:{client_ip}:{minute_window}"
                    current_count = await client.incr(rate_key)
                    if current_count == 1:
                        await client.expire(rate_key, 65)

                    if current_count > self.max_requests:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": {
                                    "code": "RATE_LIMIT_EXCEEDED",
                                    "message": f"Rate limit of {self.max_requests} requests per minute exceeded.",
                                    "correlation_id": correlation_id,
                                    "request_id": request_id,
                                }
                            },
                        )
                except Exception as e:
                    logger.warning(f"Rate limiting check skipped due to Redis error: {e}")

        # 3. Process Request
        response = await call_next(request)

        # 4. Inject Tracing Headers in Response
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        
        duration = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration}ms)",
            extra={"correlation_id": correlation_id, "request_id": request_id},
        )
        return response
