from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from services.inventory_service.models import InventoryItem, InventoryReservation
from services.inventory_service.schemas import StockInitialize, StockReplenish, ReserveStockRequest
from services.inventory_service.repository import InventoryRepository
from shared.exceptions import EntityNotFoundException


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.repo = InventoryRepository(db)

    async def get_stock(self, product_id: str) -> InventoryItem:
        item = await self.repo.get_by_product_id(product_id)
        if not item:
            raise EntityNotFoundException("InventoryItem", product_id)
        return item

    async def initialize_stock(self, schema: StockInitialize) -> InventoryItem:
        return await self.repo.initialize_stock(schema.product_id, schema.quantity)

    async def replenish_stock(self, product_id: str, schema: StockReplenish) -> InventoryItem:
        return await self.repo.replenish_stock(product_id, schema.quantity)

    async def reserve_stock(self, req: ReserveStockRequest) -> List[InventoryReservation]:
        items_data = [{"product_id": i.product_id, "quantity": i.quantity} for i in req.items]
        return await self.repo.reserve_stock(req.order_id, items_data)

    async def confirm_reservation(self, order_id: str) -> None:
        await self.repo.confirm_reservation(order_id)

    async def release_reservation(self, order_id: str) -> None:
        await self.repo.release_reservation(order_id)
