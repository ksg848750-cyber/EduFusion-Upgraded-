import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("edufusion.database")


class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None


db_instance = Database()


async def connect_to_mongo():
    logger.info("Connecting to MongoDB Atlas...")
    db_instance.client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
    
    # Ping the database to verify connectivity
    try:
        await db_instance.client.admin.command('ping')
        logger.info(f"Successfully connected to MongoDB database: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e


async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    if db_instance.db is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo first.")
    return db_instance.db
