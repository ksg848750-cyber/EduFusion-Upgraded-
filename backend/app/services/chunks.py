from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection
from app.rag.embeddings import to_vector_string


async def insert_chunk(
    material_id: str,
    subject_id: str,
    chunk_index: int,
    text: str,
    page_number: int | None,
    section_title: str | None,
    metadata: dict | None,
    embedding: list[float],
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        vector = to_vector_string(embedding)
        row = await conn.execute(
            """
            INSERT INTO public.document_chunks
              (material_id, subject_id, chunk_index, text, page_number, section_title, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS vector))
            RETURNING id, chunk_index, page_number, section_title
            """,
            (
                material_id,
                subject_id,
                chunk_index,
                text,
                page_number,
                section_title,
                Jsonb(metadata or {}),
                vector,
            ),
        )
        record = await row.fetchone()
        return {
            "id": str(record[0]),
            "chunkIndex": record[1],
            "pageNumber": record[2],
            "sectionTitle": record[3],
        } if record else None


async def delete_chunks_for_material(material_id: str, subject_id: str) -> int:
    """Remove existing chunks so a re-ingest does not duplicate embeddings."""
    async with connection() as conn:
        if conn is None:
            return 0
        result = await conn.execute(
            "DELETE FROM public.document_chunks WHERE material_id = %s AND subject_id = %s",
            (material_id, subject_id),
        )
        return result.rowcount or 0


async def query_chunks(
    owner_id: str,
    subject_id: str,
    query_vector: list[float],
    top_k: int = 6,
) -> list[dict[str, Any]]:
    """Nearest-neighbor retrieval over document_chunks, scoped to subject owner.

    Returns the most relevant source chunks for grounded lesson generation.
    """
    vector = to_vector_string(query_vector)
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT c.id, c.chunk_index, c.text, c.page_number, c.section_title,
                   1 - (c.embedding <=> CAST(%s AS vector)) AS score
            FROM public.document_chunks c
            JOIN public.subjects s ON s.id = c.subject_id AND s.owner_id = %s
            WHERE c.subject_id = %s AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(%s AS vector)
            LIMIT %s
            """,
            (vector, owner_id, subject_id, vector, top_k),
        )
        return [
            {
                "id": str(r[0]),
                "chunkIndex": r[1],
                "text": r[2],
                "pageNumber": r[3],
                "sectionTitle": r[4],
                "score": float(r[5]),
            }
            for r in await rows.fetchall()
        ]