"""Pydantic contracts for M7 Reassessment question generation.

The LLM produces a single reassessment question that targets the same root
cause as the original diagnosis but uses novel wording and context.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReassessmentOption(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class GeneratedReassessment(BaseModel):
    questionType: Literal["MCQ", "SHORT_ANSWER"] = "MCQ"
    questionText: str = Field(min_length=1)
    expectedAnswer: str = Field(min_length=1)
    expectedReasoning: str = ""
    options: list[ReassessmentOption] = Field(default_factory=list)
    correctOptionId: str = ""
    difficulty: int = Field(ge=1, le=5, default=3)
    sourceChunks: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_mcq(self):
        if self.questionType == "MCQ":
            if len(self.options) < 2:
                raise ValueError("MCQ requires at least 2 options")
            if not self.correctOptionId:
                raise ValueError("MCQ requires a correctOptionId")
            ids = {o.id for o in self.options}
            if self.correctOptionId not in ids:
                raise ValueError("correctOptionId must match one of the option ids")
        return self
