import time
from datetime import datetime, timezone

import jwt

from app.api.v1.endpoints import auth as auth_module
from app.core import security as security_module
from app.core.config import get_settings

_TEST_SECRET = "unit-test-hs256-secret-for-edufusion-32bytes"


def _make_token(settings, sub="user-bearer-1"):
    payload = {
        "sub": sub,
        "email": "bearer@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


def test_auth_me_accepts_bearer_token(raw_client, monkeypatch):
    """Regression: the HTTPBearer scheme must be wired into get_current_user,
    otherwise a valid Authorization header is never parsed.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_jwt_secret", _TEST_SECRET)

    async def no_key(kid=None):
        return None

    monkeypatch.setattr(security_module, "_get_signing_key", no_key)

    async def fake_get(auth_user_id):
        return _profile(authUserId=auth_user_id)

    monkeypatch.setattr(auth_module, "get_user_by_auth_id", fake_get)

    token = _make_token(settings)
    resp = raw_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["authUserId"] == "user-bearer-1"


def _profile(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "authUserId": "test-auth-uid-123",
        "email": "learner@example.com",
        "name": "Test Learner",
        "isOnboarded": False,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def test_health_rejects_unauthenticated(raw_client):
    resp = raw_client.get("/api/v1/health")
    assert resp.status_code == 401


def test_auth_me_rejects_unauthenticated(raw_client):
    resp = raw_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_health_accepts_authenticated(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["user"] == "test-auth-uid-123"


def test_auth_me_persists_new_user(client, monkeypatch):
    async def fake_get(auth_user_id):
        return None

    async def fake_upsert(auth_user_id, email, name):
        return _profile()

    monkeypatch.setattr(auth_module, "get_user_by_auth_id", fake_get)
    monkeypatch.setattr(auth_module, "upsert_user", fake_upsert)

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authUserId"] == "test-auth-uid-123"
    assert body["email"] == "learner@example.com"
    assert body["name"] == "Test Learner"


def test_auth_me_returns_existing_user(client, monkeypatch):
    async def fake_get(auth_user_id):
        return _profile(name="Returned Learner")

    monkeypatch.setattr(auth_module, "get_user_by_auth_id", fake_get)

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Returned Learner"
