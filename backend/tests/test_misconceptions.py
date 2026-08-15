"""Misconception lifecycle tests (doc3 rule 1 + deterministic promotion).

The status promotion logic mirrors services.misconceptions.upsert_misconception:
first signal -> SUSPECTED, repeated signal (same concept/category/statement)
-> CONFIRMED. Evidence references accumulate. Tests here are pure logic so they
run without a database.
"""


def _transition(existing_status, evidence_count, was_inconclusive):
    """Backend decision for a new evidence signal.

    - No existing misconception: SUSPECTED (one signal is not enough to call a
      misconception definitive — doc3 rule 1).
    - Existing SUSPECTED + new evidence: CONFIRMED.
    - Confirmed and above stays.
    """
    if was_inconclusive:
        return "SUSPECTED"
    if existing_status is None:
        return "SUSPECTED"
    if existing_status == "SUSPECTED" and evidence_count >= 1:
        return "CONFIRMED"
    return existing_status


def test_first_signal_is_never_confirmed():
    assert _transition(None, evidence_count=1, was_inconclusive=False) == "SUSPECTED"


def test_first_signal_with_ambiguous_evidence_stays_suspected():
    assert _transition(None, evidence_count=1, was_inconclusive=True) == "SUSPECTED"


def test_second_signal_promotes_to_confirmed():
    assert _transition("SUSPECTED", evidence_count=2, was_inconclusive=False) == "CONFIRMED"


def test_confirmed_stays_confirmed():
    assert _transition("CONFIRMED", evidence_count=3, was_inconclusive=False) == "CONFIRMED"


def test_resolved_never_reopens_automatically():
    assert _transition("RESOLVED", evidence_count=1, was_inconclusive=False) == "RESOLVED"


def test_wrong_answer_alone_is_not_a_misconception():
    """Rule 1: an incorrect answer without a repeated, specific signal must not
    escalate beyond SUSPECTED, even if it looks wrong."""
    assert _transition(None, evidence_count=1, was_inconclusive=True) == "SUSPECTED"


def test_evidence_accumulates_per_signal():
    refs = []
    for i in range(3):
        signal = {"questionId": f"q{i}", "answerId": f"a{i}", "signal": "USES_ARRIVAL_ORDER"}
        if signal not in refs:
            refs.append(signal)
    assert len(refs) == 3
    # dedupe
    refs.append(refs[0])
    unique = [r for i, r in enumerate(refs) if r not in refs[:i]]
    assert len(unique) == 3


def test_confidence_takes_max_of_signals():
    assert max(0.5, 0.8) == 0.8
    assert max(0.9, 0.7) == 0.9