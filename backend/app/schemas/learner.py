from pydantic import BaseModel, Field

from app.ai.schemas.learner import ConceptExplanation


class LearnerConceptState(BaseModel):
    conceptId: str
    conceptName: str
    mastery: float
    status: str
    confidence: float
    interactionCount: int
    correctCount: int
    incorrectCount: int
    lastAssessedAt: str | None = None


class MisconceptionResponse(BaseModel):
    id: str
    category: str
    statement: str
    confidence: float
    status: str
    evidenceReferences: list[dict]


class ConceptLearnerResponse(BaseModel):
    subjectId: str
    conceptId: str
    conceptName: str
    state: LearnerConceptState
    misconceptions: list[MisconceptionResponse] = []


class SubjectLearnerResponse(BaseModel):
    subjectId: str
    overallMastery: float
    conceptStates: dict[str, dict]
    version: int


class UnderstandRequest(BaseModel):
    pass


class ExplanationResponse(BaseModel):
    conceptId: str
    conceptName: str
    explanation: ConceptExplanation


class TestQuestion(BaseModel):
    id: str
    questionText: str
    questionType: str
    difficulty: int
    diagnosticTargets: list[str] = []
    sourceChunks: list[int] = []
    options: list[dict] = []


class TestStartResponse(BaseModel):
    sessionId: str
    conceptId: str
    questions: list[TestQuestion]


class AnswerRequest(BaseModel):
    questionId: str = Field(min_length=1)
    response: str = ""
    reasoning: str = ""
    selectedOptionId: str | None = None


class AnswerResponse(BaseModel):
    answerId: str
    correct: bool
    reasoningQuality: str
    explanation: str
    evidenceSignals: list[str]
    conceptState: dict
    misconception: dict | None = None