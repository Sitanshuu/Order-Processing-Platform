import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import redis.asyncio as aioredis

from services.product_service.database import engine, Base, AsyncSessionLocal
from services.product_service.routes import router
from services.product_service.grpc_server import serve_grpc
from shared.config import settings
from shared.logging import setup_logger, correlation_id_ctx, request_id_ctx
from shared.exceptions import AppBaseException

logger = setup_logger("product-service")
grpc_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Product Service...")
    # Initialize DB schemas if not yet migrated
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start gRPC server in background
    global grpc_task
    grpc_task = asyncio.create_task(serve_grpc())
    logger.info("Product Service initialized successfully.")

    yield

    logger.info("Shutting down Product Service...")
    if grpc_task:
        grpc_task.cancel()
    await engine.dispose()
    logger.info("Product Service shutdown complete.")


app = FastAPI(
    title="Product Service",
    version="1.0.0",
    description="Catalog management, category organization, and low-latency cache-aside product queries.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id_ctx.set(corr_id)
    request_id_ctx.set(req_id)

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    response.headers["X-Request-ID"] = req_id
    return response


@app.exception_handler(AppBaseException)
async def app_exception_handler(request: Request, exc: AppBaseException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "correlation_id": correlation_id_ctx.get(),
                "request_id": request_id_ctx.get(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception in Product Service: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "correlation_id": correlation_id_ctx.get(),
                "request_id": request_id_ctx.get(),
            }
        },
    )


@app.get("/health", tags=["Observability"])
async def liveness():
    return {"status": "healthy", "service": "product-service"}


@app.get("/ready", tags=["Observability"])
async def readiness():
    checks = {"database": False, "redis": False}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness check failed for DB: {e}")

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception as e:
        logger.warning(f"Readiness check failed for Redis: {e}")

    is_ready = checks["database"]
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "degraded", "checks": checks},
    )


app.include_router(router)
