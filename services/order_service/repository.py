import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from services.order_service.models import Order, OrderItem, OutboxEvent, ProcessedEvent
from shared.exceptions import (
    EntityNotFoundException,
    InvalidStateTransitionException,
    IdempotencyConflictException,
)
from shared.events import create_order_created_event

logger = logging.getLogger("order-repository")

# Strict Order State Machine Transitions
VALID_TRANSITIONS = {
    "PENDING": ["PAYMENT_PENDING", "PAYMENT_COMPLETED", "PAYMENT_FAILED", "CANCELLED"],
    "PAYMENT_PENDING": ["PAYMENT_COMPLETED", "PAYMENT_FAILED", "CANCELLED"],
    "PAYMENT_COMPLETED": ["CONFIRMED", "INVENTORY_FAILED", "CANCELLED"],
    "INVENTORY_FAILED": ["REFUND_PENDING", "CANCELLED"],
    "REFUND_PENDING": ["REFUNDED"],
    "REFUNDED": ["CANCELLED"],
    "CONFIRMED": ["FULFILLING", "CANCELLED"],
    "FULFILLING": ["COMPLETED"],
    "COMPLETED": [],     # Terminal state
    "PAYMENT_FAILED": ["CANCELLED"],
    "CANCELLED": [],     # Terminal state
}


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.idempotency_key == key)
            .options(selectinload(Order.items))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_order_with_outbox(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
        idempotency_key: str,
        correlation_id: str,
        currency: str = "USD",
        simulation_flag: str = "SUCCESS",
        payment_method: str = "CREDIT_CARD",
    ) -> Order:
        """
        ATOMIC TRANSACTIONAL OUTBOX:
        Inserts Order, OrderItems, and OutboxEvent in a single database transaction.
        """
        # Check idempotency in DB
        existing = await self.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        order = Order(
            customer_id=customer_id,
            total_amount=total_amount,
            currency=currency,
            status="PENDING",
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        self.db.add(order)
        await self.db.flush()  # Flush to generate order.id

        order_items = []
        for item in items:
            oi = OrderItem(
                order_id=order.id,
                product_id=item["product_id"],
                product_name=item.get("product_name", f"Product-{item['product_id'][:8]}"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                subtotal=item["subtotal"],
            )
            self.db.add(oi)
            order_items.append(oi)

        # Build Domain Event payload
        domain_event = create_order_created_event(
            order_id=order.id,
            customer_id=customer_id,
            total_amount=total_amount,
            items=[
                {
                    "product_id": oi.product_id,
                    "product_name": oi.product_name,
                    "quantity": oi.quantity,
                    "unit_price": oi.unit_price,
                    "subtotal": oi.subtotal,
                }
                for oi in order_items
            ],
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            simulation_flag=simulation_flag,
            payment_method=payment_method,
        )

        outbox_event = OutboxEvent(
            aggregate_type="Order",
            aggregate_id=order.id,
            event_type="OrderCreated",
            payload=domain_event.to_json(),
            status="PENDING",
        )
        self.db.add(outbox_event)

        await self.db.commit()
        await self.db.refresh(order)
        return await self.get_by_id(order.id)

    async def update_status(self, order_id: str, target_status: str) -> Order:
        order = await self.get_by_id(order_id)
        if not order:
            raise EntityNotFoundException("Order", order_id)

        # Validate state transition
        allowed = VALID_TRANSITIONS.get(order.status, [])
        if target_status not in allowed and order.status != target_status:
            raise InvalidStateTransitionException(
                entity_name="Order",
                current_state=order.status,
                attempted_state=target_status,
            )

        order.status = target_status
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def list_orders(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Order], int]:
        query = select(Order).options(selectinload(Order.items))
        count_query = select(func.count(Order.id))

        if customer_id:
            query = query.where(Order.customer_id == customer_id)
            count_query = count_query.where(Order.customer_id == customer_id)

        if status:
            query = query.where(Order.status == status)
            count_query = count_query.where(Order.status == status)

        query = query.offset(skip).limit(limit).order_by(Order.created_at.desc())

        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0

        res = await self.db.execute(query)
        return list(res.scalars().all()), total

    async def fetch_pending_outbox_events(self, limit: int = 50) -> List[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def mark_outbox_published(self, event_id: str) -> None:
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                status="PUBLISHED",
                published_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def mark_outbox_failed(self, event_id: str, error_msg: str) -> None:
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                status="FAILED",
                error_message=error_msg,
                retry_count=OutboxEvent.retry_count + 1,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def is_event_processed(self, event_id: str) -> bool:
        stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def mark_event_processed(self, event_id: str, event_type: str) -> None:
        pe = ProcessedEvent(event_id=event_id, event_type=event_type)
        self.db.add(pe)
        await self.db.commit()
