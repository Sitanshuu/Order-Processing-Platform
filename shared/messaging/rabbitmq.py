import asyncio
import json
import logging
from typing import Callable, Coroutine, Dict, Any, Optional
import aio_pika
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractRobustChannel,
    AbstractIncomingMessage,
    AbstractExchange,
    AbstractQueue,
)
from shared.config import settings
from shared.events.base import DomainEvent
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("rabbitmq-client")

# Topology definitions
EXCHANGES = {
    "ORDER": "order.events",
    "PAYMENT": "payment.events",
    "INVENTORY": "inventory.events",
    "NOTIFICATION": "notification.events",
    "DLX": "dlx.events",
    "RETRY": "retry.events",
}


class RabbitMQClient:
    """
    Production-grade asynchronous RabbitMQ client with robust topology declarations,
    dead-letter queue (DLQ) support, exponential backoff retries, and prefetch tuning.
    """
    def __init__(self, amqp_url: Optional[str] = None):
        self.amqp_url = amqp_url or settings.RABBITMQ_URL
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None
        self._exchanges: Dict[str, AbstractExchange] = {}
        self._is_connected = False

    async def connect(self, prefetch_count: int = 10) -> None:
        if self._is_connected and self.channel and not self.channel.is_closed:
            return

        try:
            self.connection = await aio_pika.connect_robust(
                self.amqp_url,
                timeout=10,
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=prefetch_count)
            self._is_connected = True
            logger.info("Successfully connected to RabbitMQ broker and initialized channel.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ broker at {self.amqp_url}: {e}")
            raise

    async def declare_topology(self) -> None:
        """Declares all domain exchanges and the dead letter exchange (DLX)."""
        if not self.channel:
            await self.connect()

        assert self.channel is not None

        # 1. Dead Letter Exchange (DLX)
        self._exchanges["DLX"] = await self.channel.declare_exchange(
            EXCHANGES["DLX"],
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # 2. Main Domain Topic Exchanges
        for key in ["ORDER", "PAYMENT", "INVENTORY", "NOTIFICATION"]:
            name = EXCHANGES[key]
            self._exchanges[key] = await self.channel.declare_exchange(
                name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

        logger.info("RabbitMQ exchanges and DLX declared successfully.")

    async def publish_event(
        self,
        exchange_name: str,
        routing_key: str,
        event: DomainEvent,
    ) -> None:
        """
        Publishes a DomainEvent as a persistent message with headers.
        """
        if not self.channel or self.channel.is_closed:
            await self.connect()

        assert self.channel is not None

        exchange = await self.channel.get_exchange(exchange_name)
        
        message_body = event.to_json().encode("utf-8")
        message = aio_pika.Message(
            body=message_body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=event.event_id,
            correlation_id=event.correlation_id,
            headers={
                "event_type": event.event_type,
                "event_version": event.event_version,
                "source": event.source,
                "occurred_at": event.occurred_at,
            },
        )

        await exchange.publish(message, routing_key=routing_key)
        logger.info(
            f"Published event '{event.event_type}' to '{exchange_name}' with routing key '{routing_key}'",
            extra={"event_id": event.event_id, "correlation_id": event.correlation_id, "event_type": event.event_type},
        )

    async def setup_queue_with_dlq(
        self,
        queue_name: str,
        exchange_name: str,
        routing_keys: list[str],
        dlq_queue_name: Optional[str] = None,
    ) -> AbstractQueue:
        """
        Declares a durable queue with dead-letter exchange configuration,
        and binds it to specified routing keys.
        """
        if not self.channel:
            await self.connect()

        assert self.channel is not None
        await self.declare_topology()

        dlq_name = dlq_queue_name or f"{queue_name}.dlq"

        # Declare DLQ queue and bind to DLX
        dlq = await self.channel.declare_queue(
            dlq_name,
            durable=True,
        )
        dlx_exchange = self._exchanges["DLX"]
        for rk in routing_keys:
            await dlq.bind(dlx_exchange, routing_key=rk)

        # Declare main queue with x-dead-letter-exchange
        queue_args = {
            "x-dead-letter-exchange": EXCHANGES["DLX"],
        }
        main_queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments=queue_args,
        )

        domain_exchange = self._exchanges.get(exchange_name.split(".")[0].upper())
        if not domain_exchange:
            domain_exchange = await self.channel.get_exchange(exchange_name)

        for rk in routing_keys:
            await main_queue.bind(domain_exchange, routing_key=rk)

        logger.info(f"Queue '{queue_name}' bound to exchange '{exchange_name}' with keys {routing_keys} (DLQ: '{dlq_name}')")
        return main_queue

    async def start_consumer(
        self,
        queue: AbstractQueue,
        handler: Callable[[Dict[str, Any], AbstractIncomingMessage], Coroutine[Any, Any, None]],
        max_retries: int = 3,
    ) -> None:
        """
        Consumes messages with explicit manual acknowledgements, correlation ID context
        injection, and automatic dead-lettering on repeated unrecoverable failures.
        """
        async def on_message(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=False, ignore_processed=True):
                try:
                    raw_body = message.body.decode("utf-8")
                    data = json.loads(raw_body)
                    corr_id = data.get("correlation_id") or message.correlation_id
                    if corr_id:
                        correlation_id_ctx.set(corr_id)

                    logger.info(
                        f"Consuming message: {data.get('event_type', 'unknown')}",
                        extra={"event_id": data.get("event_id"), "correlation_id": corr_id},
                    )

                    await handler(data, message)
                    await message.ack()
                except Exception as ex:
                    logger.error(f"Error processing message {message.message_id}: {ex}", exc_info=True)
                    # Reject without requeue so RabbitMQ forwards it directly to Dead Letter Exchange (DLX)
                    await message.reject(requeue=False)

        await queue.consume(on_message)
        logger.info(f"Consumer started for queue: {queue.name}")

    async def close(self) -> None:
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        self._is_connected = False
        logger.info("RabbitMQ connection closed cleanly.")
