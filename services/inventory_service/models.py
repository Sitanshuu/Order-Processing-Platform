from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship
from services.inventory_service.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), unique=True, nullable=False, index=True)
    total_quantity = Column(Integer, default=0, nullable=False)
    reserved_quantity = Column(Integer, default=0, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="chk_positive_total_quantity"),
        CheckConstraint("reserved_quantity >= 0", name="chk_positive_reserved_quantity"),
        CheckConstraint("reserved_quantity <= total_quantity", name="chk_reserved_lte_total"),
    )

    @property
    def available_quantity(self) -> int:
        return self.total_quantity - self.reserved_quantity


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), nullable=False, index=True)
    product_id = Column(String(36), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    # RESERVED, CONFIRMED, RELEASED
    status = Column(String(30), default="RESERVED", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_res_order_product", "order_id", "product_id"),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id = Column(String(36), primary_key=True)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
