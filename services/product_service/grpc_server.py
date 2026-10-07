import asyncio
import logging
import grpc
from concurrent import futures
from shared.grpc_gen.proto import product_pb2, product_pb2_grpc
from services.product_service.database import AsyncSessionLocal
from services.product_service.repository import ProductRepository
from shared.config import settings

logger = logging.getLogger("product-grpc-server")


class ProductGrpcServicer(product_pb2_grpc.ProductServiceServicer):
    async def GetProduct(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = ProductRepository(session)
            product = await repo.get_by_id(request.product_id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Product {request.product_id} not found")
                return product_pb2.ProductResponse()

            return product_pb2.ProductResponse(
                product_id=product.id,
                name=product.name,
                sku=product.sku,
                price=float(product.price),
                currency=product.currency,
                is_active=product.is_active,
            )

    async def ValidateProducts(self, request, context):
        async with AsyncSessionLocal() as session:
            repo = ProductRepository(session)
            items_res = []
            total_amount = 0.0
            all_valid = True

            for item in request.items:
                product = await repo.get_by_id(item.product_id)
                if not product or not product.is_active:
                    all_valid = False
                    items_res.append(
                        product_pb2.ValidatedProductDetail(
                            product_id=item.product_id,
                            name="",
                            price=0.0,
                            is_valid=False,
                            error_message="Product not found or inactive",
                        )
                    )
                else:
                    subtotal = float(product.price) * item.quantity
                    total_amount += subtotal
                    items_res.append(
                        product_pb2.ValidatedProductDetail(
                            product_id=product.id,
                            name=product.name,
                            price=float(product.price),
                            is_valid=True,
                            error_message="",
                        )
                    )

            return product_pb2.ValidateProductsResponse(
                all_valid=all_valid,
                items=items_res,
                total_amount=total_amount,
            )


async def serve_grpc():
    server = grpc.aio.server()
    product_pb2_grpc.add_ProductServiceServicer_to_server(ProductGrpcServicer(), server)
    bind_addr = f"0.0.0.0:{settings.PRODUCT_SERVICE_GRPC_PORT}"
    server.add_insecure_port(bind_addr)
    logger.info(f"Product gRPC Server listening on {bind_addr}")
    await server.start()
    await server.wait_for_termination()
