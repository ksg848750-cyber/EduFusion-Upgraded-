import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.ai.schemas.learner import AnswerEvaluation, GeneratedQuestion, QuestionSet
from app.ai.service import AIService
from app.services import study as study_service


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _no_db_chunks():
    """Keep submit_answer tests free of DB/embedding dependencies."""
    with patch("app.services.study.get_concept_chunks", AsyncMock(return_value=[])):
        yield


def _mcq_payload(correct_option_id="B"):
    return {
        "questions": [
            {
                "questionText": "Which request does SSTF serve next?",
                "questionType": "MCQ",
                "difficulty": 3,
                "expectedAnswer": "The closest request",
                "expectedReasoning": "SSTF minimizes seek distance",
                "diagnosticTargets": ["SHORTEST_SEEK_SELECTION"],
                "sourceChunks": [1],
                "options": [
                    {"id": "A", "text": "The oldest request in the queue"},
                    {"id": "B", "text": "The request closest to the head"},
                    {"id": "C", "text": "The request with the longest seek"},
                ],
                "correctOptionId": correct_option_id,
            }
        ]
    }


def _question_dict():
    return {
        "id": "q-mcq-1",
        "questionText": "Which request does SSTF serve next?",
        "questionType": "MCQ",
        "difficulty": 3,
        "expectedAnswer": "The closest request",
        "expectedReasoning": "SSTF minimizes seek distance",
        "diagnosticTargets": ["SHORTEST_SEEK_SELECTION"],
        "sourceReferences": [1],
        "options": [
            {"id": "A", "text": "The oldest request in the queue"},
            {"id": "B", "text": "The request closest to the head"},
            {"id": "C", "text": "The request with the longest seek"},
        ],
        "correctOptionId": "B",
    }


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


def _session():
    return {"id": "s1", "conceptId": "c1", "status": "CREATED"}


class CapturingAI(AIService):
    """Fake AI that records structured inputs and returns a canned evaluation."""

    def __init__(self, evaluation: AnswerEvaluation):
        super().__init__(provider=None)
        self.evaluation = evaluation
        self.captured = {}

    async def evaluate_answer(self, concept, question, chunks, student_response,
                              student_reasoning, options=None, selected_option_id="",
                              selected_option_text=""):
        self.captured = {
            "question": question,
            "response": student_response,
            "reasoning": student_reasoning,
            "options": options,
            "selectedOptionId": selected_option_id,
            "selectedOptionText": selected_option_text,
        }
        return self.evaluation


# ---- Schema: MCQ requires options ----

def test_generated_question_mcq_requires_options():
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "questionText": "q", "questionType": "MCQ", "expectedAnswer": "a",
        })


def test_generated_question_mcq_requires_valid_options():
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "questionText": "q", "questionType": "MCQ", "expectedAnswer": "a",
            "options": [{"id": "A", "text": "one"}],
        })


def test_generated_question_mcq_requires_exactly_one_correct():
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "questionText": "q", "questionType": "MCQ", "expectedAnswer": "a",
            "options": [
                {"id": "A", "text": "one"},
                {"id": "B", "text": "two"},
            ],
            "correctOptionId": "",
        })


def test_generated_question_mcq_correct_option_must_reference_existing():
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "questionText": "q", "questionType": "MCQ", "expectedAnswer": "a",
            "options": [
                {"id": "A", "text": "one"},
                {"id": "B", "text": "two"},
            ],
            "correctOptionId": "Z",
        })


def test_generated_question_non_mcq_rejects_options():
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "questionText": "q", "questionType": "SHORT_ANSWER", "expectedAnswer": "a",
            "options": [{"id": "A", "text": "one"}],
            "correctOptionId": "A",
        })


def test_generated_question_mcq_accepts_valid_payload():
    q = GeneratedQuestion.model_validate(_mcq_payload()["questions"][0])
    assert len(q.options) == 3
    assert q.correctOptionId == "B"


def test_question_set_parses_mcq_options():
    payload = _mcq_payload()
    result = QuestionSet.model_validate(payload)
    assert result.questions[0].options[1].text == "The request closest to the head"
    assert result.questions[0].correctOptionId == "B"


# ---- Structured submission preserves reasoning, evaluation gets structured info ----

def _submit(question, response, reasoning, selected_option_id=None, evaluation=None):
    evaluation = evaluation or AnswerEvaluation(
        correct=True, reasoningQuality="SOLID", explanation="ok",
        evidenceSignals=["SHORTEST_SEEK_TIME_CORRECT"], misconception=None,
    )
    ai = CapturingAI(evaluation)
    return _run(study_service.submit_answer(
        owner_id="u1", subject_id="sub1", session=_session(), concept=_concept(),
        question=question, learner_id="u1", response=response, reasoning=reasoning,
        selected_option_id=selected_option_id, ai=ai,
    )), ai


def test_mcq_requires_a_selected_option():
    with pytest.raises(ValueError):
        _submit(_question_dict(), "", "I think closest", None)


def test_mcq_rejects_unknown_option_id():
    with pytest.raises(ValueError):
        _submit(_question_dict(), "", "I think closest", "Z")


def test_mcq_correct_option_scores_correct():
    result, ai = _submit(_question_dict(), "", "because shortest seek", "B")
    assert result["correct"] is True
    assert ai.captured["selectedOptionId"] == "B"
    assert ai.captured["selectedOptionText"] == "The request closest to the head"
    assert ai.captured["options"] == _question_dict()["options"]
    assert ai.captured["reasoning"] == "because shortest seek"


def test_mcq_wrong_option_scores_incorrect_even_if_llm_says_correct():
    # The evaluator is told "correct", but deterministic option matching wins.
    evaluation = AnswerEvaluation(
        correct=True, reasoningQuality="SOLID", explanation="llm",
        evidenceSignals=[], misconception=None,
    )
    result, _ = _submit(_question_dict(), "", "because arrival order", "A", evaluation)
    assert result["correct"] is False


def test_mcq_reasoning_is_preserved_in_evaluation():
    result, ai = _submit(_question_dict(), "", "I picked closest because seek distance", "B")
    assert ai.captured["reasoning"] == "I picked closest because seek distance"


def test_short_answer_still_works_without_options():
    q = {
        "id": "q-sa-1",
        "questionText": "Define SSTF.",
        "questionType": "SHORT_ANSWER",
        "difficulty": 2,
        "expectedAnswer": "Shortest seek time first",
        "expectedReasoning": "definition",
        "diagnosticTargets": ["DEFINITION"],
        "sourceReferences": [1],
        "options": [],
        "correctOptionId": "",
    }
    evaluation = AnswerEvaluation(
        correct=True, reasoningQuality="SOLID", explanation="ok",
        evidenceSignals=["DEFINITION_OK"], misconception=None,
    )
    result, ai = _submit(q, "shortest seek time first", "by definition", None, evaluation)
    assert result["correct"] is True
    assert ai.captured["options"] is None
    assert ai.captured["selectedOptionId"] == ""
    assert ai.captured["response"] == "shortest seek time first"


def test_short_answer_requires_nonempty_response():
    q = {
        "id": "q-sa-2", "questionText": "q", "questionType": "SHORT_ANSWER",
        "difficulty": 2, "expectedAnswer": "a", "expectedReasoning": "r",
        "diagnosticTargets": [], "sourceReferences": [1], "options": [], "correctOptionId": "",
    }
    with pytest.raises(ValueError):
        _submit(q, "   ", "reasoning", None)