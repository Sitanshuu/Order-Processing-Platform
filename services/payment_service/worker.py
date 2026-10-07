import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from aio_pika.abc import AbstractIncomingMessage

from services.payment_service.database import AsyncSessionLocal
from services.payment_service.repository import PaymentRepository
from services.payment_service.schemas import ProcessPaymentRequest, RefundPaymentRequest
from shared.messaging.rabbitmq import RabbitMQClient, EXCHANGES
from shared.events import (
    create_payment_completed_event,
    create_payment_failed_event,
    create_payment_refunded_event,
)
from shared.logging import setup_logger, correlation_id_ctx

logger = setup_logger("payment-worker")


class PaymentEventWorker:
    def __init__(self, rmq_client: RabbitMQClient):
        self.rmq = rmq_client

    async def start(self) -> None:
        logger.info("Initializing Payment Event Worker...")
        await self.rmq.connect()
        await self.rmq.declare_topology()

        # Listen to OrderCreated events to trigger payment processing
        order_queue = await self.rmq.setup_queue_with_dlq(
            queue_name="payment.service.order_events",
            exchange_name=EXCHANGES["ORDER"],
            routing_keys=["order.created", "order.refund_requested"],
        )

        # Listen to InventoryReservationFailed events to trigger compensating refunds
        inventory_queue = await self.rmq.setup_queue_with_dlq(
            queue_name="payment.service.inventory_events",
            exchange_name=EXCHANGES["INVENTORY"],
            routing_keys=["inventory.reservation_failed"],
        )

        await self.rmq.start_consumer(order_queue, self.handle_order_event)
        await self.rmq.start_consumer(inventory_queue, self.handle_inventory_event)
        logger.info("Payment Event Worker is consuming events from RabbitMQ.")

    async def handle_order_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        if corr_id:
            correlation_id_ctx.set(corr_id)

        async with AsyncSessionLocal() as session:
            repo = PaymentRepository(session)

            if await repo.is_event_processed(event_id):
                logger.info(f"Payment event {event_id} already processed. Skipping.")
                return

            if event_type == "OrderCreated":
                logger.info(f"Processing payment for order {order_id} (amount: {payload.get('total_amount')})")
                
                req = ProcessPaymentRequest(
                    order_id=order_id,
                    customer_id=payload.get("customer_id", "guest"),
                    amount=float(payload.get("total_amount", 0.0)),
                    currency=payload.get("currency", "USD"),
                    payment_method=payload.get("payment_method", "CREDIT_CARD"),
                    simulation_flag=payload.get("simulation_flag", "SUCCESS"),
                )

                payment = await repo.process_payment(req)

                if payment.status == "COMPLETED":
                    completed_event = create_payment_completed_event(
                        payment_id=payment.id,
                        order_id=order_id,
                        customer_id=payment.customer_id,
                        amount=payment.amount,
                        currency=payment.currency,
                        payment_method=payment.payment_method,
                        processed_at=datetime.now(timezone.utc).isoformat(),
                        correlation_id=corr_id,
                        causation_id=event_id,
                    )
                    # Include items in payload so downstream inventory worker can reserve directly
                    completed_event.payload["items"] = payload.get("items", [])

                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["PAYMENT"],
                        routing_key="payment.completed",
                        event=completed_event,
                    )
                    logger.info(f"PaymentCompleted event published for order {order_id}")
                else:
                    failed_event = create_payment_failed_event(
                        order_id=order_id,
                        customer_id=payment.customer_id,
                        amount=payment.amount,
                        currency=payment.currency,
                        error_code="PAYMENT_DECLINED",
                        reason=payment.error_message or "Payment declined",
                        failed_at=datetime.now(timezone.utc).isoformat(),
                        correlation_id=corr_id,
                        causation_id=event_id,
                        payment_id=payment.id,
                    )
                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["PAYMENT"],
                        routing_key="payment.failed",
                        event=failed_event,
                    )
                    logger.warning(f"PaymentFailed event published for order {order_id}")

                await repo.mark_event_processed(event_id, event_type)

    async def handle_inventory_event(self, event_data: Dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")
        payload = event_data.get("payload", {})
        corr_id = event_data.get("correlation_id")
        order_id = payload.get("order_id")

        async with AsyncSessionLocal() as session:
            repo = PaymentRepository(session)

            if await repo.is_event_processed(event_id):
                return

            if event_type == "InventoryReservationFailed":
                logger.info(f"Triggering compensating refund for order {order_id} due to inventory failure.")
                payment = await repo.get_by_order_id(order_id)
                if payment and payment.status == "COMPLETED":
                    refund_req = RefundPaymentRequest(
                        order_id=order_id,
                        amount=payment.amount,
                        reason="Compensating action: Inventory reservation failed",
                    )
                    refund = await repo.refund_payment(refund_req)

                    refunded_event = create_payment_refunded_event(
                        refund_id=refund.id,
                        payment_id=payment.id,
                        order_id=order_id,
                        amount=refund.amount,
                        reason=refund.reason,
                        refunded_at=datetime.now(timezone.utc).isoformat(),
                        correlation_id=corr_id,
                        causation_id=event_id,
                    )
                    await self.rmq.publish_event(
                        exchange_name=EXCHANGES["PAYMENT"],
                        routing_key="payment.refunded",
                        event=refunded_event,
                    )
                    logger.info(f"PaymentRefunded event published for order {order_id}")

                await repo.mark_event_processed(event_id, event_type)
