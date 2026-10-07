import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from aio_pika.abc import AbstractIncomingMessage

from services.notification_service.documents import NotificationDocument
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("notification-worker")


class NotificationEventWorker:
    def __init__(self, rmq_client: RabbitMQClient):
        self.rmq = rmq_client

    async def start(self) -> None:
        logger.info("Initializing Notification Event Worker...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        # Listen to all events on order, payment, and inventory exchanges
        queue = await self.rmq.setup_queue_with_dlq(
            queue_name="notification.service.all_events",
            exchange_name=EXCHANGES["ORDER"],
            routing_keys=["order.*"],
        )
        
        # Also bind to payment and inventory exchanges
        if self.rmq.channel:
            payment_ex = await self.rmq.channel.get_exchange(EXCHANGES["PAYMENT"])
            await queue.bind(payment_ex, routing_key="payment.*")

            inventory_ex = await self.rmq.channel.get_exchange(EXCHANGES["INVENTORY"])
            await queue.bind(inventory_ex, routing_key="inventory.*")

        await self.rmq.start_consumer(queue, self.handle_event)
        logger.info("Notification Event Worker listening to all domain events.")

    async def handle_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")
        customer_id = payload.get("customer_id", "customer@example.com")

        if corr_id:
            correlation_id_ctx.set(corr_id)

        template = f"TEMPLATE_{event_type.upper()}"
        content = f"Simulated Notification: Event {event_type} occurred for Order {order_id}."

        logger.info(
            f"[SIMULATED NOTIFICATION DISPATCH] To: {customer_id} | Channel: EMAIL | Event: {event_type} | Order: {order_id}"
        )

        # Store in MongoDB via Beanie
        doc = NotificationDocument(
            order_id=order_id,
            recipient=customer_id,
            channel="EMAIL",
            template=template,
            content=content,
            status="SENT",
            correlation_id=corr_id,
            metadata={"source_event_id": event_id, "event_type": event_type, "payload": payload},
        )
        await doc.insert()
