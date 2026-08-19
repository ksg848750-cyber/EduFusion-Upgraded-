"""Unit tests for the M4 deterministic evidence analysis engine (doc3)."""

from app.services.diagnostic_analysis import (
    AMBIGUOUS,
    CONFIDENT,
    NO_ISSUE,
    analyze_evidence,
    differentiation_target,
)


def _ev(correct, quality="PARTIAL", signals=None, mc=None):
    return {
        "questionId": "q1",
        "correct": correct,
        "reasoningQuality": quality,
        "evidenceSignals": signals or [],
        "misconception": mc,
    }


def _mc(category, confidence, statement="s"):
    return {"category": category, "statement": statement, "confidence": confidence}


# ---- NO_ISSUE -----------------------------------------------------------------

def test_all_correct_is_no_issue():
    decision = analyze_evidence([
        _ev(True, "SOLID", ["A_CORRECT"]),
        _ev(True, "SOLID", ["B_CORRECT"]),
    ])
    assert decision["status"] == NO_ISSUE
    assert decision["rootCause"] is None


# ---- CONFIDENT -----------------------------------------------------------------

def test_single_dominant_misconception_is_confident():
    decision = analyze_evidence([
        _ev(False, "POOR", ["USES_ARRIVAL"], mc=_mc("MISCONCEPTION", 0.8)),
        _ev(False, "POOR", ["USES_ARRIVAL"], mc=_mc("MISCONCEPTION", 0.7)),
    ])
    assert decision["status"] == CONFIDENT
    assert decision["rootCause"] == "MISCONCEPTION"
    assert decision["confidence"] == 0.8 + 0.7


def test_confident_requires_threshold():
    # Single hypothesis below 0.75 -> not confident (wrong answer alone is not
    # a misconception; doc3 rule 1).
    decision = analyze_evidence([
        _ev(False, "POOR", ["USES_ARRIVAL"], mc=_mc("MISCONCEPTION", 0.6)),
    ])
    assert decision["status"] == AMBIGUOUS
    assert decision["rootCause"] is None


def test_confident_requires_clear_margin():
    # Top clears threshold but runner-up is too close -> ambiguous.
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc=_mc("MISSING_PREREQUISITE", 0.8)),
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.75)),
    ])
    assert decision["status"] == AMBIGUOUS


# ---- AMBIGUOUS -----------------------------------------------------------------

def test_wrong_answer_alone_is_not_misconception():
    decision = analyze_evidence([_ev(False, "POOR", ["SLIP"])])
    assert decision["status"] == AMBIGUOUS
    assert decision["rootCause"] is None
    assert decision["statement"]


def test_low_confidence_hypotheses_ignored():
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.3)),
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.2)),
    ])
    assert decision["status"] == AMBIGUOUS
    assert decision["rootCause"] is None


def test_invalid_category_ignored():
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc={"category": "BOGUS", "statement": "x", "confidence": 0.9}),
    ])
    assert decision["status"] == AMBIGUOUS
    assert decision["rootCause"] is None


# ---- differentiation target ----------------------------------------------------

def test_differentiation_target_from_two_hypotheses():
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc=_mc("MISSING_PREREQUISITE", 0.8)),
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.75)),
    ])
    target = differentiation_target(decision)
    assert target is not None
    assert target["hypothesisA"] == "MISSING_PREREQUISITE"
    assert target["hypothesisB"] == "MISCONCEPTION"


def test_differentiation_target_none_when_single_hypothesis():
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.6)),
    ])
    assert differentiation_target(decision) is None


def test_differentiation_target_none_when_confident():
    decision = analyze_evidence([
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.8)),
        _ev(False, "POOR", [], mc=_mc("MISCONCEPTION", 0.7)),
    ])
    assert differentiation_target(decision) is None


# ---- signal union --------------------------------------------------------------

def test_evidence_signals_are_deduplicated():
    decision = analyze_evidence([
        _ev(False, "POOR", ["USES_ARRIVAL"], mc=_mc("MISCONCEPTION", 0.8)),
        _ev(False, "POOR", ["USES_ARRIVAL", "FORGETS_SEEK"], mc=_mc("MISCONCEPTION", 0.7)),
    ])
    assert decision["evidenceSignals"] == ["USES_ARRIVAL", "FORGETS_SEEK"]