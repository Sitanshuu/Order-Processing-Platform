from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class StockInitialize(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=0)


class StockReplenish(BaseModel):
    quantity: int = Field(..., gt=0)


class StockItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)


class ReserveStockRequest(BaseModel):
    order_id: str
    items: List[StockItemRequest]


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    total_quantity: int
    reserved_quantity: int
    available_quantity: int
    updated_at: datetime


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    order_id: str
    product_id: str
    quantity: int
    status: str
    created_at: datetime
