from pydantic import BaseModel, Field
from typing import Optional


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, example="Computer Architecture")
    description: Optional[str] = Field(None, max_length=500)


class SubjectResponse(BaseModel):
    id: str = Field(..., alias="_id")
    ownerId: str
    name: str
    description: Optional[str] = None
    status: str = "ACTIVE"
    conceptCount: int = 0
    createdAt: str
    updatedAt: str

    class Config:
        populate_by_name = True
