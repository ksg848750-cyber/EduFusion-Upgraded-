from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.user import UserProfile
from app.services.users import get_user_by_auth_id, upsert_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserProfile)
async def get_me(claims: dict = Depends(get_current_user)):
    """Return (and lazily persist) the authenticated user's app profile."""
    auth_user_id = claims.get("sub")
    email = claims.get("email", "")
    name = claims.get("user_metadata", {}).get("full_name") or claims.get("user_metadata", {}).get("name")

    profile = await get_user_by_auth_id(auth_user_id)
    if profile is None:
        profile = await upsert_user(auth_user_id, email, name)

    if profile is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="User store unavailable")

    return profile
