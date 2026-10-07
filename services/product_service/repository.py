import json
import logging
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
import redis.asyncio as aioredis
from services.product_service.models import Product, Category
from services.product_service.schemas import ProductCreate, ProductUpdate, CategoryCreate
from shared.config import settings

logger = logging.getLogger("product-repository")


class ProductRepository:
    def __init__(self, db: AsyncSession, redis_client: Optional[aioredis.Redis] = None):
        self.db = db
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour cache TTL

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        # 1. Try Cache-Aside from Redis
        if self.redis:
            cache_key = f"product:{product_id}"
            try:
                cached_data = await self.redis.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    # Return object or build product
                    product = Product(
                        id=data["id"],
                        name=data["name"],
                        description=data["description"],
                        sku=data["sku"],
                        price=data["price"],
                        currency=data["currency"],
                        category_id=data["category_id"],
                        is_active=data["is_active"],
                    )
                    return product
            except Exception as e:
                logger.warning(f"Redis cache read error for {cache_key}: {e}")

        # 2. Cache Miss: Query PostgreSQL
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()

        # 3. Populate Redis Cache
        if product and self.redis:
            cache_key = f"product:{product_id}"
            try:
                data = {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "sku": product.sku,
                    "price": product.price,
                    "currency": product.currency,
                    "category_id": product.category_id,
                    "is_active": product.is_active,
                }
                await self.redis.set(cache_key, json.dumps(data), ex=self.cache_ttl)
            except Exception as e:
                logger.warning(f"Redis cache write error for {cache_key}: {e}")

        return product

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, schema: ProductCreate) -> Product:
        product = Product(
            name=schema.name,
            description=schema.description,
            sku=schema.sku,
            price=schema.price,
            currency=schema.currency,
            category_id=schema.category_id,
            is_active=schema.is_active,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update(self, product_id: str, schema: ProductUpdate) -> Optional[Product]:
        product = await self.get_by_id(product_id)
        if not product:
            return None

        update_data = schema.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)

        await self.db.commit()
        await self.db.refresh(product)

        # Invalidate Cache
        if self.redis:
            try:
                await self.redis.delete(f"product:{product_id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate cache for product {product_id}: {e}")

        return product

    async def list_products(
        self,
        skip: int = 0,
        limit: int = 20,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Product], int]:
        query = select(Product)
        count_query = select(func.count(Product.id))

        if category_id:
            query = query.where(Product.category_id == category_id)
            count_query = count_query.where(Product.category_id == category_id)

        if is_active is not None:
            query = query.where(Product.is_active == is_active)
            count_query = count_query.where(Product.is_active == is_active)

        query = query.offset(skip).limit(limit).order_by(Product.created_at.desc())

        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0

        res = await self.db.execute(query)
        items = list(res.scalars().all())
        return items, total

    async def create_category(self, schema: CategoryCreate) -> Category:
        category = Category(name=schema.name, description=schema.description)
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def list_categories(self) -> List[Category]:
        stmt = select(Category).order_by(Category.name.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
