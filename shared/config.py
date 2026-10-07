from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class GlobalSettings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "EventDrivenOrderPlatform"

    # Security
    JWT_SECRET_KEY: str = "dev_insecure_jwt_secret_key_change_in_production_32chars!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # PostgreSQL Shared Credentials
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Database URLs
    ORDER_DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/order_db"
    PRODUCT_DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/product_db"
    INVENTORY_DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db"
    PAYMENT_DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_db"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    NOTIFICATION_DB_NAME: str = "notification_db"
    AUDIT_DB_NAME: str = "audit_db"

    # Service Ports & Hosts
    GATEWAY_PORT: int = 8000
    ORDER_SERVICE_HOST: str = "localhost"
    ORDER_SERVICE_PORT: int = 8001
    ORDER_SERVICE_GRPC_PORT: int = 50051

    PRODUCT_SERVICE_HOST: str = "localhost"
    PRODUCT_SERVICE_PORT: int = 8002
    PRODUCT_SERVICE_GRPC_PORT: int = 50052

    INVENTORY_SERVICE_HOST: str = "localhost"
    INVENTORY_SERVICE_PORT: int = 8003
    INVENTORY_SERVICE_GRPC_PORT: int = 50053

    PAYMENT_SERVICE_HOST: str = "localhost"
    PAYMENT_SERVICE_PORT: int = 8004
    PAYMENT_SERVICE_GRPC_PORT: int = 50054

    NOTIFICATION_SERVICE_HOST: str = "localhost"
    NOTIFICATION_SERVICE_PORT: int = 8005

    AUDIT_SERVICE_HOST: str = "localhost"
    AUDIT_SERVICE_PORT: int = 8006

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = GlobalSettings()
