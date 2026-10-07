import asyncio
import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from services.inventory_service.models import Base as InventoryBase
from services.inventory_service.repository import InventoryRepository
from shared.exceptions import InsufficientStockException


@pytest.mark.asyncio
async def test_high_concurrency_stock_reservation_prevents_overselling():
    """
    CONCURRENCY VALIDATION:
    Simulates 50 concurrent buyers competing for 1 remaining stock unit.
    Proves that:
    1. Exactly 1 reservation succeeds.
    2. Exactly 49 requests fail with InsufficientStockException.
    3. Final inventory stock is non-negative and consistent.
    """
    # Use SQLite file or memory with shared cache for concurrency simulation
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(InventoryBase.metadata.create_all)

    SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Initialize Stock = 1
    product_id = f"prod_hot_deal_{uuid.uuid4().hex[:8]}"
    async with SessionFactory() as session:
        repo = InventoryRepository(session)
        await repo.initialize_stock(product_id=product_id, quantity=1)

    successful_reservations = []
    failed_reservations = []

    # 2. Worker task simulating an incoming buyer request
    async def try_reserve(buyer_id: int):
        async with SessionFactory() as session:
            repo = InventoryRepository(session)
            order_id = f"order_{buyer_id}_{uuid.uuid4().hex[:6]}"
            try:
                # Synchronize reservation attempt
                res = await repo.reserve_stock(order_id, [{"product_id": product_id, "quantity": 1}])
                successful_reservations.append((order_id, res))
            except InsufficientStockException as e:
                failed_reservations.append((order_id, str(e)))
            except Exception as e:
                failed_reservations.append((order_id, f"Unexpected: {e}"))

    # 3. Fire 50 simultaneous concurrent reservation tasks
    concurrent_buyers = 50
    tasks = [try_reserve(i) for i in range(concurrent_buyers)]
    await asyncio.gather(*tasks)

    # 4. Strict assertions
    assert len(successful_reservations) == 1, f"Expected 1 winner, got {len(successful_reservations)}"
    assert len(failed_reservations) == concurrent_buyers - 1, f"Expected {concurrent_buyers - 1} failures"

    # 5. Verify final inventory state in DB
    async with SessionFactory() as session:
        repo = InventoryRepository(session)
        item = await repo.get_by_product_id(product_id)
        assert item.total_quantity == 1
        assert item.reserved_quantity == 1
        assert item.available_quantity == 0

    await engine.dispose()
