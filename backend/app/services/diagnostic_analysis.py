"""M4 Diagnostic Reasoning Engine — deterministic evidence analysis (doc3).

This module is the deterministic heart of the diagnostic flow. Given the
evidence collected across a diagnostic session (correctness + reasoning
quality + evaluator misconception hypotheses), it decides whether a root
cause is confidently established, whether a targeted probe is required, or
whether the evidence is insufficient.

Rules grounded in doc3:
  - A wrong answer is NEVER automatically a misconception.
  - A hypothesis only counts when the evaluator attached real confidence.
  - A root cause is CONFIDENT only when a single category clears the
    conclusive threshold by a clear margin.
  - Otherwise the flow is AMBIGUOUS -> generate a targeted probe.
  - After a probe, if still ambiguous -> INSUFFICIENT_EVIDENCE.
"""

from typing import Any

# Canonical root-cause taxonomy (AGENTS.md §5 + DB CHECK in 004/007).
ROOT_CAUSES: tuple[str, ...] = (
    "MISSING_PREREQUISITE",
    "MISCONCEPTION",
    "PROCEDURAL_ERROR",
    "TERMINOLOGY_CONFUSION",
    "REPRESENTATION_PROBLEM",
    "INSUFFICIENT_EVIDENCE",
)

# doc3: conclusive diagnosis threshold.
CONFIDENT_THRESHOLD = 0.75
# A hypothesis must clear this to be considered real evidence at all.
MIN_HYPOTHESIS_CONFIDENCE = 0.5
# Margin the top category must hold over the runner-up to be conclusive.
MIN_CONFIDENT_MARGIN = 0.15

# Analysis outcomes.
CONFIDENT = "CONFIDENT"
AMBIGUOUS = "AMBIGUOUS"
NO_ISSUE = "NO_ISSUE"


def analyze_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify session evidence into a diagnostic decision.

    Each evidence dict:
      {
        "questionId": str,
        "correct": bool,
        "reasoningQuality": "POOR"|"PARTIAL"|"SOLID",
        "evidenceSignals": [str, ...],
        "misconception": {"category","statement","confidence"} | None,
      }

    Returns:
      {
        "status": "CONFIDENT"|"AMBIGUOUS"|"NO_ISSUE",
        "rootCause": category | None,
        "confidence": float,          # total confidence of the winning cause
        "statement": str,             # synthesized statement
        "evidenceSignals": [str,...], # union of signals from decisive evidence
        "hypotheses": [ {category, statement, confidence, support} ... ],
      }
    """
    incorrect = [e for e in evidence if not bool(e.get("correct", False))]
    if not incorrect:
        return {
            "status": NO_ISSUE,
            "rootCause": None,
            "confidence": 0.0,
            "statement": "The learner answered all diagnostic items correctly.",
            "evidenceSignals": _union_signals(evidence),
            "hypotheses": [],
        }

    tally: dict[str, dict[str, Any]] = {}
    for e in incorrect:
        h = e.get("misconception") or {}
        category = h.get("category")
        confidence = float(h.get("confidence") or 0.0)
        if category not in ROOT_CAUSES or confidence < MIN_HYPOTHESIS_CONFIDENCE:
            continue
        bucket = tally.setdefault(
            category,
            {"category": category, "confidence": 0.0, "statement": "",
             "evidenceSignals": [], "support": 0},
        )
        bucket["confidence"] += confidence
        bucket["support"] += 1
        if not bucket["statement"] and h.get("statement"):
            bucket["statement"] = h["statement"]
        bucket["evidenceSignals"].extend(e.get("evidenceSignals") or [])

    if not tally:
        return {
            "status": AMBIGUOUS,
            "rootCause": None,
            "confidence": 0.0,
            "statement": (
                "The learner answered incorrectly but no systematic root cause "
                "could be attributed to the errors."
            ),
            "evidenceSignals": _union_signals(evidence),
            "hypotheses": [],
        }

    ranked = sorted(
        tally.values(),
        key=lambda b: (b["confidence"], b["support"], b["category"]),
        reverse=True,
    )
    top = ranked[0]
    runner_up = ranked[1]["confidence"] if len(ranked) > 1 else 0.0
    decisive = top["confidence"] >= CONFIDENT_THRESHOLD
    clear_margin = top["confidence"] - runner_up >= MIN_CONFIDENT_MARGIN

    if decisive and clear_margin:
        return {
            "status": CONFIDENT,
            "rootCause": top["category"],
            "confidence": round(top["confidence"], 3),
            "statement": top["statement"],
            "evidenceSignals": _dedupe(top["evidenceSignals"]),
            "hypotheses": [_hypothesis(b) for b in ranked[:2]],
        }

    return {
        "status": AMBIGUOUS,
        "rootCause": None,
        "confidence": round(top["confidence"], 3),
        "statement": (
            "Evidence points to more than one plausible root cause; a targeted "
            "probe is required to disambiguate."
        ),
        "evidenceSignals": _union_signals(evidence),
        "hypotheses": [_hypothesis(b) for b in ranked[:2]],
    }


def _hypothesis(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": bucket["category"],
        "statement": bucket["statement"],
        "confidence": round(bucket["confidence"], 3),
        "support": bucket["support"],
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _union_signals(evidence: list[dict[str, Any]]) -> list[str]:
    signals: list[str] = []
    for e in evidence:
        signals.extend(e.get("evidenceSignals") or [])
    return _dedupe(signals)


def differentiation_target(decision: dict[str, Any]) -> dict[str, Any] | None:
    """Build the probe differentiation target from an ambiguous decision.

    Uses the top two hypotheses as the two poles the probe must distinguish.
    Returns None when fewer than two hypotheses are available.
    """
    hypotheses = decision.get("hypotheses") or []
    if len(hypotheses) < 2:
        return None
    a, b = hypotheses[:2]
    return {
        "hypothesisA": a["category"],
        "hypothesisB": b["category"],
        "hypothesisAStatement": a.get("statement", ""),
        "hypothesisBStatement": b.get("statement", ""),
    }