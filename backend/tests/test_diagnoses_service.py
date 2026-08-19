"""Tests for the diagnoses persistence service and the evidence bundle."""

import asyncio
from datetime import datetime, timezone

from app.services import diagnoses as diagnoses_service
from app.services import diagnostics as diag
from app.services import (
    answers as answers_service,
    concepts as concepts_service,
    questions as questions_service,
    sessions as sessions_service,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.executes = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, sql, params):
        self.executes.append(sql)
        return self

    async def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    async def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows


def _diag_row(**o):
    now = datetime.now(timezone.utc)
    base = {
        "id": "diag-1", "learnerId": "u1", "subjectId": "s1", "sessionId": "sess1",
        "conceptId": "c1", "rootCause": "MISCONCEPTION", "confidence": 0.8,
        "status": "OPEN", "resolution": {"a": 1}, "investigation": {"b": 2},
        "evidenceReferences": [{"x": 1}], "createdAt": now, "updatedAt": now,
    }
    base.update(o)
    return tuple(base.values())


def test_diagnoses_row_mapping(monkeypatch):
    conn = FakeConn([_diag_row()])
    monkeypatch.setattr("app.services.diagnoses.connection", lambda: conn)

    result = _run(diagnoses_service.get_diagnosis_by_session("u1", "sess1"))
    assert result is not None
    assert result["rootCause"] == "MISCONCEPTION"
    assert result["confidence"] == 0.8
    assert result["resolution"] == {"a": 1}


def test_diagnoses_insert_returns_none_without_row(monkeypatch):
    conn = FakeConn([])
    monkeypatch.setattr("app.services.diagnoses.connection", lambda: conn)
    result = _run(diagnoses_service.insert_diagnosis(
        "u1", "s1", "sess1", "c1", "MISCONCEPTION", 0.8, {}, {}, [],
    ))
    assert result is None


# ---- evidence_bundle ----------------------------------------------------------

def test_evidence_bundle_assembles_trace(monkeypatch):
    session = {
        "id": "sess1", "subjectId": "s1", "conceptId": "c1",
        "resolution": {"status": "TARGET_FOUND", "conceptId": "c1"},
    }

    async def fake_get_session(learner, sid):
        return session

    async def fake_list_concepts(subject_id):
        return [{"id": "c1", "name": "Forwarding"}]

    async def fake_list_answers(learner, sid):
        return [{"id": "a1", "questionId": "q1", "correctness": False,
                 "reasoning": "Stages run independently.",
                 "response": "B",
                 "reasoningAssessment": {"reasoningQuality": "POOR", "misconception": {"category": "MISCONCEPTION"}},
                 "evidenceSignals": ["X"]}]

    async def fake_list_questions(subject_id, concept_id, qids):
        return [{"id": "q1", "questionText": "What can a stage do?"}]

    async def fake_get_diagnosis(learner, sid):
        return {"id": "diag1", "rootCause": "MISCONCEPTION", "confidence": 0.8}

    monkeypatch.setattr(sessions_service, "get_session", fake_get_session)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_list_concepts)
    monkeypatch.setattr(answers_service, "list_answers_for_session", fake_list_answers)
    monkeypatch.setattr(questions_service, "list_questions_for_session", fake_list_questions)
    monkeypatch.setattr(diagnoses_service, "get_diagnosis_by_session", fake_get_diagnosis)

    result = _run(diag.evidence_bundle("u1", "s1", "sess1"))
    assert result["status"] == "OK"
    assert result["conceptName"] == "Forwarding"
    assert result["resolution"]["conceptId"] == "c1"
    assert result["diagnosis"]["rootCause"] == "MISCONCEPTION"
    assert result["evidence"][0]["correct"] is False
    assert result["evidence"][0]["reasoning"] == "Stages run independently."
    assert result["evidence"][0]["questionText"] == "What can a stage do?"


def test_evidence_bundle_not_found(monkeypatch):
    async def fake_get_session(learner, sid):
        return None

    monkeypatch.setattr(sessions_service, "get_session", fake_get_session)
    result = _run(diag.evidence_bundle("u1", "s1", "nope"))
    assert result["status"] == "NOT_FOUND"