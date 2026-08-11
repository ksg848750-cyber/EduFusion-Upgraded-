from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database
from app.core.middleware import get_current_user
from app.schemas.subject import SubjectCreate, SubjectResponse

router = APIRouter()


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_in: SubjectCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new Subject for the authenticated user in MongoDB Atlas.
    Enforces ownership: ownerId = current_user['_id'].
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    new_subject = {
        "ownerId": current_user["_id"],
        "name": subject_in.name,
        "description": subject_in.description,
        "status": "ACTIVE",
        "conceptCount": 0,
        "createdAt": now_iso,
        "updatedAt": now_iso
    }
    
    result = await db["subjects"].insert_one(new_subject)
    new_subject["_id"] = str(result.inserted_id)
    return new_subject


@router.get("", response_model=List[SubjectResponse])
async def list_subjects(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Lists all subjects owned by the authenticated user.
    """
    cursor = db["subjects"].find({"ownerId": current_user["_id"]})
    subjects = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        subjects.append(doc)
    return subjects
