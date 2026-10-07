from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.payment_service.database import get_db
from services.payment_service.schemas import (
    ProcessPaymentRequest,
    RefundPaymentRequest,
    PaymentResponse,
    RefundResponse,
)
from services.payment_service.service import PaymentService

router = APIRouter(prefix="/api/v1/payments", tags=["Payments & Refunds"])


def get_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


@router.get("/order/{order_id}", response_model=PaymentResponse)
async def get_payment_by_order(
    order_id: str,
    service: PaymentService = Depends(get_service),
):
    payment = await service.get_payment_by_order(order_id)
    return PaymentResponse.model_validate(payment)


@router.post("/process", response_model=PaymentResponse, status_code=status.HTTP_200_OK)
async def process_payment(
    payload: ProcessPaymentRequest,
    service: PaymentService = Depends(get_service),
):
    payment = await service.process_payment(payload)
    return PaymentResponse.model_validate(payment)


@router.post("/refund", response_model=RefundResponse, status_code=status.HTTP_200_OK)
async def refund_payment(
    payload: RefundPaymentRequest,
    service: PaymentService = Depends(get_service),
):
    refund = await service.refund_payment(payload)
    return RefundResponse.model_validate(refund)
