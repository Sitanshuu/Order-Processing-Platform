import json
from shared.events import (
    create_order_created_event,
    create_payment_completed_event,
    create_inventory_reserved_event,
    create_inventory_reservation_failed_event,
    create_payment_refunded_event,
    create_order_confirmed_event,
    create_order_cancelled_event,
    DomainEvent,
)


def test_order_created_event_serialization():
    event = create_order_created_event(
        order_id="ord-1",
        customer_id="cust-1",
        total_amount=150.0,
        items=[{"product_id": "p1", "product_name": "Keyboard", "quantity": 1, "unit_price": 150.0, "subtotal": 150.0}],
        idempotency_key="key-1",
        correlation_id="corr-1",
        simulation_flag="SUCCESS",
    )
    json_str = event.to_json()
    data = json.loads(json_str)

    assert data["event_type"] == "OrderCreated"
    assert data["source"] == "order-service"
    assert data["correlation_id"] == "corr-1"
    assert data["payload"]["total_amount"] == 150.0

    # Deserialization test
    deserialized = DomainEvent.from_dict(data)
    assert deserialized.event_id == event.event_id
    assert deserialized.payload["order_id"] == "ord-1"


def test_payment_events():
    completed = create_payment_completed_event(
        payment_id="pay-1",
        order_id="ord-1",
        customer_id="cust-1",
        amount=150.0,
        currency="USD",
        payment_method="CREDIT_CARD",
        processed_at="2026-10-07T12:00:00Z",
        correlation_id="corr-1",
        causation_id="evt-1",
    )
    assert completed.event_type == "PaymentCompleted"
    assert completed.causation_id == "evt-1"

    refunded = create_payment_refunded_event(
        refund_id="ref-1",
        payment_id="pay-1",
        order_id="ord-1",
        amount=150.0,
        reason="Stock unavailable",
        refunded_at="2026-10-07T12:01:00Z",
        correlation_id="corr-1",
        causation_id="evt-2",
    )
    assert refunded.event_type == "PaymentRefunded"
    assert refunded.payload["amount"] == 150.0


def test_inventory_events():
    reserved = create_inventory_reserved_event(
        reservation_id="res-1",
        order_id="ord-1",
        items=[{"product_id": "p1", "quantity": 1}],
        reserved_at="2026-10-07T12:00:00Z",
        correlation_id="corr-1",
        causation_id="evt-1",
    )
    assert reserved.event_type == "InventoryReserved"

    failed = create_inventory_reservation_failed_event(
        order_id="ord-1",
        reason="Insufficient stock",
        error_code="INSUFFICIENT_STOCK",
        failed_at="2026-10-07T12:00:00Z",
        items=[{"product_id": "p1", "quantity": 1}],
        correlation_id="corr-1",
        causation_id="evt-1",
    )
    assert failed.event_type == "InventoryReservationFailed"
    assert failed.payload["error_code"] == "INSUFFICIENT_STOCK"
