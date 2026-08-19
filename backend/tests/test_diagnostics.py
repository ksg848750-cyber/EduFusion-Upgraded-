"""End-to-end service tests for the M4 diagnostic orchestration (doc3/doc10)."""

import asyncio

from app.ai.schemas.learner import GeneratedQuestion
from app.services import diagnostics as diag
from app.services import (
    answers as answers_service,
    concepts as concepts_service,
    diagnoses as diagnoses_service,
    learning_events as events_service,
    questions as questions_service,
    sessions as sessions_service,
)
from app.services.concept_context import build_graph_position, get_concept_chunks


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


OWNER = "user-1"
SUBJECT = "subj-1"


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


def _chunks():
    return [{"chunkIndex": 1, "sectionTitle": "s", "pageNumber": 1, "text": "forwarding passes values"}]


def _resolution(status="TARGET_FOUND", concept_id="c-forward"):
    return {
        "status": status,
        "conceptId": concept_id,
        "conceptName": "Forwarding",
        "path": ["Forwarding"],
        "rootGap": False,
        "candidatesConsidered": ["Forwarding"],
        "reason": "it is the gap",
    }


def _question(question_type="MCQ"):
    return {
        "questionText": "How does forwarding resolve a hazard?",
        "questionType": question_type,
        "difficulty": 3,
        "expectedAnswer": "passes value",
        "expectedReasoning": "bypass",
        "diagnosticTargets": ["UNDERSTANDING_forwarding_passes_computed_values_between_pipeline_stages"],
        "sourceChunks": [1],
        "options": [{"id": "A", "text": "a"}, {"id": "B", "text": "b"},
                    {"id": "C", "text": "c"}, {"id": "D", "text": "d"}],
        "correctOptionId": "A",
    }


def _mcq_question_dict(**o):
    base = {
        "id": "q-1", "subjectId": SUBJECT, "conceptId": "c-forward",
        "questionType": "MCQ", "difficulty": 3, "questionText": "How does forwarding resolve a hazard?",
        "expectedAnswer": "passes value", "expectedReasoning": "bypass",
        "diagnosticTargets": ["T"], "sourceReferences": [{"chunkIndex": 1}],
        "generationMetadata": {}, "options": [{"id": "A", "text": "a"}, {"id": "B", "text": "b"},
                                               {"id": "C", "text": "c"}, {"id": "D", "text": "d"}],
        "correctOptionId": "A", "createdAt": "2024-01-01T00:00:00Z",
    }
    base.update(o)
    return base


class FakeAI:
    def __init__(self, questions=None, probe=None, evaluation=None):
        self.questions = questions
        self.probe = probe
        self.evaluation = evaluation

    async def generate_diagnostic_questions(self, concept, vocab, graph, chunks, learner_context="", question_count=5):
        return self.questions

    async def generate_probe(self, concept, target, vocab, chunks):
        return self.probe

    async def evaluate_answer(self, *args, **kwargs):
        return self.evaluation


# ---- start_diagnostic: generation -------------------------------------------------

def test_start_diagnostic_target_found_creates_session_and_questions(monkeypatch):
    async def fake_resolve(uid, sid, entry_concept_id=None):
        return _resolution()

    async def fake_list_concepts(subject_id):
        return [_concept()]

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_graph(subject, concept):
        return "Forwarding --PART_OF--> Pipeline"

    async def fake_create_session(learner, subject, concept, resolution=None):
        return {"id": "sess-1", "subjectId": SUBJECT, "conceptId": concept,
                "resolution": resolution or {}, "status": "CREATED"}

    async def fake_mark(learner, sid):
        return {"id": sid, "status": "IN_PROGRESS"}

    async def fake_insert_question(**kw):
        return "q-" + kw["question_text"][:3]

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr(diag, "resolve_diagnostic_target", fake_resolve)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_list_concepts)
    monkeypatch.setattr(get_concept_chunks, "__name__", "x")  # noqa
    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr("app.services.diagnostics.build_graph_position", fake_graph)
    monkeypatch.setattr(sessions_service, "create_session", fake_create_session)
    monkeypatch.setattr(sessions_service, "mark_in_progress", fake_mark)
    monkeypatch.setattr(questions_service, "insert_question", fake_insert_question)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    vocab = diag.derive_target_vocabulary(_concept())
    qs = type("QS", (), {"questions": [GeneratedQuestion.model_validate(_question())]})()
    ai = FakeAI(questions=qs)

    result = _run(diag.start_diagnostic(OWNER, SUBJECT, ai=ai))
    assert result["status"] == "TARGET_FOUND"
    assert result["sessionId"] == "sess-1"
    assert len(result["questions"]) == 1
    assert result["questions"][0]["id"] is not None
    assert result["resolution"]["conceptId"] == "c-forward"


def test_start_diagnostic_no_target(monkeypatch):
    async def fake_resolve(uid, sid, entry_concept_id=None):
        return _resolution(status="NO_TARGET", concept_id=None)

    monkeypatch.setattr(diag, "resolve_diagnostic_target", fake_resolve)
    result = _run(diag.start_diagnostic(OWNER, SUBJECT))
    assert result["status"] == "NO_TARGET"


def test_start_diagnostic_generation_error(monkeypatch):
    async def fake_resolve(uid, sid, entry_concept_id=None):
        return _resolution()

    async def fake_list_concepts(subject_id):
        return [_concept()]

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_graph(subject, concept):
        return "g"

    monkeypatch.setattr(diag, "resolve_diagnostic_target", fake_resolve)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_list_concepts)
    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr("app.services.diagnostics.build_graph_position", fake_graph)

    class BoomAI:
        async def generate_diagnostic_questions(self, *a, **k):
            raise RuntimeError("llm down")

    result = _run(diag.start_diagnostic(OWNER, SUBJECT, ai=BoomAI()))
    assert result["status"] == "GENERATION_ERROR"


def test_start_diagnostic_validation_error(monkeypatch):
    async def fake_resolve(uid, sid, entry_concept_id=None):
        return _resolution()

    async def fake_list_concepts(subject_id):
        return [_concept()]

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_graph(subject, concept):
        return "g"

    monkeypatch.setattr(diag, "resolve_diagnostic_target", fake_resolve)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_list_concepts)
    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr("app.services.diagnostics.build_graph_position", fake_graph)

    vocab = diag.derive_target_vocabulary(_concept())
    bad = _question()
    bad["diagnosticTargets"] = ["NOT_IN_VOCAB"]
    qs = type("QS", (), {"questions": [GeneratedQuestion.model_validate(bad)]})()
    ai = FakeAI(questions=qs)

    result = _run(diag.start_diagnostic(OWNER, SUBJECT, ai=ai))
    assert result["status"] == "VALIDATION_ERROR"


# ---- submit_diagnostic_answer: evidence only, no mastery -----------------------

def test_diagnostic_answer_does_not_mutate_mastery(monkeypatch):
    from app.ai.schemas.learner import AnswerEvaluation, MisconceptionHypothesis

    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    question = _mcq_question_dict()
    ev = AnswerEvaluation(
        correct=False, reasoningQuality="POOR", explanation="e",
        evidenceSignals=["USES_ARRIVAL"],
        misconception=MisconceptionHypothesis(category="MISCONCEPTION", statement="s", confidence=0.8),
    )
    ai = FakeAI(evaluation=ev)

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_insert_answer(**kw):
        return "ans-1"

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr(answers_service, "insert_answer", fake_insert_answer)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    import app.services.learner as learner_service
    learner_service_calls = []

    async def fake_update_concept_state(*a, **k):
        learner_service_calls.append("called")
        return None

    monkeypatch.setattr(learner_service, "update_concept_state", fake_update_concept_state)

    result = _run(diag.submit_diagnostic_answer(
        OWNER, SUBJECT, session, _concept(), question, OWNER,
        response="", reasoning="r", selected_option_id="B", ai=ai,
    ))
    assert result["correct"] is False
    assert result["answerId"] == "ans-1"
    assert learner_service_calls == [], "diagnostic answer must not update the learner model"


def test_diagnostic_answer_mcq_deterministic_correctness(monkeypatch):
    from app.ai.schemas.learner import AnswerEvaluation

    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    question = _mcq_question_dict()
    # Evaluator says wrong, but deterministic MCQ grading overrides to correct.
    ev = AnswerEvaluation(correct=False, reasoningQuality="POOR", explanation="e",
                          evidenceSignals=[], misconception=None)
    ai = FakeAI(evaluation=ev)

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_insert_answer(**kw):
        return "ans-2"

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr(answers_service, "insert_answer", fake_insert_answer)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    result = _run(diag.submit_diagnostic_answer(
        OWNER, SUBJECT, session, _concept(), question, OWNER,
        response="", reasoning="r", selected_option_id="A", ai=ai,
    ))
    assert result["correct"] is True  # A is correctOptionId


def test_diagnostic_answer_requires_option_for_mcq(monkeypatch):
    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    question = _mcq_question_dict()

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    try:
        _run(diag.submit_diagnostic_answer(
            OWNER, SUBJECT, session, _concept(), question, OWNER,
            response="", reasoning="r", selected_option_id=None, ai=FakeAI(),
        ))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_diagnostic_answer_persists_evidence_signals_and_reasoning(monkeypatch):
    from app.ai.schemas.learner import AnswerEvaluation, MisconceptionHypothesis

    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    question = _mcq_question_dict()
    ev = AnswerEvaluation(
        correct=False, reasoningQuality="PARTIAL", explanation="wrong signal",
        evidenceSignals=["USES_ARRIVAL", "MISREADS_STAGE"],
        misconception=MisconceptionHypothesis(category="MISCONCEPTION", statement="s", confidence=0.8),
    )
    ai = FakeAI(evaluation=ev)

    captured = {}

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_insert_answer(**kw):
        captured.update(kw)
        return "ans-ev"

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr(answers_service, "insert_answer", fake_insert_answer)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    _run(diag.submit_diagnostic_answer(
        OWNER, SUBJECT, session, _concept(), question, OWNER,
        response="", reasoning="r", selected_option_id="A", ai=ai,
    ))

    # Evidence is persisted to the answers table with full diagnostic metadata.
    assert captured.get("evidence_signals") == ["USES_ARRIVAL", "MISREADS_STAGE"]
    assert captured.get("diagnostic_session_id") == "sess-1"
    assert captured.get("learner_id") == OWNER
    assert captured.get("selected_option_id") == "A"
    assessment = captured.get("reasoning_assessment") or {}
    assert assessment.get("reasoningQuality") == "PARTIAL"
    assert assessment.get("diagnostic") is True
    assert assessment.get("misconception", {}).get("category") == "MISCONCEPTION"


def test_diagnostic_answer_short_answer_scenario_supported(monkeypatch):
    from app.ai.schemas.learner import AnswerEvaluation

    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    question = _mcq_question_dict(questionType="SCENARIO", options=[], correctOptionId=None)
    ev = AnswerEvaluation(
        correct=True, reasoningQuality="SOLID", explanation="understands forwarding",
        evidenceSignals=["APPLIES_FORWARDING"], misconception=None,
    )
    ai = FakeAI(evaluation=ev)

    captured = {}

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_insert_answer(**kw):
        captured.update(kw)
        return "ans-sa"

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr(answers_service, "insert_answer", fake_insert_answer)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    result = _run(diag.submit_diagnostic_answer(
        OWNER, SUBJECT, session, _concept(), question, OWNER,
        response="the pipeline forwards the value to the next stage",
        reasoning="forwarding bypasses the stall", selected_option_id=None, ai=ai,
    ))
    assert result["answerId"] == "ans-sa"
    assert result["correct"] is True
    assert captured.get("response") == "the pipeline forwards the value to the next stage"
    assert captured.get("selected_option_id") is None
    assert captured.get("evidence_signals") == ["APPLIES_FORWARDING"]


# ---- analysis, probe, finalize -------------------------------------------------

def test_analyze_session_confident(monkeypatch):
    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    answers = [
        {"id": "a1", "questionId": "q1", "correctness": False,
         "reasoningAssessment": {"reasoningQuality": "POOR", "misconception": {"category": "MISCONCEPTION", "confidence": 0.8}},
         "evidenceSignals": ["X"]},
        {"id": "a2", "questionId": "q2", "correctness": False,
         "reasoningAssessment": {"reasoningQuality": "POOR", "misconception": {"category": "MISCONCEPTION", "confidence": 0.7}},
         "evidenceSignals": ["X"]},
    ]

    async def fake_list(learner, sid):
        return answers

    monkeypatch.setattr(answers_service, "list_answers_for_session", fake_list)
    decision = _run(diag.analyze_session(OWNER, session))
    assert decision["status"] == "CONFIDENT"
    assert decision["rootCause"] == "MISCONCEPTION"


def test_generate_probe_persists_probe(monkeypatch):
    from app.ai.schemas.learner import ProbeQuestion

    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward"}
    decision = {
        "status": "AMBIGUOUS",
        "hypotheses": [
            {"category": "MISSING_PREREQUISITE", "statement": "s", "confidence": 0.8},
            {"category": "MISCONCEPTION", "statement": "s2", "confidence": 0.75},
        ],
    }
    probe = ProbeQuestion(
        questionText="Which behavior is observable?",
        questionType="MCQ", expectedAnswer="a", expectedReasoning="r",
        diagnosticTargets=["T"], sourceChunks=[1],
        options=[{"id": "A", "text": "a"}, {"id": "B", "text": "b"},
                 {"id": "C", "text": "c"}, {"id": "D", "text": "d"}],
        correctOptionId="A",
        differentiationTarget={"hypothesisA": "MISSING_PREREQUISITE", "hypothesisB": "MISCONCEPTION"},
    )
    ai = FakeAI(probe=probe)

    async def fake_chunks(owner, subject, concept, top=8):
        return _chunks()

    async def fake_insert_question(**kw):
        assert kw["question_type"] == "PROBE"
        return "probe-1"

    monkeypatch.setattr("app.services.diagnostics.get_concept_chunks", fake_chunks)
    monkeypatch.setattr(questions_service, "insert_question", fake_insert_question)

    result = _run(diag.generate_probe_for(OWNER, SUBJECT, session, _concept(), decision, ai=ai))
    assert result["probeQuestion"]["id"] == "probe-1"
    assert result["probeQuestion"]["questionType"] == "MCQ"

def test_finalize_diagnosis_persists_and_completes(monkeypatch):
    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward",
               "resolution": _resolution()}
    decision = {
        "status": "CONFIDENT", "rootCause": "MISCONCEPTION", "confidence": 0.8,
        "statement": "s", "evidenceSignals": ["X"], "hypotheses": [],
    }
    diagnosis = {
        "id": "diag-1", "conceptId": "c-forward", "rootCause": "MISCONCEPTION",
        "confidence": 0.8, "resolution": {}, "investigation": {}, "evidenceReferences": [],
    }

    async def fake_list(learner, sid):
        return [{"id": "a1", "questionId": "q1", "correctness": False}]

    async def fake_insert(**kw):
        assert kw["root_cause"] == "MISCONCEPTION"
        return diagnosis

    async def fake_complete(learner, sid):
        return {"id": sid, "status": "COMPLETED"}

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr(answers_service, "list_answers_for_session", fake_list)
    monkeypatch.setattr(diagnoses_service, "insert_diagnosis", fake_insert)
    monkeypatch.setattr(sessions_service, "complete_session", fake_complete)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    result = _run(diag.finalize_diagnosis(OWNER, SUBJECT, session, _concept(), decision))
    assert result["rootCause"] == "MISCONCEPTION"
    assert result["id"] == "diag-1"


def test_finalize_insufficient_when_not_confident(monkeypatch):
    session = {"id": "sess-1", "subjectId": SUBJECT, "conceptId": "c-forward", "resolution": {}}
    decision = {"status": "AMBIGUOUS", "rootCause": None, "confidence": 0.6,
                "statement": "s", "evidenceSignals": [], "hypotheses": []}
    diagnosis = {
        "id": "diag-1", "conceptId": "c-forward", "rootCause": "INSUFFICIENT_EVIDENCE",
        "confidence": 0.6, "resolution": {}, "investigation": {}, "evidenceReferences": [],
    }

    async def fake_list(learner, sid):
        return []

    async def fake_insert(**kw):
        assert kw["root_cause"] == "INSUFFICIENT_EVIDENCE"
        return diagnosis

    async def fake_complete(learner, sid):
        return {"id": sid, "status": "COMPLETED"}

    async def fake_event(*a, **kw):
        return None

    monkeypatch.setattr(answers_service, "list_answers_for_session", fake_list)
    monkeypatch.setattr(diagnoses_service, "insert_diagnosis", fake_insert)
    monkeypatch.setattr(sessions_service, "complete_session", fake_complete)
    monkeypatch.setattr(events_service, "append_event", fake_event)

    result = _run(diag.finalize_diagnosis(OWNER, SUBJECT, session, _concept(), decision))
    assert result["rootCause"] == "INSUFFICIENT_EVIDENCE"
