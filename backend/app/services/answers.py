from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


async def insert_answer(
    question_id: str,
    learner_id: str,
    diagnostic_session_id: str,
    response: str,
    reasoning: str,
    correctness: bool,
    reasoning_assessment: dict | None,
    evidence_signals: list[str],
    selected_option_id: str | None = None,
) -> str | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.answers
              (question_id, learner_id, diagnostic_session_id, response, reasoning,
               correctness, reasoning_assessment, evidence_signals, selected_option_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                question_id,
                learner_id,
                diagnostic_session_id,
                response,
                reasoning,
                correctness,
                Jsonb(reasoning_assessment or {}),
                Jsonb(evidence_signals),
                selected_option_id,
            ),
        )
        record = await row.fetchone()
        return str(record[0]) if record else None


async def has_answer(learner_id: str, question_id: str) -> bool:
    async with connection() as conn:
        if conn is None:
            return False
        row = await conn.execute(
            "SELECT 1 FROM public.answers WHERE learner_id = %s AND question_id = %s LIMIT 1",
            (learner_id, question_id),
        )
        return await row.fetchone() is not None


async def list_answers_for_session(learner_id: str, session_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, question_id, response, reasoning, correctness, reasoning_assessment,
                   evidence_signals, selected_option_id, created_at
            FROM public.answers
            WHERE learner_id = %s AND diagnostic_session_id = %s
            ORDER BY created_at
            """,
            (learner_id, session_id),
        )
        return [
            {
                "id": str(r[0]),
                "questionId": str(r[1]),
                "response": r[2],
                "reasoning": r[3],
                "correctness": r[4],
                "reasoningAssessment": r[5] or {},
                "evidenceSignals": r[6] or [],
                "selectedOptionId": r[7],
                "createdAt": r[8].isoformat(),
            }
            for r in await rows.fetchall()
        ]