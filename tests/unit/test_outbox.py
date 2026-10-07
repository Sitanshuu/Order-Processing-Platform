import pytest
import uuid
import json
from services.order_service.repository import OrderRepository


@pytest.mark.asyncio
async def test_atomic_order_and_outbox_creation(order_db_session):
    repo = OrderRepository(order_db_session)
    idempotency_key = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    order = await repo.create_order_with_outbox(
        customer_id="cust_test_outbox",
        items=[
            {"product_id": "prod_1", "product_name": "Monitor", "quantity": 2, "unit_price": 200.0, "subtotal": 400.0}
        ],
        total_amount=400.0,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        simulation_flag="SUCCESS",
    )

    assert order is not None
    assert order.id is not None
    assert len(order.items) == 1

    # Verify Outbox table has exactly one PENDING event for this aggregate
    pending_events = await repo.fetch_pending_outbox_events(limit=10)
    matching = [e for e in pending_events if e.aggregate_id == order.id]
    assert len(matching) == 1

    outbox_event = matching[0]
    assert outbox_event.event_type == "OrderCreated"
    assert outbox_event.status == "PENDING"
    
    payload = json.loads(outbox_event.payload)
    assert payload["payload"]["order_id"] == order.id
    assert payload["correlation_id"] == correlation_id

    # Test marking outbox as published
    await repo.mark_outbox_published(outbox_event.id)
    pending_after = await repo.fetch_pending_outbox_events(limit=10)
    matching_after = [e for e in pending_after if e.aggregate_id == order.id]
    assert len(matching_after) == 0
