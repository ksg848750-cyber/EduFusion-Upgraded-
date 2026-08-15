from typing import Any

from app.core.database import connection
from app.rag.embeddings import embed_single


async def get_chunks_by_indices(subject_id: str, chunk_indices: list[int], top: int = 8) -> list[dict[str, Any]]:
    """Fetch exact source chunks referenced by a concept (deterministic grounding)."""
    if not chunk_indices:
        return []
    async with connection() as conn:
        if conn is None:
            return []
        rows = await conn.execute(
            """
            SELECT c.chunk_index, c.text, c.page_number, c.section_title
            FROM public.document_chunks c
            WHERE c.subject_id = %s AND c.chunk_index = ANY(%s)
            ORDER BY c.chunk_index
            LIMIT %s
            """,
            (subject_id, list(chunk_indices), top),
        )
        return [
            {
                "chunkIndex": r[0],
                "text": r[1],
                "pageNumber": r[2],
                "sectionTitle": r[3],
            }
            for r in await rows.fetchall()
        ]


async def get_concept_chunks(owner_id: str, subject_id: str, concept: dict[str, Any], top: int = 8) -> list[dict[str, Any]]:
    """Grounding chunks for a concept: exact sourceReferences first, then RAG
    vector retrieval on the concept name when exact evidence is thin."""
    exact = await get_chunks_by_indices(subject_id, concept.get("sourceReferences") or [], top=top)
    if len(exact) >= 3:
        return exact[:top]
    query = concept.get("name") or concept.get("canonicalName") or ""
    if not query:
        return exact
    try:
        vector = await embed_single(query)
    except Exception:  # noqa: BLE001 - embedding must never break the flow
        return exact
    async with connection() as conn:
        if conn is None:
            return exact
        rows = await conn.execute(
            """
            SELECT c.chunk_index, c.text, c.page_number, c.section_title,
                   1 - (c.embedding <=> CAST(%s AS vector)) AS score
            FROM public.document_chunks c
            JOIN public.subjects s ON s.id = c.subject_id AND s.owner_id = %s
            WHERE c.subject_id = %s AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(%s AS vector)
            LIMIT %s
            """,
            (
                _to_vector(vector),
                owner_id,
                subject_id,
                _to_vector(vector),
                max(top - len(exact), 1),
            ),
        )
        extra = [
            {
                "chunkIndex": r[0],
                "text": r[1],
                "pageNumber": r[2],
                "sectionTitle": r[3],
                "score": float(r[4]),
            }
            for r in await rows.fetchall()
        ]
    seen = {c["chunkIndex"] for c in exact}
    merged = list(exact)
    for c in extra:
        if c["chunkIndex"] not in seen:
            merged.append(c)
            seen.add(c["chunkIndex"])
    return merged[:top]


def _to_vector(vector: list[float]) -> str:
    inner = ",".join(f"{v:.6f}" for v in vector)
    return f"[{inner}]"


async def build_graph_position(subject_id: str, concept: dict[str, Any]) -> str:
    """Render the concept's position in the M2 knowledge graph as prompt context."""
    concept_id = concept["id"]
    async with connection() as conn:
        if conn is None:
            return "(graph unavailable)"
        rows = await conn.execute(
            """
            SELECT cr.relationship_type, fc.canonical_name, tc.canonical_name,
                   cr.from_concept_id, cr.to_concept_id
            FROM public.concept_relationships cr
            JOIN public.concepts fc ON fc.id = cr.from_concept_id
            JOIN public.concepts tc ON tc.id = cr.to_concept_id
            WHERE cr.subject_id = %s AND (cr.from_concept_id = %s OR cr.to_concept_id = %s)
            """,
            (subject_id, concept_id, concept_id),
        )
        relations = await rows.fetchall()

    if not relations:
        return "(no direct graph relations)"

    lines = []
    for rtype, from_name, to_name, from_id, to_id in relations:
        if from_id == concept_id:
            lines.append(f"- {concept['name']} --{rtype}--> {to_name}")
        else:
            lines.append(f"- {from_name} --{rtype}--> {concept['name']}")
    return "\n".join(lines) or "(no direct graph relations)"