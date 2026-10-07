import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.order_service.database import get_db
from services.order_service.schemas import (
    CreateOrderRequest,
    OrderResponse,
    OrderListResponse,
    CancelOrderRequest,
)
from services.order_service.service import OrderService
from shared.idempotency.redis_idempotency import RedisIdempotencyManager
from shared.exceptions import IdempotencyConflictException
from shared.logging import correlation_id_ctx

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])
idempotency_mgr = RedisIdempotencyManager()


def get_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(db)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    service: OrderService = Depends(get_service),
):
    idem_key = idempotency_key or str(uuid.uuid4())
    corr_id = x_correlation_id or correlation_id_ctx.get() or str(uuid.uuid4())

    # 1. Distributed Redis Idempotency Check
    is_new, cached_result = await idempotency_mgr.check_and_lock(idem_key)
    if not is_new:
        if cached_result:
            return OrderResponse.model_validate(cached_result)
        else:
            raise IdempotencyConflictException(key=idem_key)

    try:
        # 2. Atomic Order + Outbox creation
        order = await service.create_order(payload, idempotency_key=idem_key, correlation_id=corr_id)
        response_model = OrderResponse.model_validate(order)

        # 3. Save successful result in Redis idempotency cache
        await idempotency_mgr.save_result(idem_key, response_model.model_dump())
        return response_model

    except Exception:
        await idempotency_mgr.release_lock(idem_key)
        raise


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    service: OrderService = Depends(get_service),
):
    order = await service.get_order(order_id)
    return OrderResponse.model_validate(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: OrderService = Depends(get_service),
):
    items, total = await service.list_orders(customer_id=customer_id, status=status, page=page, size=size)
    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    payload: CancelOrderRequest = CancelOrderRequest(),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    service: OrderService = Depends(get_service),
):
    corr_id = x_correlation_id or correlation_id_ctx.get() or str(uuid.uuid4())
    order = await service.cancel_order(order_id, reason=payload.reason, correlation_id=corr_id)
    return OrderResponse.model_validate(order)
