from app.services.learner import (
    apply_evidence,
    confidence_for,
    empty_concept_state,
    mastery_delta,
    overall_mastery,
)


def test_mastery_delta_correct_solid_mid_difficulty():
    d = mastery_delta(correct=True, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    assert d == 0.35


def test_mastery_delta_incorrect_solid():
    d = mastery_delta(correct=False, reasoning_quality="SOLID", difficulty=3, prior_in_session=0)
    assert d == -0.20


def test_mastery_delta_reasoning_scales_credit():
    solid = mastery_delta(True, "SOLID", 3, 0)
    partial = mastery_delta(True, "PARTIAL", 3, 0)
    poor = mastery_delta(True, "POOR", 3, 0)
    assert solid > partial > poor
    assert poor == 0.35 * 0.5


def test_mastery_delta_difficulty_modifier():
    easy = mastery_delta(True, "SOLID", 1, 0)
    hard = mastery_delta(True, "SOLID", 5, 0)
    assert easy < hard


def test_mastery_delta_independence_factor_decays():
    first = mastery_delta(True, "SOLID", 3, 0)
    second = mastery_delta(True, "SOLID", 3, 1)
    third = mastery_delta(True, "SOLID", 3, 2)
    assert first > second > third
    assert round(second, 10) == round(first * 0.85, 10)


def test_apply_evidence_clamps_to_zero_and_one():
    state = {"mastery": 0.99, "interactionCount": 5, "correctCount": 5,
             "incorrectCount": 0, "confidence": 0.9, "lastAssessedAt": "x"}
    after = apply_evidence(state, True, "SOLID", 3, 0)
    assert after["mastery"] <= 1.0
    assert after["interactionCount"] == 6
    assert after["correctCount"] == 6


def test_apply_evidence_from_empty():
    s = apply_evidence(empty_concept_state(), True, "SOLID", 3, 0)
    assert s["status"] == "WEAK"  # 0.35 < 0.50 threshold
    assert s["mastery"] == 0.35
    assert s["interactionCount"] == 1
    assert s["correctCount"] == 1


def test_status_mapping_weak_developing_mastered():
    weak = apply_evidence(empty_concept_state(), False, "SOLID", 5, 0)
    assert weak["status"] == "WEAK"
    # two correct SOLID -> DEVELOPING; needs repeated evidence for MASTERED
    s1 = apply_evidence(empty_concept_state(), True, "SOLID", 3, 0)
    s2 = apply_evidence(s1, True, "SOLID", 3, 1)
    assert s2["status"] == "DEVELOPING"
    assert s2["mastery"] >= 0.35


def test_status_unknown_before_interaction():
    assert empty_concept_state()["status"] == "UNKNOWN"


def test_confidence_rises_with_interaction():
    assert confidence_for(0) == 0.4
    assert confidence_for(1) == 0.52
    assert confidence_for(10) == 0.95
    assert confidence_for(100) == 0.95


def test_overall_mastery_ignores_unassessed():
    states = {
        "a": {"mastery": 0.6, "interactionCount": 2},
        "b": {"mastery": 0.0, "interactionCount": 0},
        "c": {"mastery": 0.4, "interactionCount": 1},
    }
    assert overall_mastery(states) == 0.5
    assert overall_mastery({}) == 0.0


def test_incorrect_answer_reduces_mastery():
    s = apply_evidence(empty_concept_state(), False, "SOLID", 3, 0)
    assert s["mastery"] == 0.0  # clamped at zero
    assert s["incorrectCount"] == 1
    # A previous positive mastery should drop
    s1 = apply_evidence(empty_concept_state(), True, "SOLID", 3, 0)
    s2 = apply_evidence(s1, False, "SOLID", 3, 0)
    assert s2["mastery"] == round(0.35 - 0.20, 4) == 0.15