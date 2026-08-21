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


class DiagnosticStartRequest(BaseModel):
    conceptId: str | None = None


class DiagnosticStartResponse(BaseModel):
    status: str
    sessionId: str | None = None
    conceptId: str | None = None
    conceptName: str | None = None
    questions: list[TestQuestion] = []
    resolution: dict | None = None
    targetVocabulary: list[str] = []
    error: str | None = None


class DiagnosticAnswerRequest(BaseModel):
    questionId: str = Field(min_length=1)
    response: str = ""
    reasoning: str = ""
    selectedOptionId: str | None = None


class DiagnosticAnswerResponse(BaseModel):
    answerId: str
    correct: bool
    reasoningQuality: str
    explanation: str
    evidenceSignals: list[str]
    misconception: dict | None = None


class DiagnosticDecisionResponse(BaseModel):
    status: str
    rootCause: str | None = None
    confidence: float
    statement: str
    evidenceSignals: list[str] = []
    hypotheses: list[dict] = []
    needsProbe: bool = False
    differentiationTarget: dict | None = None


class ProbeStartResponse(BaseModel):
    status: str
    probeQuestion: TestQuestion | None = None
    target: dict | None = None
    error: str | None = None


class DiagnosisResponse(BaseModel):
    id: str
    conceptId: str
    conceptName: str
    rootCause: str
    confidence: float
    resolution: dict = {}
    investigation: dict = {}
    evidenceReferences: list[dict] = []


class EvidenceBundleResponse(BaseModel):
    status: str
    conceptId: str | None = None
    conceptName: str | None = None
    resolution: dict = {}
    diagnosis: dict | None = None
    evidence: list[dict] = []


class TeachingDecisionRequest(BaseModel):
    sessionId: str
    interestContext: str = "normal"


class TeachingDecisionResponse(BaseModel):
    status: str
    lessonId: str | None = None
    sessionId: str | None = None
    diagnosisId: str | None = None
    conceptId: str | None = None
    conceptName: str | None = None
    rootCause: str | None = None
    action: str | None = None
    reason: str | None = None
    teachingStrategy: str | None = None
    attempt: int = 1
    excluded: list[str] = []
    interestContext: str = "normal"


class LessonGenerateRequest(BaseModel):
    interestContext: str = "normal"


class LessonContentResponse(BaseModel):
    status: str
    lessonId: str | None = None
    conceptId: str | None = None
    rootCause: str | None = None
    teachingAction: str | None = None
    teachingStrategy: str | None = None
    attempt: int = 1
    interestContext: str = "normal"
    explanation: str = ""
    keyPoints: list[str] = []
    analogy: dict | None = None
    sourceChunks: list[int] = []
    sourceReferences: list[dict] = []
    visualizationSpec: dict | None = None


class LessonDetailResponse(BaseModel):
    status: str = "OK"
    lesson: dict | None = None


class ClarifyRequest(BaseModel):
    question: str


class ClarifyResponse(BaseModel):
    status: str
    lessonId: str | None = None
    conceptId: str | None = None
    answer: str = ""
    covered: bool = False
    sourceChunks: list[int] = []
    disclaimer: str = ""