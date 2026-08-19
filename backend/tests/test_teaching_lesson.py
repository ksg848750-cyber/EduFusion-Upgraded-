"""Tests for M5 Part 2 — grounded lesson generation, interest lens, doubt
clarification, and their API endpoints (doc4/doc12)."""

import asyncio

from app.ai.schemas.teaching import Clarification, GeneratedLesson
from app.api.v1.endpoints import teaching as teaching_module
from app.main import app
from app.services.teaching import ALLOWED_INTERESTS, _validate_interest

OWNER = "user-1"
SUBJECT = "subj-1"
LESSON = "lesson-1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _concept(**o):
    base = {"id": "c-forward", "name": "Forwarding", "canonicalName": "forwarding"}
    base.update(o)
    return base


def _lesson(**o):
    base = {
        "id": LESSON, "learnerId": OWNER, "subjectId": SUBJECT,
        "diagnosisId": "diag-1", "conceptId": "c-forward",
        "rootCause": "MISCONCEPTION", "teachingAction": "MENTAL_MODEL_CORRECTION",
        "teachingStrategy": "VISUAL_STEP_BY_STEP", "interestContext": "normal",
        "attempt": 1, "status": "DELIVERED", "explanation": "",
        "visualizationSpec": {}, "sourceReferences": [],
    }
    base.update(o)
    return base


class _FakeAI:
    def __init__(self, lesson: GeneratedLesson, clarification: Clarification):
        self.lesson = lesson
        self.clarification = clarification

    async def generate_lesson(self, concept, **kwargs):
        return self.lesson

    async def clarify_doubt(self, concept, question, chunks):
        return self.clarification


# ---- interest validation ---------------------------------------------------

def test_allowed_interests():
    assert "normal" in ALLOWED_INTERESTS
    assert "cricket" in ALLOWED_INTERESTS


def test_validate_interest_rejects_unknown():
    try:
        _validate_interest("space")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---- generate_lesson_content ------------------------------------------------

def _lesson_deps(monkeypatch, lesson=None):
    from app.services import teaching as teaching_service
    from app.services import concepts as concepts_service

    async def fake_get(owner, lid):
        return lesson if lesson else _lesson(id=lid)

    async def fake_concepts(subject_id):
        return [_concept()]

    monkeypatch.setattr(teaching_service, "get_lesson", fake_get)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_concepts)


def _patch_chunks(monkeypatch):
    async def fake_chunks(owner, subject, concept, top=8):
        return [{"chunkIndex": 1, "text": "A hazard occurs when..."}]
    monkeypatch.setattr("app.services.concept_context.get_concept_chunks", fake_chunks)


def test_generate_lesson_content_ok(monkeypatch):
    from app.services import teaching as teaching_service
    from app.services import learning_events as events_service

    _lesson_deps(monkeypatch)
    _patch_chunks(monkeypatch)

    async def fake_save(owner, lid, explanation, refs, interest):
        return {"id": lid, "updatedAt": "now"}

    async def fake_event(*a, **k):
        return None

    monkeypatch.setattr(teaching_service, "_save_lesson_content", fake_save)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    generated = GeneratedLesson(
        explanation="Forwarding passes values between stages.",
        keyPoints=["k1", "k2"],
        analogy=None,
        sourceChunks=[1, 999],
    )
    ai = _FakeAI(lesson=generated, clarification=None)
    result = _run(teaching_service.generate_lesson_content(OWNER, SUBJECT, LESSON, interest_context="normal", ai=ai))

    assert result["status"] == "OK"
    assert result["explanation"] == generated.explanation
    assert result["analogy"] is None
    assert result["sourceChunks"] == [1]  # 999 clipped — never surface unshown chunks
    assert result["sourceReferences"] == [{"chunkIndex": 1}]
    assert result["teachingStrategy"] == "VISUAL_STEP_BY_STEP"


def test_generate_lesson_content_interest_analogy(monkeypatch):
    from app.services import teaching as teaching_service
    from app.services import learning_events as events_service

    _lesson_deps(monkeypatch)
    _patch_chunks(monkeypatch)

    async def fake_save(owner, lid, explanation, refs, interest):
        return {"id": lid, "updatedAt": "now"}
    async def fake_event(*a, **k):
        return None
    monkeypatch.setattr(teaching_service, "_save_lesson_content", fake_save)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    from app.ai.schemas.teaching import AnalogyMapping, InterestAnalogy
    generated = GeneratedLesson(
        explanation="Forwarding passes values between stages.",
        keyPoints=[],
        analogy=InterestAnalogy(
            scene="Kohli turning for a sharp single",
            mapping=[AnalogyMapping(element="EX/MEM register", mappedTo="non-striker", description="holds the run until allowed")],
            analogy_works="runners wait on the call",
            analogy_breaks="noise does not wear a batsman out",
        ),
        sourceChunks=[1],
    )
    ai = _FakeAI(lesson=generated, clarification=None)
    result = _run(teaching_service.generate_lesson_content(OWNER, SUBJECT, LESSON, interest_context="cricket", ai=ai))
    assert result["status"] == "OK"
    assert result["interestContext"] == "cricket"
    assert result["analogy"]["scene"].startswith("Kohli")


def test_generate_lesson_content_not_found(monkeypatch):
    from app.services import teaching as teaching_service

    async def fake_get(owner, lid):
        return None
    monkeypatch.setattr(teaching_service, "get_lesson", fake_get)
    result = _run(teaching_service.generate_lesson_content(OWNER, SUBJECT, LESSON, ai=_FakeAI(None, None)))
    assert result["status"] == "LESSON_NOT_FOUND"


# ---- clarify_doubt ----------------------------------------------------------

def test_clarify_ok(monkeypatch):
    from app.services import teaching as teaching_service
    from app.services import concepts as concepts_service
    from app.rag import retriever

    async def fake_get(owner, lid):
        return _lesson()
    async def fake_concepts(subject_id):
        return [_concept()]
    async def fake_retrieve(owner, subject, query, top_k=4):
        return [{"chunkIndex": 2, "text": "Forwarding resolves data hazards."}]
    monkeypatch.setattr(teaching_service, "get_lesson", fake_get)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_concepts)
    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)

    clar = Clarification(answer="Forwarding sends the value early.", covered=True, sourceChunks=[2, 9], disclaimer="")
    ai = _FakeAI(lesson=None, clarification=clar)
    result = _run(teaching_service.clarify_doubt(OWNER, SUBJECT, LESSON, "How does forwarding help?", ai=ai))
    assert result["status"] == "OK"
    assert result["covered"] is True
    assert result["sourceChunks"] == [2]  # 9 clipped


def test_clarify_hard_rag_guard_no_chunks(monkeypatch):
    """No retrieved chunks must force covered=False regardless of the LLM."""
    from app.services import teaching as teaching_service
    from app.services import concepts as concepts_service
    from app.rag import retriever

    async def fake_get(owner, lid):
        return _lesson()
    async def fake_concepts(subject_id):
        return [_concept()]
    async def fake_retrieve(owner, subject, query, top_k=4):
        return []
    monkeypatch.setattr(teaching_service, "get_lesson", fake_get)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_concepts)
    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)

    result = _run(teaching_service.clarify_doubt(OWNER, SUBJECT, LESSON, "What is quantum computing?", ai=_FakeAI(None, None)))
    assert result["status"] == "OK"
    assert result["covered"] is False
    assert result["sourceChunks"] == []
    assert "could not find" in result["answer"].lower()


def test_clarify_empty_question_rejected(monkeypatch):
    from app.services import teaching as teaching_service
    async def fake_get(owner, lid):
        return _lesson()
    monkeypatch.setattr(teaching_service, "get_lesson", fake_get)
    try:
        _run(teaching_service.clarify_doubt(OWNER, SUBJECT, LESSON, "   "))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---- endpoints --------------------------------------------------------------

def _patch_endpoint_auth(monkeypatch, owner_id=OWNER):
    async def fake_owner(auth_user_id):
        return owner_id
    monkeypatch.setattr(teaching_module.users_service, "get_user_id_by_auth", fake_owner)

    async def fake_subject(owner_id, subject_id):
        return {"id": subject_id, "ownerId": owner_id, "name": "CA"}
    monkeypatch.setattr(teaching_module.subjects_service, "get_subject", fake_subject)


def test_lesson_generate_endpoint_ok(client, monkeypatch):
    _patch_endpoint_auth(monkeypatch)
    async def fake_gen(owner, subject, lesson_id, interest_context="normal", ai=None):
        return {
            "status": "OK", "lessonId": lesson_id, "conceptId": "c-forward",
            "rootCause": "MISCONCEPTION", "teachingAction": "MENTAL_MODEL_CORRECTION",
            "teachingStrategy": "VISUAL_STEP_BY_STEP", "attempt": 1,
            "interestContext": interest_context, "explanation": "Forwarding...",
            "keyPoints": ["k"], "analogy": None, "sourceChunks": [1],
            "sourceReferences": [{"chunkIndex": 1}],
        }
    monkeypatch.setattr(teaching_module, "generate_lesson_content", fake_gen)

    resp = client.post(f"/api/v1/subjects/{SUBJECT}/lessons/{LESSON}/generate",
                       json={"interestContext": "cricket"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OK"
    assert body["explanation"] == "Forwarding..."
    assert body["interestContext"] == "cricket"


def test_lesson_generate_endpoint_bad_interest(client, monkeypatch):
    _patch_endpoint_auth(monkeypatch)
    async def fake_gen(owner, subject, lesson_id, interest_context="normal", ai=None):
        from app.services.teaching import _validate_interest
        _validate_interest(interest_context)
        raise AssertionError("should not reach")
    monkeypatch.setattr(teaching_module, "generate_lesson_content", fake_gen)

    resp = client.post(f"/api/v1/subjects/{SUBJECT}/lessons/{LESSON}/generate",
                       json={"interestContext": "notreal"})
    assert resp.status_code == 422, resp.text


def test_lesson_detail_endpoint_ok(client, monkeypatch):
    _patch_endpoint_auth(monkeypatch)
    async def fake_get(owner, lesson_id):
        return _lesson(id=lesson_id)
    monkeypatch.setattr(teaching_module, "get_lesson", fake_get)

    resp = client.get(f"/api/v1/subjects/{SUBJECT}/lessons/{LESSON}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["lesson"]["id"] == LESSON


def test_clarify_endpoint_ok(client, monkeypatch):
    _patch_endpoint_auth(monkeypatch)
    async def fake_clarify(owner, subject, lesson_id, question, ai=None):
        return {
            "status": "OK", "lessonId": lesson_id, "conceptId": "c-forward",
            "answer": "Forwarding sends the value early.", "covered": True,
            "sourceChunks": [2], "disclaimer": "",
        }
    monkeypatch.setattr(teaching_module, "clarify_doubt", fake_clarify)

    resp = client.post(f"/api/v1/subjects/{SUBJECT}/lessons/{LESSON}/clarify",
                       json={"question": "How does forwarding help?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["covered"] is True


def test_part2_endpoints_registered():
    routes: set[str] = set()

    def walk(router):
        for route in router.routes:
            path = getattr(route, "path", None)
            if path is None:
                nested = getattr(route, "routes", None) or getattr(route, "original_router", None)
                if nested:
                    walk(nested)
                continue
            for method in getattr(route, "methods", []) or []:
                routes.add(f"{method.upper()} {path}")

    walk(app.router)
    for expected in (
        "POST /subjects/{subject_id}/lessons/{lesson_id}/generate",
        "GET /subjects/{subject_id}/lessons/{lesson_id}",
        "POST /subjects/{subject_id}/lessons/{lesson_id}/clarify",
    ):
        assert expected in routes, f"missing {expected}"