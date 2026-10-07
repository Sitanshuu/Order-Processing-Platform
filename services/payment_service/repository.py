import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.payment_service.models import Payment, Refund, ProcessedEvent
from services.payment_service.schemas import ProcessPaymentRequest, RefundPaymentRequest
from shared.exceptions import EntityNotFoundException, AppBaseException

logger = logging.getLogger("payment-repository")


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.id == payment_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_order_id(self, order_id: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.order_id == order_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def process_payment(self, req: ProcessPaymentRequest) -> Payment:
        # Check if already processed for this order (Idempotency)
        existing = await self.get_by_order_id(req.order_id)
        if existing:
            logger.info(f"Payment for order {req.order_id} already exists with status {existing.status}")
            return existing

        # Deterministic simulation check
        is_success = req.simulation_flag.upper() != "FAIL"
        
        status = "COMPLETED" if is_success else "FAILED"
        txn_id = f"txn_{uuid.uuid4().hex[:16]}" if is_success else None
        err_msg = None if is_success else "Payment authorization declined by simulated gateway."

        payment = Payment(
            order_id=req.order_id,
            customer_id=req.customer_id,
            amount=req.amount,
            currency=req.currency,
            payment_method=req.payment_method,
            status=status,
            transaction_id=txn_id,
            error_message=err_msg,
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def refund_payment(self, req: RefundPaymentRequest) -> Refund:
        payment = await self.get_by_order_id(req.order_id)
        if not payment:
            raise EntityNotFoundException("Payment for order", req.order_id)

        if payment.status != "COMPLETED":
            raise AppBaseException(
                message=f"Cannot refund payment with status '{payment.status}'.",
                code="INVALID_PAYMENT_STATE_FOR_REFUND",
                status_code=400,
            )

        refund_amount = req.amount or payment.amount
        refund = Refund(
            payment_id=payment.id,
            order_id=req.order_id,
            amount=refund_amount,
            reason=req.reason,
            status="COMPLETED",
        )
        payment.status = "REFUNDED"

        self.db.add(refund)
        await self.db.commit()
        await self.db.refresh(refund)
        return refund

    async def is_event_processed(self, event_id: str) -> bool:
        stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def mark_event_processed(self, event_id: str, event_type: str) -> None:
        pe = ProcessedEvent(event_id=event_id, event_type=event_type)
        self.db.add(pe)
        await self.db.commit()
