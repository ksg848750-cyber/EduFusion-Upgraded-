from datetime import datetime

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: str
    authUserId: str
    email: str
    name: str
    isOnboarded: bool
    createdAt: datetime
    updatedAt: datetime
