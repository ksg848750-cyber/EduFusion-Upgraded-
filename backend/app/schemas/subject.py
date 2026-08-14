from datetime import datetime

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class SubjectResponse(BaseModel):
    id: str
    ownerId: str
    name: str
    description: str
    status: str
    conceptCount: int
    createdAt: datetime
    updatedAt: datetime
