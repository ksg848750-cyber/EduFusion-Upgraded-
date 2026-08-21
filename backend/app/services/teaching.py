"""M5 Adaptive Teaching Engine — Dual-Decision (doc4).

The diagnosis controls the lesson. This module executes the two deterministic
decisions that sit between diagnosis and lesson delivery:

  Decision A (WHAT to teach): root cause -> teaching action + pedagogical
                              strategy (fixed mapping).
  Decision B (HOW to teach):  select a teaching strategy from the learner's
                              strategy outcome history, escalating by attempt.

Decision A/B are deterministic and fully unit-testable. The grounded lesson
generation (RAG + LLM), interest lens, and doubt clarification build on top of
the decision this module produces.
"""

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection

ALLOWED_INTERESTS = (
    "normal", "cricket", "movies", "f1", "gaming", "anime",
    "football", "web-series", "music",
)

ROOT_CAUSE_ACTIONS: dict[str, tuple[str, str]] = {
    "MISSING_PREREQUISITE": (
        "PREREQUISITE_REPAIR",
        "Step back in the knowledge graph to repair the missing prerequisite before retrying the target.",
    ),
    "MISCONCEPTION": (
        "MENTAL_MODEL_CORRECTION",
        "Present a counterexample that highlights the flaw, then replace it with the correct mental model.",
    ),
    "PROCEDURAL_ERROR": (
        "GUIDED_PRACTICE",
        "Skip definition overviews; walk through step-by-step worked examples of proper application.",
    ),
    "TERMINOLOGY_CONFUSION": (
        "DISTINCTION_CONTRAST",
        "Present a side-by-side comparison contrasting the confused terms.",
    ),
    "REPRESENTATION_PROBLEM": (
        "REPRESENTATION_SHIFT",
        "Change the primary modal medium (e.g. text to an interactive diagram).",
    ),
    "INSUFFICIENT_EVIDENCE": (
        "TARGETED_PROBING",
        "Issue a targeted probe question to collect diagnostic signal.",
    ),
}

# Teaching strategies appropriate per action (doc4 strategy library).
ACTION_STRATEGIES: dict[str, list[str]] = {
    "PREREQUISITE_REPAIR": ["PREREQUISITE_REPAIR", "DIRECT_EXPLANATION"],
    "MENTAL_MODEL_CORRECTION": ["VISUAL_STEP_BY_STEP", "WORKED_EXAMPLE", "INTERACTIVE_EXPLANATION"],
    "GUIDED_PRACTICE": ["WORKED_EXAMPLE", "VISUAL_STEP_BY_STEP", "INTERACTIVE_EXPLANATION"],
    "DISTINCTION_CONTRAST": ["DIRECT_EXPLANATION", "VISUAL_STEP_BY_STEP"],
    "REPRESENTATION_SHIFT": ["VISUAL_STEP_BY_STEP", "INTERACTIVE_EXPLANATION"],
    "TARGETED_PROBING": [],
}

# Attempt escalation ladder (doc4): each retry changes strategy.
ATTEMPT_LADDER: dict[int, str] = {
    1: "VISUAL_STEP_BY_STEP",
    2: "WORKED_EXAMPLE",
    3: "PREREQUISITE_REPAIR",
}
MAX_ATTEMPTS = 3

POOR_OUTCOMES = ("NO_CHANGE", "REGRESSED")
GOOD_OUTCOMES = ("IMPROVED",)


def decision_a(root_cause: str) -> dict[str, Any]:
    """Decision A: WHAT to teach (deterministic root-cause -> action mapping)."""
    if root_cause not in ROOT_CAUSE_ACTIONS:
        raise ValueError(f"Unknown root cause: {root_cause!r}")
    action, reason = ROOT_CAUSE_ACTIONS[root_cause]
    return {"rootCause": root_cause, "action": action, "reason": reason}


def decision_b(
    root_cause: str,
    strategy_profile: dict[str, str] | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """Decision B: HOW to teach (deterministic strategy selection + escalation).

    ``strategy_profile`` maps a strategy to its last observed outcome
    (IMPROVED / NO_CHANGE / REGRESSED) for the target concept. Ineffective
    strategies are excluded; proven ones are prioritized; the attempt ladder
    escalates the strategy on retries. TARGETED_PROBING yields no lesson
    strategy (a probe question replaces the lesson).
    """
    action = decision_a(root_cause)["action"]
    if action == "TARGETED_PROBING":
        return {
            "rootCause": root_cause,
            "action": action,
            "strategy": None,
            "attempt": attempt,
            "excluded": [],
            "reason": "Insufficient evidence — issue a targeted probe instead of a lesson.",
        }

    profile = strategy_profile or {}
    excluded = sorted({s for s, o in profile.items() if o in POOR_OUTCOMES})
    candidates = list(ACTION_STRATEGIES.get(action, [])) or ["DIRECT_EXPLANATION"]

    def rank(s: str) -> tuple[int, int]:
        outcome = profile.get(s)
        priority = 0 if outcome in GOOD_OUTCOMES else (2 if outcome in POOR_OUTCOMES else 1)
        return priority, candidates.index(s)

    ladder = ATTEMPT_LADDER.get(attempt, "PREREQUISITE_REPAIR")
    if ladder in candidates and ladder not in excluded:
        chosen = ladder
    else:
        eligible = [s for s in candidates if s not in excluded]
        chosen = min(eligible, key=rank) if eligible else None

    reasons = []
    if excluded:
        reasons.append(f"excluded previously ineffective: {', '.join(excluded)}")
    if chosen is None:
        reasons.append("no viable strategy remains for this attempt")
    elif ladder == chosen:
        reasons.append(f"attempt {attempt} default strategy")
    else:
        reasons.append(f"attempt {attempt} default '{ladder}' unavailable; chose '{chosen}'")

    return {
        "rootCause": root_cause,
        "action": action,
        "strategy": chosen,
        "attempt": attempt,
        "excluded": excluded,
        "reason": "; ".join(reasons),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def count_lessons(learner_id: str, subject_id: str, concept_id: str) -> int:
    """Return the number of prior lessons delivered for this concept
    (attempt = count + 1, bounded by MAX_ATTEMPTS)."""
    async with connection() as conn:
        if conn is None:
            return 0
        row = await conn.execute(
            """
            SELECT count(*) FROM public.lessons
            WHERE learner_id = %s AND subject_id = %s AND concept_id = %s
            """,
            (learner_id, subject_id, concept_id),
        )
        record = await row.fetchone()
        return int(record[0]) if record else 0


async def record_lesson(
    learner_id: str,
    subject_id: str,
    diagnosis_id: str | None,
    concept_id: str,
    root_cause: str,
    decision: dict[str, Any],
    interest_context: str = "normal",
) -> dict[str, Any] | None:
    """Persist the teaching decision as a lesson row and log LESSON_STARTED."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.lessons
              (learner_id, subject_id, diagnosis_id, concept_id, root_cause,
               teaching_action, teaching_strategy, interest_context, attempt)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, learner_id, subject_id, diagnosis_id, concept_id, root_cause,
                      teaching_action, teaching_strategy, interest_context, attempt,
                      status, created_at, updated_at
            """,
            (
                learner_id, subject_id, diagnosis_id, concept_id, root_cause,
                decision["action"], decision.get("strategy") or "NONE",
                interest_context, decision["attempt"],
            ),
        )
        record = await row.fetchone()
        if record is None:
            return None
        lesson = {
            "id": str(record[0]),
            "learnerId": str(record[1]),
            "subjectId": str(record[2]),
            "diagnosisId": str(record[3]) if record[3] else None,
            "conceptId": str(record[4]),
            "rootCause": record[5],
            "teachingAction": record[6],
            "teachingStrategy": record[7],
            "interestContext": record[8],
            "attempt": record[9],
            "status": record[10],
            "createdAt": record[11].isoformat(),
            "updatedAt": record[12].isoformat(),
        }
    from app.services import learning_events as events_service

    await events_service.append_event(
        learner_id, subject_id, "LESSON_STARTED",
        entity_type="lesson", entity_id=lesson["id"],
        metadata={
            "conceptId": concept_id,
            "rootCause": root_cause,
            "action": decision["action"],
            "strategy": decision.get("strategy"),
            "attempt": decision["attempt"],
            "interestContext": interest_context,
        },
    )
    return lesson


async def compute_teaching_decision(
    owner_id: str,
    subject_id: str,
    session_id: str,
    interest_context: str = "normal",
) -> dict[str, Any]:
    """Orchestrate the Dual-Decision for a completed diagnostic session.

    Reads the session's diagnosis, derives the attempt from prior lessons for
    the concept, reads the learner's strategy outcome history, applies
    Decision A + Decision B, and persists the lesson.
    """
    from app.services import concepts as concepts_service
    from app.services import diagnoses as diagnoses_service
    from app.services import learner as learner_service
    from app.services import sessions as sessions_service

    session = await sessions_service.get_session(owner_id, session_id)
    if session is None:
        return {"status": "SESSION_NOT_FOUND"}
    diagnosis = await diagnoses_service.get_diagnosis_by_session(owner_id, session_id)
    if diagnosis is None:
        return {"status": "NO_DIAGNOSIS", "sessionId": session_id}

    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == session["conceptId"]:
            concept = c
            break
    concept_name = (concept or {}).get("name", "")

    root_cause = diagnosis["rootCause"]
    prior = await count_lessons(owner_id, subject_id, session["conceptId"])
    attempt = min(prior + 1, MAX_ATTEMPTS)
    profile = await learner_service.get_strategy_profile(owner_id, subject_id)

    a = decision_a(root_cause)
    b = decision_b(root_cause, profile.get(session["conceptId"]) or {}, attempt)
    decision = {**a, **b}

    lesson = await record_lesson(
        owner_id, subject_id, diagnosis["id"], session["conceptId"],
        root_cause, decision, interest_context=interest_context,
    )
    if lesson is None:
        return {"status": "LESSON_ERROR", "sessionId": session_id}

    return {
        "status": "OK",
        "lessonId": lesson["id"],
        "sessionId": session_id,
        "diagnosisId": diagnosis["id"],
        "conceptId": session["conceptId"],
        "conceptName": concept_name,
        "rootCause": root_cause,
        "action": decision["action"],
        "reason": decision["reason"],
        "teachingStrategy": decision["strategy"],
        "attempt": attempt,
        "excluded": decision["excluded"],
        "interestContext": interest_context,
    }


def _validate_interest(interest: str) -> str:
    if interest not in ALLOWED_INTERESTS:
        raise ValueError(f"Unsupported interest context: {interest!r}")
    return interest


async def get_lesson(owner_id: str, lesson_id: str) -> dict[str, Any] | None:
    """Load a lesson owned by the learner (authorization scoped by owner)."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT l.id, l.learner_id, l.subject_id, l.diagnosis_id, l.concept_id,
                   l.root_cause, l.teaching_action, l.teaching_strategy,
                   l.interest_context, l.attempt, l.status,
                   l.explanation, l.visualization_spec, l.source_references,
                   l.created_at, l.updated_at
            FROM public.lessons l
            JOIN public.subjects s ON s.id = l.subject_id
            WHERE l.id = %s AND s.owner_id = %s
            """,
            (lesson_id, owner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "learnerId": str(record[1]),
            "subjectId": str(record[2]),
            "diagnosisId": str(record[3]) if record[3] else None,
            "conceptId": str(record[4]),
            "rootCause": record[5],
            "teachingAction": record[6],
            "teachingStrategy": record[7],
            "interestContext": record[8],
            "attempt": record[9],
            "status": record[10],
            "explanation": record[11] or "",
            "visualizationSpec": record[12] or {},
            "sourceReferences": record[13] or [],
            "createdAt": record[14].isoformat(),
            "updatedAt": record[15].isoformat(),
        }


async def generate_lesson_content(
    owner_id: str,
    subject_id: str,
    lesson_id: str,
    interest_context: str = "normal",
    ai: Any = None,
) -> dict[str, Any]:
    """Generate and persist the grounded lesson for an existing decision.

    Reuses the established grounding path (exact sourceReferences, then RAG
    vector fallback) and the validated-LLM-output pattern. The interest lens
    only changes the narrative analogy; the technical explanation and any
    visualization stay concept-accurate.
    """
    from app.ai.service import AIService
    from app.services import concepts as concepts_service
    from app.services import diagnoses as diagnoses_service
    from app.services import answers as answers_service
    from app.services.concept_context import get_concept_chunks

    interest_context = _validate_interest(interest_context)

    lesson = await get_lesson(owner_id, lesson_id)
    if lesson is None:
        return {"status": "LESSON_NOT_FOUND", "lessonId": lesson_id}
    if lesson["status"] == "COMPLETED":
        return {"status": "LESSON_COMPLETED", "lessonId": lesson_id}

    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == lesson["conceptId"]:
            concept = c
            break
    if concept is None:
        return {"status": "CONCEPT_NOT_FOUND", "lessonId": lesson_id}

    chunks = await get_concept_chunks(owner_id, subject_id, concept)

    concepts = await concepts_service.list_concepts(subject_id)
    topic_names = [c.get("name") for c in concepts if c.get("name")]
    topic_context = (
        "Related concepts in this subject: " + ", ".join(topic_names)
        if topic_names
        else ""
    )

    student_answers = ""
    diagnosis = await diagnoses_service.get_diagnosis_by_id(
        owner_id, lesson["diagnosisId"]
    ) if lesson.get("diagnosisId") else None
    if diagnosis:
        answers = await answers_service.list_answers_for_session(
            owner_id, diagnosis["sessionId"]
        )
        lines = []
        for a in answers:
            flag = "correct" if a["correctness"] else "WRONG"
            chosen = a.get("selectedOptionId") or a.get("response") or ""
            lines.append(
                f"- {flag}; chose: {chosen}; reasoning: {(a.get('reasoning') or '')[:400]}"
            )
        if lines:
            student_answers = "\n".join(lines)

    service = ai or AIService()
    generated = await service.generate_lesson(
        concept,
        root_cause=lesson["rootCause"],
        teaching_action=lesson["teachingAction"],
        teaching_strategy=lesson["teachingStrategy"],
        interest=interest_context,
        chunks=chunks,
        topic_context=topic_context,
        student_answers=student_answers,
    )

    available = {c["chunkIndex"] for c in chunks}
    generated.sourceChunks = [c for c in generated.sourceChunks if c in available]

    source_refs = [{"chunkIndex": ci} for ci in generated.sourceChunks]
    analogy = generated.analogy.model_dump() if generated.analogy else None
    persisted = await _save_lesson_content(
        owner_id, lesson_id, generated.explanation, source_refs, interest_context,
        visualization_spec=generated.visualizationSpec,
    )
    if persisted is None:
        return {"status": "LESSON_ERROR", "lessonId": lesson_id}

    from app.services import learning_events as events_service

    await events_service.append_event(
        owner_id, lesson["subjectId"], "LESSON_CONTENT_READY",
        entity_type="lesson", entity_id=lesson_id,
        metadata={
            "conceptId": lesson["conceptId"],
            "rootCause": lesson["rootCause"],
            "strategy": lesson["teachingStrategy"],
            "interestContext": interest_context,
            "sourceChunkCount": len(source_refs),
        },
    )

    return {
        "status": "OK",
        "lessonId": lesson_id,
        "conceptId": lesson["conceptId"],
        "rootCause": lesson["rootCause"],
        "teachingAction": lesson["teachingAction"],
        "teachingStrategy": lesson["teachingStrategy"],
        "attempt": lesson["attempt"],
        "interestContext": interest_context,
        "explanation": generated.explanation,
        "keyPoints": generated.keyPoints,
        "analogy": analogy,
        "sourceChunks": generated.sourceChunks,
        "sourceReferences": source_refs,
        "visualizationSpec": generated.visualizationSpec,
    }


async def _save_lesson_content(
    owner_id: str,
    lesson_id: str,
    explanation: str,
    source_refs: list[dict],
    interest_context: str,
    visualization_spec: dict | None = None,
) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            UPDATE public.lessons l
            SET explanation = %s,
                source_references = %s,
                interest_context = %s,
                visualization_spec = %s,
                updated_at = now()
            FROM public.subjects s
            WHERE l.id = %s AND s.id = l.subject_id AND s.owner_id = %s
            RETURNING l.id, l.updated_at
            """,
            (explanation, Jsonb(source_refs), interest_context, Jsonb(visualization_spec or {}), lesson_id, owner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {"id": str(record[0]), "updatedAt": record[1].isoformat()}


async def clarify_doubt(
    owner_id: str,
    subject_id: str,
    lesson_id: str,
    question: str,
    ai: Any = None,
) -> dict[str, Any]:
    """Answer a lesson doubt strictly from RAG-retrieved chunks.

    Pure clarification: it never mutates the learner model, mastery, or
    misconceptions. If no relevant chunk is found, the hard RAG guard forces
    covered=False.
    """
    from app.ai.service import AIService
    from app.rag.retriever import retrieve
    from app.services import concepts as concepts_service

    question = question.strip()
    if not question:
        raise ValueError("Question must not be empty")

    lesson = await get_lesson(owner_id, lesson_id)
    if lesson is None:
        return {"status": "LESSON_NOT_FOUND", "lessonId": lesson_id}

    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == lesson["conceptId"]:
            concept = c
            break
    if concept is None:
        return {"status": "CONCEPT_NOT_FOUND", "lessonId": lesson_id}

    chunks = await retrieve(owner_id, subject_id, question, top_k=4)
    if not chunks:
        return {
            "status": "OK",
            "lessonId": lesson_id,
            "conceptId": lesson["conceptId"],
            "answer": "I could not find that in your material.",
            "covered": False,
            "sourceChunks": [],
            "disclaimer": "Your uploaded material does not appear to cover this.",
        }

    service = ai or AIService()
    clarification = await service.clarify_doubt(concept, question, chunks)
    available = {c["chunkIndex"] for c in chunks}
    clarification.sourceChunks = [c for c in clarification.sourceChunks if c in available]
    if not clarification.covered:
        clarification.disclaimer = (
            clarification.disclaimer or "Your uploaded material does not appear to cover this."
        )

    return {
        "status": "OK",
        "lessonId": lesson_id,
        "conceptId": lesson["conceptId"],
        "answer": clarification.answer,
        "covered": clarification.covered,
        "sourceChunks": clarification.sourceChunks,
        "disclaimer": clarification.disclaimer,
    }