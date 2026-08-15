from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


async def insert_question(
    subject_id: str,
    concept_id: str,
    question_type: str,
    difficulty: int,
    question_text: str,
    expected_answer: str,
    expected_reasoning: str,
    diagnostic_targets: list[str],
    source_references: list[dict],
    generation_metadata: dict | None = None,
    options: list[dict] | None = None,
    correct_option_id: str = "",
) -> str | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.questions
              (subject_id, concept_id, question_type, difficulty, question_text,
               expected_answer, expected_reasoning, diagnostic_targets, source_references,
               generation_metadata, options, correct_option_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                subject_id,
                concept_id,
                question_type,
                difficulty,
                question_text,
                expected_answer,
                expected_reasoning,
                Jsonb(diagnostic_targets),
                Jsonb(source_references),
                Jsonb(generation_metadata or {}),
                Jsonb(options or []),
                correct_option_id,
            ),
        )
        record = await row.fetchone()
        return str(record[0]) if record else None


async def get_question(question_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, subject_id, concept_id, question_type, difficulty, question_text,
                   expected_answer, expected_reasoning, diagnostic_targets, source_references,
                   generation_metadata, options, correct_option_id, created_at
            FROM public.questions
            WHERE id = %s
            """,
            (question_id,),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "subjectId": str(record[1]),
            "conceptId": str(record[2]),
            "questionType": record[3],
            "difficulty": record[4],
            "questionText": record[5],
            "expectedAnswer": record[6],
            "expectedReasoning": record[7],
            "diagnosticTargets": record[8] or [],
            "sourceReferences": record[9] or [],
            "generationMetadata": record[10] or {},
            "options": record[11] or [],
            "correctOptionId": record[12] or "",
            "createdAt": record[13].isoformat(),
        }


async def list_questions_for_session(subject_id: str, concept_id: str, question_ids: list[str]) -> list[dict[str, Any]]:
    if not question_ids:
        return []
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, subject_id, concept_id, question_type, difficulty, question_text,
                   expected_answer, expected_reasoning, diagnostic_targets, source_references,
                   generation_metadata, options, correct_option_id, created_at
            FROM public.questions
            WHERE subject_id = %s AND concept_id = %s AND id = ANY(%s)
            """,
            (subject_id, concept_id, question_ids),
        )
        return [
            {
                "id": str(r[0]),
                "subjectId": str(r[1]),
                "conceptId": str(r[2]),
                "questionType": r[3],
                "difficulty": r[4],
                "questionText": r[5],
                "expectedAnswer": r[6],
                "expectedReasoning": r[7],
                "diagnosticTargets": r[8] or [],
                "sourceReferences": r[9] or [],
                "generationMetadata": r[10] or {},
                "options": r[11] or [],
                "correctOptionId": r[12] or "",
                "createdAt": r[13].isoformat(),
            }
            for r in await rows.fetchall()
        ]