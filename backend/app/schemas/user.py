from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class UserPreferences(BaseModel):
    language: str = "en"
    educationLevel: str = "undergraduate"
    studyClass: Optional[str] = "btech-3"


class UserProfileResponse(BaseModel):
    id: str = Field(..., alias="_id")
    authUserId: str
    email: EmailStr
    name: str
    interests: List[str] = []
    preferences: UserPreferences
    isOnboarded: bool = False
    createdAt: datetime
    updatedAt: datetime

    class Config:
        populate_by_name = True
