from typing import Optional, Dict, Any, List
import httpx
from fastapi import APIRouter, Request, Response, Depends, Header, status, HTTPException
from pydantic import BaseModel

from services.api_gateway.auth import create_access_token, require_auth, TokenData
from shared.config import settings
from shared.logging import correlation_id_ctx, request_id_ctx

router = APIRouter(prefix="/api/v1")

SERVICE_MAP = {
    "orders": f"http://{settings.ORDER_SERVICE_HOST}:{settings.ORDER_SERVICE_PORT}/api/v1/orders",
    "products": f"http://{settings.PRODUCT_SERVICE_HOST}:{settings.PRODUCT_SERVICE_PORT}/api/v1/products",
    "categories": f"http://{settings.PRODUCT_SERVICE_HOST}:{settings.PRODUCT_SERVICE_PORT}/api/v1/categories",
    "inventory": f"http://{settings.INVENTORY_SERVICE_HOST}:{settings.INVENTORY_SERVICE_PORT}/api/v1/inventory",
    "payments": f"http://{settings.PAYMENT_SERVICE_HOST}:{settings.PAYMENT_SERVICE_PORT}/api/v1/payments",
    "notifications": f"http://{settings.NOTIFICATION_SERVICE_HOST}:{settings.NOTIFICATION_SERVICE_PORT}/api/v1/notifications",
    "audit": f"http://{settings.AUDIT_SERVICE_HOST}:{settings.AUDIT_SERVICE_PORT}/api/v1/audit",
}


class LoginRequest(BaseModel):
    username: str
    password: str
    user_id: Optional[str] = None
    role: Optional[str] = "customer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


@router.post("/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def login_for_access_token(payload: LoginRequest):
    # Simulated auth verification
    uid = payload.user_id or f"usr_{payload.username}"
    token = create_access_token(
        data={"sub": uid, "username": payload.username, "role": payload.role or "customer"}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=uid,
        username=payload.username,
    )


async def forward_request(
    service_target_base: str,
    path_suffix: str,
    request: Request,
) -> Response:
    """
    Forwards HTTP request to downstream microservice, propagating tracing and idempotency headers.
    """
    url = f"{service_target_base}{path_suffix}"
    if request.url.query:
        url += f"?{request.url.query}"

    headers = dict(request.headers)
    # Inject active tracing context
    headers["X-Correlation-ID"] = correlation_id_ctx.get() or ""
    headers["X-Request-ID"] = request_id_ctx.get() or ""
    # Remove host header to avoid host mismatch in downstream services
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = await request.body()

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            downstream_res = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )
            return Response(
                content=downstream_res.content,
                status_code=downstream_res.status_code,
                headers=dict(downstream_res.headers),
                media_type=downstream_res.headers.get("content-type"),
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Downstream service at {service_target_base} is unavailable.",
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Downstream service at {service_target_base} timed out.",
            )


# Product & Category Proxy
@router.api_route("/products{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Catalog Proxy"])
async def proxy_products(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["products"], path, request)


@router.api_route("/categories{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Catalog Proxy"])
async def proxy_categories(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["categories"], path, request)


# Order Proxy
@router.api_route("/orders{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Order Proxy"])
async def proxy_orders(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["orders"], path, request)


# Inventory Proxy
@router.api_route("/inventory{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Inventory Proxy"])
async def proxy_inventory(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["inventory"], path, request)


# Payment Proxy
@router.api_route("/payments{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Payment Proxy"])
async def proxy_payments(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["payments"], path, request)


# Notification Proxy
@router.api_route("/notifications{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Notification Proxy"])
async def proxy_notifications(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["notifications"], path, request)


# Audit Proxy
@router.api_route("/audit{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["Audit Proxy"])
async def proxy_audit(request: Request, path: str = ""):
    return await forward_request(SERVICE_MAP["audit"], path, request)
