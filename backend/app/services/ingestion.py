import logging
from typing import Any

from app.ai.schemas.extraction import KnowledgeExtraction
from app.ai.service import AIService
from app.core.config import get_settings
from app.parsing.chunker import ExtractedChunk, chunk_document
from app.parsing.pdf import extract_pages
from app.rag.embeddings import embed_texts
from app.services import chunks as chunks_service
from app.services import concepts as concepts_service
from app.services import materials as materials_service
from app.services import relationships as relationships_service
from app.services.graph import GraphPlan, build_graph

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"


class IngestionError(Exception):
    pass


def _chunk_to_dict(chunk: ExtractedChunk) -> dict[str, Any]:
    return {
        "chunkIndex": chunk.chunk_index,
        "text": chunk.text,
        "pageNumber": chunk.page_number,
        "sectionTitle": chunk.section_title,
        "headingPath": chunk.heading_path,
        "ocrPages": chunk.ocr_page_numbers,
    }


async def process_material(
    owner_id: str,
    subject_id: str,
    material_id: str,
    content: bytes,
    ai: AIService | None = None,
) -> dict[str, Any]:
    """Run the full ingestion pipeline for an uploaded PDF synchronously.

    Steps: parse -> chunk -> embed+persist chunks -> LLM extract ->
    build+validate graph -> persist graph -> update subject counts.
    Material status transitions: PROCESSING -> COMPLETED (or FAILED on error).
    """
    await materials_service.update_material_status(owner_id, material_id, "PROCESSING")

    try:
        if not content.startswith(PDF_MAGIC):
            raise IngestionError("Only text-based PDF files are supported")

        pages = extract_pages(content, ocr_enabled=get_settings().ocr_enabled)
        extracted_chunks = chunk_document(pages)

        if not extracted_chunks:
            raise IngestionError("No readable text could be extracted from the PDF")

        chunk_dicts = [_chunk_to_dict(c) for c in extracted_chunks]

        # 1. Embed and persist chunks.
        embeddings = await embed_texts([c["text"] for c in chunk_dicts])
        if len(embeddings) != len(chunk_dicts):
            raise IngestionError("Embedding count mismatch")
        for chunk, embedding in zip(extracted_chunks, embeddings):
            await chunks_service.insert_chunk(
                material_id=material_id,
                subject_id=subject_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                metadata={"section": chunk.section_title, "headingPath": chunk.heading_path, "ocrPages": chunk.ocr_page_numbers},
                embedding=embedding,
            )

        # 2. LLM concept/relationship extraction + validation.
        service = ai or AIService()
        extraction: KnowledgeExtraction = await service.extract_knowledge(chunk_dicts)

        # 3. Deterministic graph build + validation.
        plan: GraphPlan = build_graph(extraction, chunks=chunk_dicts)
        concept_ids = await _persist_graph(subject_id, plan)

        # 4. Finalize subject + material state.
        await concepts_service.set_subject_concept_count(subject_id, len(concept_ids))
        page_count = len(pages)
        return await materials_service.update_material_status(
            owner_id,
            material_id,
            "COMPLETED",
            page_count=page_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ingestion failed for material %s", material_id)
        await materials_service.update_material_status(
            owner_id,
            material_id,
            "FAILED",
            processing_error=str(exc),
        )
        raise


async def _persist_graph(subject_id: str, plan: GraphPlan) -> list[str]:
    concept_ids: list[str] = []
    id_by_canonical: dict[str, str] = {}
    for concept in plan.concepts:
        cid = await concepts_service.insert_concept(subject_id, concept)
        if cid:
            concept_ids.append(cid)
            id_by_canonical[concept.canonical_name] = cid

    for edge in plan.edges:
        from_id = id_by_canonical.get(edge.from_canonical)
        to_id = id_by_canonical.get(edge.to_canonical)
        if from_id and to_id:
            source_refs = [
                {"chunkIndex": ci} for ci in edge.source_chunks
            ]
            await relationships_service.insert_relationship(
                subject_id,
                from_id,
                to_id,
                edge.relationship_type,
                edge.confidence,
                source_references=source_refs,
                metadata={"reason": edge.reason},
            )

    if plan.dropped_edges:
        logger.info("Dropped %d edges during graph validation", len(plan.dropped_edges))
    return concept_ids