import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from services.order_service.main import app as order_app
from services.order_service.database import get_db as get_order_db
from services.product_service.main import app as product_app
from services.inventory_service.main import app as inventory_app
from services.payment_service.main import app as payment_app
from services.api_gateway.main import app as gateway_app


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints():
    async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

    async with AsyncClient(transport=ASGITransport(app=order_app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "order-service"

    async with AsyncClient(transport=ASGITransport(app=product_app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "product-service"

    async with AsyncClient(transport=ASGITransport(app=inventory_app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "inventory-service"

    async with AsyncClient(transport=ASGITransport(app=payment_app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "payment-service"


@pytest.mark.asyncio
async def test_gateway_auth_token_issuance():
    async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/token",
            json={"username": "dev_user", "password": "password123", "role": "admin"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "dev_user"


@pytest.mark.asyncio
async def test_order_creation_rest_endpoint(order_db_session):
    async def override_get_order_db():
        yield order_db_session

    order_app.dependency_overrides[get_order_db] = override_get_order_db

    async with AsyncClient(transport=ASGITransport(app=order_app), base_url="http://test") as ac:
        idempotency_key = str(uuid.uuid4())
        payload = {
            "customer_id": "cust_rest_test",
            "items": [{"product_id": "p_phone_1", "quantity": 1}],
            "payment_method": "CREDIT_CARD",
            "simulation_flag": "SUCCESS",
        }
        res = await ac.post(
            "/api/v1/orders",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["customer_id"] == "cust_rest_test"
        assert data["status"] == "PENDING"
        assert data["idempotency_key"] == idempotency_key
        assert "id" in data
        order_id = data["id"]

        # Query back via GET /api/v1/orders/{order_id}
        res_get = await ac.get(f"/api/v1/orders/{order_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == order_id

    order_app.dependency_overrides.clear()
