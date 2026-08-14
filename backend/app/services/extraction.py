from app.ai.schemas.extraction import KnowledgeExtraction
from app.ai.service import AIService


async def extract_knowledge_from_chunks(
    chunks: list[dict],
    ai: AIService | None = None,
) -> KnowledgeExtraction:
    """Run validated concept/relationship extraction over document chunks."""
    service = ai or AIService()
    return await service.extract_knowledge(chunks)