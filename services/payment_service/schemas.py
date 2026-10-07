from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProcessPaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount: float = Field(..., gt=0.0)
    currency: str = "USD"
    payment_method: str = "CREDIT_CARD"
    simulation_flag: str = "SUCCESS"  # SUCCESS or FAIL for deterministic testing


class RefundPaymentRequest(BaseModel):
    order_id: str
    amount: Optional[float] = None
    reason: str = "Customer cancellation or Saga inventory failure compensation"


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    payment_id: str
    order_id: str
    amount: float
    reason: str
    status: str
    created_at: datetime
