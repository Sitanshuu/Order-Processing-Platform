from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from services.payment_service.models import Payment, Refund
from services.payment_service.schemas import ProcessPaymentRequest, RefundPaymentRequest
from services.payment_service.repository import PaymentRepository
from shared.exceptions import EntityNotFoundException


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.repo = PaymentRepository(db)

    async def get_payment_by_order(self, order_id: str) -> Payment:
        payment = await self.repo.get_by_order_id(order_id)
        if not payment:
            raise EntityNotFoundException("Payment for order", order_id)
        return payment

    async def process_payment(self, req: ProcessPaymentRequest) -> Payment:
        return await self.repo.process_payment(req)

    async def refund_payment(self, req: RefundPaymentRequest) -> Refund:
        return await self.repo.refund_payment(req)
