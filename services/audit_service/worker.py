import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from aio_pika.abc import AbstractIncomingMessage

from services.audit_service.documents import AuditEventDocument
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("audit-worker")


class AuditEventWorker:
    def __init__(self, rmq_client: RabbitMQClient):
        self.rmq = rmq_client

    async def start(self) -> None:
        logger.info("Initializing Audit Event Worker...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        # Listen to all events across all domain exchanges
        queue = await self.rmq.setup_queue_with_dlq(
            queue_name="audit.service.all_events",
            exchange_name=EXCHANGES["ORDER"],
            routing_keys=["order.*"],
        )

        if self.rmq.channel:
            payment_ex = await self.rmq.channel.get_exchange(EXCHANGES["PAYMENT"])
            await queue.bind(payment_ex, routing_key="payment.*")

            inventory_ex = await self.rmq.channel.get_exchange(EXCHANGES["INVENTORY"])
            await queue.bind(inventory_ex, routing_key="inventory.*")

            notif_ex = await self.rmq.channel.get_exchange(EXCHANGES["NOTIFICATION"])
            await queue.bind(notif_ex, routing_key="notification.*")

        await self.rmq.start_consumer(queue, self.handle_event)
        logger.info("Audit Event Worker is actively ingesting all domain events into MongoDB.")

    async def handle_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type", "Unknown")
        source = event_data.get("source", "unknown-source")
        corr_id = event_data.get("correlation_id", "")
        causation_id = event_data.get("causation_id")
        occurred_at = event_data.get("occurred_at", datetime.now(timezone.utc).isoformat())
        payload = event_data.get("payload", {})

        if corr_id:
            correlation_id_ctx.set(corr_id)

        # Idempotency check: don't duplicate audit documents if redelivered
        existing = await AuditEventDocument.find_one(AuditEventDocument.event_id == event_id)
        if existing:
            logger.info(f"Audit event {event_id} already ingested. Skipping.")
            return

        doc = AuditEventDocument(
            event_id=event_id,
            event_type=event_type,
            event_version=event_data.get("event_version", 1),
            source_service=source,
            correlation_id=corr_id,
            causation_id=causation_id,
            payload=payload,
            occurred_at=occurred_at,
        )
        await doc.insert()
        logger.info(f"Ingested audit record for event: {event_type} ({event_id})")
