import logging
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("edufusion.security")

jwk_client = PyJWKClient(settings.JWKS_URL) if settings.JWKS_URL else None


def verify_jwt_token(token: str) -> dict:
    """
    Verifies a JWT token issued by Better Auth / Auth system.
    Supports JWKS endpoint verification (RS256) or fallback secret verification (HS256).
    Returns the decoded token payload if valid, or raises HTTPException 401.
    """
    try:
        if settings.JWKS_URL and jwk_client:
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256", settings.JWT_ALGORITHM],
                options={"verify_aud": False}
            )
        else:
            payload = jwt.decode(
                token,
                settings.BETTER_AUTH_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False}
            )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token signature has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Authentication token has expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTH_FAILED", "message": "Authentication verification failed."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
