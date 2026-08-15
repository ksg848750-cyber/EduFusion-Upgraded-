from datetime import datetime, timezone
from typing import Any

from app.core.database import connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_session(learner_id: str, subject_id: str, concept_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.diagnostic_sessions (learner_id, subject_id, concept_id, status)
            VALUES (%s, %s, %s, 'CREATED')
            RETURNING id, learner_id, subject_id, concept_id, status, started_at, completed_at, created_at, updated_at
            """,
            (learner_id, subject_id, concept_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "learnerId": str(record[1]),
            "subjectId": str(record[2]),
            "conceptId": str(record[3]),
            "status": record[4],
            "startedAt": record[5].isoformat(),
            "completedAt": record[6].isoformat() if record[6] else None,
            "createdAt": record[7].isoformat(),
            "updatedAt": record[8].isoformat(),
        }


async def get_session(learner_id: str, session_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, learner_id, subject_id, concept_id, status, started_at, completed_at, created_at, updated_at
            FROM public.diagnostic_sessions
            WHERE id = %s AND learner_id = %s
            """,
            (session_id, learner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "learnerId": str(record[1]),
            "subjectId": str(record[2]),
            "conceptId": str(record[3]),
            "status": record[4],
            "startedAt": record[5].isoformat(),
            "completedAt": record[6].isoformat() if record[6] else None,
            "createdAt": record[7].isoformat(),
            "updatedAt": record[8].isoformat(),
        }


async def count_answered_in_session(learner_id: str, session_id: str, concept_id: str) -> int:
    """Prior answers for this concept within this session (independence factor)."""
    async with connection() as conn:
        if conn is None:
            return 0
        row = await conn.execute(
            """
            SELECT COUNT(*) FROM public.answers a
            JOIN public.questions q ON q.id = a.question_id
            WHERE a.diagnostic_session_id = %s AND a.learner_id = %s AND q.concept_id = %s
            """,
            (session_id, learner_id, concept_id),
        )
        record = await row.fetchone()
        return int(record[0]) if record else 0


async def complete_session(learner_id: str, session_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        now = _now_iso()
        row = await conn.execute(
            """
            UPDATE public.diagnostic_sessions
            SET status = 'COMPLETED', completed_at = %s, updated_at = %s
            WHERE id = %s AND learner_id = %s
            RETURNING id, status, completed_at
            """,
            (now, now, session_id, learner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {"id": str(record[0]), "status": record[1], "completedAt": record[2].isoformat()}