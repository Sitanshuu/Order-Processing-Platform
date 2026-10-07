import logging
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from services.inventory_service.models import InventoryItem, InventoryReservation, ProcessedEvent
from shared.exceptions import EntityNotFoundException, InsufficientStockException

logger = logging.getLogger("inventory-repository")


class InventoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_product_id(self, product_id: str, for_update: bool = False) -> Optional[InventoryItem]:
        query = select(InventoryItem).where(InventoryItem.product_id == product_id)
        if for_update:
            # PESSIMISTIC ROW-LEVEL LOCK to eliminate race conditions during concurrent checkouts
            query = query.with_for_update()
        res = await self.db.execute(query)
        return res.scalar_one_or_none()

    async def initialize_stock(self, product_id: str, quantity: int) -> InventoryItem:
        item = await self.get_by_product_id(product_id)
        if item:
            item.total_quantity = quantity
            item.reserved_quantity = 0
        else:
            item = InventoryItem(product_id=product_id, total_quantity=quantity, reserved_quantity=0)
            self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def replenish_stock(self, product_id: str, quantity: int) -> InventoryItem:
        item = await self.get_by_product_id(product_id, for_update=True)
        if not item:
            item = InventoryItem(product_id=product_id, total_quantity=quantity, reserved_quantity=0)
            self.db.add(item)
        else:
            item.total_quantity += quantity
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def reserve_stock(self, order_id: str, items: List[Dict[str, int]]) -> List[InventoryReservation]:
        """
        Executes atomic reservation across all requested items using atomic conditional updates
        and row-level locks. If any single product lacks sufficient stock, raises InsufficientStockException and rolls back.
        """
        reservations = []
        sorted_items = sorted(items, key=lambda x: x["product_id"])

        for req in sorted_items:
            p_id = req["product_id"]
            qty = req["quantity"]

            # Atomic conditional update: only increment reserved_quantity if available >= qty
            stmt = (
                update(InventoryItem)
                .where(
                    InventoryItem.product_id == p_id,
                    (InventoryItem.total_quantity - InventoryItem.reserved_quantity) >= qty,
                )
                .values(reserved_quantity=InventoryItem.reserved_quantity + qty)
            )
            result = await self.db.execute(stmt)

            if result.rowcount == 0:
                # Could be missing product or insufficient stock
                item = await self.get_by_product_id(p_id)
                if not item:
                    raise EntityNotFoundException("InventoryItem", p_id)
                available = item.total_quantity - item.reserved_quantity
                logger.warning(
                    f"Insufficient stock for product {p_id}. Requested: {qty}, Available: {available}"
                )
                raise InsufficientStockException(product_id=p_id, requested=qty, available=available)

            reservation = InventoryReservation(
                order_id=order_id,
                product_id=p_id,
                quantity=qty,
                status="RESERVED",
            )
            self.db.add(reservation)
            reservations.append(reservation)

        await self.db.commit()
        for r in reservations:
            await self.db.refresh(r)
        return reservations

    async def confirm_reservation(self, order_id: str) -> None:
        """Deducts stock permanently once order is confirmed."""
        res_stmt = select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == "RESERVED",
        )
        res = await self.db.execute(res_stmt)
        reservations = list(res.scalars().all())

        for r in reservations:
            item = await self.get_by_product_id(r.product_id, for_update=True)
            if item:
                item.total_quantity -= r.quantity
                item.reserved_quantity -= r.quantity
            r.status = "CONFIRMED"

        await self.db.commit()

    async def release_reservation(self, order_id: str) -> None:
        """Compensating action: releases reserved stock back to available pool."""
        res_stmt = select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == "RESERVED",
        )
        res = await self.db.execute(res_stmt)
        reservations = list(res.scalars().all())

        for r in reservations:
            item = await self.get_by_product_id(r.product_id, for_update=True)
            if item:
                item.reserved_quantity = max(0, item.reserved_quantity - r.quantity)
            r.status = "RELEASED"

        await self.db.commit()

    async def is_event_processed(self, event_id: str) -> bool:
        stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def mark_event_processed(self, event_id: str, event_type: str) -> None:
        pe = ProcessedEvent(event_id=event_id, event_type=event_type)
        self.db.add(pe)
        await self.db.commit()
