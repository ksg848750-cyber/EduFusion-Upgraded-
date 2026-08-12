from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.core.config import settings
from app.core import security


def create_rs256_token(private_key):
    return jwt.encode(
        {
            "sub": "auth_user_001",
            "email": "student@example.com",
            "name": "Student",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def test_verify_jwt_token_accepts_expected_rs256_jwks_token(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        security,
        "jwk_client",
        SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())),
    )

    payload = security.verify_jwt_token(create_rs256_token(private_key))

    assert payload["sub"] == "auth_user_001"


def test_verify_jwt_token_rejects_hs256_token(monkeypatch):
    monkeypatch.setattr(
        security,
        "jwk_client",
        SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="shared-secret")),
    )
    token = jwt.encode(
        {"sub": "auth_user_001", "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE},
        "shared-secret",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as error:
        security.verify_jwt_token(token)

    assert error.value.status_code == 401
