from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import get_pool
from app.core.security import get_current_user

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(claims: dict = Depends(get_current_user)):
    """Protected health endpoint: returns app status plus DB connectivity."""
    settings = get_settings()
    pool = get_pool()
    db_ok = pool is not None and not pool.closed
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "user": claims.get("sub"),
        "database": "connected" if db_ok else "unconfigured",
    }
