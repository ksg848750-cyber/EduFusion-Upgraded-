import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("edufusion.database")


class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None


db_instance = Database()


async def connect_to_mongo(database_name: str | None = None):
    logger.info("Connecting to MongoDB Atlas...")
    db_instance.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5_000,
    )
    selected_database = database_name or settings.MONGODB_DB_NAME
    db_instance.db = db_instance.client[selected_database]
    
    # Ping the database to verify connectivity
    try:
        await db_instance.client.admin.command('ping')
        await db_instance.db["users"].create_index("authUserId", unique=True)
        await db_instance.db["users"].create_index("email", unique=True)
        logger.info(f"Successfully connected to MongoDB database: {selected_database}")
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
