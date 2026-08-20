"""M4 Diagnostic Reasoning service (doc3, doc10).

Orchestrates the full diagnostic loop:
  1. Resolve the diagnostic target (M4 Target Resolution, doc14).
  2. Derive a deterministic target vocabulary from the concept's own fields.
  3. Generate a focused diagnostic question set (fixed concept, validated).
  4. Evaluate answers and persist them as EVIDENCE — diagnostic answers do NOT
     mutate the learner model (only reassessment does).
  5. Run deterministic evidence analysis -> CONFIDENT / AMBIGUOUS / NO_ISSUE.
  6. When AMBIGUOUS, generate a targeted probe and re-analyze.
  7. Persist a final diagnosis and expose the "Why We Think This" bundle.
"""

import re
from typing import Any

from app.ai.schemas.learner import AnswerEvaluation, ProbeQuestion, QuestionSet
from app.ai.service import AIService
from app.services import answers as answers_service
from app.services import diagnoses as diagnoses_service
from app.services import learning_events as events_service
from app.services import questions as questions_service
from app.services import sessions as sessions_service
from app.services import learner as learner_service
from app.services.concept_context import build_graph_position, get_concept_chunks
from app.services.diagnostic_analysis import (
    CONFIDENT,
    analyze_evidence,
    differentiation_target,
)
from app.services.target_resolution import resolve_diagnostic_target

DEFAULT_QUESTION_COUNT = 5
MAX_PROBE_ATTEMPTS = 2


# --------------------------------------------------------------------------- #
# Deterministic target vocabulary (AGENTS.md: no LLM-chosen targets)
# --------------------------------------------------------------------------- #

def derive_target_vocabulary(concept: dict[str, Any]) -> list[str]:
    """Deterministically derive the diagnostic target tags from a concept's own
    fields (expectedUnderstanding + commonMisconceptions). Never consults the
    LLM: generation and validation use exactly this list.
    """
    vocab: list[str] = []
    seen: set[str] = set()

    def add(raw: str, prefix: str = "") -> None:
        tag = _slug(raw, prefix)
        if tag and tag not in seen:
            seen.add(tag)
            vocab.append(tag)

    for mc in concept.get("commonMisconceptions") or []:
        add(str(mc), "MC")
    understanding = (concept.get("expectedUnderstanding") or "").strip()
    if understanding:
        add(understanding, "UNDERSTANDING")
    if not vocab:
        add(concept.get("canonicalName") or concept.get("name") or "concept", "CORE")
    if not vocab:
        vocab = ["CORE_UNDERSTANDING"]
    return vocab


def _slug(raw: str, prefix: str) -> str:
    text = raw.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        return ""
    return f"{prefix}_{text}" if prefix else text


async def _build_learner_context(
    owner_id: str,
    subject_id: str,
    concept: dict[str, Any],
) -> str:
    """Build a short, plain-text description of the learner's known state for the
    diagnostic target concept, so question generation adapts to where the learner
    is missing (AGENTS.md: updated learner state drives the next adaptive action).

    Falls back to 'no prior assessment' when there is no learner signal — this
    keeps fresh-user behavior unchanged while making repeat attempts adaptive.
    """
    parts: list[str] = []
    target_id = concept.get("id")
    target_name = concept.get("name") or concept.get("canonicalName") or "the target concept"

    model = await learner_service.get_learner_model(owner_id, subject_id)
    states = (model or {}).get("conceptStates") or {}
    if states and target_id and target_id in states:
        st = states[target_id]
        status = st.get("status") or "UNKNOWN"
        mastery = st.get("mastery")
        if mastery is not None:
            parts.append(
                f"Learner state: '{target_name}' is currently {status} "
                f"(mastery {mastery:.2f})."
            )
        else:
            parts.append(f"Learner state: '{target_name}' is currently {status}.")
    elif states:
        parts.append(
            f"Learner state: '{target_name}' has not been assessed yet, though the "
            "learner has a model for this subject."
        )
    else:
        parts.append(
            "Learner state: no assessment exists yet for this subject — "
            "probe the concept broadly."
        )

    try:
        prior = [
            d for d in await diagnoses_service.list_diagnoses(owner_id, subject_id)
            if d.get("conceptId") == target_id
        ]
    except Exception:  # noqa: BLE001
        prior = []
    if prior:
        d = prior[0]
        root = d.get("rootCause") or "UNKNOWN"
        statement = (d.get("investigation") or {}).get("statement") or ""
        line = f"Previous diagnosis for this concept: root cause {root}."
        if statement:
            line += f" ({statement})"
        line += " Probe whether this cause still holds and sharpen the specific gap."
        parts.append(line)

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

async def start_diagnostic(
    owner_id: str,
    subject_id: str,
    ai: AIService | None = None,
    question_count: int = DEFAULT_QUESTION_COUNT,
    entry_concept_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the target and open a diagnostic session with generated questions.

    ``entry_concept_id`` is the concept the learner selected. The Target
    Resolution Engine starts from it and may resolve an upstream prerequisite as
    the actual diagnostic target (doc14). When omitted, the subject-wide weakest
    candidate is used.

    Returns {status, session?, resolution?, error?}. NO_TARGET and
    RESOLUTION_ERROR are surfaced as non-raising outcomes so the UI can explain
    why no diagnostic was started.
    """
    resolution = await resolve_diagnostic_target(owner_id, subject_id, entry_concept_id)
    if resolution.get("status") != "TARGET_FOUND":
        return {"status": resolution.get("status"), "resolution": resolution}

    target_id = resolution["conceptId"]
    from app.services import concepts as concepts_service

    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == target_id:
            concept = c
            break
    if concept is None:
        return {
            "status": "RESOLUTION_ERROR",
            "resolution": {**resolution, "reason": "Resolved concept not found."},
        }

    vocab = derive_target_vocabulary(concept)
    chunks = await get_concept_chunks(owner_id, subject_id, concept)
    graph_position = await build_graph_position(subject_id, concept)
    available = {c["chunkIndex"] for c in chunks}
    learner_context = await _build_learner_context(owner_id, subject_id, concept)

    service = ai or AIService()
    try:
        question_set: QuestionSet = await service.generate_diagnostic_questions(
            concept, vocab, graph_position, chunks,
            learner_context=learner_context, question_count=question_count,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "GENERATION_ERROR",
            "resolution": resolution,
            "error": f"Question generation failed: {exc}",
        }

    cleaned, errors = _validate_diagnostic_questions(
        question_set.questions, vocab, available, question_count
    )
    if errors or not cleaned:
        return {
            "status": "VALIDATION_ERROR",
            "resolution": resolution,
            "error": "; ".join(errors) if errors else "No valid questions produced.",
        }

    session = await sessions_service.create_session(
        owner_id, subject_id, concept["id"], resolution=resolution
    )
    if session is None:
        return {"status": "SESSION_ERROR", "resolution": resolution,
                "error": "Could not create diagnostic session."}

    questions_out = []
    for q in cleaned:
        qid = await questions_service.insert_question(
            subject_id=subject_id,
            concept_id=concept["id"],
            question_type=q.questionType,
            difficulty=q.difficulty,
            question_text=q.questionText,
            expected_answer=q.expectedAnswer,
            expected_reasoning=q.expectedReasoning,
            diagnostic_targets=q.diagnosticTargets,
            source_references=[{"chunkIndex": ci} for ci in q.sourceChunks],
            generation_metadata={
                "conceptName": concept.get("name", ""),
                "targetVocabulary": vocab,
                "diagnostic": True,
            },
            options=[o.model_dump() for o in q.options],
            correct_option_id=q.correctOptionId,
        )
        questions_out.append(_public_question(qid, q))

    await sessions_service.mark_in_progress(owner_id, session["id"])
    await events_service.append_event(
        owner_id, subject_id, "DIAGNOSTIC_STARTED",
        entity_type="diagnostic_session", entity_id=session["id"],
        metadata={
            "conceptId": concept["id"],
            "questionCount": len(questions_out),
            "resolvedFrom": resolution.get("path", []),
            "rootGap": resolution.get("rootGap", False),
        },
    )
    return {
        "status": "TARGET_FOUND",
        "sessionId": session["id"],
        "conceptId": concept["id"],
        "conceptName": concept.get("name", ""),
        "questions": questions_out,
        "resolution": resolution,
        "targetVocabulary": vocab,
    }


_DOC_META_PATTERNS = [
    re.compile(r"\bsection\s+heading", re.IGNORECASE),
    re.compile(r"\bheading[s]?\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+)?listed\b", re.IGNORECASE),
    re.compile(r"\bpage\s+(?:number|no\.?|#|heading)", re.IGNORECASE),
    re.compile(r"\btable\s+of\s+contents\b", re.IGNORECASE),
    re.compile(r"\b(?:figure|chart|diagram|table)\b", re.IGNORECASE),
    re.compile(r"\bchapter\b", re.IGNORECASE),
    re.compile(r"\bmentioned\s+(?:in|on)\b", re.IGNORECASE),
    re.compile(r"\bappears?\s+(?:in|on|as)\b", re.IGNORECASE),
    re.compile(r"\bsection\s+\w+", re.IGNORECASE),
    re.compile(r"\btitle\s+of\b", re.IGNORECASE),
    re.compile(r"\bexcerpt[s]?\b", re.IGNORECASE),
    re.compile(r"\b(?:topic|subject)\s+of\s+(?:the\s+)?(?:chapter|section|unit)\b", re.IGNORECASE),
]


def _question_text(q: Any) -> str:
    """Collect all question content that should be inspected for meta-language."""
    parts = [q.questionText, q.expectedAnswer, q.expectedReasoning]
    for opt in getattr(q, "options", None) or []:
        parts.append(getattr(opt, "text", ""))
    return "\n".join(p for p in parts if p)


def _is_document_meta_question(q: Any) -> bool:
    """Return True when the question is about document structure rather than the
    concept's mechanism (headings, sections, pages, figures, citations)."""
    text = _question_text(q)
    return any(pattern.search(text) for pattern in _DOC_META_PATTERNS)


_TARGET_PREFIXES = {"understanding", "mc", "core"}


def _ties_to_target(q: Any, vocab_set: set[str]) -> bool:
    """Return True when at least one diagnostic target term actually appears in
    the question's content, so the question genuinely probes that mechanism."""
    text = _question_text(q)
    lowered = text.lower()
    for target in q.diagnosticTargets:
        tokens = [t for t in target.lower().split("_") if t and t not in _TARGET_PREFIXES]
        if not tokens:
            continue
        if any(token in lowered for token in tokens):
            return True
    return False


def _validate_diagnostic_questions(
    questions: list[Any],
    vocab: list[str],
    available: set[int],
    question_count: int,
) -> tuple[list[Any], list[str]]:
    """Deterministically validate generated diagnostic questions.

    Returns (valid_questions, error_messages). All constraints are enforced here
    and are never left to the LLM: exact target tags, grounded chunk indices,
    valid MCQ shape, count bounds, and mechanism-based content (no document-meta
    questions, no untethered diagnostic targets).
    """
    if not questions:
        return [], ["No questions generated."]
    if len(questions) > question_count:
        return [], [
            f"Generated {len(questions)} questions; expected at most {question_count}."
        ]

    vocab_set = set(vocab)
    valid: list[Any] = []
    errors: list[str] = []
    for idx, q in enumerate(questions):
        q.sourceChunks = [c for c in q.sourceChunks if c in available]
        q.diagnosticTargets = [t for t in q.diagnosticTargets if t in vocab_set]
        if not q.diagnosticTargets:
            errors.append(f"Question {idx + 1} has no valid diagnostic target.")
            continue
        if q.questionType == "MCQ":
            if len(q.options) < 2:
                errors.append(f"Question {idx + 1} MCQ has fewer than 2 options.")
                continue
        if _is_document_meta_question(q):
            errors.append(
                f"Question {idx + 1} is a document-meta question, not a mechanism "
                "question (headings/pages/sections), and was rejected."
            )
            continue
        if not _ties_to_target(q, vocab_set):
            errors.append(
                f"Question {idx + 1} does not reference any of its diagnostic "
                "targets and was rejected as off-topic."
            )
            continue
        valid.append(q)
    return valid, errors


# --------------------------------------------------------------------------- #
# Answer / evidence (diagnostic answers do NOT mutate mastery)
# --------------------------------------------------------------------------- #

async def submit_diagnostic_answer(
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
    """Evaluate a diagnostic answer and persist it as EVIDENCE only.

    Unlike study.submit_answer, this never calls learner_service.apply_evidence /
    update_concept_state. The learner model is updated only by reassessment.
    """
    is_mcq = question.get("questionType") in ("MCQ", "PROBE") and bool(question.get("options"))
    if is_mcq:
        if not selected_option_id:
            raise ValueError("An option must be selected for MCQ questions")
        options = question.get("options") or []
        by_id = {o.get("id"): o.get("text", "") for o in options}
        if selected_option_id not in by_id:
            raise ValueError("Selected option does not exist for this question")
        correct = selected_option_id == (question.get("correctOptionId") or "")
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
        evaluation.correct = correct

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
            "diagnostic": True,
        },
        evidence_signals=evaluation.evidenceSignals,
        selected_option_id=selected_option_id,
    )

    await events_service.append_event(
        learner_id, subject_id, "QUESTION_ANSWERED",
        entity_type="answer", entity_id=answer_id,
        metadata={
            "questionId": question["id"], "correct": evaluation.correct,
            "reasoningQuality": evaluation.reasoningQuality,
            "conceptId": concept["id"], "diagnostic": True,
        },
    )
    return {
        "answerId": answer_id,
        "correct": evaluation.correct,
        "reasoningQuality": evaluation.reasoningQuality,
        "explanation": evaluation.explanation,
        "evidenceSignals": evaluation.evidenceSignals,
        "misconception": evaluation.misconception.model_dump() if evaluation.misconception else None,
    }


# --------------------------------------------------------------------------- #
# Analysis, probe, finalization
# --------------------------------------------------------------------------- #

async def analyze_session(learner_id: str, session: dict[str, Any]) -> dict[str, Any]:
    """Gather a session's evidence and run deterministic analysis."""
    evidence = await answers_service.list_answers_for_session(learner_id, session["id"])
    records = [
        {
            "questionId": e["questionId"],
            "correct": e["correctness"],
            "reasoningQuality": (e.get("reasoningAssessment") or {}).get("reasoningQuality"),
            "evidenceSignals": e.get("evidenceSignals") or [],
            "misconception": (e.get("reasoningAssessment") or {}).get("misconception"),
        }
        for e in evidence
    ]
    return analyze_evidence(records)


async def generate_probe_for(
    owner_id: str,
    subject_id: str,
    session: dict[str, Any],
    concept: dict[str, Any],
    decision: dict[str, Any],
    ai: AIService | None = None,
) -> dict[str, Any]:
    """Generate and persist a targeted probe question when evidence is ambiguous.

    Returns {probeQuestion, target}. Raises RuntimeError on LLM failure or when
    the differentiation target cannot be formed.
    """
    target = differentiation_target(decision)
    if target is None:
        raise RuntimeError("Insufficient hypotheses to form a differentiation target.")

    vocab = derive_target_vocabulary(concept)
    chunks = await get_concept_chunks(owner_id, subject_id, concept)
    available = {c["chunkIndex"] for c in chunks}

    service = ai or AIService()
    probe: ProbeQuestion = await service.generate_probe(concept, target, vocab, chunks)

    probe.sourceChunks = [c for c in probe.sourceChunks if c in available]
    probe.diagnosticTargets = [t for t in probe.diagnosticTargets if t in set(vocab)]
    if not probe.diagnosticTargets:
        probe.diagnosticTargets = vocab[:1]
    if probe.questionType == "MCQ" and len(probe.options) < 2:
        raise RuntimeError("Probe MCQ has fewer than 2 options.")

    qid = await questions_service.insert_question(
        subject_id=subject_id,
        concept_id=concept["id"],
        question_type="PROBE",
        difficulty=probe.difficulty,
        question_text=probe.questionText,
        expected_answer=probe.expectedAnswer,
        expected_reasoning=probe.expectedReasoning,
        diagnostic_targets=probe.diagnosticTargets,
        source_references=[{"chunkIndex": ci} for ci in probe.sourceChunks],
        generation_metadata={
            "conceptName": concept.get("name", ""),
            "targetVocabulary": vocab,
            "differentiationTarget": probe.differentiationTarget or target,
            "diagnostic": True,
            "probe": True,
        },
        options=[o.model_dump() for o in probe.options],
        correct_option_id=probe.correctOptionId,
    )
    return {
        "probeQuestion": _public_question(qid, probe),
        "target": probe.differentiationTarget or target,
    }


async def finalize_diagnosis(
    owner_id: str,
    subject_id: str,
    session: dict[str, Any],
    concept: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Persist a final diagnosis and complete the diagnostic session.

    INSUFFICIENT_EVIDENCE is the terminal root cause when analysis stayed
    ambiguous after the maximum probe attempts (doc3). NO_ISSUE is recorded as a
    benign diagnosis.
    """
    root_cause = decision.get("rootCause")
    if decision.get("status") != CONFIDENT:
        root_cause = "INSUFFICIENT_EVIDENCE"

    evidence = await answers_service.list_answers_for_session(owner_id, session["id"])
    evidence_references = [
        {
            "answerId": e["id"],
            "questionId": e["questionId"],
            "correct": e["correctness"],
        }
        for e in evidence
    ]
    resolution = session.get("resolution") or {}

    diagnosis = await diagnoses_service.insert_diagnosis(
        learner_id=owner_id,
        subject_id=subject_id,
        session_id=session["id"],
        concept_id=concept["id"],
        root_cause=root_cause,
        confidence=float(decision.get("confidence") or 0.0),
        resolution=resolution,
        investigation={
            "status": decision.get("status"),
            "statement": decision.get("statement", ""),
            "evidenceSignals": decision.get("evidenceSignals", []),
            "hypotheses": decision.get("hypotheses", []),
        },
        evidence_references=evidence_references,
    )
    if diagnosis is None:
        raise RuntimeError("Could not persist the diagnosis")
    await sessions_service.complete_session(owner_id, session["id"])
    await events_service.append_event(
        owner_id, subject_id, "DIAGNOSIS_CREATED",
        entity_type="diagnosis", entity_id=diagnosis["id"],
        metadata={
            "conceptId": concept["id"],
            "rootCause": root_cause,
            "confidence": float(decision.get("confidence") or 0.0),
        },
    )
    return _public_diagnosis(diagnosis, concept)


# --------------------------------------------------------------------------- #
# Why We Think This
# --------------------------------------------------------------------------- #

async def evidence_bundle(
    owner_id: str,
    subject_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Assemble the structured 'Why We Think This' bundle for a session.

    Combines the target resolution trace, the final diagnosis, and the raw
    evidence so the adaptive decision is fully transparent and visible (doc13).
    """
    session = await sessions_service.get_session(owner_id, session_id)
    if session is None:
        return {"status": "NOT_FOUND"}
    from app.services import concepts as concepts_service
    from app.services import questions as questions_service

    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == session["conceptId"]:
            concept = c
            break
    diagnosis = await diagnoses_service.get_diagnosis_by_session(owner_id, session_id)
    evidence = await answers_service.list_answers_for_session(owner_id, session_id)

    question_text = {}
    if evidence:
        qids = [e["questionId"] for e in evidence if e.get("questionId")]
        questions = await questions_service.list_questions_for_session(subject_id, session["conceptId"], qids)
        question_text = {q["id"]: q["questionText"] for q in questions}

    return {
        "status": "OK",
        "conceptId": session["conceptId"],
        "conceptName": concept.get("name", "") if concept else "",
        "resolution": session.get("resolution") or {},
        "diagnosis": diagnosis,
        "evidence": [
            {
                "questionId": e["questionId"],
                "questionText": question_text.get(e.get("questionId"), ""),
                "reasoning": e.get("reasoning") or "",
                "response": e.get("response") or "",
                "correct": e["correctness"],
                "reasoningQuality": (e.get("reasoningAssessment") or {}).get("reasoningQuality"),
                "evidenceSignals": e.get("evidenceSignals") or [],
                "misconception": (e.get("reasoningAssessment") or {}).get("misconception"),
            }
            for e in evidence
        ],
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _public_question(qid: str | None, q: Any) -> dict[str, Any]:
    return {
        "id": qid,
        "questionText": q.questionText,
        "questionType": q.questionType,
        "difficulty": q.difficulty,
        "diagnosticTargets": q.diagnosticTargets,
        "sourceChunks": q.sourceChunks,
        "options": [o.model_dump() for o in q.options],
    }


def _public_diagnosis(diagnosis: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": diagnosis["id"],
        "conceptId": concept["id"],
        "conceptName": concept.get("name", ""),
        "rootCause": diagnosis["rootCause"],
        "confidence": diagnosis["confidence"],
        "resolution": diagnosis.get("resolution") or {},
        "investigation": diagnosis.get("investigation") or {},
        "evidenceReferences": diagnosis.get("evidenceReferences") or [],
    }