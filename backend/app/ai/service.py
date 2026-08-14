import json
import re

from app.ai.context_builder import build_extraction_context
from app.ai.prompts.extraction import SYSTEM_PROMPT, build_extraction_user_prompt
from app.ai.providers.base import BaseLLMProvider
from app.ai.schemas.extraction import KnowledgeExtraction
from app.core.config import get_settings

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _clean_json(text: str) -> str:
    return _FENCE.sub("", text).strip()


class AIService:
    """Centralized LLM service.

    All LLM output is validated through Pydantic before it can be persisted.
    """

    def __init__(self, provider: BaseLLMProvider | None = None):
        self._provider = provider

    def _get_provider(self) -> BaseLLMProvider:
        if self._provider is None:
            from app.ai.providers.groq_adapter import GroqAdapter

            s = get_settings()
            self._provider = GroqAdapter(
                api_key=s.groq_api_key, model=s.groq_extraction_model
            )
        return self._provider

    async def extract_knowledge(self, chunks: list[dict]) -> KnowledgeExtraction:
        """Extract and validate a KnowledgeExtraction from document chunks."""
        context = build_extraction_context(chunks)
        user_prompt = build_extraction_user_prompt(context)
        provider = self._get_provider()

        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                raw = await provider.complete(SYSTEM_PROMPT, user_prompt, temperature=0.0)
                parsed = json.loads(_clean_json(raw))
                extraction = KnowledgeExtraction.model_validate(parsed)
                if not extraction.concepts:
                    raise ValueError("Extraction returned no concepts")
                return extraction
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(f"LLM extraction failed after retries: {last_error}") from last_error