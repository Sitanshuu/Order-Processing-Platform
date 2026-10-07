from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.inventory_service.database import get_db
from services.inventory_service.schemas import (
    StockInitialize,
    StockReplenish,
    ReserveStockRequest,
    InventoryItemResponse,
    ReservationResponse,
)
from services.inventory_service.service import InventoryService
from typing import List

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Management"])


def get_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    return InventoryService(db)


@router.get("/{product_id}", response_model=InventoryItemResponse)
async def get_stock(
    product_id: str,
    service: InventoryService = Depends(get_service),
):
    item = await service.get_stock(product_id)
    return InventoryItemResponse.model_validate(item)


@router.post("/initialize", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def initialize_stock(
    payload: StockInitialize,
    service: InventoryService = Depends(get_service),
):
    item = await service.initialize_stock(payload)
    return InventoryItemResponse.model_validate(item)


@router.post("/{product_id}/replenish", response_model=InventoryItemResponse)
async def replenish_stock(
    product_id: str,
    payload: StockReplenish,
    service: InventoryService = Depends(get_service),
):
    item = await service.replenish_stock(product_id, payload)
    return InventoryItemResponse.model_validate(item)


@router.post("/reserve", response_model=List[ReservationResponse])
async def reserve_stock(
    payload: ReserveStockRequest,
    service: InventoryService = Depends(get_service),
):
    reservations = await service.reserve_stock(payload)
    return [ReservationResponse.model_validate(r) for r in reservations]


@router.post("/orders/{order_id}/release", status_code=status.HTTP_200_OK)
async def release_reservation(
    order_id: str,
    service: InventoryService = Depends(get_service),
):
    await service.release_reservation(order_id)
    return {"message": f"Stock reservations released for order {order_id}"}


@router.post("/orders/{order_id}/confirm", status_code=status.HTTP_200_OK)
async def confirm_reservation(
    order_id: str,
    service: InventoryService = Depends(get_service),
):
    await service.confirm_reservation(order_id)
    return {"message": f"Stock reservations confirmed for order {order_id}"}
