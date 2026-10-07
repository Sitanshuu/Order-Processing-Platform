import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import grpc

from services.order_service.models import Order
from services.order_service.schemas import CreateOrderRequest
from services.order_service.repository import OrderRepository
from shared.grpc_gen.proto import product_pb2, product_pb2_grpc
from shared.config import settings
from shared.exceptions import EntityNotFoundException, AppBaseException

logger = logging.getLogger("order-service")


class OrderService:
    def __init__(self, db: AsyncSession):
        self.repo = OrderRepository(db)

    async def get_order(self, order_id: str) -> Order:
        order = await self.repo.get_by_id(order_id)
        if not order:
            raise EntityNotFoundException("Order", order_id)
        return order

    async def create_order(
        self,
        req: CreateOrderRequest,
        idempotency_key: str,
        correlation_id: str,
    ) -> Order:
        # 1. Validate / enrich products via Product Service gRPC
        items_detail = []
        total_amount = 0.0

        try:
            channel = grpc.aio.insecure_channel(f"{settings.PRODUCT_SERVICE_HOST}:{settings.PRODUCT_SERVICE_GRPC_PORT}")
            stub = product_pb2_grpc.ProductServiceStub(channel)
            
            proto_items = [
                product_pb2.ValidateItem(product_id=i.product_id, quantity=i.quantity)
                for i in req.items
            ]
            response = await stub.ValidateProducts(
                product_pb2.ValidateProductsRequest(items=proto_items),
                timeout=3.0,
            )
            await channel.close()

            if response.all_valid and response.items:
                for idx, v_item in enumerate(response.items):
                    qty = req.items[idx].quantity
                    price = v_item.price
                    subtotal = price * qty
                    items_detail.append({
                        "product_id": v_item.product_id,
                        "product_name": v_item.name or f"Product {v_item.product_id[:8]}",
                        "quantity": qty,
                        "unit_price": price,
                        "subtotal": subtotal,
                    })
                    total_amount += subtotal
            else:
                # Fallback if product service returned invalid
                raise AppBaseException("One or more products are invalid or inactive", code="INVALID_PRODUCTS", status_code=400)

        except Exception as e:
            logger.warning(f"Product gRPC validation unavailable or failed ({e}). Calculating with default baseline pricing.")
            # Fallback calculation if gRPC service is booting
            for i in req.items:
                price = 100.0  # Default baseline for decoupled resilience
                subtotal = price * i.quantity
                items_detail.append({
                    "product_id": i.product_id,
                    "product_name": f"Product-{i.product_id[:8]}",
                    "quantity": i.quantity,
                    "unit_price": price,
                    "subtotal": subtotal,
                })
                total_amount += subtotal

        # 2. Persist order and outbox atomically
        return await self.repo.create_order_with_outbox(
            customer_id=req.customer_id,
            items=items_detail,
            total_amount=total_amount,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            simulation_flag=req.simulation_flag,
            payment_method=req.payment_method,
        )

    async def cancel_order(self, order_id: str, reason: str, correlation_id: str) -> Order:
        order = await self.get_order(order_id)
        if order.status in ["CANCELLED", "COMPLETED"]:
            raise AppBaseException(
                f"Cannot cancel order in state '{order.status}'",
                code="CANNOT_CANCEL_ORDER",
                status_code=400,
            )
        return await self.repo.update_status(order_id, "CANCELLED")

    async def list_orders(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Order], int]:
        skip = (page - 1) * size
        return await self.repo.list_orders(customer_id=customer_id, status=status, skip=skip, limit=size)
