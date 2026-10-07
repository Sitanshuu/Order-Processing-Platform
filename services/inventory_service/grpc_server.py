import asyncio
import logging
import grpc
from shared.grpc_gen.proto import inventory_pb2, inventory_pb2_grpc
from services.inventory_service.database import AsyncSessionLocal
from services.inventory_service.repository import InventoryRepository
from shared.config import settings
from shared.exceptions import InsufficientStockException, EntityNotFoundException

logger = logging.getLogger("inventory-grpc-server")


class InventoryGrpcServicer(inventory_pb2_grpc.InventoryServiceServicer):
    async def GetStock(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)
            item = await repo.get_by_product_id(request.product_id)
            if not item:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Product {request.product_id} not found in inventory")
                return inventory_pb2.GetStockResponse()

            return inventory_pb2.GetStockResponse(
                product_id=item.product_id,
                available_quantity=item.available_quantity,
                reserved_quantity=item.reserved_quantity,
                total_quantity=item.total_quantity,
            )

    async def ReserveStock(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)
            items_data = [{"product_id": i.product_id, "quantity": i.quantity} for i in request.items]
            try:
                reservations = await repo.reserve_stock(request.order_id, items_data)
                res_id = reservations[0].id if reservations else ""
                return inventory_pb2.ReserveStockResponse(
                    success=True,
                    reservation_id=res_id,
                    message="Stock reserved successfully",
                )
            except InsufficientStockException as e:
                return inventory_pb2.ReserveStockResponse(
                    success=False,
                    message=e.message,
                    error_code="INSUFFICIENT_STOCK",
                )
            except EntityNotFoundException as e:
                return inventory_pb2.ReserveStockResponse(
                    success=False,
                    message=e.message,
                    error_code="PRODUCT_NOT_FOUND",
                )
            except Exception as e:
                logger.error(f"Error reserving stock via gRPC for order {request.order_id}: {e}")
                return inventory_pb2.ReserveStockResponse(
                    success=False,
                    message=str(e),
                    error_code="INTERNAL_ERROR",
                )

    async def ReleaseStock(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)
            try:
                await repo.release_reservation(request.order_id)
                return inventory_pb2.ReleaseStockResponse(
                    success=True,
                    message="Stock released successfully",
                )
            except Exception as e:
                logger.error(f"Error releasing stock via gRPC for order {request.order_id}: {e}")
                return inventory_pb2.ReleaseStockResponse(
                    success=False,
                    message=str(e),
                )

    async def ConfirmStock(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = InventoryRepository(session)
            try:
                await repo.confirm_reservation(request.order_id)
                return inventory_pb2.ConfirmStockResponse(
                    success=True,
                    message="Stock reservation confirmed",
                )
            except Exception as e:
                logger.error(f"Error confirming stock via gRPC for order {request.order_id}: {e}")
                return inventory_pb2.ConfirmStockResponse(
                    success=False,
                    message=str(e),
                )


async def serve_grpc():
    server = grpc.aio.server()
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryGrpcServicer(), server)
    bind_addr = f"0.0.0.0:{settings.INVENTORY_SERVICE_GRPC_PORT}"
    server.add_insecure_port(bind_addr)
    logger.info(f"Inventory gRPC Server listening on {bind_addr}")
    await server.start()
    await server.wait_for_termination()
