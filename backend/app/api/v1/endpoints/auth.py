from fastapi import APIRouter, Depends
from app.core.middleware import get_current_user
from app.schemas.user import UserProfileResponse

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Returns authenticated user's profile from MongoDB Atlas.
    Requires Bearer JWT token in Authorization header.
    """
    return current_user
