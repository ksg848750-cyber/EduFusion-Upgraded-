import pytest
import pytest_asyncio
import jwt
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, db_instance

from unittest.mock import patch
from fastapi import HTTPException, status

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


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await connect_to_mongo()
    # Clean test database collections
    await db_instance.db["users"].delete_many({})
    await db_instance.db["subjects"].delete_many({})
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
async def test_valid_token_provisions_user_and_creates_subject():
    headers = {"Authorization": "Bearer mock_valid_token_ganesh"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch user profile - auto provisions in MongoDB
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        user_data = me_res.json()
        assert user_data["authUserId"] == "auth_ganesh_001"
        assert user_data["email"] == "ganesh@example.com"
        user_id = user_data["_id"]

        # Verify document exists in MongoDB Atlas 'users' collection
        user_in_db = await db_instance.db["users"].find_one({"authUserId": "auth_ganesh_001"})
        assert user_in_db is not None
        assert str(user_in_db["_id"]) == user_id

        # 2. Create a subject for this user
        subject_payload = {
            "name": "Computer Architecture",
            "description": "CPU design, pipelining, hazards"
        }
        create_res = await ac.post("/api/v1/subjects", json=subject_payload, headers=headers)
        assert create_res.status_code == 201
        subject_data = create_res.json()
        assert subject_data["name"] == "Computer Architecture"
        assert subject_data["ownerId"] == user_id

        # Verify subject document in MongoDB Atlas 'subjects' collection
        subj_in_db = await db_instance.db["subjects"].find_one({"ownerId": user_id})
        assert subj_in_db is not None
        assert subj_in_db["name"] == "Computer Architecture"

        # 3. List subjects owned by this user
        list_res = await ac.get("/api/v1/subjects", headers=headers)
        assert list_res.status_code == 200
        subjects_list = list_res.json()
        assert len(subjects_list) == 1
        assert subjects_list[0]["name"] == "Computer Architecture"
