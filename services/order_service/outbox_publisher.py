import asyncio
import json
import logging
from services.order_service.database import AsyncSessionLocal
from services.order_service.repository import OrderRepository
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.events.base import DomainEvent
from shared.logging import setup_logger

logger = setup_logger("outbox-publisher")


class OutboxPublisherWorker:
    """
    Background worker that reliably publishes Outbox events to RabbitMQ,
    solving the dual-write problem by decoupling DB commits from message broker delivery.
    """
    def __init__(self, rmq_client: RabbitMQClient, poll_interval_seconds: float = 0.5):
        self.rmq = rmq_client
        self.poll_interval = poll_interval_seconds
        self.is_running = False

    async def start(self) -> None:
        self.is_running = True
        logger.info("Starting Outbox Publisher background worker loop...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        while self.is_running:
            try:
                await self.publish_pending_events()
            except Exception as e:
                logger.error(f"Error in outbox publishing loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval)

    async def publish_pending_events(self) -> None:
        async with AsyncSessionLocal() as session:
            repo = OrderRepository(session)
            pending_events = await repo.fetch_pending_outbox_events(limit=50)

            for event in pending_events:
                try:
                    event_data = json.loads(event.payload)
                    domain_event = DomainEvent.from_dict(event_data)

                    routing_key = f"order.{event.event_type.lower().replace('order', '')}"
                    if event.event_type == "OrderCreated":
                        routing_key = "order.created"
                    elif event.event_type == "OrderConfirmed":
                        routing_key = "order.confirmed"
                    elif event.event_type == "OrderCancelled":
                        routing_key = "order.cancelled"

                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["ORDER"],
                        routing_key=routing_key,
                        event=domain_event,
                    )

                    await repo.mark_outbox_published(event.id)
                    logger.info(
                        f"Outbox event {event.id} ({event.event_type}) published successfully to {EXCHANGES['ORDER']}"
                    )
                except Exception as ex:
                    logger.error(f"Failed to publish outbox event {event.id}: {ex}", exc_info=True)
                    await repo.mark_outbox_failed(event.id, str(ex))

    def stop(self) -> None:
        self.is_running = False
        logger.info("Stopping Outbox Publisher worker...")
