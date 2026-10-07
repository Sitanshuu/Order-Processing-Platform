import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from services.order_service.database import engine, Base, AsyncSessionLocal
from services.order_service.routes import router
from services.order_service.grpc_server import serve_grpc
from services.order_service.outbox_publisher import OutboxPublisherWorker
from services.order_service.worker import OrderSagaWorker
from shared.messaging.rabbitmq import RabbitMQClient
from shared.config import settings
from shared.logging import setup_logger, correlation_id_ctx, request_id_ctx
from shared.exceptions import AppBaseException

logger = setup_logger("order-service")
grpc_task: asyncio.Task = None
outbox_task: asyncio.Task = None
saga_task: asyncio.Task = None
rmq_client_outbox: RabbitMQClient = None
rmq_client_saga: RabbitMQClient = None
outbox_worker: OutboxPublisherWorker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global grpc_task, outbox_task, saga_task, rmq_client_outbox, rmq_client_saga, outbox_worker
    logger.info("Starting Order Service...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 1. Start gRPC Server
    grpc_task = asyncio.create_task(serve_grpc())

    # 2. Start Outbox Publisher Worker
    try:
        rmq_client_outbox = RabbitMQClient()
        outbox_worker = OutboxPublisherWorker(rmq_client_outbox)
        outbox_task = asyncio.create_task(outbox_worker.start())
    except Exception as e:
        logger.warning(f"Outbox publisher not started: {e}")

    # 3. Start Saga Event Consumer Worker
    try:
        rmq_client_saga = RabbitMQClient()
        saga_worker = OrderSagaWorker(rmq_client_saga)
        saga_task = asyncio.create_task(saga_worker.start())
    except Exception as e:
        logger.warning(f"Order Saga worker not started: {e}")

    logger.info("Order Service initialized successfully.")

    yield

    logger.info("Shutting down Order Service...")
    if outbox_worker:
        outbox_worker.stop()
    if grpc_task:
        grpc_task.cancel()
    if outbox_task:
        outbox_task.cancel()
    if saga_task:
        saga_task.cancel()
    if rmq_client_outbox:
        await rmq_client_outbox.close()
    if rmq_client_saga:
        await rmq_client_saga.close()
    await engine.dispose()
    logger.info("Order Service shutdown complete.")


app = FastAPI(
    title="Order Service",
    version="1.0.0",
    description="Order lifecycle management, Transactional Outbox pattern, Saga orchestration, and state machine validation.",
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
    logger.error(f"Unhandled exception in Order Service: {exc}", exc_info=True)
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
    return {"status": "healthy", "service": "order-service"}


@app.get("/ready", tags=["Observability"])
async def readiness():
    checks = {"database": False}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness check failed for DB: {e}")

    is_ready = checks["database"]
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "degraded", "checks": checks},
    )


app.include_router(router)
