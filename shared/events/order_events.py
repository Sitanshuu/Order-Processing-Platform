from typing import List, Dict, Any
from pydantic import BaseModel, Field
from shared.events.base import DomainEvent


class OrderItemPayload(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float


class OrderCreatedPayload(BaseModel):
    order_id: str
    customer_id: str
    total_amount: float
    currency: str = "USD"
    items: List[OrderItemPayload]
    idempotency_key: str
    status: str = "PENDING"
    payment_method: str = "CREDIT_CARD"
    simulation_flag: str = "SUCCESS"  # Allows deterministic testing of payment outcomes


class OrderConfirmedPayload(BaseModel):
    order_id: str
    customer_id: str
    confirmed_at: str
    status: str = "CONFIRMED"


class OrderCancelledPayload(BaseModel):
    order_id: str
    customer_id: str
    reason: str
    cancelled_at: str
    status: str = "CANCELLED"


def create_order_created_event(
    order_id: str,
    customer_id: str,
    total_amount: float,
    items: List[Dict[str, Any]],
    idempotency_key: str,
    correlation_id: str,
    simulation_flag: str = "SUCCESS",
    payment_method: str = "CREDIT_CARD",
) -> DomainEvent:
    return DomainEvent(
        event_type="OrderCreated",
        source="order-service",
        correlation_id=correlation_id,
        payload=OrderCreatedPayload(
            order_id=order_id,
            customer_id=customer_id,
            total_amount=total_amount,
            items=[OrderItemPayload(**item) for item in items],
            idempotency_key=idempotency_key,
            simulation_flag=simulation_flag,
            payment_method=payment_method,
        ).model_dump(),
    )


def create_order_confirmed_event(
    order_id: str,
    customer_id: str,
    confirmed_at: str,
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="OrderConfirmed",
        source="order-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=OrderConfirmedPayload(
            order_id=order_id,
            customer_id=customer_id,
            confirmed_at=confirmed_at,
        ).model_dump(),
    )


def create_order_cancelled_event(
    order_id: str,
    customer_id: str,
    reason: str,
    cancelled_at: str,
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="OrderCancelled",
        source="order-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=OrderCancelledPayload(
            order_id=order_id,
            customer_id=customer_id,
            reason=reason,
            cancelled_at=cancelled_at,
        ).model_dump(),
    )
