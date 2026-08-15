from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.core.database import connection

# ---- Deterministic mastery engine (M3) ----
# The LLM proposes evidence (correct/incorrect + reasoning quality); the backend
# computes every mastery delta. Never ask the LLM for a mastery percentage.

OUTCOME_WEIGHT = {"correct": 0.35, "incorrect": -0.20}
REASONING_WEIGHT = {"SOLID": 1.0, "PARTIAL": 0.7, "POOR": 0.5}
DIFFICULTY_MODIFIER = {1: 0.85, 2: 0.9, 3: 1.0, 4: 1.1, 5: 1.2}
INDEPENDENCE_DECAY = 0.85

MASTERED_THRESHOLD = 0.85
WEAK_THRESHOLD = 0.5
REPEATED_EVIDENCE_REQUIRED = 2


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def mastery_delta(correct: bool, reasoning_quality: str, difficulty: int, prior_in_session: int) -> float:
    """Evidence-weighted, deterministic mastery update for a single answer.

    ΔM = OutcomeWeight × ReasoningWeight × DifficultyModifier × IndependenceFactor
    """
    outcome = OUTCOME_WEIGHT["correct" if correct else "incorrect"]
    reasoning = REASONING_WEIGHT.get(reasoning_quality, REASONING_WEIGHT["PARTIAL"])
    difficulty_mod = DIFFICULTY_MODIFIER.get(difficulty, 1.0)
    independence = INDEPENDENCE_DECAY ** max(prior_in_session, 0)
    return outcome * reasoning * difficulty_mod * independence


def _status_for(mastery: float, interaction_count: int, correct_count: int) -> str:
    if interaction_count == 0:
        return "UNKNOWN"
    if mastery < WEAK_THRESHOLD:
        return "WEAK"
    if mastery >= MASTERED_THRESHOLD and correct_count >= REPEATED_EVIDENCE_REQUIRED:
        return "MASTERED"
    return "DEVELOPING"


def confidence_for(interaction_count: int) -> float:
    return round(min(0.95, 0.4 + 0.12 * interaction_count), 3)


def empty_concept_state() -> dict[str, Any]:
    return {
        "mastery": 0.0,
        "status": "UNKNOWN",
        "confidence": 0.0,
        "interactionCount": 0,
        "correctCount": 0,
        "incorrectCount": 0,
        "lastAssessedAt": None,
    }


def apply_evidence(
    state: dict[str, Any] | None,
    correct: bool,
    reasoning_quality: str,
    difficulty: int,
    prior_in_session: int = 0,
) -> dict[str, Any]:
    """Deterministically fold one answer's evidence into a concept state."""
    state = dict(state or empty_concept_state())
    mastery = float(state.get("mastery") or 0.0)
    delta = mastery_delta(correct, reasoning_quality, difficulty, prior_in_session)
    new_mastery = _clamp(mastery + delta)

    interaction_count = int(state.get("interactionCount") or 0) + 1
    correct_count = int(state.get("correctCount") or 0) + (1 if correct else 0)
    incorrect_count = int(state.get("incorrectCount") or 0) + (0 if correct else 1)

    return {
        "mastery": round(new_mastery, 4),
        "status": _status_for(new_mastery, interaction_count, correct_count),
        "confidence": confidence_for(interaction_count),
        "interactionCount": interaction_count,
        "correctCount": correct_count,
        "incorrectCount": incorrect_count,
        "lastAssessedAt": datetime.now(timezone.utc).isoformat(),
    }


def overall_mastery(states: dict[str, Any]) -> float:
    assessed = [float(s.get("mastery") or 0.0) for s in states.values()
                if (s.get("interactionCount") or 0) > 0]
    if not assessed:
        return 0.0
    return round(sum(assessed) / len(assessed), 4)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_learner_model(user_id: str, subject_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            SELECT id, user_id, subject_id, overall_mastery, concept_states, version,
                   created_at, updated_at
            FROM public.learner_models
            WHERE user_id = %s AND subject_id = %s
            """,
            (user_id, subject_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "userId": str(record[1]),
            "subjectId": str(record[2]),
            "overallMastery": float(record[3] or 0.0),
            "conceptStates": record[4] or {},
            "version": record[5],
            "createdAt": record[6].isoformat(),
            "updatedAt": record[7].isoformat(),
        }


async def ensure_learner_model(user_id: str, subject_id: str) -> dict[str, Any]:
    existing = await get_learner_model(user_id, subject_id)
    if existing:
        return existing
    async with connection() as conn:
        if conn is None:
            return {"id": "", "userId": user_id, "subjectId": subject_id,
                    "overallMastery": 0.0, "conceptStates": {}, "version": 1,
                    "createdAt": _now_iso(), "updatedAt": _now_iso()}
        now = _now_iso()
        row = await conn.execute(
            """
            INSERT INTO public.learner_models (user_id, subject_id, overall_mastery, concept_states, version)
            VALUES (%s, %s, 0.0, '{}'::jsonb, 1)
            ON CONFLICT (user_id, subject_id) DO NOTHING
            RETURNING id, user_id, subject_id, overall_mastery, concept_states, version,
                      created_at, updated_at
            """,
            (user_id, subject_id),
        )
        record = await row.fetchone()
        if record is None:
            return await get_learner_model(user_id, subject_id) or {
                "id": "", "userId": user_id, "subjectId": subject_id,
                "overallMastery": 0.0, "conceptStates": {}, "version": 1,
                "createdAt": now, "updatedAt": now}
        return {
            "id": str(record[0]),
            "userId": str(record[1]),
            "subjectId": str(record[2]),
            "overallMastery": float(record[3] or 0.0),
            "conceptStates": record[4] or {},
            "version": record[5],
            "createdAt": record[6].isoformat(),
            "updatedAt": record[7].isoformat(),
        }


async def update_concept_state(
    user_id: str,
    subject_id: str,
    concept_id: str,
    new_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply a new concept state to the learner model (current-state update)."""
    model = await ensure_learner_model(user_id, subject_id)
    if not model or not model.get("id"):
        return model
    states = dict(model.get("conceptStates") or {})
    states[concept_id] = new_state
    overall = overall_mastery(states)
    version = int(model.get("version") or 1) + 1
    now = _now_iso()
    async with connection() as conn:
        if conn is None:
            return None
        row = await conn.execute(
            """
            UPDATE public.learner_models
            SET concept_states = %s, overall_mastery = %s, version = %s, updated_at = %s
            WHERE user_id = %s AND subject_id = %s
            RETURNING id, overall_mastery, concept_states, version, updated_at
            """,
            (Jsonb(states), overall, version, now, user_id, subject_id),
        )
        record = await row.fetchone()
        if record is None:
            return None
        return {
            "id": str(record[0]),
            "overallMastery": float(record[1] or 0.0),
            "conceptStates": record[2],
            "version": record[3],
            "updatedAt": record[4].isoformat(),
        }


async def get_concept_state(user_id: str, subject_id: str, concept_id: str) -> dict[str, Any] | None:
    model = await get_learner_model(user_id, subject_id)
    if model is None:
        return empty_concept_state()
    state = (model.get("conceptStates") or {}).get(concept_id)
    if state is None:
        return empty_concept_state()
    return state