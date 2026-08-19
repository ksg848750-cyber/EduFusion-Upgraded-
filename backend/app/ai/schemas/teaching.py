"""Pydantic contracts for M5 lesson generation and doubt clarification.

All LLM output for the Adaptive Teaching engine is validated against these
schemas before persistence (doc12 guardrail). The visualization spec is a
separate concern owned by M6, so it is intentionally absent here.
"""

from pydantic import BaseModel, Field


class AnalogyMapping(BaseModel):
    """One element of the concept mapped to one element of the interest scene."""

    element: str = Field(min_length=1)
    mappedTo: str = Field(min_length=1)
    description: str = Field(min_length=1)


class InterestAnalogy(BaseModel):
    """The interest-lens narrative bridge (present only when interest != normal).

    Interest context alters narrative text only; the technical explanation and
    any visualization remain concept-accurate (doc4/doc5).
    """

    scene: str = Field(min_length=1)
    mapping: list[AnalogyMapping] = Field(default_factory=list)
    analogy_works: str = Field(min_length=1)
    analogy_breaks: str = Field(min_length=1)


class GeneratedLesson(BaseModel):
    """The LLM-authored, grounded lesson content delivered to the student.

    ``sourceChunks`` are integer indices referencing the retrieved chunks shown
    to the model; the service deterministically clips them to the available set
    so the LLM can never cite a source it was not given.
    """

    explanation: str = Field(min_length=1)
    keyPoints: list[str] = Field(default_factory=list)
    analogy: InterestAnalogy | None = None
    sourceChunks: list[int] = Field(default_factory=list)


class Clarification(BaseModel):
    """A doubt-clarification answer, grounded strictly in retrieved chunks.

    ``covered`` tells the student whether the answer actually exists in their
    uploaded material. The service forces ``covered=False`` (with a fixed
    disclaimer) when no chunks were retrieved, so the hard RAG guard holds even
    if the LLM behaves unexpectedly.
    """

    answer: str = Field(min_length=1)
    covered: bool
    sourceChunks: list[int] = Field(default_factory=list)
    disclaimer: str = ""
