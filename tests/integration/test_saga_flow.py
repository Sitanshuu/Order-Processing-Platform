import pytest
import uuid
from services.order_service.repository import OrderRepository
from services.payment_service.repository import PaymentRepository
from services.payment_service.schemas import ProcessPaymentRequest, RefundPaymentRequest
from services.inventory_service.repository import InventoryRepository
from shared.exceptions import InsufficientStockException


@pytest.mark.asyncio
async def test_saga_happy_path(order_db_session, payment_db_session, inventory_db_session):
    """
    SAGA HAPPY PATH:
    1. Order Created (PENDING)
    2. Payment Processed (COMPLETED) -> Order (PAYMENT_COMPLETED)
    3. Inventory Reserved -> Order (CONFIRMED)
    """
    order_repo = OrderRepository(order_db_session)
    payment_repo = PaymentRepository(payment_db_session)
    inv_repo = InventoryRepository(inventory_db_session)

    product_id = "prod_laptop_001"
    await inv_repo.initialize_stock(product_id=product_id, quantity=10)

    # Step 1: Create Order
    order = await order_repo.create_order_with_outbox(
        customer_id="customer_alice",
        items=[{"product_id": product_id, "product_name": "Laptop", "quantity": 2, "unit_price": 1000.0, "subtotal": 2000.0}],
        total_amount=2000.0,
        idempotency_key=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        simulation_flag="SUCCESS",
    )
    assert order.status == "PENDING"

    # Step 2: Payment Service processes payment
    payment = await payment_repo.process_payment(
        ProcessPaymentRequest(
            order_id=order.id,
            customer_id=order.customer_id,
            amount=order.total_amount,
            simulation_flag="SUCCESS",
        )
    )
    assert payment.status == "COMPLETED"

    # Order transition to PAYMENT_COMPLETED
    order = await order_repo.update_status(order.id, "PAYMENT_COMPLETED")
    assert order.status == "PAYMENT_COMPLETED"

    # Step 3: Inventory Service reserves stock
    reservations = await inv_repo.reserve_stock(order.id, [{"product_id": product_id, "quantity": 2}])
    assert len(reservations) == 1
    assert reservations[0].status == "RESERVED"

    # Order transition to CONFIRMED
    order = await order_repo.update_status(order.id, "CONFIRMED")
    assert order.status == "CONFIRMED"

    # Verify inventory state
    stock_item = await inv_repo.get_by_product_id(product_id)
    assert stock_item.total_quantity == 10
    assert stock_item.reserved_quantity == 2
    assert stock_item.available_quantity == 8


@pytest.mark.asyncio
async def test_saga_failure_and_compensating_refund(order_db_session, payment_db_session, inventory_db_session):
    """
    SAGA COMPENSATING ACTION PATH:
    1. Order Created (PENDING)
    2. Payment Completed
    3. Inventory Reservation FAILS (Out of stock)
    4. Compensating Action: Payment is Refunded
    5. Order is Cancelled
    """
    order_repo = OrderRepository(order_db_session)
    payment_repo = PaymentRepository(payment_db_session)
    inv_repo = InventoryRepository(inventory_db_session)

    # Initialize with 0 stock to force failure
    product_id = "prod_sold_out_002"
    await inv_repo.initialize_stock(product_id=product_id, quantity=0)

    # Step 1: Create Order
    order = await order_repo.create_order_with_outbox(
        customer_id="customer_bob",
        items=[{"product_id": product_id, "product_name": "Sold Out Item", "quantity": 1, "unit_price": 500.0, "subtotal": 500.0}],
        total_amount=500.0,
        idempotency_key=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        simulation_flag="SUCCESS",
    )
    assert order.status == "PENDING"

    # Step 2: Payment succeeds initially
    payment = await payment_repo.process_payment(
        ProcessPaymentRequest(
            order_id=order.id,
            customer_id=order.customer_id,
            amount=order.total_amount,
            simulation_flag="SUCCESS",
        )
    )
    assert payment.status == "COMPLETED"
    order = await order_repo.update_status(order.id, "PAYMENT_COMPLETED")

    # Step 3: Inventory Reservation fails
    with pytest.raises(InsufficientStockException):
        await inv_repo.reserve_stock(order.id, [{"product_id": product_id, "quantity": 1}])

    order = await order_repo.update_status(order.id, "INVENTORY_FAILED")
    order = await order_repo.update_status(order.id, "REFUND_PENDING")
    assert order.status == "REFUND_PENDING"

    # Step 4: Compensating Refund action executed
    refund = await payment_repo.refund_payment(
        RefundPaymentRequest(
            order_id=order.id,
            amount=payment.amount,
            reason="Compensating action: Inventory out of stock",
        )
    )
    assert refund.status == "COMPLETED"

    # Step 5: Final cancellation
    order = await order_repo.update_status(order.id, "REFUNDED")
    order = await order_repo.update_status(order.id, "CANCELLED")
    assert order.status == "CANCELLED"


@pytest.mark.asyncio
async def test_order_idempotency(order_db_session):
    """
    IDEMPOTENCY VALIDATION:
    Submitting duplicate order requests with the same Idempotency-Key returns
    the existing record without inserting duplicate orders into the database.
    """
    order_repo = OrderRepository(order_db_session)
    fixed_idempotency_key = "idemp_unique_key_12345"

    order_1 = await order_repo.create_order_with_outbox(
        customer_id="customer_charlie",
        items=[{"product_id": "p1", "product_name": "Book", "quantity": 1, "unit_price": 20.0, "subtotal": 20.0}],
        total_amount=20.0,
        idempotency_key=fixed_idempotency_key,
        correlation_id=str(uuid.uuid4()),
    )

    # Second submission with exact same idempotency key
    order_2 = await order_repo.create_order_with_outbox(
        customer_id="customer_charlie",
        items=[{"product_id": "p1", "product_name": "Book", "quantity": 1, "unit_price": 20.0, "subtotal": 20.0}],
        total_amount=20.0,
        idempotency_key=fixed_idempotency_key,
        correlation_id=str(uuid.uuid4()),
    )

    assert order_1.id == order_2.id
    assert order_1.idempotency_key == order_2.idempotency_key

    # Verify total orders in DB is exactly 1
    orders, total = await order_repo.list_orders(customer_id="customer_charlie")
    assert total == 1
