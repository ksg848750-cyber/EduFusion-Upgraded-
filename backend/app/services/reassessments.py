"""M7 Reassessment Service — closes the adaptive loop.

After a lesson is delivered, a reassessment question verifies whether the
lesson repaired the diagnosed gap. The outcome feeds:
  - Mastery update (deterministic, via learner.py)
  - Strategy outcome recording (Decision B history)
  - Misconception resolution (if PASSED + root cause was MISCONCEPTION)
  - Attempt tracking (max 3 before PRESCRIPTIVE escalation)

Flow:
  1. generate_reassessment() → novel question targeting same root cause
  2. submit_reassessment_answer() → evaluate → PASSED/FAILED/INCONCLUSIVE
  3. update mastery + record strategy outcome + resolve misconception
"""

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection
from app.services import learner as learner_service
from app.services import learning_events as events_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_reassessment(
    owner_id: str,
    subject_id: str,
    lesson_id: str,
    question_data: dict[str, Any],
    question_id: str | None = None,
) -> dict[str, Any] | None:
    """Persist a reassessment question linked to a lesson."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            INSERT INTO public.reassessments
                (lesson_id, learner_id, subject_id, concept_id, diagnosis_id,
                 question_id, question_type, question_text, options,
                 correct_option_id, expected_answer, expected_reasoning, attempt)
            SELECT l.id, l.learner_id, l.subject_id, l.concept_id, l.diagnosis_id,
                   %s, %s, %s, %s, %s, %s, %s, l.attempt
            FROM public.lessons l
            WHERE l.id = %s AND l.learner_id = %s
            RETURNING id, lesson_id, learner_id, subject_id, concept_id,
                      diagnosis_id, question_id, question_type, question_text,
                      options, correct_option_id, expected_answer,
                      expected_reasoning, status, attempt, created_at
            """,
            (
                question_id,
                question_data.get("questionType", "REASSESSMENT"),
                question_data.get("questionText", ""),
                Jsonb(question_data.get("options", [])),
                question_data.get("correctOptionId", ""),
                question_data.get("expectedAnswer", ""),
                question_data.get("expectedReasoning", ""),
                lesson_id,
                owner_id,
            ),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "lessonId": str(record[1]),
            "learnerId": str(record[2]),
            "subjectId": str(record[3]),
            "conceptId": str(record[4]),
            "diagnosisId": str(record[5]) if record[5] else None,
            "questionId": str(record[6]) if record[6] else None,
            "questionType": record[7],
            "questionText": record[8],
            "options": record[9] or [],
            "correctOptionId": record[10],
            "expectedAnswer": record[11],
            "expectedReasoning": record[12],
            "status": record[13],
            "attempt": record[14],
            "createdAt": record[15].isoformat(),
        }


async def get_reassessment(reassessment_id: str, owner_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT r.id, r.lesson_id, r.learner_id, r.subject_id, r.concept_id,
                   r.diagnosis_id, r.question_id, r.question_type, r.question_text,
                   r.options, r.correct_option_id, r.expected_answer,
                   r.expected_reasoning, r.status, r.response, r.reasoning,
                   r.reasoning_assessment, r.correctness, r.attempt, r.created_at
            FROM public.reassessments r
            WHERE r.id = %s AND r.learner_id = %s
            """,
            (reassessment_id, owner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "lessonId": str(record[1]),
            "learnerId": str(record[2]),
            "subjectId": str(record[3]),
            "conceptId": str(record[4]),
            "diagnosisId": str(record[5]) if record[5] else None,
            "questionId": str(record[6]) if record[6] else None,
            "questionType": record[7],
            "questionText": record[8],
            "options": record[9] or [],
            "correctOptionId": record[10],
            "expectedAnswer": record[11],
            "expectedReasoning": record[12],
            "status": record[13],
            "response": record[14],
            "reasoning": record[15],
            "reasoningAssessment": record[16] or {},
            "correctness": record[17],
            "attempt": record[18],
            "createdAt": record[19].isoformat(),
        }


async def get_reassessment_by_lesson(lesson_id: str, owner_id: str) -> dict[str, Any] | None:
    """Get the latest reassessment for a lesson."""
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id FROM public.reassessments
            WHERE lesson_id = %s AND learner_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (lesson_id, owner_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return await get_reassessment(str(record[0]), owner_id)


async def submit_reassessment_answer(
    owner_id: str,
    reassessment_id: str,
    response: str,
    reasoning: str,
    correctness: bool,
    reasoning_quality: str = "PARTIAL",
    reasoning_assessment: dict | None = None,
) -> dict[str, Any] | None:
    """Evaluate and record a reassessment answer.

    Determines the reassessment outcome:
      - PASSED: correct AND reasoning is SOLID/PARTIAL
      - FAILED: incorrect OR reasoning is POOR
      - INCONCLUSIVE: correct but reasoning is very weak (edge case)

    Then triggers mastery update + strategy outcome recording.
    """
    reassessment = await get_reassessment(reassessment_id, owner_id)
    if reassessment is None or reassessment["status"] != "PENDING":
        return None

    # Determine outcome
    if correctness and reasoning_quality in ("SOLID", "PARTIAL"):
        outcome = "PASSED"
    elif not correctness:
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"

    now = _now_iso()
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            UPDATE public.reassessments
            SET status = %s, response = %s, reasoning = %s,
                reasoning_assessment = %s, correctness = %s, updated_at = %s
            WHERE id = %s AND learner_id = %s AND status = 'PENDING'
            RETURNING id, lesson_id, concept_id, subject_id, diagnosis_id, attempt
            """,
            (
                outcome, response, reasoning,
                Jsonb(reasoning_assessment or {}),
                correctness, now,
                reassessment_id, owner_id,
            ),
        )
        record = await row.fetchone()
        if record is None:
            return None

        lesson_id = str(record[1])
        concept_id = str(record[2])
        subject_id = str(record[3])
        diagnosis_id = str(record[4]) if record[4] else None
        attempt = record[5]

        # --- Mastery update (deterministic) ---
        model = await learner_service.ensure_learner_model(owner_id, subject_id)
        current_state = (model.get("conceptStates") or {}).get(concept_id)
        prior_in_session = int((current_state or {}).get("interactionCount") or 0)
        new_state = learner_service.apply_evidence(
            current_state, correctness, reasoning_quality,
            difficulty=3, prior_in_session=prior_in_session,
        )
        await learner_service.update_concept_state(
            owner_id, subject_id, concept_id, new_state,
        )

        # --- Strategy outcome recording ---
        await _record_strategy_outcome(
            owner_id, subject_id, concept_id, lesson_id, outcome, new_state,
        )

        # --- Misconception resolution ---
        if outcome == "PASSED" and diagnosis_id:
            await _resolve_misconception(owner_id, diagnosis_id)

        # --- Mark lesson as COMPLETED ---
        await conn.execute(
            "UPDATE public.lessons SET status = 'COMPLETED', updated_at = %s "
            "WHERE id = %s",
            (now, lesson_id),
        )

        # --- Log events ---
        await events_service.append_event(
            owner_id, subject_id, "REASSESSMENT_COMPLETED",
            entity_type="reassessment", entity_id=reassessment_id,
            metadata={
                "lessonId": lesson_id,
                "conceptId": concept_id,
                "outcome": outcome,
                "attempt": attempt,
                "correctness": correctness,
            },
        )
        await events_service.append_event(
            owner_id, subject_id, "MASTERY_UPDATED",
            entity_type="concept", entity_id=concept_id,
            metadata={
                "mastery": new_state["mastery"],
                "status": new_state["status"],
                "outcome": outcome,
            },
        )

    return {
        "id": reassessment_id,
        "lessonId": lesson_id,
        "conceptId": concept_id,
        "status": outcome,
        "correctness": correctness,
        "mastery": new_state["mastery"],
        "conceptStatus": new_state["status"],
        "attempt": attempt,
    }


async def _record_strategy_outcome(
    owner_id: str,
    subject_id: str,
    concept_id: str,
    lesson_id: str,
    reassessment_outcome: str,
    new_state: dict[str, Any],
) -> None:
    """Record the teaching strategy's outcome in the learner's strategy profile.

    Decision B reads this to exclude ineffective strategies and prioritize
    proven ones on future attempts.
    """
    async with connection() as conn:
        if conn is None:
            return
        row = await conn.execute(
            """
            SELECT teaching_strategy FROM public.lessons
            WHERE id = %s AND learner_id = %s
            """,
            (lesson_id, owner_id),
        )
        record = await row.fetchone()
        if record is None:
            return
        strategy = record[0]

        # Determine strategy outcome based on mastery change
        old_mastery = 0.0  # If no prior state, assume 0
        model = await learner_service.get_learner_model(owner_id, subject_id)
        if model:
            old_state = (model.get("conceptStates") or {}).get(concept_id)
            if old_state:
                old_mastery = float(old_state.get("mastery") or 0.0)

        new_mastery = float(new_state.get("mastery") or 0.0)
        if reassessment_outcome == "PASSED":
            strategy_outcome = "IMPROVED" if new_mastery > old_mastery + 0.05 else "NO_CHANGE"
        else:
            strategy_outcome = "REGRESSED" if new_mastery < old_mastery - 0.05 else "NO_CHANGE"

        # Update strategy_profile in learner_models
        await conn.execute(
            """
            UPDATE public.learner_models
            SET strategy_profile = strategy_profile || %s::jsonb,
                updated_at = now()
            WHERE user_id = %s AND subject_id = %s
            """,
            (Jsonb({concept_id: {strategy: strategy_outcome}}), owner_id, subject_id),
        )


async def _resolve_misconception(owner_id: str, diagnosis_id: str) -> None:
    """After a PASSED reassessment, resolve the misconception and diagnosis."""
    async with connection() as conn:
        if conn is None:
            return
        now = _now_iso()
        # Update diagnosis status
        await conn.execute(
            """
            UPDATE public.diagnoses
            SET status = 'RESOLVED', updated_at = %s
            WHERE id = %s AND learner_id = %s AND status IN ('OPEN', 'PERSISTENT')
            """,
            (now, diagnosis_id, owner_id),
        )
        # Update related misconceptions
        row = await conn.execute(
            """
            SELECT concept_id FROM public.diagnoses WHERE id = %s
            """,
            (diagnosis_id,),
        )
        record = await row.fetchone()
        if record:
            await conn.execute(
                """
                UPDATE public.misconceptions
                SET status = 'RESOLVED', resolved_at = %s, updated_at = %s
                WHERE learner_id = %s AND concept_id = %s
                  AND status IN ('SUSPECTED', 'CONFIRMED', 'ACTIVE')
                """,
                (now, now, owner_id, str(record[0])),
            )
