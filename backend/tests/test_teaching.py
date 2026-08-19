"""Tests for M5 Part 1 — the Adaptive Teaching Dual-Decision Engine (doc4)."""

import asyncio

import pytest

from app.api.v1.endpoints import teaching as teaching_module
from app.main import app
from app.services.teaching import decision_a, decision_b

OWNER = "user-1"
SUBJECT = "subj-1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---- Decision A: WHAT to teach -------------------------------------------------

def test_decision_a_maps_all_root_causes():
    expected = {
        "MISSING_PREREQUISITE": "PREREQUISITE_REPAIR",
        "MISCONCEPTION": "MENTAL_MODEL_CORRECTION",
        "PROCEDURAL_ERROR": "GUIDED_PRACTICE",
        "TERMINOLOGY_CONFUSION": "DISTINCTION_CONTRAST",
        "REPRESENTATION_PROBLEM": "REPRESENTATION_SHIFT",
        "INSUFFICIENT_EVIDENCE": "TARGETED_PROBING",
    }
    for cause, action in expected.items():
        result = decision_a(cause)
        assert result["rootCause"] == cause
        assert result["action"] == action
        assert result["reason"]


def test_decision_a_unknown_cause_raises():
    with pytest.raises(ValueError):
        decision_a("NOT_A_CAUSE")


# ---- Decision B: HOW to teach --------------------------------------------------

def test_decision_b_insufficient_evidence_returns_no_strategy():
    result = decision_b("INSUFFICIENT_EVIDENCE")
    assert result["action"] == "TARGETED_PROBING"
    assert result["strategy"] is None


def test_decision_b_default_attempt1_for_misconception():
    result = decision_b("MISCONCEPTION")
    assert result["action"] == "MENTAL_MODEL_CORRECTION"
    assert result["strategy"] == "VISUAL_STEP_BY_STEP"
    assert result["attempt"] == 1


def test_decision_b_missing_prerequisite_goes_to_prereq_repair():
    result = decision_b("MISSING_PREREQUISITE")
    assert result["action"] == "PREREQUISITE_REPAIR"
    assert result["strategy"] == "PREREQUISITE_REPAIR"


def test_decision_b_escalates_on_attempt():
    result = decision_b("MISCONCEPTION", attempt=2)
    assert result["strategy"] == "WORKED_EXAMPLE"
    result3 = decision_b("MISCONCEPTION", attempt=3)
    assert result3["attempt"] == 3


def test_decision_b_excludes_ineffective_strategy():
    profile = {"VISUAL_STEP_BY_STEP": "NO_CHANGE"}
    result = decision_b("MISCONCEPTION", strategy_profile=profile, attempt=1)
    assert result["strategy"] == "WORKED_EXAMPLE"
    assert result["excluded"] == ["VISUAL_STEP_BY_STEP"]


def test_decision_b_prioritizes_improved_strategy():
    # attempt 3 ladder (PREREQUISITE_REPAIR) is not a candidate for GUIDED_PRACTICE,
    # so the selector falls back to the first eligible — and IMPROVED wins.
    profile = {"INTERACTIVE_EXPLANATION": "IMPROVED"}
    result = decision_b("PROCEDURAL_ERROR", strategy_profile=profile, attempt=3)
    assert result["strategy"] == "INTERACTIVE_EXPLANATION"


def test_decision_b_no_viable_strategy_returns_none():
    profile = {
        "VISUAL_STEP_BY_STEP": "REGRESSED",
        "WORKED_EXAMPLE": "REGRESSED",
        "INTERACTIVE_EXPLANATION": "REGRESSED",
    }
    result = decision_b("MISCONCEPTION", strategy_profile=profile, attempt=1)
    assert result["strategy"] is None
    assert result["excluded"] == sorted(profile.keys())


# ---- compute_teaching_decision orchestration -----------------------------------

def _session(**o):
    base = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward",
            "status": "IN_PROGRESS"}
    base.update(o)
    return base


def _diagnosis(**o):
    base = {"id": "diag-1", "learnerId": OWNER, "subjectId": SUBJECT,
            "conceptId": "c-forward", "rootCause": "MISCONCEPTION",
            "confidence": 0.9, "status": "OPEN"}
    base.update(o)
    return base


def test_compute_teaching_decision_ok(monkeypatch):
    from app.services import teaching as teaching_service
    from app.services import concepts as concepts_service
    from app.services import diagnoses as diagnoses_service
    from app.services import learner as learner_service
    from app.services import sessions as sessions_service

    async def fake_session(owner, sid):
        return _session()

    async def fake_diagnosis(owner, sid):
        return _diagnosis()

    async def fake_concepts(subject_id):
        return [{"id": "c-forward", "name": "Forwarding", "canonicalName": "forwarding"}]

    async def fake_count(owner, subject, concept):
        return 0

    async def fake_profile(owner, subject):
        return {}

    async def fake_record(owner, subject, diagnosis_id, concept_id, root_cause, decision, interest_context="normal"):
        return {"id": "lesson-1", "learnerId": OWNER, "subjectId": SUBJECT,
                "diagnosisId": diagnosis_id, "conceptId": concept_id,
                "rootCause": root_cause, "teachingAction": decision["action"],
                "teachingStrategy": decision["strategy"], "interestContext": interest_context,
                "attempt": decision["attempt"], "status": "DELIVERED"}

    monkeypatch.setattr(sessions_service, "get_session", fake_session)
    monkeypatch.setattr(diagnoses_service, "get_diagnosis_by_session", fake_diagnosis)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_concepts)
    monkeypatch.setattr(teaching_service, "count_lessons", fake_count)
    monkeypatch.setattr(learner_service, "get_strategy_profile", fake_profile)
    monkeypatch.setattr(teaching_service, "record_lesson", fake_record)

    result = _run(teaching_service.compute_teaching_decision(OWNER, SUBJECT, "sess-1"))
    assert result["status"] == "OK"
    assert result["lessonId"] == "lesson-1"
    assert result["rootCause"] == "MISCONCEPTION"
    assert result["action"] == "MENTAL_MODEL_CORRECTION"
    assert result["teachingStrategy"] == "VISUAL_STEP_BY_STEP"
    assert result["attempt"] == 1


def test_compute_teaching_decision_no_diagnosis(monkeypatch):
    from app.services import diagnoses as diagnoses_service
    from app.services import teaching as teaching_service
    from app.services import sessions as sessions_service

    async def fake_session(owner, sid):
        return _session()

    async def fake_none(owner, sid):
        return None

    monkeypatch.setattr(sessions_service, "get_session", fake_session)
    monkeypatch.setattr(diagnoses_service, "get_diagnosis_by_session", fake_none)

    result = _run(teaching_service.compute_teaching_decision(OWNER, SUBJECT, "sess-1"))
    assert result["status"] == "NO_DIAGNOSIS"


# ---- endpoint -------------------------------------------------------------------

def test_teaching_decision_endpoint_ok(client, monkeypatch):
    async def fake_owner(auth_user_id):
        return OWNER

    async def fake_subject(owner_id, subject_id):
        return {"id": subject_id, "ownerId": owner_id, "name": "CA"}

    async def fake_compute(owner, subject, session_id, interest_context="normal"):
        return {
            "status": "OK", "lessonId": "lesson-1", "sessionId": session_id,
            "diagnosisId": "diag-1", "conceptId": "c-forward",
            "conceptName": "Forwarding", "rootCause": "MISCONCEPTION",
            "action": "MENTAL_MODEL_CORRECTION", "reason": "attempt 1 default strategy",
            "teachingStrategy": "VISUAL_STEP_BY_STEP", "attempt": 1,
            "excluded": [], "interestContext": interest_context,
        }

    monkeypatch.setattr(teaching_module.users_service, "get_user_id_by_auth", fake_owner)
    monkeypatch.setattr(teaching_module.subjects_service, "get_subject", fake_subject)
    monkeypatch.setattr(teaching_module, "compute_teaching_decision", fake_compute)

    resp = client.post(f"/api/v1/subjects/{SUBJECT}/teaching-decision",
                       json={"sessionId": "sess-1", "interestContext": "cricket"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OK"
    assert body["teachingStrategy"] == "VISUAL_STEP_BY_STEP"
    assert body["interestContext"] == "cricket"


def test_teaching_decision_endpoint_no_diagnosis_404(client, monkeypatch):
    async def fake_owner(auth_user_id):
        return OWNER

    async def fake_subject(owner_id, subject_id):
        return {"id": subject_id, "ownerId": owner_id, "name": "CA"}

    async def fake_compute(owner, subject, session_id, interest_context="normal"):
        return {"status": "NO_DIAGNOSIS", "sessionId": session_id}

    monkeypatch.setattr(teaching_module.users_service, "get_user_id_by_auth", fake_owner)
    monkeypatch.setattr(teaching_module.subjects_service, "get_subject", fake_subject)
    monkeypatch.setattr(teaching_module, "compute_teaching_decision", fake_compute)

    resp = client.post(f"/api/v1/subjects/{SUBJECT}/teaching-decision",
                       json={"sessionId": "sess-1"})
    assert resp.status_code == 404


def test_teaching_decision_endpoint_registered():
    routes: set[str] = set()

    def walk(router):
        for route in router.routes:
            path = getattr(route, "path", None)
            if path is None:
                nested = getattr(route, "routes", None) or getattr(
                    route, "original_router", None
                )
                if nested:
                    walk(nested)
                continue
            for method in getattr(route, "methods", []) or []:
                routes.add(f"{method.upper()} {path}")

    walk(app.router)
    assert "POST /subjects/{subject_id}/teaching-decision" in routes