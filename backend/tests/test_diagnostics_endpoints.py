"""API endpoint tests for the M4 diagnostics endpoints (doc3/doc10)."""

from app.api.v1.endpoints import diagnostics as diagnostics_module
from app.main import app

OWNER = "user-1"
SUBJECT = "subj-1"


def _registered_diagnostic_routes() -> set[str]:
    """Return the set of 'METHOD path' strings for M4 diagnostic routes.

    Guarded against the included-router nesting by walking every APIRoute.
    """
    routes: set[str] = set()

    def walk(router):
        for route in router.routes:
            path = getattr(route, "path", None)
            if path is None:
                # nested include_router -> recurse into its routes
                nested = getattr(route, "routes", None) or getattr(
                    route, "original_router", None
                )
                if nested:
                    walk(nested)
                continue
            for method in getattr(route, "methods", []) or []:
                routes.add(f"{method.upper()} {path}")

    walk(app.router)
    return routes


def test_all_m4_diagnostic_endpoints_registered():
    """Regression: the full M4 diagnostic pipeline must be reachable from the API
    so the frontend DiagnosticFlow can drive it end-to-end."""
    expected = {
        "POST /subjects/{subject_id}/diagnostic",
        "POST /subjects/{subject_id}/sessions/{session_id}/diagnostic-answers",
        "GET /subjects/{subject_id}/sessions/{session_id}/diagnostic-decision",
        "POST /subjects/{subject_id}/sessions/{session_id}/diagnostic-probe",
        "POST /subjects/{subject_id}/sessions/{session_id}/diagnosis",
        "GET /subjects/{subject_id}/sessions/{session_id}/evidence-bundle",
    }
    actual = _registered_diagnostic_routes()
    missing = expected - actual
    assert not missing, f"Missing M4 diagnostic routes: {sorted(missing)}"


def _subject(**o):
    base = {
        "id": SUBJECT,
        "ownerId": OWNER,
        "name": "CA",
        "description": "",
        "status": "ACTIVE",
        "conceptCount": 1,
    }
    base.update(o)
    return base


def _concept(**o):
    base = {
        "id": "c-forward",
        "name": "Forwarding",
        "canonicalName": "forwarding",
        "description": "hazard resolution",
        "difficulty": 3,
        "expectedUnderstanding": "forwarding passes computed values between pipeline stages",
        "commonMisconceptions": ["confusing forwarding with stalling"],
        "sourceReferences": [1],
    }
    base.update(o)
    return base


def _session(**o):
    base = {
        "id": "sess-1",
        "subjectId": SUBJECT,
        "conceptId": "c-forward",
        "status": "IN_PROGRESS",
        "resolution": {"status": "TARGET_FOUND", "conceptId": "c-forward",
                       "conceptName": "Forwarding", "path": ["Forwarding"]},
    }
    base.update(o)
    return base


def _patch_owner(monkeypatch, owner_id=OWNER):
    async def fake(auth_user_id):
        return owner_id

    monkeypatch.setattr(diagnostics_module.users_service, "get_user_id_by_auth", fake)


def _patch_subject(monkeypatch, subject=None):
    async def fake(owner_id, subject_id):
        return subject if subject else _subject(id=subject_id)

    monkeypatch.setattr(diagnostics_module.subjects_service, "get_subject", fake)


def _patch_session(monkeypatch, session=None):
    async def fake(owner_id, session_id, subject_id):
        s = session if session else _session(id=session_id, subjectId=subject_id)
        if s["subjectId"] != subject_id:
            return _session(id=session_id, subjectId="other")
        return s

    monkeypatch.setattr(diagnostics_module, "_session", fake)


def _patch_concept(monkeypatch, concept=None):
    async def fake(subject_id, concept_id):
        return concept if concept else _concept(id=concept_id)

    monkeypatch.setattr(diagnostics_module, "_concept", fake)


# ---- start diagnostic ---------------------------------------------------------

def test_start_diagnostic_ok(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    result = {
        "status": "TARGET_FOUND",
        "sessionId": "sess-1",
        "conceptId": "c-forward",
        "conceptName": "Forwarding",
        "questions": [{"id": "q1", "questionText": "How does forwarding help?",
                       "questionType": "MCQ", "diagnosticTargets": ["T"], "sourceChunks": [1],
                       "options": [{"id": "A", "text": "a"}], "difficulty": 3}],
        "resolution": {"status": "TARGET_FOUND"},
        "targetVocabulary": ["T"],
    }

    async def fake_start(owner, subject, ai=None, question_count=5, entry_concept_id=None):
        return result

    monkeypatch.setattr(diagnostics_module, "start_diagnostic", fake_start)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/diagnostic")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "TARGET_FOUND"
    assert body["sessionId"] == "sess-1"
    assert body["questions"][0]["questionType"] == "MCQ"


def test_start_diagnostic_forwards_entry_concept(client, monkeypatch):
    """The selected concept (Test yourself) must be forwarded to the service so
    the Target Resolution Engine can start from it and resolve upstream."""
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    captured = {}

    async def fake_start(owner, subject, ai=None, question_count=5, entry_concept_id=None):
        captured["entry_concept_id"] = entry_concept_id
        return {
            "status": "TARGET_FOUND",
            "sessionId": "sess-1",
            "conceptId": "c-forward",
            "conceptName": "Forwarding",
            "questions": [],
            "resolution": {"status": "TARGET_FOUND"},
            "targetVocabulary": [],
        }

    monkeypatch.setattr(diagnostics_module, "start_diagnostic", fake_start)
    resp = client.post(
        f"/api/v1/subjects/{SUBJECT}/diagnostic",
        json={"conceptId": "c-forward"},
    )
    assert resp.status_code == 200, resp.text
    assert captured["entry_concept_id"] == "c-forward"


def test_start_diagnostic_optional_entry_concept(client, monkeypatch):
    """Subject-wide start (no entry concept) must still work."""
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    captured = {}

    async def fake_start(owner, subject, ai=None, question_count=5, entry_concept_id=None):
        captured["entry_concept_id"] = entry_concept_id
        return {"status": "TARGET_FOUND", "sessionId": "s1", "conceptId": "c",
                "conceptName": "C", "questions": [], "resolution": {},
                "targetVocabulary": []}

    monkeypatch.setattr(diagnostics_module, "start_diagnostic", fake_start)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/diagnostic")
    assert resp.status_code == 200, resp.text
    assert captured["entry_concept_id"] is None


def test_start_diagnostic_no_target_409(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    async def fake_start(owner, subject, ai=None, question_count=5, entry_concept_id=None):
        return {"status": "NO_TARGET", "resolution": {"status": "NO_TARGET"}}

    monkeypatch.setattr(diagnostics_module, "start_diagnostic", fake_start)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/diagnostic")
    assert resp.status_code == 409


def test_start_diagnostic_validation_422(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    async def fake_start(owner, subject, ai=None, question_count=5, entry_concept_id=None):
        return {"status": "VALIDATION_ERROR", "resolution": {}, "error": "no valid questions"}

    monkeypatch.setattr(diagnostics_module, "start_diagnostic", fake_start)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/diagnostic")
    assert resp.status_code == 422


# ---- diagnostic answer --------------------------------------------------------

def test_diagnostic_answer_ok(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)
    _patch_concept(monkeypatch)

    async def fake_question_in_session(session, question_id):
        return {"id": question_id, "subjectId": SUBJECT, "conceptId": "c-forward",
                "questionType": "MCQ", "options": [{"id": "A", "text": "a"}],
                "correctOptionId": "A"}

    monkeypatch.setattr(diagnostics_module, "_question_in_session", fake_question_in_session)

    result = {"answerId": "ans-1", "correct": True, "reasoningQuality": "SOLID",
              "explanation": "e", "evidenceSignals": ["X"], "misconception": None}

    async def fake_submit(*args, **kwargs):
        return result

    monkeypatch.setattr(diagnostics_module, "submit_diagnostic_answer", fake_submit)
    resp = client.post(
        f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnostic-answers",
        json={"questionId": "q1", "reasoning": "r", "selectedOptionId": "A"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["correct"] is True


def test_diagnostic_answer_requires_option(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)
    _patch_concept(monkeypatch)

    async def fake_question_in_session(session, question_id):
        return {"id": question_id, "subjectId": SUBJECT, "conceptId": "c-forward",
                "questionType": "MCQ", "options": [{"id": "A", "text": "a"}],
                "correctOptionId": "A"}

    monkeypatch.setattr(diagnostics_module, "_question_in_session", fake_question_in_session)

    async def fake_submit(*args, **kwargs):
        raise ValueError("An option must be selected for MCQ questions")

    monkeypatch.setattr(diagnostics_module, "submit_diagnostic_answer", fake_submit)
    resp = client.post(
        f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnostic-answers",
        json={"questionId": "q1", "reasoning": "r"},
    )
    assert resp.status_code == 422


def test_diagnostic_answer_endpoint_forwards_service_args(client, monkeypatch):
    """Regression: the endpoint must call the service submit_diagnostic_answer
    (not its own handler) and forward learner identity + body fields correctly."""
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)
    _patch_concept(monkeypatch)

    async def fake_question_in_session(session, question_id):
        return {"id": question_id, "subjectId": SUBJECT, "conceptId": "c-forward",
                "questionType": "MCQ", "options": [{"id": "A", "text": "a"}],
                "correctOptionId": "A"}

    monkeypatch.setattr(diagnostics_module, "_question_in_session", fake_question_in_session)

    captured = {}

    async def spy_submit(owner_id, subject_id, session, concept, question,
                         learner_id, response, reasoning, selected_option_id=None, ai=None):
        captured["owner_id"] = owner_id
        captured["subject_id"] = subject_id
        captured["learner_id"] = learner_id
        captured["response"] = response
        captured["reasoning"] = reasoning
        captured["selected_option_id"] = selected_option_id
        return {"answerId": "ans-spy", "correct": True, "reasoningQuality": "SOLID",
                "explanation": "e", "evidenceSignals": ["X"], "misconception": None}

    monkeypatch.setattr(diagnostics_module, "submit_diagnostic_answer", spy_submit)
    resp = client.post(
        f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnostic-answers",
        json={"questionId": "q1", "response": "the value", "reasoning": "r",
              "selectedOptionId": "A"},
    )
    assert resp.status_code == 200, resp.text
    # learner_id is the authenticated owner, not a client-supplied value
    assert captured["learner_id"] == captured["owner_id"]
    assert captured["subject_id"] == SUBJECT
    assert captured["response"] == "the value"
    assert captured["reasoning"] == "r"
    assert captured["selected_option_id"] == "A"


# ---- decision / probe / diagnosis / evidence bundle ---------------------------

def test_diagnostic_decision_ambiguous(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)

    async def fake_analyze(learner, session):
        return {"status": "AMBIGUOUS", "rootCause": None, "confidence": 0.8,
                "statement": "ambiguous", "evidenceSignals": [], "hypotheses": [
                    {"category": "MISSING_PREREQUISITE", "confidence": 0.8},
                    {"category": "MISCONCEPTION", "confidence": 0.75},
                ]}

    monkeypatch.setattr(diagnostics_module, "analyze_session", fake_analyze)
    resp = client.get(f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnostic-decision")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["needsProbe"] is True
    assert body["differentiationTarget"]["hypothesisA"] == "MISSING_PREREQUISITE"


def test_diagnostic_probe_ready(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)
    _patch_concept(monkeypatch)

    async def fake_analyze(learner, session):
        return {"status": "AMBIGUOUS", "hypotheses": [
            {"category": "MISSING_PREREQUISITE", "confidence": 0.8},
            {"category": "MISCONCEPTION", "confidence": 0.75},
        ]}

    async def fake_probe(owner, subject, session, concept, decision, ai=None):
        return {"probeQuestion": {"id": "p1", "questionText": "which?", "questionType": "MCQ",
                                  "diagnosticTargets": ["T"], "sourceChunks": [1],
                                  "options": [{"id": "A", "text": "a"}], "difficulty": 3},
                "target": {"hypothesisA": "MISSING_PREREQUISITE"}}

    monkeypatch.setattr(diagnostics_module, "analyze_session", fake_analyze)
    monkeypatch.setattr(diagnostics_module, "generate_probe_for", fake_probe)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnostic-probe")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PROBE_READY"
    assert resp.json()["probeQuestion"]["id"] == "p1"


def test_final_diagnosis_ok(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)
    _patch_session(monkeypatch)
    _patch_concept(monkeypatch)

    async def fake_analyze(learner, session):
        return {"status": "CONFIDENT", "rootCause": "MISCONCEPTION", "confidence": 0.8,
                "statement": "s", "evidenceSignals": [], "hypotheses": []}

    async def fake_finalize(owner, subject, session, concept, decision):
        return {"id": "diag-1", "conceptId": "c-forward", "conceptName": "Forwarding",
                "rootCause": "MISCONCEPTION", "confidence": 0.8,
                "resolution": {}, "investigation": {}, "evidenceReferences": []}

    monkeypatch.setattr(diagnostics_module, "analyze_session", fake_analyze)
    monkeypatch.setattr(diagnostics_module, "finalize_diagnosis", fake_finalize)
    resp = client.post(f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/diagnosis")
    assert resp.status_code == 200, resp.text
    assert resp.json()["rootCause"] == "MISCONCEPTION"


def test_evidence_bundle_ok(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    async def fake_bundle(owner, subject, session_id):
        return {"status": "OK", "conceptId": "c-forward", "conceptName": "Forwarding",
                "resolution": {"status": "TARGET_FOUND"}, "diagnosis": {"rootCause": "MISCONCEPTION"},
                "evidence": []}

    monkeypatch.setattr(diagnostics_module, "evidence_bundle", fake_bundle)
    resp = client.get(f"/api/v1/subjects/{SUBJECT}/sessions/sess-1/evidence-bundle")
    assert resp.status_code == 200, resp.text
    assert resp.json()["diagnosis"]["rootCause"] == "MISCONCEPTION"


def test_evidence_bundle_not_found(client, monkeypatch):
    _patch_owner(monkeypatch)
    _patch_subject(monkeypatch)

    async def fake_bundle(owner, subject, session_id):
        return {"status": "NOT_FOUND"}

    monkeypatch.setattr(diagnostics_module, "evidence_bundle", fake_bundle)
    resp = client.get(f"/api/v1/subjects/{SUBJECT}/sessions/nope/evidence-bundle")
    assert resp.status_code == 404