from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class OrderItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItemRequest] = Field(..., min_length=1)
    payment_method: str = "CREDIT_CARD"
    simulation_flag: str = "SUCCESS"  # SUCCESS or FAIL for deterministic payment testing


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    total_amount: float
    currency: str
    status: str
    idempotency_key: str
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]


class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    size: int


class CancelOrderRequest(BaseModel):
    reason: str = "Customer requested cancellation"
