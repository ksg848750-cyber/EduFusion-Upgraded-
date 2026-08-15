import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.context_builder import build_extraction_context
from app.ai.prompts.extraction import SYSTEM_PROMPT, build_extraction_user_prompt
from app.ai.prompts.learner import (
    EVALUATE_SYSTEM_PROMPT,
    EXPLAIN_SYSTEM_PROMPT,
    TEST_SYSTEM_PROMPT,
    build_evaluate_user_prompt,
    build_explain_user_prompt,
    build_test_user_prompt,
)
from app.ai.providers.base import BaseLLMProvider
from app.ai.schemas.extraction import KnowledgeExtraction
from app.ai.schemas.learner import AnswerEvaluation, ConceptExplanation, QuestionSet
from app.core.config import get_settings

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_T = TypeVar("_T", bound=BaseModel)


def _clean_json(text: str) -> str:
    return _FENCE.sub("", text).strip()


def _render_chunks(chunks: list[dict[str, Any]]) -> str:
    """Render source chunks as an indexed block for prompt grounding."""
    if not chunks:
        return "(no source chunks available)"
    parts = []
    for c in chunks:
        label = c.get("sectionTitle") or c.get("section") or "untitled"
        page = c.get("pageNumber")
        page_str = f" (page {page})" if page is not None else ""
        parts.append(
            f"[{c['chunkIndex']}] SECTION: {label}{page_str}\n{(c.get('text') or '')[:1500]}"
        )
    return "\n\n".join(parts)


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

    async def _complete_validated(
        self,
        system: str,
        user: str,
        schema: type[_T],
        *,
        temperature: float = 0.0,
        attempts: int = 2,
    ) -> _T:
        """Run a completion, parse JSON, and validate against a Pydantic schema.

        Retries on invalid JSON/schema failures so transient formatting issues
        never bubble up to the user as raw errors.
        """
        provider = self._get_provider()
        last_error: Exception | None = None
        for _attempt in range(attempts):
            try:
                raw = await provider.complete(system, user, temperature=temperature)
                parsed = json.loads(_clean_json(raw))
                return schema.model_validate(parsed)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(f"LLM call failed after retries: {last_error}") from last_error

    async def explain_concept(
        self,
        concept: dict[str, Any],
        graph_position: str,
        learner_evidence: str,
        chunks: list[dict[str, Any]],
    ) -> ConceptExplanation:
        user = build_explain_user_prompt(
            concept_name=concept.get("name", ""),
            description=concept.get("description", ""),
            expected_understanding=concept.get("expectedUnderstanding", ""),
            graph_position=graph_position,
            learner_evidence=learner_evidence,
            source_chunks=_render_chunks(chunks),
        )
        return await self._complete_validated(
            EXPLAIN_SYSTEM_PROMPT, user, ConceptExplanation, temperature=0.2
        )

    async def generate_questions(
        self,
        concept: dict[str, Any],
        graph_position: str,
        chunks: list[dict[str, Any]],
    ) -> QuestionSet:
        user = build_test_user_prompt(
            concept_name=concept.get("name", ""),
            description=concept.get("description", ""),
            expected_understanding=concept.get("expectedUnderstanding", ""),
            common_misconceptions=_list_text(concept.get("commonMisconceptions") or []),
            graph_position=graph_position,
            source_chunks=_render_chunks(chunks),
        )
        return await self._complete_validated(
            TEST_SYSTEM_PROMPT, user, QuestionSet, temperature=0.3
        )

    async def evaluate_answer(
        self,
        concept: dict[str, Any],
        question: dict[str, Any],
        chunks: list[dict[str, Any]],
        student_response: str,
        student_reasoning: str,
        options: list[dict] | None = None,
        selected_option_id: str = "",
        selected_option_text: str = "",
    ) -> AnswerEvaluation:
        user = build_evaluate_user_prompt(
            concept_name=concept.get("name", ""),
            expected_understanding=concept.get("expectedUnderstanding", ""),
            common_misconceptions=_list_text(concept.get("commonMisconceptions") or []),
            question_text=question.get("questionText", ""),
            question_type=question.get("questionType", ""),
            diagnostic_targets=", ".join(question.get("diagnosticTargets") or []),
            expected_answer=question.get("expectedAnswer", ""),
            expected_reasoning=question.get("expectedReasoning", ""),
            source_chunks=_render_chunks(chunks),
            student_response=student_response,
            student_reasoning=student_reasoning,
            options=options,
            selected_option_id=selected_option_id,
            selected_option_text=selected_option_text,
        )
        return await self._complete_validated(
            EVALUATE_SYSTEM_PROMPT, user, AnswerEvaluation, temperature=0.1
        )


def _list_text(values: list[str]) -> str:
    return "; ".join(values) if values else "(none listed)"