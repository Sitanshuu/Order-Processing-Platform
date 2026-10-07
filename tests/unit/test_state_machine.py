import pytest
import uuid
from services.order_service.repository import OrderRepository
from shared.exceptions import InvalidStateTransitionException


@pytest.mark.asyncio
async def test_valid_order_state_transitions(order_db_session):
    repo = OrderRepository(order_db_session)
    order = await repo.create_order_with_outbox(
        customer_id="cust_123",
        items=[{"product_id": "p1", "product_name": "Item 1", "quantity": 1, "unit_price": 50.0, "subtotal": 50.0}],
        total_amount=50.0,
        idempotency_key=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
    )
    assert order.status == "PENDING"

    # PENDING -> PAYMENT_PENDING
    order = await repo.update_status(order.id, "PAYMENT_PENDING")
    assert order.status == "PAYMENT_PENDING"

    # PAYMENT_PENDING -> PAYMENT_COMPLETED
    order = await repo.update_status(order.id, "PAYMENT_COMPLETED")
    assert order.status == "PAYMENT_COMPLETED"

    # PAYMENT_COMPLETED -> CONFIRMED
    order = await repo.update_status(order.id, "CONFIRMED")
    assert order.status == "CONFIRMED"

    # CONFIRMED -> FULFILLING
    order = await repo.update_status(order.id, "FULFILLING")
    assert order.status == "FULFILLING"

    # FULFILLING -> COMPLETED (Terminal)
    order = await repo.update_status(order.id, "COMPLETED")
    assert order.status == "COMPLETED"


@pytest.mark.asyncio
async def test_invalid_state_transition_raises_error(order_db_session):
    repo = OrderRepository(order_db_session)
    order = await repo.create_order_with_outbox(
        customer_id="cust_456",
        items=[{"product_id": "p1", "product_name": "Item 1", "quantity": 1, "unit_price": 50.0, "subtotal": 50.0}],
        total_amount=50.0,
        idempotency_key=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
    )
    assert order.status == "PENDING"

    # PENDING directly to CONFIRMED is illegal without payment
    with pytest.raises(InvalidStateTransitionException) as excinfo:
        await repo.update_status(order.id, "CONFIRMED")
    assert excinfo.value.code == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_cannot_transition_out_of_terminal_state(order_db_session):
    repo = OrderRepository(order_db_session)
    order = await repo.create_order_with_outbox(
        customer_id="cust_789",
        items=[{"product_id": "p1", "product_name": "Item 1", "quantity": 1, "unit_price": 50.0, "subtotal": 50.0}],
        total_amount=50.0,
        idempotency_key=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
    )
    order = await repo.update_status(order.id, "CANCELLED")
    assert order.status == "CANCELLED"

    # Cannot transition from CANCELLED to PENDING or CONFIRMED
    with pytest.raises(InvalidStateTransitionException):
        await repo.update_status(order.id, "CONFIRMED")
