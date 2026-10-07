import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from services.notification_service.database import init_db, close_db, motor_client
from services.notification_service.routes import router
from services.notification_service.worker import NotificationEventWorker
from shared.messaging.rabbitmq import RabbitMQClient
from shared.logging import setup_logger, correlation_id_ctx, request_id_ctx
from shared.exceptions import AppBaseException

logger = setup_logger("notification-service")
worker_task: asyncio.Task = None
rmq_client: RabbitMQClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_task, rmq_client
    logger.info("Starting Notification Service...")

    try:
        await init_db()
    except Exception as e:
        logger.warning(f"MongoDB not reachable immediately: {e}")

    try:
        rmq_client = RabbitMQClient()
        worker = NotificationEventWorker(rmq_client)
        worker_task = asyncio.create_task(worker.start())
    except Exception as e:
        logger.warning(f"RabbitMQ notification consumer not started: {e}")

    logger.info("Notification Service initialized successfully.")

    yield

    logger.info("Shutting down Notification Service...")
    if worker_task:
        worker_task.cancel()
    if rmq_client:
        await rmq_client.close()
    await close_db()
    logger.info("Notification Service shutdown complete.")


app = FastAPI(
    title="Notification Service",
    version="1.0.0",
    description="Asynchronous email & SMS notification simulator backed by MongoDB document store.",
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


@app.get("/health", tags=["Observability"])
async def liveness():
    return {"status": "healthy", "service": "notification-service"}


@app.get("/ready", tags=["Observability"])
async def readiness():
    checks = {"mongodb": False}
    try:
        if motor_client:
            await motor_client.admin.command("ping")
            checks["mongodb"] = True
    except Exception as e:
        logger.error(f"Readiness check failed for MongoDB: {e}")

    is_ready = checks["mongodb"]
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "degraded", "checks": checks},
    )


app.include_router(router)
