import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)

# Supabase access tokens carry this fixed audience claim.
SUPABASE_AUDIENCE = "authenticated"

_JWKS_CACHE: dict[str, Any] | None = None
_JWKS_FETCHED_AT: float = 0.0
_JWKS_TTL_SECONDS = 3600


def _jwk_to_key(jwk: dict[str, Any]):
    """Convert a JWK dict from the Supabase JWKS into a PyJWT key object."""
    kty = jwk.get("kty")
    if kty == "EC":
        return ECAlgorithm.from_jwk(jwk)
    if kty == "RSA":
        return RSAAlgorithm.from_jwk(jwk)
    raise ValueError(f"Unsupported JWK key type: {kty}")


async def _get_signing_key(kid: str | None) -> dict[str, Any] | None:
    """Fetch and cache Supabase JWKS so we can resolve the token's signing key."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    settings = get_settings()
    now = time.time()
    if _JWKS_CACHE is None or now - _JWKS_FETCHED_AT > _JWKS_TTL_SECONDS:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(settings.jwks_url)
            resp.raise_for_status()
            _JWKS_CACHE = resp.json()
            _JWKS_FETCHED_AT = now
    for key in (_JWKS_CACHE or {}).get("keys", []):
        if kid is None or key.get("kid") == kid:
            return key
    return None


async def verify_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT and return its claims.

    Primary path: Supabase JWKS public keys (kid-resolved RS256).
    Fallback: SUPABASE_JWT_SECRET HS256 (used when JWKS is unavailable).
    Raises HTTPException(401) when the token is invalid/expired.
    """
    settings = get_settings()
    unverified = jwt.decode(token, options={"verify_signature": False})
    kid = unverified.get("kid")
    alg = jwt.get_unverified_header(token).get("alg", "RS256")
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"

    if not settings.supabase_url:
        raise HTTPException(status_code=401, detail="Auth is not configured")

    try:
        signing_key = await _get_signing_key(kid)
        if signing_key:
            try:
                key = _jwk_to_key(signing_key)
                return jwt.decode(
                    token,
                    key,
                    algorithms=[alg],
                    audience=SUPABASE_AUDIENCE,
                    issuer=issuer,
                    options={"require": ["exp", "sub"]},
                )
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="Invalid token")

        if settings.supabase_jwt_secret:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=SUPABASE_AUDIENCE,
                issuer=issuer,
                options={"require": ["exp", "sub"]},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Token audience is invalid")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Token issuer is invalid")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    raise HTTPException(status_code=401, detail="Could not verify token signature")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency resolving the authenticated Supabase user from a Bearer JWT."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await verify_jwt(credentials.credentials)
