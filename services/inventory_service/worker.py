import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from aio_pika.abc import AbstractIncomingMessage

from services.inventory_service.database import AsyncSessionLocal
from services.inventory_service.repository import InventoryRepository
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.events import (
    create_inventory_reserved_event,
    create_inventory_reservation_failed_event,
    create_inventory_released_event,
)
from shared.exceptions import InsufficientStockException, EntityNotFoundException
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("inventory-worker")


class InventoryEventWorker:
    def __init__(self, rmq_client: RabbitMQClient):
        self.rmq = rmq_client

    async def start(self) -> None:
        logger.info("Initializing Inventory Event Worker...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        # Listen to payment events (for forward reservation upon payment completion)
        queue = await self.rmq.setup_queue_with_dlq(
            queue_name="inventory.service.payment_events",
            exchange_name=EXCHANGES["PAYMENT"],
            routing_keys=["payment.completed", "payment.refunded"],
        )

        # Listen to order events (for compensation / cancellation release)
        order_queue = await self.rmq.setup_queue_with_dlq(
            queue_name="inventory.service.order_events",
            exchange_name=EXCHANGES["ORDER"],
            routing_keys=["order.cancelled"],
        )

        await self.rmq.start_consumer(queue, self.handle_payment_event)
        await self.rmq.start_consumer(order_queue, self.handle_order_event)
        logger.info("Inventory Event Worker is consuming events from RabbitMQ.")

    async def handle_payment_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        if corr_id:
            correlation_id_ctx.set(corr_id)

        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)

            # Idempotency check: has this event already been processed?
            if await repo.is_event_processed(event_id):
                logger.info(f"Event {event_id} ({event_type}) already processed. Skipping.")
                return

            if event_type == "PaymentCompleted":
                logger.info(f"Processing stock reservation for order {order_id} following PaymentCompleted.")
                # Retrieve items from payload or metadata
                items = payload.get("items")
                if not items:
                    # If items were not directly in PaymentCompleted payload, check order details
                    logger.info(f"No item details embedded in event for order {order_id}; using default stock check.")
                    items = []

                try:
                    reservations = await repo.reserve_stock(order_id, items) if items else []
                    res_id = reservations[0].id if reservations else f"res-{order_id}"
                    
                    reserved_event = create_inventory_reserved_event(
                        reservation_id=res_id,
                        order_id=order_id,
                        items=items,
                        reserved_at=datetime.now(timezone.utc).isoformat(),
                        correlation_id=corr_id,
                        causation_id=event_id,
                    )
                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["INVENTORY"],
                        routing_key="inventory.reserved",
                        event=reserved_event,
                    )
                    await repo.mark_event_processed(event_id, event_type)
                    logger.info(f"Inventory successfully reserved for order {order_id}")

                except InsufficientStockException as e:
                    logger.warning(f"Stock reservation failed for order {order_id}: {e.message}")
                    failed_event = create_inventory_reservation_failed_event(
                        order_id=order_id,
                        reason=e.message,
                        error_code="INSUFFICIENT_STOCK",
                        failed_at=datetime.now(timezone.utc).isoformat(),
                        items=items,
                        correlation_id=corr_id,
                        causation_id=event_id,
                    )
                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["INVENTORY"],
                        routing_key="inventory.reservation_failed",
                        event=failed_event,
                    )
                    await repo.mark_event_processed(event_id, event_type)

                except Exception as ex:
                    logger.error(f"Unexpected error reserving inventory for order {order_id}: {ex}", exc_info=True)
                    raise

    async def handle_order_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)
            if await repo.is_event_processed(event_id):
                return

            if event_type == "OrderCancelled":
                logger.info(f"Releasing inventory hold for cancelled order {order_id}")
                await repo.release_reservation(order_id)
                
                released_event = create_inventory_released_event(
                    order_id=order_id,
                    reason=payload.get("reason", "Order cancelled"),
                    released_at=datetime.now(timezone.utc).isoformat(),
                    correlation_id=corr_id,
                    causation_id=event_id,
                )
                await self.rmq.publish_event(
                    exchange_name=EXCHANGES["INVENTORY"],
                    routing_key="inventory.released",
                    event=released_event,
                )
                await repo.mark_event_processed(event_id, event_type)
