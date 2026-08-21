import asyncio
import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.context_builder import build_extraction_context
from app.ai.prompts.extraction import SYSTEM_PROMPT, build_extraction_user_prompt
from app.ai.prompts.learner import (
    DIAGNOSTIC_SYSTEM_PROMPT,
    EVALUATE_SYSTEM_PROMPT,
    EXPLAIN_SYSTEM_PROMPT,
    PROBE_SYSTEM_PROMPT,
    TEST_SYSTEM_PROMPT,
    build_diagnostic_user_prompt,
    build_evaluate_user_prompt,
    build_explain_user_prompt,
    build_probe_user_prompt,
    build_test_user_prompt,
)
from app.ai.prompts.teaching import (
    CLARIFY_SYSTEM_PROMPT,
    LESSON_SYSTEM_PROMPT,
    build_clarify_user_prompt,
    build_lesson_user_prompt,
)
from app.ai.prompts.reassessment import (
    REASSESSMENT_SYSTEM_PROMPT,
    REASSESSMENT_USER_TEMPLATE,
)
from app.ai.providers.base import BaseLLMProvider
from app.ai.schemas.extraction import KnowledgeExtraction
from app.ai.schemas.learner import (
    AnswerEvaluation,
    ConceptExplanation,
    ProbeQuestion,
    QuestionSet,
)
from app.ai.schemas.teaching import Clarification, GeneratedLesson
from app.ai.schemas.reassessment import GeneratedReassessment
from app.ai.schemas.visualization import ConceptMapSpec, VisualizationSpec
from app.core.config import get_settings

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_T = TypeVar("_T", bound=BaseModel)


def _clean_json(text: str) -> str:
    return _FENCE.sub("", text).strip()


def _is_rate_limit(exc: Exception) -> bool:
    """Detect provider rate-limit errors (HTTP 429) across error types."""
    if "429" in str(exc) or "rate limit" in str(exc).lower():
        return True
    return hasattr(exc, "status_code") and exc.status_code == 429


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


def _normalize_visualization_spec(raw: dict | None, concept_name: str = "") -> dict:
    """Validate a raw visualizationSpec dict, falling back to a concept map.

    The fail-safe pipeline (doc5): validate → if invalid, retry once with the
    same spec → if still invalid, return a generic concept-map fallback so a
    visualization is ALWAYS guaranteed. The LLM never generates executable code.
    """
    if not raw:
        return {
            "type": "CONCEPT_MAP",
            "title": concept_name or "Concept",
            "caption": "",
            "conceptMap": {"nodes": [{"id": "n1", "label": concept_name or "Concept"}], "edges": []},
        }
    try:
        spec = VisualizationSpec.model_validate(raw)
        return spec.model_dump(by_alias=True)
    except Exception:
        pass
    # Retry once: try wrapping as a process flow if it looks like one
    if "stages" in raw or "animation" in raw:
        try:
            wrapped = {"type": "PROCESS_FLOW", "title": raw.get("title", concept_name), "process": raw}
            spec = VisualizationSpec.model_validate(wrapped)
            return spec.model_dump(by_alias=True)
        except Exception:
            pass
    # Final fallback: generic concept map
    return {
        "type": "CONCEPT_MAP",
        "title": concept_name or "Concept",
        "caption": "",
        "conceptMap": {"nodes": [{"id": "n1", "label": concept_name or "Concept"}], "edges": []},
    }


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
                api_keys=s.groq_api_key_pool, model=s.groq_extraction_model
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
                raw = await provider.complete(SYSTEM_PROMPT, user_prompt, temperature=0.0, max_tokens=8192)
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
        max_tokens: int | None = None,
        rate_limit_backoff: float = 5.0,
    ) -> _T:
        """Run a completion, parse JSON, and validate against a Pydantic schema.

        Retries on invalid JSON/schema failures so transient formatting issues
        never bubble up to the user as raw errors. When a call fails due to a
        provider rate limit (HTTP 429), it waits ``rate_limit_backoff`` seconds
        before retrying so the limit can reset rather than failing the request.
        """
        provider = self._get_provider()
        last_error: Exception | None = None
        for _attempt in range(attempts):
            try:
                raw = await provider.complete(
                    system, user, temperature=temperature, max_tokens=max_tokens
                )
                parsed = json.loads(_clean_json(raw))
                return schema.model_validate(parsed)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if _is_rate_limit(exc) and _attempt < attempts - 1:
                    rotate = getattr(provider, "rotate", None)
                    if callable(rotate):
                        rotate()
                    await asyncio.sleep(rate_limit_backoff)
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

    async def generate_diagnostic_questions(
        self,
        concept: dict[str, Any],
        target_vocabulary: list[str],
        graph_position: str,
        chunks: list[dict[str, Any]],
        learner_context: str = "",
        question_count: int = 5,
    ) -> QuestionSet:
        """Generate a focused diagnostic question set for a fixed concept.

        The concept is fixed; only the supplied target vocabulary may be used in
        diagnosticTargets (deterministic enforcement happens in the caller).
        ``learner_context`` carries the learner's current state so questions adapt
        to known gaps; empty means no prior assessment.
        """
        user = build_diagnostic_user_prompt(
            concept_name=concept.get("name", ""),
            description=concept.get("description", ""),
            expected_understanding=concept.get("expectedUnderstanding", ""),
            common_misconceptions=_list_text(concept.get("commonMisconceptions") or []),
            target_vocabulary="; ".join(target_vocabulary),
            graph_position=graph_position,
            learner_context=learner_context,
            source_chunks=_render_chunks(chunks),
            question_count=question_count,
        )
        return await self._complete_validated(
            DIAGNOSTIC_SYSTEM_PROMPT.format(question_count=question_count),
            user,
            QuestionSet,
            temperature=0.3,
        )

    async def generate_probe(
        self,
        concept: dict[str, Any],
        differentiation_target: dict,
        target_vocabulary: list[str],
        chunks: list[dict[str, Any]],
    ) -> ProbeQuestion:
        """Generate a single targeted probe to disambiguate two hypotheses."""
        user = build_probe_user_prompt(
            concept_name=concept.get("name", ""),
            expected_understanding=concept.get("expectedUnderstanding", ""),
            differentiation_target=_json_text(differentiation_target),
            target_vocabulary="; ".join(target_vocabulary),
            source_chunks=_render_chunks(chunks),
        )
        return await self._complete_validated(
            PROBE_SYSTEM_PROMPT, user, ProbeQuestion, temperature=0.3
        )

    async def generate_lesson(
        self,
        concept: dict[str, Any],
        root_cause: str,
        teaching_action: str,
        teaching_strategy: str,
        interest: str,
        chunks: list[dict[str, Any]],
        topic_context: str = "",
        student_answers: str = "",
    ) -> GeneratedLesson:
        """Generate a grounded, strategy-aware lesson for a diagnosed gap.

        ``topic_context`` lists the sibling/related concepts of the same topic so
        the lesson can cover the full picture. ``student_answers`` carries the
        learner's actual diagnostic choices and reasoning so the lesson presses
        on their weak areas and names confusion with other sub-concepts. The
        interest lens only alters the narrative; the technical explanation stays
        concept-accurate. TARGETED_PROBING must never reach this method (a probe
        replaces the lesson).
        """
        user = build_lesson_user_prompt(
            concept_name=concept.get("name", ""),
            root_cause=root_cause,
            teaching_action=teaching_action,
            teaching_strategy=teaching_strategy or "DIRECT_EXPLANATION",
            interest=interest,
            source_chunks=_render_chunks(chunks),
            topic_context=topic_context,
            student_answers=student_answers,
        )
        lesson = await self._complete_validated(
            LESSON_SYSTEM_PROMPT, user, GeneratedLesson, temperature=0.3,
            max_tokens=3000, attempts=3,
        )
        # Validate/normalize the visualization spec (fail-safe, doc5).
        lesson.visualizationSpec = _normalize_visualization_spec(
            lesson.visualizationSpec, concept.get("name", "")
        )
        return lesson

    async def clarify_doubt(
        self,
        concept: dict[str, Any],
        question: str,
        chunks: list[dict[str, Any]],
    ) -> Clarification:
        """Answer a lesson doubt strictly from the retrieved chunks.

        If the caller passed no chunks the hard RAG guard is enforced in the
        service layer (covered=False), so the model is never asked with zero
        grounding.
        """
        user = build_clarify_user_prompt(
            concept_name=concept.get("name", ""),
            question=question,
            source_chunks=_render_chunks(chunks),
        )
        return await self._complete_validated(
            CLARIFY_SYSTEM_PROMPT, user, Clarification, temperature=0.1
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

    async def generate_reassessment(
        self,
        concept: dict[str, Any],
        root_cause: str,
        teaching_strategy: str,
        existing_questions: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> GeneratedReassessment:
        """Generate a NOVEL reassessment question targeting the same root cause.

        The question must use different wording/context from the original
        diagnostic questions to verify the lesson actually repaired the gap.
        """
        existing_text = "\n".join(
            f"- [{q.get('questionType', '?')}] {q.get('questionText', '')[:120]}"
            for q in existing_questions
        ) or "(none)"
        user = REASSESSMENT_USER_TEMPLATE.format(
            concept_name=concept.get("name", ""),
            root_cause=root_cause,
            teaching_strategy=teaching_strategy,
            existing_questions=existing_text,
            source_chunks=_render_chunks(chunks),
        )
        return await self._complete_validated(
            REASSESSMENT_SYSTEM_PROMPT, user, GeneratedReassessment,
            temperature=0.3, max_tokens=2000, attempts=3,
        )


def _list_text(values: list[str]) -> str:
    return "; ".join(values) if values else "(none listed)"


def _json_text(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False) if value else "{}"