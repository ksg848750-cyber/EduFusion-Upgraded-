from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import connection
from app.core.security import get_current_user
from app.services import users as users_service

router = APIRouter(tags=["history"])


class LearningEvent(BaseModel):
    id: str
    eventType: str
    entityType: str
    entityId: str | None = None
    metadata: dict
    timestamp: str


class LearningHistory(BaseModel):
    subjectId: str
    events: list[LearningEvent]


@router.get("/subjects/{subject_id}/history", response_model=LearningHistory)
async def get_learning_history(
    subject_id: str,
    claims: dict = Depends(get_current_user),
):
    auth_user_id = claims.get("sub")
    owner_id = await users_service.get_user_id_by_auth(auth_user_id) if auth_user_id else None
    if not owner_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    async with connection() as conn:
        if conn is None:
            raise HTTPException(status_code=500, detail="Database unavailable")
        rows = await conn.execute(
            """
            select id, event_type, entity_type, entity_id, metadata, timestamp
            from public.learning_events
            where subject_id = %s
              and learner_id = %s
            order by timestamp desc
            limit 100
            """,
            [subject_id, owner_id],
        )
        records = await rows.fetchall()

    events = [
        LearningEvent(
            id=str(r[0]),
            eventType=r[1],
            entityType=r[2],
            entityId=str(r[3]) if r[3] else None,
            metadata=r[4] if isinstance(r[4], dict) else {},
            timestamp=r[5].isoformat() if r[5] else "",
        )
        for r in records
    ]
    return LearningHistory(subjectId=subject_id, events=events)
