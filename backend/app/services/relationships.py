from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection


async def insert_relationship(
    subject_id: str,
    from_concept_id: str,
    to_concept_id: str,
    relationship_type: str,
    confidence: float,
    source_references: list[dict] | None = None,
    metadata: dict | None = None,
) -> str | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.concept_relationships
              (subject_id, from_concept_id, to_concept_id, relationship_type,
               confidence, source_references, extraction_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (subject_id, from_concept_id, to_concept_id, relationship_type)
              DO UPDATE SET confidence = EXCLUDED.confidence,
                            source_references = EXCLUDED.source_references,
                            extraction_metadata = EXCLUDED.extraction_metadata
            RETURNING id
            """,
            (
                subject_id,
                from_concept_id,
                to_concept_id,
                relationship_type,
                confidence,
                Jsonb(source_references or []),
                Jsonb(metadata or {}),
            ),
        )
        record = await row.fetchone()
        return str(record[0]) if record else None


async def list_relationships(subject_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT cr.id, cr.from_concept_id, cr.to_concept_id, cr.relationship_type,
                   cr.confidence, cr.extraction_metadata, cr.source_references,
                   fc.canonical_name, tc.canonical_name
            FROM public.concept_relationships cr
            JOIN public.concepts fc ON fc.id = cr.from_concept_id
            JOIN public.concepts tc ON tc.id = cr.to_concept_id
            WHERE cr.subject_id = %s
            """,
            (subject_id,),
        )
        return [
            {
                "id": str(r[0]),
                "fromConceptId": str(r[1]),
                "toConceptId": str(r[2]),
                "relationshipType": r[3],
                "confidence": float(r[4]),
                "reason": (r[5] or {}).get("reason", ""),
                "sourceReferences": [int(s.get("chunkIndex", 0)) for s in (r[6] or [])],
                "fromName": r[7],
                "toName": r[8],
            }
            for r in await rows.fetchall()
        ]