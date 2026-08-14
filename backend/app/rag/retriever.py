from typing import Any

from app.rag.embeddings import embed_single
from app.services.chunks import query_chunks


async def retrieve(
    owner_id: str,
    subject_id: str,
    query: str,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    """Embed a query and return the nearest source chunks for the subject."""
    query_vector = await embed_single(query)
    return await query_chunks(owner_id, subject_id, query_vector, top_k=top_k)