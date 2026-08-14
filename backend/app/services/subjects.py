from datetime import datetime, timezone
from typing import Any

from app.core.database import connection


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _subject_row(record) -> dict[str, Any]:
    return {
        "id": str(record[0]),
        "ownerId": str(record[1]),
        "name": record[2],
        "description": record[3],
        "status": record[4],
        "conceptCount": record[5],
        "createdAt": _iso(record[6]),
        "updatedAt": _iso(record[7]),
    }


async def create_subject(owner_id: str, name: str, description: str = "") -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        row = await conn.execute(
            """
            INSERT INTO public.subjects (owner_id, name, description, status, created_at, updated_at)
            VALUES (%s, %s, %s, 'ACTIVE', %s, %s)
            RETURNING id, owner_id, name, description, status, concept_count, created_at, updated_at
            """,
            (owner_id, name, description, now, now),
        )
        record = await row.fetchone()
        return _subject_row(record) if record else None


async def get_subject(owner_id: str, subject_id: str) -> dict[str, Any] | None:
    """Fetch a subject, scoped to the owner (prevents cross-user access)."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, owner_id, name, description, status, concept_count, created_at, updated_at
            FROM public.subjects
            WHERE id = %s AND owner_id = %s
            """,
            (subject_id, owner_id),
        )
        record = await row.fetchone()
        return _subject_row(record) if record else None


async def list_subjects(owner_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, owner_id, name, description, status, concept_count, created_at, updated_at
            FROM public.subjects
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (owner_id,),
        )
        return [_subject_row(r) for r in await rows.fetchall()]