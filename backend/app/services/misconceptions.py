from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_misconception(
    learner_id: str,
    subject_id: str,
    concept_id: str,
    category: str,
    statement: str,
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, learner_id, subject_id, concept_id, category, statement,
                   confidence, evidence_references, status, first_detected_at,
                   last_confirmed_at, resolved_at, created_at, updated_at
            FROM public.misconceptions
            WHERE learner_id = %s AND subject_id = %s AND concept_id = %s
              AND category = %s AND statement = %s
            """,
            (learner_id, subject_id, concept_id, category, statement),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return _row(record)


async def upsert_misconception(
    learner_id: str,
    subject_id: str,
    concept_id: str,
    category: str,
    statement: str,
    confidence: float,
    evidence: list[dict],
) -> dict[str, Any] | None:
    """Create or promote a misconception.

    Lifecycle: first signal -> SUSPECTED; same (concept, category, statement)
    signal again -> CONFIRMED. Evidence references accumulate.
    """
    now = _now_iso()
    existing = await get_misconception(learner_id, subject_id, concept_id, category, statement)
    if existing is None:
        async with connection() as conn:
            if conn is None:
                return None
            row = await conn.execute(
                """
                INSERT INTO public.misconceptions
                  (learner_id, subject_id, concept_id, category, statement, confidence,
                   evidence_references, status, first_detected_at, last_confirmed_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'SUSPECTED', %s, %s, %s)
                RETURNING id, learner_id, subject_id, concept_id, category, statement,
                          confidence, evidence_references, status, first_detected_at,
                          last_confirmed_at, resolved_at, created_at, updated_at
                """,
                (
                    learner_id, subject_id, concept_id, category, statement, confidence,
                    Jsonb(evidence), now, now, now,
                ),
            )
            record = await row.fetchone()
            return _row(record) if record else None

    # Promote SUSPECTED -> CONFIRMED on repeated evidence.
    status = "CONFIRMED" if existing["status"] == "SUSPECTED" else existing["status"]
    refs = list(existing.get("evidenceReferences") or [])
    for ref in evidence:
        if ref not in refs:
            refs.append(ref)
    confidence = max(float(existing.get("confidence") or 0.0), float(confidence))
    last_confirmed = now if status == "CONFIRMED" else existing.get("lastConfirmedAt")
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            UPDATE public.misconceptions
            SET confidence = %s, evidence_references = %s, status = %s,
                last_confirmed_at = %s, updated_at = %s
            WHERE id = %s
            RETURNING id, learner_id, subject_id, concept_id, category, statement,
                      confidence, evidence_references, status, first_detected_at,
                      last_confirmed_at, resolved_at, created_at, updated_at
            """,
            (confidence, Jsonb(refs), status, last_confirmed, now, existing["id"]),
        )
        record = await row.fetchone()
        return _row(record) if record else None


def _row(r) -> dict[str, Any]:
    return {
        "id": str(r[0]),
        "learnerId": str(r[1]),
        "subjectId": str(r[2]),
        "conceptId": str(r[3]),
        "category": r[4],
        "statement": r[5],
        "confidence": float(r[6] or 0.0),
        "evidenceReferences": r[7] or [],
        "status": r[8],
        "firstDetectedAt": r[9].isoformat(),
        "lastConfirmedAt": r[10].isoformat() if r[10] else None,
        "resolvedAt": r[11].isoformat() if r[11] else None,
        "createdAt": r[12].isoformat(),
        "updatedAt": r[13].isoformat(),
    }


async def list_misconceptions_for_concept(
    learner_id: str,
    subject_id: str,
    concept_id: str,
) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, learner_id, subject_id, concept_id, category, statement,
                   confidence, evidence_references, status, first_detected_at,
                   last_confirmed_at, resolved_at, created_at, updated_at
            FROM public.misconceptions
            WHERE learner_id = %s AND subject_id = %s AND concept_id = %s
              AND status IN ('SUSPECTED','CONFIRMED','ACTIVE')
            ORDER BY created_at
            """,
            (learner_id, subject_id, concept_id),
        )
        return [_row(r) for r in await rows.fetchall()]