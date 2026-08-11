import pytest
import jwt
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, db_instance


def create_test_jwt(auth_user_id: str, email: str, name: str, expires_in_minutes: int = 60) -> str:
    payload = {
        "sub": auth_user_id,
        "email": email,
        "name": name,
        "interests": ["cricket", "gaming"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    }
    return jwt.encode(payload, settings.BETTER_AUTH_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_expired_jwt(auth_user_id: str) -> str:
    payload = {
        "sub": auth_user_id,
        "email": "expired@example.com",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10)
    }
    return jwt.encode(payload, settings.BETTER_AUTH_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(autouse=True)
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
    expired_token = create_expired_jwt("user_expired_123")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_valid_token_provisions_user_and_creates_subject():
    token = create_test_jwt("auth_ganesh_001", "ganesh@example.com", "Ganesh")
    headers = {"Authorization": f"Bearer {token}"}

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
