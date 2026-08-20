import asyncio
import json

import pytest

from app.ai.schemas.learner import AnswerEvaluation, ConceptExplanation, QuestionSet
from app.ai.service import AIService, _clean_json


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
        "name": "SSTF",
        "canonicalName": "sstf",
        "description": "Shortest Seek Time First scheduling",
        "difficulty": 3,
        "expectedUnderstanding": "picks the request closest to current head",
        "commonMisconceptions": ["confusing SSTF selection with FCFS arrival order"],
        "sourceReferences": [1, 2],
    }


def _chunks():
    return [
        {"chunkIndex": 1, "sectionTitle": "Disk Scheduling", "pageNumber": 4,
         "text": "SSTF selects the request with the shortest seek time from the current head position."},
        {"chunkIndex": 2, "sectionTitle": "Disk Scheduling", "pageNumber": 4,
         "text": "Unlike FCFS, SSTF is not a purely arrival-ordered policy."},
    ]


def _explain_payload():
    return {
        "summary": "SSTF minimizes head movement.",
        "sections": [
            {"heading": "What it is", "body": "SSTF picks the closest request.", "sourceChunks": [1]},
            {"heading": "Why it matters", "body": "Less seek time.", "sourceChunks": [1]},
        ],
        "example": "Head at 50, queue 90/10 -> picks 10.",
        "commonConfusion": "It is not the same as FCFS ordering.",
        "sourceChunks": [1, 2],
    }


def _questions_payload():
    return {
        "questions": [
            {"questionText": "How does SSTF choose?", "questionType": "SCENARIO", "difficulty": 3,
             "expectedAnswer": "Closest request.", "expectedReasoning": "shortest seek time",
             "diagnosticTargets": ["SHORTEST_SEEK_SELECTION"], "sourceChunks": [1]},
            {"questionText": "Define SSTF.", "questionType": "SHORT_ANSWER", "difficulty": 2,
             "expectedAnswer": "Shortest seek time first.", "expectedReasoning": "definition",
             "diagnosticTargets": ["DEFINITION"], "sourceChunks": [1]},
            {"questionText": "SSTF vs FCFS?", "questionType": "SCENARIO", "difficulty": 4,
             "expectedAnswer": "Differs in ordering.", "expectedReasoning": "seek vs arrival",
             "diagnosticTargets": ["DIFFERENTIATE_FCFS"], "sourceChunks": [2]},
        ]
    }


def _evaluation_payload():
    return {
        "correct": False,
        "reasoningQuality": "POOR",
        "explanation": "You used arrival order.",
        "evidenceSignals": ["USES_ARRIVAL_ORDER"],
        "misconception": {
            "category": "MISCONCEPTION",
            "statement": "Confuses SSTF selection with FCFS arrival order",
            "confidence": 0.7,
        },
    }


def test_explain_parses_and_validates():
    provider = FakeProvider([json.dumps(_explain_payload())])
    service = AIService(provider=provider)
    result = _run(service.explain_concept(_concept(), "SSTF --PART_OF--> Disk Scheduling", "none", _chunks()))
    assert isinstance(result, ConceptExplanation)
    assert result.summary == "SSTF minimizes head movement."
    assert result.sections[0].sourceChunks == [1]
    assert result.commonConfusion


def test_generate_questions_parses_and_validates():
    provider = FakeProvider([json.dumps(_questions_payload())])
    service = AIService(provider=provider)
    result = _run(service.generate_questions(_concept(), "graph", _chunks()))
    assert isinstance(result, QuestionSet)
    assert len(result.questions) == 3
    assert result.questions[0].questionType == "SCENARIO"
    assert result.questions[0].diagnosticTargets == ["SHORTEST_SEEK_SELECTION"]


def test_evaluate_answer_parses_and_validates():
    provider = FakeProvider([json.dumps(_evaluation_payload())])
    service = AIService(provider=provider)
    question = {
        "questionText": "How does SSTF choose?",
        "questionType": "SCENARIO",
        "diagnosticTargets": ["SHORTEST_SEEK_SELECTION"],
        "expectedAnswer": "Closest request.",
        "expectedReasoning": "shortest seek time",
    }
    result = _run(service.evaluate_answer(
        _concept(), question, _chunks(), "first come first serve", "in arrival order"))
    assert isinstance(result, AnswerEvaluation)
    assert result.correct is False
    assert result.misconception is not None
    assert result.misconception.category == "MISCONCEPTION"
    assert result.misconception.confidence == 0.7


def test_evaluate_answer_allows_null_misconception():
    payload = {"correct": True, "reasoningQuality": "SOLID", "explanation": "Good",
               "evidenceSignals": ["SHORTEST_SEEK_TIME_CORRECT"], "misconception": None}
    provider = FakeProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    question = {"questionText": "q", "questionType": "SHORT_ANSWER", "diagnosticTargets": [],
                "expectedAnswer": "a", "expectedReasoning": "r"}
    result = _run(service.evaluate_answer(_concept(), question, _chunks(), "closest", "shortest seek"))
    assert result.correct is True
    assert result.misconception is None


def test_retries_on_invalid_json_then_succeeds():
    provider = FakeProvider(["not json", json.dumps(_explain_payload())])
    service = AIService(provider=provider)
    result = _run(service.explain_concept(_concept(), "g", "none", _chunks()))
    assert result.summary == "SSTF minimizes head movement."


def test_rejects_invalid_category():
    payload = {
        "correct": False, "reasoningQuality": "POOR", "explanation": "",
        "evidenceSignals": [], "misconception": {"category": "BOGUS", "statement": "x", "confidence": 0.5},
    }
    provider = FakeProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    with pytest.raises(RuntimeError):
        _run(service.evaluate_answer(_concept(), {"questionText": "q", "questionType": "MCQ",
                                                 "diagnosticTargets": [], "expectedAnswer": "a",
                                                 "expectedReasoning": "r"}, _chunks(), "x", "y"))


def test_clean_json_handles_fences():
    assert _clean_json("```json\n{\"a\":1}\n```") == '{"a":1}'