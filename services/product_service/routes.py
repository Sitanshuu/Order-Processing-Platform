from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from services.product_service.database import get_db
from services.product_service.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    CategoryCreate,
    CategoryResponse,
)
from services.product_service.service import ProductService
from shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["Products & Categories"])

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            _redis_client = None
    return _redis_client


def get_service(
    db: AsyncSession = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
) -> ProductService:
    return ProductService(db, redis_client)


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    service: ProductService = Depends(get_service),
):
    items, total = await service.list_products(page=page, size=size, category_id=category_id, is_active=is_active)
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    service: ProductService = Depends(get_service),
):
    product = await service.create_product(payload)
    return ProductResponse.model_validate(product)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_service),
):
    product = await service.get_product(product_id)
    return ProductResponse.model_validate(product)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    service: ProductService = Depends(get_service),
):
    product = await service.update_product(product_id, payload)
    return ProductResponse.model_validate(product)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    service: ProductService = Depends(get_service),
):
    category = await service.create_category(payload)
    return CategoryResponse.model_validate(category)


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    service: ProductService = Depends(get_service),
):
    categories = await service.list_categories()
    return [CategoryResponse.model_validate(c) for c in categories]
