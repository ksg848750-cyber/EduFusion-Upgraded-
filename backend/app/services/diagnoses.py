from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def insert_diagnosis(
    learner_id: str,
    subject_id: str,
    session_id: str,
    concept_id: str,
    root_cause: str,
    confidence: float,
    resolution: dict,
    investigation: dict,
    evidence_references: list[dict],
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.diagnoses
              (learner_id, subject_id, session_id, concept_id, root_cause, confidence,
               status, resolution, investigation, evidence_references)
            VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', %s, %s, %s)
            RETURNING id, learner_id, subject_id, session_id, concept_id, root_cause,
                      confidence, status, resolution, investigation, evidence_references,
                      created_at, updated_at
            """,
            (
                learner_id, subject_id, session_id, concept_id, root_cause, confidence,
                Jsonb(resolution or {}), Jsonb(investigation or {}), Jsonb(evidence_references or []),
            ),
        )
        record = await row.fetchone()
        return _row(record) if record else None


async def get_diagnosis_by_session(learner_id: str, session_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, learner_id, subject_id, session_id, concept_id, root_cause,
                   confidence, status, resolution, investigation, evidence_references,
                   created_at, updated_at
            FROM public.diagnoses
            WHERE learner_id = %s AND session_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (learner_id, session_id),
        )
        record = await row.fetchone()
        return _row(record) if record else None


async def get_diagnosis_by_id(learner_id: str, diagnosis_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, learner_id, subject_id, session_id, concept_id, root_cause,
                   confidence, status, resolution, investigation, evidence_references,
                   created_at, updated_at
            FROM public.diagnoses
            WHERE learner_id = %s AND id = %s
            """,
            (learner_id, diagnosis_id),
        )
        record = await row.fetchone()
        return _row(record) if record else None


async def get_diagnosis_by_id(learner_id: str, diagnosis_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, learner_id, subject_id, session_id, concept_id, root_cause,
                   confidence, status, resolution, investigation, evidence_references,
                   created_at, updated_at
            FROM public.diagnoses
            WHERE learner_id = %s AND id = %s
            """,
            (learner_id, diagnosis_id),
        )
        record = await row.fetchone()
        return _row(record) if record else None


async def list_diagnoses(learner_id: str, subject_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, learner_id, subject_id, session_id, concept_id, root_cause,
                   confidence, status, resolution, investigation, evidence_references,
                   created_at, updated_at
            FROM public.diagnoses
            WHERE learner_id = %s AND subject_id = %s
            ORDER BY created_at DESC
            """,
            (learner_id, subject_id),
        )
        return [_row(r) for r in await rows.fetchall()]


def _row(r) -> dict[str, Any]:
    return {
        "id": str(r[0]),
        "learnerId": str(r[1]),
        "subjectId": str(r[2]),
        "sessionId": str(r[3]),
        "conceptId": str(r[4]),
        "rootCause": r[5],
        "confidence": float(r[6] or 0.0),
        "status": r[7],
        "resolution": r[8] or {},
        "investigation": r[9] or {},
        "evidenceReferences": r[10] or [],
        "createdAt": r[11].isoformat(),
        "updatedAt": r[12].isoformat(),
    }