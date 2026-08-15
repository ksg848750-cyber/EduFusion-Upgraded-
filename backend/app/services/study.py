from typing import Any

from app.ai.schemas.learner import AnswerEvaluation, ConceptExplanation, QuestionSet
from app.ai.service import AIService
from app.services import answers as answers_service
from app.services import learner as learner_service
from app.services import learning_events as events_service
from app.services import misconceptions as misconceptions_service
from app.services import questions as questions_service
from app.services import sessions as sessions_service
from app.services.concept_context import build_graph_position, get_concept_chunks


def _source_refs(source_chunks: list[int]) -> list[dict]:
    return [{"chunkIndex": ci} for ci in source_chunks]


async def explain_concept(
    owner_id: str,
    subject_id: str,
    concept: dict[str, Any],
    learner_id: str,
    ai: AIService | None = None,
) -> ConceptExplanation:
    """Understand mode: grounded, adaptive explanation of a concept."""
    chunks = await get_concept_chunks(owner_id, subject_id, concept)
    graph_position = await build_graph_position(subject_id, concept)
    state = await learner_service.get_concept_state(learner_id, subject_id, concept["id"])
    misconceptions = await misconceptions_service.list_misconceptions_for_concept(
        learner_id, subject_id, concept["id"]
    )
    learner_evidence = _render_learner_evidence(state, misconceptions)

    service = ai or AIService()
    explanation = await service.explain_concept(concept, graph_position, learner_evidence, chunks)

    # Deterministic guard: never surface a source the LLM was not shown.
    available = {c["chunkIndex"] for c in chunks}
    explanation.sourceChunks = [c for c in explanation.sourceChunks if c in available]
    for section in explanation.sections:
        section.sourceChunks = [c for c in section.sourceChunks if c in available]

    await events_service.append_event(
        learner_id, subject_id, "CONCEPT_UNDERSTAND_REQUESTED",
        entity_type="concept", entity_id=concept["id"],
        metadata={"conceptName": concept.get("name", "")},
    )
    return explanation


async def start_test(
    owner_id: str,
    subject_id: str,
    concept: dict[str, Any],
    learner_id: str,
    ai: AIService | None = None,
) -> dict[str, Any]:
    """Test mode: generate grounded questions and open a diagnostic session."""
    chunks = await get_concept_chunks(owner_id, subject_id, concept)
    graph_position = await build_graph_position(subject_id, concept)

    service = ai or AIService()
    question_set: QuestionSet = await service.generate_questions(concept, graph_position, chunks)

    available = {c["chunkIndex"] for c in chunks}
    session = await sessions_service.create_session(learner_id, subject_id, concept["id"])
    if session is None:
        raise RuntimeError("Could not create diagnostic session")

    questions_out = []
    for q in question_set.questions:
        q.sourceChunks = [c for c in q.sourceChunks if c in available]
        qid = await questions_service.insert_question(
            subject_id=subject_id,
            concept_id=concept["id"],
            question_type=q.questionType,
            difficulty=q.difficulty,
            question_text=q.questionText,
            expected_answer=q.expectedAnswer,
            expected_reasoning=q.expectedReasoning,
            diagnostic_targets=q.diagnosticTargets,
            source_references=_source_refs(q.sourceChunks),
            generation_metadata={"conceptName": concept.get("name", "")},
            options=[o.model_dump() for o in q.options],
            correct_option_id=q.correctOptionId,
        )
        questions_out.append(
            {
                "id": qid,
                "questionText": q.questionText,
                "questionType": q.questionType,
                "difficulty": q.difficulty,
                "diagnosticTargets": q.diagnosticTargets,
                "sourceChunks": q.sourceChunks,
                "options": [o.model_dump() for o in q.options],
            }
        )

    await events_service.append_event(
        learner_id, subject_id, "DIAGNOSTIC_STARTED",
        entity_type="diagnostic_session", entity_id=session["id"],
        metadata={"conceptId": concept["id"], "questionCount": len(questions_out)},
    )
    return {"sessionId": session["id"], "conceptId": concept["id"], "questions": questions_out}


async def submit_answer(
    owner_id: str,
    subject_id: str,
    session: dict[str, Any],
    concept: dict[str, Any],
    question: dict[str, Any],
    learner_id: str,
    response: str,
    reasoning: str,
    selected_option_id: str | None = None,
    ai: AIService | None = None,
) -> dict[str, Any]:
    """Evaluate a student answer, update the learner model, surface misconceptions.

    For MCQ questions the selected option id is graded deterministically against
    the stored correct option id; the reasoning still drives misconception
    detection. Short-answer / scenario answers are graded by the evaluator.
    """
    is_mcq = question.get("questionType") == "MCQ"
    if is_mcq:
        if not selected_option_id:
            raise ValueError("An option must be selected for MCQ questions")
        options = question.get("options") or []
        by_id = {o.get("id"): o.get("text", "") for o in options}
        if selected_option_id not in by_id:
            raise ValueError("Selected option does not exist for this question")
        correct_option_id = question.get("correctOptionId") or ""
        correct = selected_option_id == correct_option_id
        selected_option_text = by_id[selected_option_id]
    else:
        if not response.strip():
            raise ValueError("Answer must not be empty")
        selected_option_text = ""

    chunks = await get_concept_chunks(owner_id, subject_id, concept)
    service = ai or AIService()
    evaluation: AnswerEvaluation = await service.evaluate_answer(
        concept,
        question,
        chunks,
        response,
        reasoning,
        options=question.get("options") if is_mcq else None,
        selected_option_id=selected_option_id or "",
        selected_option_text=selected_option_text,
    )
    if is_mcq:
        # MCQ correctness is deterministic: the option ids are stored structured,
        # never string-parsed.
        evaluation.correct = correct

    prior_in_session = await sessions_service.count_answered_in_session(
        learner_id, session["id"], concept["id"]
    )
    current_state = await learner_service.get_concept_state(
        learner_id, subject_id, concept["id"]
    )
    new_state = learner_service.apply_evidence(
        current_state,
        correct=evaluation.correct,
        reasoning_quality=evaluation.reasoningQuality,
        difficulty=concept.get("difficulty") or 3,
        prior_in_session=prior_in_session,
    )

    answer_id = await answers_service.insert_answer(
        question_id=question["id"],
        learner_id=learner_id,
        diagnostic_session_id=session["id"],
        response=response,
        reasoning=reasoning,
        correctness=evaluation.correct,
        reasoning_assessment={
            "reasoningQuality": evaluation.reasoningQuality,
            "explanation": evaluation.explanation,
            "misconception": evaluation.misconception.model_dump() if evaluation.misconception else None,
        },
        evidence_signals=evaluation.evidenceSignals,
        selected_option_id=selected_option_id,
    )

    await learner_service.update_concept_state(learner_id, subject_id, concept["id"], new_state)

    misconception = None
    hypothesis = evaluation.misconception
    if not evaluation.correct and hypothesis and hypothesis.confidence >= 0.6:
        evidence = [{
            "questionId": question["id"],
            "answerId": answer_id,
            "signal": ", ".join(evaluation.evidenceSignals) or hypothesis.statement,
        }]
        misconception = await misconceptions_service.upsert_misconception(
            learner_id, subject_id, concept["id"],
            hypothesis.category, hypothesis.statement, hypothesis.confidence, evidence,
        )

    await events_service.append_event(
        learner_id, subject_id, "QUESTION_ANSWERED",
        entity_type="answer", entity_id=answer_id,
        metadata={
            "questionId": question["id"], "correct": evaluation.correct,
            "reasoningQuality": evaluation.reasoningQuality,
            "masteryAfter": new_state.get("mastery"),
            "conceptId": concept["id"],
        },
    )
    if misconception:
        await events_service.append_event(
            learner_id, subject_id, "MISCONCEPTION_DETECTED",
            entity_type="misconception", entity_id=misconception["id"],
            metadata={"category": misconception["category"], "status": misconception["status"]},
        )
    await events_service.append_event(
        learner_id, subject_id, "MASTERY_UPDATED",
        entity_type="concept", entity_id=concept["id"],
        metadata={"mastery": new_state.get("mastery"), "status": new_state.get("status")},
    )

    return {
        "answerId": answer_id,
        "correct": evaluation.correct,
        "reasoningQuality": evaluation.reasoningQuality,
        "explanation": evaluation.explanation,
        "evidenceSignals": evaluation.evidenceSignals,
        "conceptState": new_state,
        "misconception": _public_misconception(misconception) if misconception else None,
    }


def _public_misconception(mc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": mc["id"],
        "category": mc["category"],
        "statement": mc["statement"],
        "confidence": mc["confidence"],
        "status": mc["status"],
        "evidenceReferences": mc["evidenceReferences"],
    }


def _render_learner_evidence(state: dict[str, Any] | None, misconceptions: list[dict[str, Any]]) -> str:
    lines = []
    if state:
        status = state.get("status") or "UNKNOWN"
        mastery = state.get("mastery") or 0.0
        if status != "UNKNOWN":
            lines.append(
                f"Learner status for this concept: {status} (mastery {mastery}, "
                f"{state.get('interactionCount') or 0} interactions)."
            )
    for mc in misconceptions:
        lines.append(
            f"Known {mc['status']} misconception: [{mc['category']}] {mc['statement']}"
        )
    return "\n".join(lines) if lines else "No prior learner evidence for this concept."