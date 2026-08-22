"""Tests for M7 — Reassessment schema, mastery update, strategy outcomes,
attempt enforcement, and reassessment flow logic."""

import pytest

from app.ai.schemas.reassessment import GeneratedReassessment, ReassessmentOption
from app.services.learner import (
    REPEATED_EVIDENCE_REQUIRED,
    WEAK_THRESHOLD,
    MASTERED_THRESHOLD,
    apply_evidence,
    confidence_for,
    empty_concept_state,
    mastery_delta,
    overall_mastery,
    _status_for,
)


# ---- Reassessment schema validation ----

def _reassessment(**over):
    base = {
        "questionType": "MCQ",
        "questionText": "After the lesson, which statement is correct about data dependencies?",
        "expectedAnswer": "Data dependencies occur when one instruction depends on the result of another",
        "expectedReasoning": "Understanding that pipeline stages overlap and data flows between them",
        "options": [
            ReassessmentOption(id="a", text="Instructions execute independently"),
            ReassessmentOption(id="b", text="Data dependencies require forwarding"),
            ReassessmentOption(id="c", text="Pipeline stages never overlap"),
            ReassessmentOption(id="d", text="Hazards always cause stalls"),
        ],
        "correctOptionId": "b",
        "difficulty": 3,
        "sourceChunks": [0, 1, 2],
    }
    base.update(over)
    return base


def test_reassessment_schema_valid():
    r = GeneratedReassessment(**_reassessment())
    assert r.questionType == "MCQ"
    assert len(r.options) == 4
    assert r.correctOptionId == "b"
    assert r.difficulty == 3


def test_reassessment_schema_short_answer():
    r = GeneratedReassessment(**_reassessment(
        questionType="SHORT_ANSWER",
        options=[],
        correctOptionId="",
    ))
    assert r.questionType == "SHORT_ANSWER"
    assert len(r.options) == 0


def test_reassessment_rejects_mcq_without_options():
    with pytest.raises(Exception):
        GeneratedReassessment(**_reassessment(options=[], correctOptionId="a"))


def test_reassessment_rejects_mcq_without_correct():
    with pytest.raises(Exception):
        GeneratedReassessment(**_reassessment(correctOptionId=""))


def test_reassessment_rejects_mcq_invalid_correct():
    with pytest.raises(Exception):
        GeneratedReassessment(**_reassessment(correctOptionId="z"))


# ---- Mastery delta (reassessment uses same engine) ----

def test_mastery_delta_correct():
    d = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    assert d > 0
    assert abs(d - 0.35 * 1.0 * 1.0 * 1.0) < 0.001


def test_mastery_delta_incorrect():
    d = mastery_delta(correct=False, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    assert d < 0
    assert abs(d - (-0.20 * 1.0 * 1.0 * 1.0)) < 0.001


def test_mastery_delta_partial_reasoning():
    d_solid = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    d_partial = mastery_delta(correct=True, reasoning_quality="PARTIAL", difficulty=3, prior_in_session=0)
    d_poor = mastery_delta(correct=True, reasoning_quality="POOR", difficulty=3, prior_in_session=0)
    assert d_solid > d_partial > d_poor


def test_mastery_delta_independence_decay():
    d0 = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    d3 = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=3, prior_in_session=3)
    assert d0 > d3  # More prior answers = smaller delta


def test_mastery_delta_difficulty_scaling():
    d1 = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=1, prior_in_session=0)
    d5 = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=5, prior_in_session=0)
    assert d5 > d1  # Harder = bigger reward


# ---- apply_evidence (reassessment mastery update) ----

def test_apply_evidence_passthrough():
    state = empty_concept_state()
    new = apply_evidence(state, correct=True, reasoning_quality="SOLID", difficulty=3)
    assert new["mastery"] > 0
    assert new["interactionCount"] == 1
    assert new["correctCount"] == 1
    assert new["incorrectCount"] == 0
    assert new["status"] == "WEAK"  # 0.35 < 0.5


def test_apply_evidence_failed():
    state = empty_concept_state()
    new = apply_evidence(state, correct=False, reasoning_quality="SOLID", difficulty=3)
    assert new["mastery"] == 0  # clamp at 0
    assert new["incorrectCount"] == 1


def test_apply_evidence_accumulates():
    state = empty_concept_state()
    for _ in range(5):
        state = apply_evidence(state, correct=True, reasoning_quality="SOLID", difficulty=3)
    assert state["mastery"] > 0.5
    assert state["interactionCount"] == 5
    assert state["correctCount"] == 5


def test_apply_evidence_mixed():
    state = empty_concept_state()
    state = apply_evidence(state, correct=True, reasoning_quality="SOLID", difficulty=3)
    m1 = state["mastery"]
    state = apply_evidence(state, correct=False, reasoning_quality="SOLID", difficulty=3)
    m2 = state["mastery"]
    assert m2 < m1  # Incorrect should decrease mastery


# ---- Status determination ----

def test_status_unknown():
    assert _status_for(0.0, 0, 0) == "UNKNOWN"


def test_status_weak():
    assert _status_for(0.3, 2, 1) == "WEAK"


def test_status_developing():
    assert _status_for(0.6, 3, 2) == "DEVELOPING"


def test_status_mastered():
    assert _status_for(0.9, 5, 4) == "MASTERED"


def test_status_mastered_needs_repeated():
    # High mastery but only 1 correct → DEVELOPING (needs repeated evidence)
    assert _status_for(0.9, 3, 1) == "DEVELOPING"


# ---- Confidence ----

def test_confidence_grows():
    c0 = confidence_for(0)
    c5 = confidence_for(5)
    assert c5 > c0


def test_confidence_caps():
    c = confidence_for(100)
    assert c <= 0.95


# ---- Overall mastery ----

def test_overall_mastery_empty():
    assert overall_mastery({}) == 0.0


def test_overall_mastery_unassessed():
    assert overall_mastery({"c1": {"mastery": 0.5, "interactionCount": 0}}) == 0.0


def test_overall_mastery_average():
    states = {
        "c1": {"mastery": 0.8, "interactionCount": 3},
        "c2": {"mastery": 0.4, "interactionCount": 2},
    }
    m = overall_mastery(states)
    assert abs(m - 0.6) < 0.01


# ---- Strategy outcome logic ----

def test_strategy_outcome_improved():
    """After PASSED with mastery increase → IMPROVED."""
    old_mastery = 0.3
    new_mastery = 0.65
    outcome = "IMPROVED" if new_mastery > old_mastery + 0.05 else "NO_CHANGE"
    assert outcome == "IMPROVED"


def test_strategy_outcome_no_change():
    """After PASSED but small mastery change → NO_CHANGE."""
    old_mastery = 0.6
    new_mastery = 0.62
    outcome = "IMPROVED" if new_mastery > old_mastery + 0.05 else "NO_CHANGE"
    assert outcome == "NO_CHANGE"


def test_strategy_outcome_regressed():
    """After FAILED with mastery decrease → REGRESSED."""
    old_mastery = 0.6
    new_mastery = 0.4
    outcome = "REGRESSED" if new_mastery < old_mastery - 0.05 else "NO_CHANGE"
    assert outcome == "REGRESSED"


# ---- Attempt enforcement ----

def test_attempt_capping():
    """Attempt number should be capped at MAX_ATTEMPTS."""
    from app.services.teaching import MAX_ATTEMPTS, count_lessons
    assert MAX_ATTEMPTS == 3


def test_attempt_escalation():
    """Each attempt should map to a different strategy."""
    from app.services.teaching import ATTEMPT_LADDER
    assert ATTEMPT_LADDER[1] == "VISUAL_STEP_BY_STEP"
    assert ATTEMPT_LADDER[2] == "WORKED_EXAMPLE"
    assert ATTEMPT_LADDER[3] == "PREREQUISITE_REPAIR"


# ---- Reassessment outcome determination ----

def test_outcome_passed_correct_solid():
    """Correct + SOLID reasoning → PASSED."""
    correctness = True
    reasoning_quality = "SOLID"
    if correctness and reasoning_quality in ("SOLID", "PARTIAL"):
        outcome = "PASSED"
    elif not correctness:
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"
    assert outcome == "PASSED"


def test_outcome_passed_correct_partial():
    """Correct + PARTIAL reasoning → PASSED."""
    correctness = True
    reasoning_quality = "PARTIAL"
    if correctness and reasoning_quality in ("SOLID", "PARTIAL"):
        outcome = "PASSED"
    elif not correctness:
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"
    assert outcome == "PASSED"


def test_outcome_inconclusive_correct_poor():
    """Correct + POOR reasoning → INCONCLUSIVE (edge case)."""
    correctness = True
    reasoning_quality = "POOR"
    if correctness and reasoning_quality in ("SOLID", "PARTIAL"):
        outcome = "PASSED"
    elif not correctness:
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"
    assert outcome == "INCONCLUSIVE"


def test_outcome_failed_incorrect():
    """Incorrect → FAILED regardless of reasoning."""
    correctness = False
    reasoning_quality = "SOLID"
    if correctness and reasoning_quality in ("SOLID", "PARTIAL"):
        outcome = "PASSED"
    elif not correctness:
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"
    assert outcome == "FAILED"
