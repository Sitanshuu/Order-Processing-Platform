import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from aio_pika.abc import AbstractIncomingMessage

from services.order_service.database import AsyncSessionLocal
from services.order_service.repository import OrderRepository
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.events import create_order_confirmed_event, create_order_cancelled_event
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("order-saga-worker")


class OrderSagaWorker:
    """
    Saga event consumer for Order Service.
    Transitions order states in response to downstream Payment and Inventory events.
    """
    def __init__(self, rmq_client: RabbitMQClient):
        self.rmq = rmq_client

    async def start(self) -> None:
        logger.info("Initializing Order Saga Worker...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        # Listen to Payment events
        payment_queue = await self.rmq.setup_queue_with_dlq(
            queue_name="order.service.payment_events",
            exchange_name=EXCHANGES["PAYMENT"],
            routing_keys=["payment.completed", "payment.failed", "payment.refunded"],
        )

        # Listen to Inventory events
        inventory_queue = await self.rmq.setup_queue_with_dlq(
            queue_name="order.service.inventory_events",
            exchange_name=EXCHANGES["INVENTORY"],
            routing_keys=["inventory.reserved", "inventory.reservation_failed", "inventory.released"],
        )

        await self.rmq.start_consumer(payment_queue, self.handle_payment_event)
        await self.rmq.start_consumer(inventory_queue, self.handle_inventory_event)
        logger.info("Order Saga Worker is actively consuming payment and inventory events.")

    async def handle_payment_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        if corr_id:
            correlation_id_ctx.set(corr_id)

        async with AsyncSessionLocal() as session:
            repo = OrderRepository(session)
            if await repo.is_event_processed(event_id):
                logger.info(f"Payment event {event_id} already processed for order {order_id}. Skipping.")
                return

            if event_type == "PaymentCompleted":
                logger.info(f"Order {order_id}: Payment Completed. Updating state to PAYMENT_COMPLETED.")
                await repo.update_status(order_id, "PAYMENT_COMPLETED")

            elif event_type == "PaymentFailed":
                logger.warning(f"Order {order_id}: Payment Failed ({payload.get('reason')}). Cancelling order.")
                await repo.update_status(order_id, "PAYMENT_FAILED")
                await repo.update_status(order_id, "CANCELLED")

                cancelled_evt = create_order_cancelled_event(
                    order_id=order_id,
                    customer_id=payload.get("customer_id", ""),
                    reason=f"Payment failed: {payload.get('reason')}",
                    cancelled_at=datetime.now(timezone.utc).isoformat(),
                    correlation_id=corr_id,
                    causation_id=event_id,
                )
                await self.rmq.publish_event(
                    exchange_name=EXCHANGES["ORDER"],
                    routing_key="order.cancelled",
                    event=cancelled_evt,
                )

            elif event_type == "PaymentRefunded":
                logger.info(f"Order {order_id}: Payment Refunded. Finalizing state as REFUNDED -> CANCELLED.")
                await repo.update_status(order_id, "REFUNDED")
                await repo.update_status(order_id, "CANCELLED")

                cancelled_evt = create_order_cancelled_event(
                    order_id=order_id,
                    customer_id=payload.get("customer_id", ""),
                    reason=f"Refund completed: {payload.get('reason')}",
                    cancelled_at=datetime.now(timezone.utc).isoformat(),
                    correlation_id=corr_id,
                    causation_id=event_id,
                )
                await self.rmq.publish_event(
                    exchange_name=EXCHANGES["ORDER"],
                    routing_key="order.cancelled",
                    event=cancelled_evt,
                )

            await repo.mark_event_processed(event_id, event_type)

    async def handle_inventory_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        if corr_id:
            correlation_id_ctx.set(corr_id)

        async with AsyncSessionLocal() as session:
            repo = OrderRepository(session)
            if await repo.is_event_processed(event_id):
                return

            if event_type == "InventoryReserved":
                logger.info(f"Order {order_id}: Inventory Reserved. Updating status to CONFIRMED.")
                order = await repo.update_status(order_id, "CONFIRMED")

                confirmed_evt = create_order_confirmed_event(
                    order_id=order_id,
                    customer_id=order.customer_id,
                    confirmed_at=datetime.now(timezone.utc).isoformat(),
                    correlation_id=corr_id,
                    causation_id=event_id,
                )
                await self.rmq.publish_event(
                    exchange_name=EXCHANGES["ORDER"],
                    routing_key="order.confirmed",
                    event=confirmed_evt,
                )

            elif event_type == "InventoryReservationFailed":
                logger.warning(
                    f"Order {order_id}: Inventory Reservation Failed ({payload.get('reason')}). Setting INVENTORY_FAILED -> REFUND_PENDING."
                )
                await repo.update_status(order_id, "INVENTORY_FAILED")
                await repo.update_status(order_id, "REFUND_PENDING")

            await repo.mark_event_processed(event_id, event_type)
