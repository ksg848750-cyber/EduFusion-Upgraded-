import { supabase } from "./supabase";

export type UserProfile = {
  id: string;
  authUserId: string;
  email: string;
  name: string;
  isOnboarded: boolean;
  createdAt: string;
  updatedAt: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/** Get the current access token from the Supabase session. */
export async function getAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) {
    throw new Error("No active session");
  }
  return data.session.access_token;
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await getAccessToken();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...(init?.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res;
}

/** Call the protected backend /auth/me endpoint with the Supabase JWT. */
export async function fetchMe(): Promise<UserProfile> {
  const res = await authedFetch("/auth/me");
  return res.json();
}

// ---- Milestone 2: subjects, materials, knowledge graph ----

export type Subject = {
  id: string;
  ownerId: string;
  name: string;
  description: string;
  status: string;
  conceptCount: number;
  createdAt: string;
  updatedAt: string;
};

export type Material = {
  id: string;
  subjectId: string;
  ownerId: string;
  filename: string;
  fileType: string;
  storageReference: string;
  processingStatus: string;
  pageCount: number | null;
  processingError: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Concept = {
  id: string;
  name: string;
  canonicalName: string;
  description: string;
  difficulty: number;
  expectedUnderstanding: string;
  commonMisconceptions: string[];
  sourceReferences?: number[];
};

export type Relationship = {
  id: string;
  fromConceptId: string;
  toConceptId: string;
  relationshipType: string;
  confidence: number;
  fromName: string;
  toName: string;
  reason?: string;
  sourceReferences?: number[];
};

export type KnowledgeGraph = {
  subject: Subject;
  concepts: Concept[];
  relationships: Relationship[];
  status: string;
  conceptCount: number;
};

export async function listSubjects(): Promise<Subject[]> {
  const res = await authedFetch("/subjects");
  return res.json();
}

export async function createSubject(name: string, description: string): Promise<Subject> {
  const res = await authedFetch("/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  return res.json();
}

export async function listMaterials(subjectId: string): Promise<Material[]> {
  const res = await authedFetch(`/subjects/${subjectId}/materials`);
  return res.json();
}

export async function uploadMaterial(subjectId: string, file: File): Promise<Material> {
  const token = await getAccessToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/subjects/${subjectId}/materials`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (res.ok) {
    return res.json();
  }
  if (res.status === 422) {
    const body = await res.json().catch(() => null);
    const material = body?.detail?.material;
    if (material) return material as Material;
  }
  throw new Error(`Upload failed (${res.status})`);
}

export async function fetchKnowledgeGraph(subjectId: string): Promise<KnowledgeGraph> {
  const res = await authedFetch(`/subjects/${subjectId}/knowledge-graph`);
  return res.json();
}

// ---- Milestone 3: adaptive learner model & topic understanding ----

export type ConceptState = {
  conceptId: string;
  conceptName: string;
  mastery: number;
  status: "UNKNOWN" | "WEAK" | "DEVELOPING" | "MASTERED";
  confidence: number;
  interactionCount: number;
  correctCount: number;
  incorrectCount: number;
  lastAssessedAt: string | null;
};

export type Misconception = {
  id: string;
  category: string;
  statement: string;
  confidence: number;
  status: string;
  evidenceReferences: Record<string, unknown>[];
};

export type ConceptLearner = {
  subjectId: string;
  conceptId: string;
  conceptName: string;
  state: ConceptState;
  misconceptions: Misconception[];
};

export type ExplanationSection = {
  heading: string;
  body: string;
  sourceChunks: number[];
};

export type ConceptExplanation = {
  summary: string;
  sections: ExplanationSection[];
  example: string;
  commonConfusion: string;
  sourceChunks: number[];
};

export type ExplanationResponse = {
  conceptId: string;
  conceptName: string;
  explanation: ConceptExplanation;
};

export type McqOption = {
  id: string;
  text: string;
};

export type TestQuestion = {
  id: string;
  questionText: string;
  questionType: string;
  difficulty: number;
  diagnosticTargets: string[];
  sourceChunks: number[];
  options: McqOption[];
};

export type TestStartResponse = {
  sessionId: string;
  conceptId: string;
  questions: TestQuestion[];
};

export type AnswerResponse = {
  answerId: string;
  correct: boolean;
  reasoningQuality: string;
  explanation: string;
  evidenceSignals: string[];
  conceptState: ConceptState;
  misconception: Misconception | null;
};

export async function fetchConceptLearner(
  subjectId: string,
  conceptId: string,
): Promise<ConceptLearner> {
  const res = await authedFetch(`/subjects/${subjectId}/concepts/${conceptId}/learner`);
  return res.json();
}

export async function explainConcept(
  subjectId: string,
  conceptId: string,
): Promise<ExplanationResponse> {
  const res = await authedFetch(`/subjects/${subjectId}/concepts/${conceptId}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json();
}

export async function startConceptTest(
  subjectId: string,
  conceptId: string,
): Promise<TestStartResponse> {
  const res = await authedFetch(`/subjects/${subjectId}/concepts/${conceptId}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json();
}

export async function submitAnswer(
  subjectId: string,
  sessionId: string,
  questionId: string,
  response: string,
  reasoning: string,
  selectedOptionId?: string,
): Promise<AnswerResponse> {
  const res = await authedFetch(`/subjects/${subjectId}/sessions/${sessionId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ questionId, response, reasoning, selectedOptionId }),
  });
  return res.json();
}

// ---- Milestone 4: adaptive diagnostic reasoning ----

export type DiagnosticStartResponse = {
  status: string;
  sessionId?: string | null;
  conceptId?: string | null;
  conceptName?: string | null;
  questions?: TestQuestion[];
  resolution?: Record<string, unknown> | null;
  targetVocabulary?: string[];
  error?: string | null;
};

export type DiagnosticAnswerResponse = {
  answerId: string;
  correct: boolean;
  reasoningQuality: string;
  explanation: string;
  evidenceSignals: string[];
  misconception: { category: string; statement: string; confidence: number } | null;
};

export type DiagnosticDecisionResponse = {
  status: string;
  rootCause?: string | null;
  confidence: number;
  statement: string;
  evidenceSignals: string[];
  hypotheses: { category: string; confidence: number }[];
  needsProbe: boolean;
  differentiationTarget?: { hypothesisA: string; hypothesisB: string } | null;
};

export type EvidenceBundleResponse = {
  status: string;
  conceptId?: string | null;
  conceptName?: string | null;
  resolution: Record<string, unknown>;
  diagnosis: {
    rootCause: string;
    confidence: number;
    resolution: Record<string, unknown>;
    investigation: Record<string, unknown>;
    evidenceReferences: unknown[];
  } | null;
  evidence: {
    questionId: string;
    questionText: string;
    reasoning: string;
    response: string;
    correct: boolean;
    reasoningQuality: string;
    evidenceSignals: string[];
    misconception: { category: string } | null;
  }[];
};

export async function startDiagnostic(
  subjectId: string,
  conceptId?: string,
): Promise<DiagnosticStartResponse> {
  const res = await authedFetch(`/subjects/${subjectId}/diagnostic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conceptId: conceptId ?? null }),
  });
  return res.json();
}

export async function submitDiagnosticAnswer(
  subjectId: string,
  sessionId: string,
  questionId: string,
  response: string,
  reasoning: string,
  selectedOptionId?: string,
): Promise<DiagnosticAnswerResponse> {
  const res = await authedFetch(
    `/subjects/${subjectId}/sessions/${sessionId}/diagnostic-answers`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questionId, response, reasoning, selectedOptionId }),
    },
  );
  return res.json();
}

export async function getDiagnosticDecision(
  subjectId: string,
  sessionId: string,
): Promise<DiagnosticDecisionResponse> {
  const res = await authedFetch(
    `/subjects/${subjectId}/sessions/${sessionId}/diagnostic-decision`,
  );
  return res.json();
}

export async function getEvidenceBundle(
  subjectId: string,
  sessionId: string,
): Promise<EvidenceBundleResponse> {
  const res = await authedFetch(
    `/subjects/${subjectId}/sessions/${sessionId}/evidence-bundle`,
  );
  return res.json();
}

export type ProbeStartResponse = {
  status: string;
  probeQuestion?: TestQuestion | null;
  target?: { hypothesisA?: string; hypothesisB?: string } | null;
  error?: string | null;
};

export type DiagnosisResponse = {
  id: string;
  conceptId: string;
  conceptName: string;
  rootCause: string;
  confidence: number;
  resolution: Record<string, unknown>;
  investigation: Record<string, unknown>;
  evidenceReferences: unknown[];
};

export async function startDiagnosticProbe(
  subjectId: string,
  sessionId: string,
): Promise<ProbeStartResponse> {
  const res = await authedFetch(
    `/subjects/${subjectId}/sessions/${sessionId}/diagnostic-probe`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  return res.json();
}

export async function createFinalDiagnosis(
  subjectId: string,
  sessionId: string,
): Promise<DiagnosisResponse> {
  const res = await authedFetch(
    `/subjects/${subjectId}/sessions/${sessionId}/diagnosis`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  return res.json();
}

// ---- Milestone 5: adaptive teaching engine (lesson delivery + clarify) ----

export const INTERESTS = [
  "normal",
  "cricket",
  "movies",
  "f1",
  "gaming",
  "anime",
  "football",
  "web-series",
  "music",
] as const;
export type Interest = (typeof INTERESTS)[number];

export type TeachingDecision = {
  status: string;
  lessonId?: string | null;
  sessionId?: string | null;
  diagnosisId?: string | null;
  conceptId?: string | null;
  conceptName?: string | null;
  rootCause?: string | null;
  action?: string | null;
  reason?: string | null;
  teachingStrategy?: string | null;
  attempt: number;
  excluded: string[];
  interestContext: string;
};

export type AnalogyMapping = {
  element: string;
  mappedTo: string;
  description: string;
};

export type InterestAnalogy = {
  scene: string;
  mapping: AnalogyMapping[];
  analogy_works: string;
  analogy_breaks: string;
};

export type LessonContent = {
  status: string;
  lessonId?: string | null;
  conceptId?: string | null;
  rootCause?: string | null;
  teachingAction?: string | null;
  teachingStrategy?: string | null;
  attempt: number;
  interestContext: string;
  explanation: string;
  keyPoints: string[];
  analogy: InterestAnalogy | null;
  sourceChunks: number[];
  sourceReferences: { chunkIndex: number }[];
  visualizationSpec?: Record<string, unknown> | null;
};

export type ClarifyResponse = {
  status: string;
  lessonId?: string | null;
  conceptId?: string | null;
  answer: string;
  covered: boolean;
  sourceChunks: number[];
  disclaimer: string;
};

export async function createTeachingDecision(
  subjectId: string,
  sessionId: string,
  interestContext: Interest = "normal",
): Promise<TeachingDecision> {
  const res = await authedFetch(`/subjects/${subjectId}/teaching-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, interestContext }),
  });
  return res.json();
}

export async function generateLesson(
  subjectId: string,
  lessonId: string,
  interestContext: Interest = "normal",
): Promise<LessonContent> {
  const res = await authedFetch(`/subjects/${subjectId}/lessons/${lessonId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interestContext }),
  });
  const json = await res.json();
  return json;
}

export async function fetchLesson(
  subjectId: string,
  lessonId: string,
): Promise<{ status: string; lesson: Record<string, unknown> }> {
  const res = await authedFetch(`/subjects/${subjectId}/lessons/${lessonId}`);
  return res.json();
}

export async function clarifyLessonDoubt(
  subjectId: string,
  lessonId: string,
  question: string,
): Promise<ClarifyResponse> {
  const res = await authedFetch(`/subjects/${subjectId}/lessons/${lessonId}/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return res.json();
}
