from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Root causes that M3 answer evaluation may propose. INSUFFICIENT_EVIDENCE is
# reserved for the probe flow (doc3) and is never auto-created here.
ProposedRootCause = Literal[
    "MISSING_PREREQUISITE",
    "MISCONCEPTION",
    "PROCEDURAL_ERROR",
    "TERMINOLOGY_CONFUSION",
    "REPRESENTATION_PROBLEM",
]


class ExplanationSection(BaseModel):
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)
    sourceChunks: list[int] = Field(default_factory=list)


class ConceptExplanation(BaseModel):
    summary: str = Field(min_length=1)
    sections: list[ExplanationSection] = Field(min_length=1)
    example: str = ""
    commonConfusion: str = ""
    sourceChunks: list[int] = Field(default_factory=list)


class McqOption(BaseModel):
    """A single selectable answer for an MCQ question."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class GeneratedQuestion(BaseModel):
    questionText: str = Field(min_length=1)
    questionType: Literal["SCENARIO", "SHORT_ANSWER", "MCQ", "PROBE"] = "SHORT_ANSWER"
    difficulty: int = Field(ge=1, le=5, default=3)
    expectedAnswer: str = Field(min_length=1)
    expectedReasoning: str = ""
    diagnosticTargets: list[str] = Field(default_factory=list)
    sourceChunks: list[int] = Field(default_factory=list)
    options: list[McqOption] = Field(default_factory=list)
    correctOptionId: str = ""

    @model_validator(mode="after")
    def _validate_mcq(self):
        if self.questionType == "MCQ":
            if len(self.options) < 2:
                raise ValueError("MCQ requires at least 2 options")
            ids = [o.id for o in self.options]
            if len(ids) != len(set(ids)):
                raise ValueError("MCQ option ids must be unique")
            if self.correctOptionId not in ids:
                raise ValueError("correctOptionId must reference one of the options")
        else:
            if self.options:
                raise ValueError("options are only allowed for MCQ questions")
            if self.correctOptionId:
                raise ValueError("correctOptionId is only allowed for MCQ questions")
        return self


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=5)


class ProbeQuestion(BaseModel):
    """A single targeted probe generated to disambiguate an ambiguous signal
    (doc3). Carries the differentiation target: the two competing hypotheses
    the probe must confirm or refute."""
    questionText: str = Field(min_length=1)
    questionType: Literal["SCENARIO", "SHORT_ANSWER", "MCQ"] = "MCQ"
    difficulty: int = Field(ge=1, le=5, default=3)
    expectedAnswer: str = Field(min_length=1)
    expectedReasoning: str = ""
    diagnosticTargets: list[str] = Field(default_factory=list)
    sourceChunks: list[int] = Field(default_factory=list)
    options: list[McqOption] = Field(default_factory=list)
    correctOptionId: str = ""
    differentiationTarget: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_mcq(self):
        if self.questionType == "MCQ":
            if len(self.options) < 2:
                raise ValueError("MCQ requires at least 2 options")
            ids = [o.id for o in self.options]
            if len(ids) != len(set(ids)):
                raise ValueError("MCQ option ids must be unique")
            if self.correctOptionId not in ids:
                raise ValueError("correctOptionId must reference one of the options")
        else:
            if self.options:
                raise ValueError("options are only allowed for MCQ questions")
            if self.correctOptionId:
                raise ValueError("correctOptionId is only allowed for MCQ questions")
        return self


class MisconceptionHypothesis(BaseModel):
    category: ProposedRootCause
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class AnswerEvaluation(BaseModel):
    correct: bool
    reasoningQuality: Literal["POOR", "PARTIAL", "SOLID"] = "PARTIAL"
    explanation: str = ""
    evidenceSignals: list[str] = Field(default_factory=list)
    misconception: MisconceptionHypothesis | None = None