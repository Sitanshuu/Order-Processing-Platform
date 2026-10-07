from typing import Optional
from pydantic import BaseModel
from shared.events.base import DomainEvent


class PaymentCompletedPayload(BaseModel):
    payment_id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    status: str = "COMPLETED"
    processed_at: str


class PaymentFailedPayload(BaseModel):
    payment_id: Optional[str] = None
    order_id: str
    customer_id: str
    amount: float
    currency: str
    error_code: str
    reason: str
    status: str = "FAILED"
    failed_at: str


class PaymentRefundRequestedPayload(BaseModel):
    order_id: str
    payment_id: str
    amount: float
    reason: str


class PaymentRefundedPayload(BaseModel):
    refund_id: str
    payment_id: str
    order_id: str
    amount: float
    reason: str
    refunded_at: str
    status: str = "REFUNDED"


def create_payment_completed_event(
    payment_id: str,
    order_id: str,
    customer_id: str,
    amount: float,
    currency: str,
    payment_method: str,
    processed_at: str,
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="PaymentCompleted",
        source="payment-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=PaymentCompletedPayload(
            payment_id=payment_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            processed_at=processed_at,
        ).model_dump(),
    )


def create_payment_failed_event(
    order_id: str,
    customer_id: str,
    amount: float,
    currency: str,
    error_code: str,
    reason: str,
    failed_at: str,
    correlation_id: str,
    causation_id: str,
    payment_id: Optional[str] = None,
) -> DomainEvent:
    return DomainEvent(
        event_type="PaymentFailed",
        source="payment-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=PaymentFailedPayload(
            payment_id=payment_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            error_code=error_code,
            reason=reason,
            failed_at=failed_at,
        ).model_dump(),
    )


def create_payment_refunded_event(
    refund_id: str,
    payment_id: str,
    order_id: str,
    amount: float,
    reason: str,
    refunded_at: str,
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="PaymentRefunded",
        source="payment-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=PaymentRefundedPayload(
            refund_id=refund_id,
            payment_id=payment_id,
            order_id=order_id,
            amount=amount,
            reason=reason,
            refunded_at=refunded_at,
        ).model_dump(),
    )
