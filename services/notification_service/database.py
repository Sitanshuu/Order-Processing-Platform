from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from shared.config import settings
from shared.logging import setup_logger

logger = setup_logger("notification-db")

motor_client: AsyncIOMotorClient = None


async def init_db():
    global motor_client
    from services.notification_service.documents import NotificationDocument
    try:
        motor_client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = motor_client[settings.NOTIFICATION_DB_NAME]
        await init_beanie(database=db, document_models=[NotificationDocument])
        logger.info(f"Connected to MongoDB database: {settings.NOTIFICATION_DB_NAME}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB for Notification Service: {e}")
        raise


async def close_db():
    global motor_client
    if motor_client:
        motor_client.close()
        logger.info("Closed MongoDB connection for Notification Service.")
