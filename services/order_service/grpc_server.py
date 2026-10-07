import asyncio
import logging
import grpc
from shared.grpc_gen.proto import order_pb2, order_pb2_grpc
from services.order_service.database import AsyncSessionLocal
from services.order_service.repository import OrderRepository
from shared.config import settings

logger = logging.getLogger("order-grpc-server")


class OrderGrpcServicer(order_pb2_grpc.OrderServiceServicer):
    async def GetOrder(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = OrderRepository(session)
            order = await repo.get_by_id(request.order_id)
            if not order:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Order {request.order_id} not found")
                return order_pb2.OrderResponse()

            items_pb = [
                order_pb2.OrderItemMessage(
                    product_id=i.product_id,
                    product_name=i.product_name,
                    quantity=i.quantity,
                    unit_price=float(i.unit_price),
                    subtotal=float(i.subtotal),
                )
                for i in order.items
            ]

            return order_pb2.OrderResponse(
                order_id=order.id,
                customer_id=order.customer_id,
                status=order.status,
                total_amount=float(order.total_amount),
                currency=order.currency,
                items=items_pb,
                created_at=order.created_at.isoformat(),
                updated_at=order.updated_at.isoformat(),
                correlation_id=order.correlation_id,
            )

    async def GetOrderStatus(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = OrderRepository(session)
            order = await repo.get_by_id(request.order_id)
            if not order:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Order {request.order_id} not found")
                return order_pb2.OrderStatusResponse()

            return order_pb2.OrderStatusResponse(
                order_id=order.id,
                status=order.status,
                updated_at=order.updated_at.isoformat(),
            )


async def serve_grpc():
    server = grpc.aio.server()
    order_pb2_grpc.add_OrderServiceServicer_to_server(OrderGrpcServicer(), server)
    bind_addr = f"0.0.0.0:{settings.ORDER_SERVICE_GRPC_PORT}"
    server.add_insecure_port(bind_addr)
    logger.info(f"Order gRPC Server listening on {bind_addr}")
    await server.start()
    await server.wait_for_termination()
