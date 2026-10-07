from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from services.product_service.models import Product, Category
from services.product_service.schemas import ProductCreate, ProductUpdate, CategoryCreate
from services.product_service.repository import ProductRepository
from shared.exceptions import EntityNotFoundException, AppBaseException


class ProductService:
    def __init__(self, db: AsyncSession, redis_client: Optional[aioredis.Redis] = None):
        self.repo = ProductRepository(db, redis_client)

    async def get_product(self, product_id: str) -> Product:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundException("Product", product_id)
        return product

    async def create_product(self, schema: ProductCreate) -> Product:
        existing = await self.repo.get_by_sku(schema.sku)
        if existing:
            raise AppBaseException(
                message=f"Product with SKU '{schema.sku}' already exists.",
                code="PRODUCT_SKU_EXISTS",
                status_code=400,
            )
        return await self.repo.create(schema)

    async def update_product(self, product_id: str, schema: ProductUpdate) -> Product:
        product = await self.repo.update(product_id, schema)
        if not product:
            raise EntityNotFoundException("Product", product_id)
        return product

    async def list_products(
        self,
        page: int = 1,
        size: int = 20,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Product], int]:
        skip = (page - 1) * size
        return await self.repo.list_products(skip=skip, limit=size, category_id=category_id, is_active=is_active)

    async def create_category(self, schema: CategoryCreate) -> Category:
        return await self.repo.create_category(schema)

    async def list_categories(self) -> List[Category]:
        return await self.repo.list_categories()
