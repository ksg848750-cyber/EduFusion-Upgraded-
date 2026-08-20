"""Tests for M4 diagnostic question generation and probe generation (AI layer)."""

import asyncio
import json

import pytest

from app.ai.schemas.learner import ProbeQuestion, QuestionSet
from app.ai.service import AIService
from app.services.diagnostics import (
    derive_target_vocabulary,
    _build_learner_context,
    _validate_diagnostic_questions,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    async def complete(self, system, user, temperature=0.0, max_tokens=None):
        return self.responses.pop(0)


def _concept():
    return {
        "id": "c1",
        "name": "Forwarding",
        "canonicalName": "forwarding",
        "description": "Resolving hazards via forwarding",
        "difficulty": 3,
        "expectedUnderstanding": "forwarding passes computed values between pipeline stages",
        "commonMisconceptions": [
            "confusing forwarding with stalling",
            "assuming forwarding works across all hazards",
        ],
        "sourceReferences": [1, 2],
    }


def _chunks():
    return [
        {"chunkIndex": 1, "sectionTitle": "Pipelining", "pageNumber": 4,
         "text": "Forwarding passes a computed value directly to a later stage."},
        {"chunkIndex": 2, "sectionTitle": "Pipelining", "pageNumber": 5,
         "text": "Forwarding cannot always resolve load-use hazards."},
    ]


def _question(question_type="MCQ", targets=None, chunks=None):
    return {
        "questionText": "How does forwarding help?",
        "questionType": question_type,
        "difficulty": 3,
        "expectedAnswer": "a",
        "expectedReasoning": "r",
        "diagnosticTargets": targets or ["UNDERSTANDING_forwarding_passes_computed_values_between_pipeline_stages"],
        "sourceChunks": chunks or [1],
        "options": [{"id": "A", "text": "a"}, {"id": "B", "text": "b"},
                    {"id": "C", "text": "c"}, {"id": "D", "text": "d"}],
        "correctOptionId": "A",
    }


# ---- vocabulary derivation ----------------------------------------------------

def test_vocabulary_derived_from_misconceptions_and_understanding():
    vocab = derive_target_vocabulary(_concept())
    assert any("confusing_forwarding_with_stalling" in v for v in vocab)
    assert any("UNDERSTANDING" in v for v in vocab)


def test_vocabulary_non_empty_fallback():
    vocab = derive_target_vocabulary({"canonicalName": "forwarding", "name": "Forwarding"})
    assert vocab == ["CORE_forwarding"]


def test_vocabulary_deduplicates():
    concept = {
        "commonMisconceptions": ["A same idea", "A same idea"],
        "expectedUnderstanding": "",
    }
    vocab = derive_target_vocabulary(concept)
    assert len(vocab) == 1


# ---- validation ---------------------------------------------------------------

def test_validation_accepts_valid_questions():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    q = GeneratedQuestion.model_validate(_question(targets=[vocab[0]]))
    valid, errors = _validate_diagnostic_questions([q], vocab, {1, 2}, 5)
    assert not errors
    assert len(valid) == 1


def test_validation_rejects_out_of_vocab_target():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    q = GeneratedQuestion.model_validate(_question(targets=["NOT_IN_VOCAB"]))
    valid, errors = _validate_diagnostic_questions([q], vocab, {1, 2}, 5)
    assert not valid
    assert errors


def test_validation_filters_bad_chunks():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    q = GeneratedQuestion.model_validate(_question(targets=[vocab[0]], chunks=[1, 99]))
    valid, _ = _validate_diagnostic_questions([q], vocab, {1}, 5)
    assert valid[0].sourceChunks == [1]


def test_validation_rejects_too_many_questions():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    qs = [GeneratedQuestion.model_validate(_question(targets=[vocab[0]])) for _ in range(3)]
    valid, errors = _validate_diagnostic_questions(qs, vocab, {1}, 2)
    assert not valid
    assert errors


def test_validation_rejects_document_meta_question():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    q = _question(
        targets=[vocab[0]],
        question_type="MCQ",
    )
    q["questionText"] = "Which of the following is NOT a section heading in the excerpts?"
    q["options"] = [{"id": "A", "text": "Sequential Access"},
                    {"id": "B", "text": "Direct Access"},
                    {"id": "C", "text": "Other Access methods"},
                    {"id": "D", "text": "Random Access"}]
    q["correctOptionId"] = "D"
    valid, errors = _validate_diagnostic_questions(
        [GeneratedQuestion.model_validate(q)], vocab, {1}, 5
    )
    assert not valid
    assert any("document-meta" in e for e in errors)


def test_validation_rejects_off_topic_untethered_question():
    from app.ai.schemas.learner import GeneratedQuestion

    vocab = derive_target_vocabulary(_concept())
    q = _question(targets=[vocab[0]], question_type="MCQ")
    q["questionText"] = "Which colour best represents the idea of time?"
    q["expectedAnswer"] = "blue"
    q["expectedReasoning"] = "colour is unrelated to the concept"
    valid, errors = _validate_diagnostic_questions(
        [GeneratedQuestion.model_validate(q)], vocab, {1}, 5
    )
    assert not valid
    assert any("off-topic" in e for e in errors)


# ---- learner context ----------------------------------------------------------

def test_build_learner_context_no_assessment(monkeypatch):
    from app.services import diagnoses as diagnoses_service
    from app.services import learner as learner_service

    async def no_model(*_a, **_k):
        return None

    async def no_diags(*_a, **_k):
        return []

    monkeypatch.setattr(learner_service, "get_learner_model", no_model)
    monkeypatch.setattr(diagnoses_service, "list_diagnoses", no_diags)
    text = _run(_build_learner_context("u", "s", _concept()))
    assert "no assessment" in text


def test_build_learner_context_uses_state_and_prior_diagnosis(monkeypatch):
    from app.services import diagnoses as diagnoses_service
    from app.services import learner as learner_service

    async def model(*_a, **_k):
        return {"conceptStates": {"c1": {"status": "WEAK", "mastery": 0.4}}}

    async def diags(*_a, **_k):
        return [{"conceptId": "c1", "rootCause": "MISCONCEPTION",
                 "investigation": {"statement": "Treats stages as independent."}}]

    monkeypatch.setattr(learner_service, "get_learner_model", model)
    monkeypatch.setattr(diagnoses_service, "list_diagnoses", diags)
    text = _run(_build_learner_context("u", "s", _concept()))
    assert "WEAK" in text
    assert "MISCONCEPTION" in text
    assert "Treats stages as independent." in text


# ---- AI generation ------------------------------------------------------------

def test_generate_diagnostic_questions_parses_and_validates():
    payload = {"questions": [_question()]}
    provider = _CaptureProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    result = _run(service.generate_diagnostic_questions(_concept(), derive_target_vocabulary(_concept()), "graph", _chunks(), learner_context="WEAK", question_count=5))
    assert isinstance(result, QuestionSet)
    assert result.questions[0].questionType == "MCQ"
    assert "WEAK" in provider.responses_capture["user"]


class _CaptureProvider(FakeProvider):
    def __init__(self, responses):
        super().__init__(responses)
        self.responses_capture = {}

    async def complete(self, system, user, temperature=0.0, max_tokens=None):
        self.responses_capture["system"] = system
        self.responses_capture["user"] = user
        return await super().complete(system, user, temperature, max_tokens=max_tokens)


def test_generate_probe_parses_and_validates():
    payload = {
        **_question(),
        "differentiationTarget": {
            "hypothesisA": "MISSING_PREREQUISITE",
            "hypothesisB": "MISCONCEPTION",
        },
    }
    provider = FakeProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    result = _run(service.generate_probe(
        _concept(),
        {"hypothesisA": "MISSING_PREREQUISITE", "hypothesisB": "MISCONCEPTION"},
        derive_target_vocabulary(_concept()),
        _chunks(),
    ))
    assert isinstance(result, ProbeQuestion)
    assert result.differentiationTarget["hypothesisA"] == "MISSING_PREREQUISITE"


def test_probe_rejects_invalid_mcq():
    payload = {
        "questionText": "q", "questionType": "MCQ",
        "expectedAnswer": "a", "expectedReasoning": "r",
        "diagnosticTargets": [], "sourceChunks": [1],
        "options": [{"id": "A", "text": "a"}],  # only 1 option
        "correctOptionId": "A",
        "differentiationTarget": {},
    }
    provider = FakeProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    with pytest.raises(RuntimeError):
        _run(service.generate_probe(_concept(), {}, [], _chunks()))