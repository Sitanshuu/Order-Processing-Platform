from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from shared.events.base import DomainEvent


class ReservedItemPayload(BaseModel):
    product_id: str
    quantity: int


class InventoryReservedPayload(BaseModel):
    reservation_id: str
    order_id: str
    items: List[ReservedItemPayload]
    reserved_at: str
    status: str = "RESERVED"


class InventoryReservationFailedPayload(BaseModel):
    order_id: str
    reason: str
    error_code: str
    failed_at: str
    items: List[ReservedItemPayload]
    status: str = "FAILED"


class InventoryReleasedPayload(BaseModel):
    reservation_id: Optional[str] = None
    order_id: str
    reason: str
    released_at: str
    status: str = "RELEASED"


def create_inventory_reserved_event(
    reservation_id: str,
    order_id: str,
    items: List[Dict[str, Any]],
    reserved_at: str,
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="InventoryReserved",
        source="inventory-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=InventoryReservedPayload(
            reservation_id=reservation_id,
            order_id=order_id,
            items=[ReservedItemPayload(**item) for item in items],
            reserved_at=reserved_at,
        ).model_dump(),
    )


def create_inventory_reservation_failed_event(
    order_id: str,
    reason: str,
    error_code: str,
    failed_at: str,
    items: List[Dict[str, Any]],
    correlation_id: str,
    causation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="InventoryReservationFailed",
        source="inventory-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=InventoryReservationFailedPayload(
            order_id=order_id,
            reason=reason,
            error_code=error_code,
            failed_at=failed_at,
            items=[ReservedItemPayload(**item) for item in items],
        ).model_dump(),
    )


def create_inventory_released_event(
    order_id: str,
    reason: str,
    released_at: str,
    correlation_id: str,
    causation_id: str,
    reservation_id: Optional[str] = None,
) -> DomainEvent:
    return DomainEvent(
        event_type="InventoryReleased",
        source="inventory-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=InventoryReleasedPayload(
            reservation_id=reservation_id,
            order_id=order_id,
            reason=reason,
            released_at=released_at,
        ).model_dump(),
    )
