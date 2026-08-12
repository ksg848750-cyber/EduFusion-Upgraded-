import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, db_instance

from unittest.mock import patch
from fastapi import HTTPException, status
from pymongo.errors import ServerSelectionTimeoutError

def mock_verify_jwt_token(token: str) -> dict:
    if token == "mock_valid_token_ganesh":
        return {
            "sub": "auth_ganesh_001",
            "email": "ganesh@example.com",
            "name": "Ganesh",
            "interests": ["cricket", "gaming"]
        }
    elif token == "mock_expired_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Authentication token has expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif token == "invalid_garbage_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
        headers={"WWW-Authenticate": "Bearer"},
    )

@pytest.fixture(autouse=True)
def patch_verify_jwt():
    with patch("app.core.middleware.verify_jwt_token", side_effect=mock_verify_jwt_token):
        yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    try:
        await connect_to_mongo(database_name=settings.MONGODB_TEST_DB_NAME)
    except ServerSelectionTimeoutError:
        await close_mongo_connection()
        pytest.skip("MongoDB is unavailable; Milestone 1 integration tests require MONGODB_URI.")

    assert db_instance.db.name == settings.MONGODB_TEST_DB_NAME
    await db_instance.db["users"].delete_many({})
    yield
    await close_mongo_connection()


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_missing_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me")
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "MISSING_TOKEN"


@pytest.mark.asyncio
async def test_invalid_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_garbage_token"})
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_expired_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": "Bearer mock_expired_token"})
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_valid_token_provisions_user():
    headers = {"Authorization": "Bearer mock_valid_token_ganesh"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch user profile - auto provisions in MongoDB
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        user_data = me_res.json()
        assert user_data["authUserId"] == "auth_ganesh_001"
        assert user_data["email"] == "ganesh@example.com"
        assert user_data["isOnboarded"] is False
        user_id = user_data["_id"]

        # Verify document exists in MongoDB Atlas 'users' collection
        user_in_db = await db_instance.db["users"].find_one({"authUserId": "auth_ganesh_001"})
        assert user_in_db is not None
        assert str(user_in_db["_id"]) == user_id
        assert user_in_db["createdAt"].tzinfo is not None
        indexes = await db_instance.db["users"].index_information()
        assert indexes["authUserId_1"]["unique"] is True
        assert indexes["email_1"]["unique"] is True
