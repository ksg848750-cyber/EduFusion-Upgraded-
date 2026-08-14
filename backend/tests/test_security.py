import asyncio
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core import security
from app.core.config import get_settings

TEST_SECRET = "unit-test-hs256-secret-for-edufusion-32bytes"


def _token(payload: dict, secret: str = TEST_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def hs256_mode(monkeypatch):
    """Force the HS256 fallback path: no JWKS resolution, secret present."""
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)
    monkeypatch.setattr(security, "_get_signing_key", _return_none)
    return settings


async def _return_none(kid=None):  # noqa: ANN001
    return None


def _valid_payload(settings):
    return {
        "sub": "user-abc",
        "email": "a@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
        "exp": int(time.time()) + 3600,
    }


def test_verify_jwt_accepts_valid_token(hs256_mode):
    payload = _valid_payload(hs256_mode)
    claims = _run(security.verify_jwt(_token(payload)))
    assert claims["sub"] == "user-abc"
    assert claims["email"] == "a@example.com"


def test_verify_jwt_rejects_expired_token(hs256_mode):
    settings = hs256_mode
    payload = _valid_payload(settings)
    payload["exp"] = int(time.time()) - 10
    with pytest.raises(Exception) as exc_info:
        _run(security.verify_jwt(_token(payload)))
    assert exc_info.value.status_code == 401


def test_verify_jwt_rejects_tampered_token(hs256_mode):
    payload = _valid_payload(hs256_mode)
    token = _token(payload, secret="wrong-secret")
    with pytest.raises(Exception) as exc_info:
        _run(security.verify_jwt(token))
    assert exc_info.value.status_code == 401


def test_verify_jwt_rejects_missing_sub(hs256_mode):
    settings = hs256_mode
    payload = _valid_payload(settings)
    del payload["sub"]
    with pytest.raises(Exception) as exc_info:
        _run(security.verify_jwt(_token(payload)))
    assert exc_info.value.status_code == 401
