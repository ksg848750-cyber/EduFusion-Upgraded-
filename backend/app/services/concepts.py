from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection
from app.services.graph import PlannedConcept


async def insert_concept(subject_id: str, concept: PlannedConcept) -> str | None:
    async with connection() as conn:
        if conn is None:
            return None
        source_refs = [
            {"chunkIndex": ci} for ci in concept.source_chunks
        ]
        row = await conn.execute(
            """
            INSERT INTO public.concepts
              (subject_id, name, canonical_name, description, difficulty,
               expected_understanding, common_misconceptions, source_references)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (subject_id, canonical_name) DO UPDATE
              SET name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  difficulty = EXCLUDED.difficulty,
                  expected_understanding = EXCLUDED.expected_understanding,
                  common_misconceptions = EXCLUDED.common_misconceptions,
                  source_references = EXCLUDED.source_references
            RETURNING id
            """,
            (
                subject_id,
                concept.name,
                concept.canonical_name,
                concept.description,
                concept.difficulty,
                concept.expected_understanding,
                Jsonb(concept.common_misconceptions),
                Jsonb(source_refs),
            ),
        )
        record = await row.fetchone()
        return str(record[0]) if record else None


async def list_concepts(subject_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT id, name, canonical_name, description, difficulty,
                   expected_understanding, common_misconceptions
            FROM public.concepts
            WHERE subject_id = %s
            ORDER BY name
            """,
            (subject_id,),
        )
        return [
            {
                "id": str(r[0]),
                "name": r[1],
                "canonicalName": r[2],
                "description": r[3],
                "difficulty": r[4],
                "expectedUnderstanding": r[5],
                "commonMisconceptions": r[6],
            }
            for r in await rows.fetchall()
        ]


async def set_subject_concept_count(subject_id: str, count: int) -> None:
    async with connection() as conn:
        if conn is None:
            return
        await conn.execute(
            "UPDATE public.subjects SET concept_count = %s WHERE id = %s",
            (count, subject_id),
        )