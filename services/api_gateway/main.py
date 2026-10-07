import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from services.api_gateway.routes import router
from services.api_gateway.middleware import GatewayTracingAndRateLimitMiddleware
from shared.logging import setup_logger, correlation_id_ctx, request_id_ctx
from shared.exceptions import AppBaseException

logger = setup_logger("api-gateway")

app = FastAPI(
    title="API Gateway - Event-Driven Order Processing Platform",
    version="1.0.0",
    description="Unified API entry point, authentication boundary, distributed tracing propagation, and rate limiting.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GatewayTracingAndRateLimitMiddleware, max_requests_per_minute=180)


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
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Gateway Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Internal gateway failure.",
                "correlation_id": correlation_id_ctx.get(),
                "request_id": request_id_ctx.get(),
            }
        },
    )


@app.get("/health", tags=["Observability"])
async def liveness():
    return {"status": "healthy", "service": "api-gateway"}


@app.get("/ready", tags=["Observability"])
async def readiness():
    return {"status": "ready", "service": "api-gateway"}


app.include_router(router)
